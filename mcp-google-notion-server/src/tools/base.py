"""Base tool interface and registry."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
import structlog
from pydantic import BaseModel, ValidationError

from ..protocol.messages import ToolDefinition, ToolCallResult, ErrorCode

logger = structlog.get_logger()


class ToolError(Exception):
    """Base exception for tool-related errors."""
    def __init__(self, message: str, code: int = ErrorCode.TOOL_ERROR):
        super().__init__(message)
        self.code = code
        self.message = message


class ToolTimeout(ToolError):
    """Raised when tool execution times out."""
    def __init__(self, timeout: float):
        super().__init__(f"Tool execution timed out after {timeout}s", ErrorCode.TIMEOUT_ERROR)
        self.timeout = timeout


class ToolValidationError(ToolError):
    """Raised when tool input validation fails."""
    def __init__(self, errors: List[Dict[str, Any]]):
        super().__init__("Tool input validation failed", ErrorCode.INVALID_PARAMS)
        self.errors = errors


class Tool(ABC):
    """Abstract base class for MCP tools."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._initialized = False
        self._cleanup_tasks: List[asyncio.Task] = []
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """JSON schema for tool input validation."""
        pass

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool with given arguments."""
        pass

    async def initialize(self) -> None:
        """Initialize tool resources."""
        if self._initialized:
            return
            
        try:
            await self._initialize_impl()
            self._initialized = True
            logger.info("Tool initialized", tool=self.name)
        except Exception as e:
            logger.error("Tool initialization failed", tool=self.name, error=str(e))
            raise ToolError(f"Failed to initialize {self.name}: {e}")

    async def cleanup(self) -> None:
        """Cleanup tool resources."""
        if not self._initialized:
            return
            
        try:
            # Cancel cleanup tasks
            for task in self._cleanup_tasks:
                if not task.done():
                    task.cancel()
                    
            # Wait for tasks to complete
            if self._cleanup_tasks:
                await asyncio.gather(*self._cleanup_tasks, return_exceptions=True)
                
            await self._cleanup_impl()
            self._initialized = False
            logger.info("Tool cleaned up", tool=self.name)
        except Exception as e:
            logger.error("Tool cleanup failed", tool=self.name, error=str(e))

    async def _initialize_impl(self) -> None:
        """Subclass-specific initialization logic."""
        pass

    async def _cleanup_impl(self) -> None:
        """Subclass-specific cleanup logic."""
        pass

    def _add_cleanup_task(self, task: asyncio.Task) -> None:
        """Add a task to be cancelled during cleanup."""
        self._cleanup_tasks.append(task)

    async def call(self, arguments: Dict[str, Any], timeout: float = 30.0) -> ToolCallResult:
        """Call the tool with validation and error handling."""
        if not self._initialized:
            await self.initialize()
            
        try:
            # Validate input
            await self._validate_input(arguments)
            
            # Execute with timeout
            result = await asyncio.wait_for(
                self.execute(arguments), 
                timeout=timeout
            )
            
            logger.info(
                "Tool executed successfully",
                tool=self.name,
                arguments=arguments
            )
            
            return ToolCallResult(
                content=[{
                    "type": "text",
                    "text": str(result)
                }],
                is_error=False
            )
            
        except asyncio.TimeoutError:
            error_msg = f"Tool {self.name} timed out after {timeout}s"
            logger.error(error_msg, tool=self.name)
            raise ToolTimeout(timeout)
            
        except ValidationError as e:
            error_msg = f"Input validation failed for {self.name}"
            logger.error(error_msg, tool=self.name, errors=e.errors())
            raise ToolValidationError(e.errors())
            
        except ToolError:
            raise  # Re-raise tool-specific errors
            
        except Exception as e:
            error_msg = f"Tool {self.name} execution failed: {e}"
            logger.error(error_msg, tool=self.name, error=str(e))
            raise ToolError(error_msg)

    async def _validate_input(self, arguments: Dict[str, Any]) -> None:
        """Validate input against schema."""
        try:
            # Create a temporary Pydantic model for validation
            schema = self.input_schema
            
            # Basic validation - subclasses can override for more complex validation
            required_fields = schema.get("required", [])
            properties = schema.get("properties", {})
            
            # Check required fields
            for field in required_fields:
                if field not in arguments:
                    raise ValidationError.from_exception_data(
                        "ValidationError",
                        [{"type": "missing", "loc": [field], "msg": "Field required"}]
                    )
                    
            # Check field types (basic)
            for field, value in arguments.items():
                if field in properties:
                    expected_type = properties[field].get("type")
                    if expected_type and not self._check_type(value, expected_type):
                        raise ValidationError.from_exception_data(
                            "ValidationError",
                            [{
                                "type": "type_error",
                                "loc": [field],
                                "msg": f"Expected {expected_type}, got {type(value).__name__}"
                            }]
                        )
                        
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError.from_exception_data(
                "ValidationError",
                [{"type": "value_error", "loc": [], "msg": str(e)}]
            )

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected JSON schema type."""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type is None:
            return True  # Unknown type, skip validation
            
        return isinstance(value, expected_python_type)

    def get_definition(self) -> ToolDefinition:
        """Get tool definition for MCP."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema
        )


class ToolRegistry:
    """Registry for managing tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._tool_classes: Dict[str, Type[Tool]] = {}
        
    def register_tool_class(self, tool_class: Type[Tool]) -> None:
        """Register a tool class."""
        # Create temporary instance to get name
        temp_instance = tool_class()
        name = temp_instance.name
        
        self._tool_classes[name] = tool_class
        logger.debug("Tool class registered", tool=name)
        
    def create_tool(self, name: str, config: Optional[Dict[str, Any]] = None) -> Tool:
        """Create a tool instance."""
        tool_class = self._tool_classes.get(name)
        if not tool_class:
            raise ValueError(f"Unknown tool: {name}")
            
        tool = tool_class(config)
        self._tools[name] = tool
        logger.info("Tool created", tool=name)
        return tool
        
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool instance."""
        return self._tools.get(name)
        
    def list_tools(self) -> List[ToolDefinition]:
        """List all available tools."""
        definitions = []
        
        # Include instantiated tools
        for tool in self._tools.values():
            definitions.append(tool.get_definition())
            
        # Include uninstantiated tool classes
        for name, tool_class in self._tool_classes.items():
            if name not in self._tools:
                temp_instance = tool_class()
                definitions.append(temp_instance.get_definition())
                
        return definitions
        
    async def initialize_all(self) -> None:
        """Initialize all instantiated tools."""
        for tool in self._tools.values():
            await tool.initialize()
            
    async def cleanup_all(self) -> None:
        """Cleanup all tools."""
        cleanup_tasks = [tool.cleanup() for tool in self._tools.values()]
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        self._tools.clear()
