"""MCP server implementation."""

import asyncio
from typing import Any, Dict, List, Optional
import structlog
from prometheus_client import Counter, Histogram, start_http_server

from .handler import ProtocolHandler
from .messages import (
    MCPMethods,
    ErrorCode,
    InitializeParams,
    InitializeResult,
    ServerCapabilities,
    ToolCallParams,
    ToolCallResult,
    ToolDefinition,
)
from ..transport.base import Transport
from ..tools.base import ToolRegistry, ToolError

logger = structlog.get_logger()

# Metrics
request_count = Counter('mcp_requests_total', 'Total MCP requests', ['method', 'status'])
request_duration = Histogram('mcp_request_duration_seconds', 'Request duration', ['method'])
tool_calls = Counter('mcp_tool_calls_total', 'Total tool calls', ['tool', 'status'])
tool_duration = Histogram('mcp_tool_duration_seconds', 'Tool execution duration', ['tool'])


class MCPServer:
    """MCP server implementation with Google and Notion tools."""

    def __init__(
        self, 
        transport: Transport, 
        config: Optional[Dict[str, Any]] = None
    ):
        self.transport = transport
        self.config = config or {}
        self.protocol_handler = ProtocolHandler(transport)
        self.tool_registry = ToolRegistry()
        self._initialized = False
        self._running = False
        self._server_info = {
            "name": "Google-Notion MCP Server",
            "version": "0.1.0"
        }
        self._capabilities = ServerCapabilities(
            tools={"listChanged": True},
            logging={"level": "info"},
            experimental={}
        )
        
        # Setup request handlers
        self._setup_handlers()
        
        # Start metrics server if configured
        metrics_port = self.config.get("metrics_port")
        if metrics_port:
            start_http_server(metrics_port)
            logger.info("Metrics server started", port=metrics_port)

    def _setup_handlers(self) -> None:
        """Setup protocol message handlers."""
        # Core MCP methods
        self.protocol_handler.register_request_handler(
            MCPMethods.INITIALIZE, self._handle_initialize
        )
        self.protocol_handler.register_notification_handler(
            MCPMethods.INITIALIZED, self._handle_initialized
        )
        self.protocol_handler.register_request_handler(
            MCPMethods.SHUTDOWN, self._handle_shutdown
        )
        
        # Tool methods
        self.protocol_handler.register_request_handler(
            MCPMethods.TOOLS_LIST, self._handle_tools_list
        )
        self.protocol_handler.register_request_handler(
            MCPMethods.TOOLS_CALL, self._handle_tools_call
        )
        
        # Logging
        self.protocol_handler.register_notification_handler(
            MCPMethods.LOGGING_SET_LEVEL, self._handle_set_log_level
        )

    async def start(self) -> None:
        """Start the MCP server."""
        if self._running:
            return
            
        try:
            # Connect transport
            await self.transport.connect()
            
            # Start protocol handler
            await self.protocol_handler.start()
            
            # Initialize tools
            await self._initialize_tools()
            
            self._running = True
            logger.info("MCP server started", server_info=self._server_info)
            
        except Exception as e:
            logger.error("Failed to start MCP server", error=str(e))
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the MCP server."""
        if not self._running:
            return
            
        try:
            self._running = False
            
            # Cleanup tools
            await self.tool_registry.cleanup_all()
            
            # Stop protocol handler
            await self.protocol_handler.stop()
            
            # Disconnect transport
            await self.transport.disconnect()
            
            logger.info("MCP server stopped")
            
        except Exception as e:
            logger.error("Error stopping MCP server", error=str(e))

    async def run_forever(self) -> None:
        """Run the server until stopped."""
        await self.start()
        
        try:
            # Keep running until stopped
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()

    async def _initialize_tools(self) -> None:
        """Initialize available tools based on configuration."""
        from ..tools import (
            GoogleCalendarTool,
            GoogleDriveTool,
            GoogleGmailTool,
            GoogleSheetsTool,
            NotionDatabaseTool,
            NotionPageTool,
            NotionSearchTool,
        )
        
        # Register all tool classes
        tool_classes = [
            GoogleCalendarTool,
            GoogleDriveTool,
            GoogleGmailTool,
            GoogleSheetsTool,
            NotionDatabaseTool,
            NotionPageTool,
            NotionSearchTool,
        ]
        
        for tool_class in tool_classes:
            self.tool_registry.register_tool_class(tool_class)
            
        # Create and initialize configured tools
        google_config = self.config.get("google", {})
        notion_config = self.config.get("notion", {})
        
        # Initialize Google tools if configured
        if google_config.get("enabled", False):
            google_tools = [
                "google_calendar", "google_drive", "gmail", "google_sheets"
            ]
            for tool_name in google_tools:
                try:
                    tool = self.tool_registry.create_tool(tool_name, google_config)
                    await tool.initialize()
                    logger.info("Google tool initialized", tool=tool_name)
                except Exception as e:
                    logger.error(
                        "Failed to initialize Google tool", 
                        tool=tool_name, 
                        error=str(e)
                    )
                    
        # Initialize Notion tools if configured
        if notion_config.get("enabled", False):
            notion_tools = [
                "notion_database", "notion_page", "notion_search"
            ]
            for tool_name in notion_tools:
                try:
                    tool = self.tool_registry.create_tool(tool_name, notion_config)
                    await tool.initialize()
                    logger.info("Notion tool initialized", tool=tool_name)
                except Exception as e:
                    logger.error(
                        "Failed to initialize Notion tool", 
                        tool=tool_name, 
                        error=str(e)
                    )

    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        with request_duration.labels(method='initialize').time():
            try:
                # Validate initialization parameters
                init_params = InitializeParams.model_validate(params)
                
                logger.info(
                    "Client initializing",
                    protocol_version=init_params.protocol_version,
                    client_info=init_params.client_info
                )
                
                # Mark as initialized
                self._initialized = True
                
                # Return server capabilities
                result = InitializeResult(
                    protocol_version="2024-11-05",
                    capabilities=self._capabilities,
                    server_info=self._server_info
                )
                
                request_count.labels(method='initialize', status='success').inc()
                return result.model_dump()
                
            except Exception as e:
                request_count.labels(method='initialize', status='error').inc()
                logger.error("Initialize failed", error=str(e))
                raise

    async def _handle_initialized(self, params: Dict[str, Any]) -> None:
        """Handle initialized notification."""
        logger.info("Client initialization complete")
        
        # Send tools list update notification
        await self.protocol_handler.send_notification(
            MCPMethods.TOOLS_UPDATED,
            {}
        )

    async def _handle_shutdown(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle shutdown request."""
        logger.info("Shutdown requested")
        
        # Schedule shutdown after response is sent
        asyncio.create_task(self._delayed_shutdown())
        
        return {}

    async def _delayed_shutdown(self) -> None:
        """Shutdown server after a brief delay."""
        await asyncio.sleep(0.1)  # Allow response to be sent
        await self.stop()

    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools list request."""
        with request_duration.labels(method='tools/list').time():
            try:
                if not self._initialized:
                    raise ValueError("Server not initialized")
                    
                tools = self.tool_registry.list_tools()
                tool_defs = [tool.model_dump() for tool in tools]
                
                request_count.labels(method='tools/list', status='success').inc()
                logger.debug("Tools list requested", tool_count=len(tool_defs))
                
                return {"tools": tool_defs}
                
            except Exception as e:
                request_count.labels(method='tools/list', status='error').inc()
                logger.error("Tools list failed", error=str(e))
                raise

    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool call request."""
        with request_duration.labels(method='tools/call').time():
            try:
                if not self._initialized:
                    raise ValueError("Server not initialized")
                    
                # Validate tool call parameters
                call_params = ToolCallParams.model_validate(params)
                tool_name = call_params.name
                arguments = call_params.arguments or {}
                
                logger.info(
                    "Tool call requested",
                    tool=tool_name,
                    arguments=arguments
                )
                
                # Get tool instance
                tool = self.tool_registry.get_tool(tool_name)
                if not tool:
                    # Try to create tool on demand
                    tool_config = self._get_tool_config(tool_name)
                    tool = self.tool_registry.create_tool(tool_name, tool_config)
                    await tool.initialize()
                    
                # Execute tool with metrics
                start_time = asyncio.get_event_loop().time()
                try:
                    with tool_duration.labels(tool=tool_name).time():
                        result = await tool.call(
                            arguments,
                            timeout=self.config.get("tool_timeout", 30.0)
                        )
                        
                    tool_calls.labels(tool=tool_name, status='success').inc()
                    request_count.labels(method='tools/call', status='success').inc()
                    
                    logger.info(
                        "Tool call completed",
                        tool=tool_name,
                        duration=asyncio.get_event_loop().time() - start_time
                    )
                    
                    return result.model_dump()
                    
                except ToolError as e:
                    tool_calls.labels(tool=tool_name, status='error').inc()
                    request_count.labels(method='tools/call', status='error').inc()
                    
                    logger.error(
                        "Tool execution failed",
                        tool=tool_name,
                        error=str(e)
                    )
                    
                    # Return error result
                    return ToolCallResult(
                        content=[{
                            "type": "text",
                            "text": f"Tool error: {e.message}"
                        }],
                        is_error=True
                    ).model_dump()
                    
            except Exception as e:
                request_count.labels(method='tools/call', status='error').inc()
                logger.error("Tool call failed", error=str(e))
                raise

    async def _handle_set_log_level(self, params: Dict[str, Any]) -> None:
        """Handle log level change notification."""
        level = params.get("level", "info")
        logger.info("Log level change requested", level=level)
        
        # Update structlog level if needed
        # This is implementation-specific

    def _get_tool_config(self, tool_name: str) -> Dict[str, Any]:
        """Get configuration for a specific tool."""
        if tool_name.startswith("google_") or tool_name == "gmail":
            return self.config.get("google", {})
        elif tool_name.startswith("notion_"):
            return self.config.get("notion", {})
        else:
            return {}

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
