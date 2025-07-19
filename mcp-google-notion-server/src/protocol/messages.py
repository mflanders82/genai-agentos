"""MCP message types and JSON-RPC 2.0 protocol definitions."""

from enum import IntEnum
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field


class ErrorCode(IntEnum):
    """JSON-RPC 2.0 error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR_START = -32099
    SERVER_ERROR_END = -32000
    # MCP-specific error codes
    TOOL_ERROR = -32001
    RESOURCE_ERROR = -32002
    TIMEOUT_ERROR = -32003


class MCPError(BaseModel):
    """JSON-RPC 2.0 error object."""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class MCPMessage(BaseModel):
    """Base MCP message."""
    jsonrpc: str = Field(default="2.0", pattern=r"^2\.0$")


class MCPRequest(MCPMessage):
    """JSON-RPC 2.0 request message."""
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPResponse(MCPMessage):
    """JSON-RPC 2.0 response message."""
    id: Union[str, int]
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None

    def model_post_init(self, __context: Any) -> None:
        """Validate that either result or error is present, but not both."""
        if self.result is None and self.error is None:
            raise ValueError("Either 'result' or 'error' must be present")
        if self.result is not None and self.error is not None:
            raise ValueError("Both 'result' and 'error' cannot be present")


class MCPNotification(MCPMessage):
    """JSON-RPC 2.0 notification message."""
    method: str
    params: Optional[Dict[str, Any]] = None


# MCP-specific method names
class MCPMethods:
    """Standard MCP method names."""
    # Server lifecycle
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"
    SHUTDOWN = "shutdown"
    
    # Tools
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    
    # Resources
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    
    # Prompts
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    
    # Logging
    LOGGING_SET_LEVEL = "logging/setLevel"
    
    # Notifications
    PROGRESS = "notifications/progress"
    MESSAGE = "notifications/message"
    RESOURCES_UPDATED = "notifications/resources/updated"
    TOOLS_UPDATED = "notifications/tools/updated"


# Standard MCP schemas
class ToolDefinition(BaseModel):
    """Tool definition schema."""
    name: str
    description: str
    inputSchema: Dict[str, Any] = Field(alias="input_schema")


class ResourceDefinition(BaseModel):
    """Resource definition schema."""
    uri: str
    name: str
    description: Optional[str] = None
    mimeType: Optional[str] = Field(default=None, alias="mime_type")


class PromptDefinition(BaseModel):
    """Prompt definition schema."""
    name: str
    description: str
    arguments: Optional[Dict[str, Any]] = None


class ServerCapabilities(BaseModel):
    """Server capabilities schema."""
    experimental: Optional[Dict[str, Any]] = None
    logging: Optional[Dict[str, Any]] = None
    prompts: Optional[Dict[str, Any]] = None
    resources: Optional[Dict[str, Any]] = None
    tools: Optional[Dict[str, Any]] = None


class ClientCapabilities(BaseModel):
    """Client capabilities schema."""
    experimental: Optional[Dict[str, Any]] = None
    roots: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None


class InitializeParams(BaseModel):
    """Initialize request parameters."""
    protocolVersion: str = Field(alias="protocol_version")
    capabilities: ClientCapabilities
    clientInfo: Dict[str, str] = Field(alias="client_info")


class InitializeResult(BaseModel):
    """Initialize response result."""
    protocolVersion: str = Field(alias="protocol_version")
    capabilities: ServerCapabilities
    serverInfo: Dict[str, str] = Field(alias="server_info")


class ToolCallParams(BaseModel):
    """Tool call request parameters."""
    name: str
    arguments: Optional[Dict[str, Any]] = None


class ToolCallResult(BaseModel):
    """Tool call response result."""
    content: list[Dict[str, Any]]
    isError: bool = Field(default=False, alias="is_error")


class ProgressNotification(BaseModel):
    """Progress notification parameters."""
    progressToken: Union[str, int] = Field(alias="progress_token")
    progress: float
    total: Optional[float] = None
