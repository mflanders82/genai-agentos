"""Configuration management for MCP server."""

import os
from typing import Any, Dict, Optional
import json
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class GoogleConfig(BaseModel):
    """Google API configuration."""
    enabled: bool = False
    client_config: Optional[Dict[str, Any]] = None
    token_file: str = "google_token.json"
    credentials: Optional[Dict[str, Any]] = None
    scopes: Optional[list[str]] = None


class NotionConfig(BaseModel):
    """Notion API configuration."""
    enabled: bool = False
    api_token: Optional[str] = None
    timeout_ms: int = 30000


class TransportConfig(BaseModel):
    """Transport configuration."""
    type: str = "stdio"  # stdio, websocket, http
    uri: Optional[str] = None
    port: Optional[int] = None
    host: str = "localhost"
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    write_timeout: float = 10.0
    max_connections: int = 100
    max_keepalive: int = 20
    poll_interval: float = 1.0


class ServerConfig(BaseSettings):
    """Main server configuration."""
    
    # Server settings
    server_name: str = "Google-Notion MCP Server"
    server_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "info"
    
    # Tool settings
    tool_timeout: float = 30.0
    max_concurrent_tools: int = 10
    
    # Metrics
    metrics_enabled: bool = False
    metrics_port: Optional[int] = None
    
    # Transport
    transport: TransportConfig = Field(default_factory=TransportConfig)
    
    # API configurations
    google: GoogleConfig = Field(default_factory=GoogleConfig)
    notion: NotionConfig = Field(default_factory=NotionConfig)
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False

    @classmethod
    def from_file(cls, config_file: str) -> "ServerConfig":
        """Load configuration from JSON file."""
        with open(config_file, "r") as f:
            config_data = json.load(f)
        return cls(**config_data)

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Load configuration from environment variables."""
        return cls()

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.model_dump()


def load_config(
    config_file: Optional[str] = None,
    use_env: bool = True
) -> ServerConfig:
    """Load configuration from file or environment."""
    
    if config_file and os.path.exists(config_file):
        config = ServerConfig.from_file(config_file)
    elif use_env:
        config = ServerConfig.from_env()
    else:
        config = ServerConfig()
    
    # Override with environment variables if specified
    if use_env:
        # Google configuration from environment
        if os.getenv("GOOGLE_ENABLED"):
            config.google.enabled = os.getenv("GOOGLE_ENABLED", "false").lower() == "true"
        if os.getenv("GOOGLE_CLIENT_CONFIG_FILE"):
            with open(os.getenv("GOOGLE_CLIENT_CONFIG_FILE"), "r") as f:
                config.google.client_config = json.load(f)
        if os.getenv("GOOGLE_TOKEN_FILE"):
            config.google.token_file = os.getenv("GOOGLE_TOKEN_FILE")
            
        # Notion configuration from environment
        if os.getenv("NOTION_ENABLED"):
            config.notion.enabled = os.getenv("NOTION_ENABLED", "false").lower() == "true"
        if os.getenv("NOTION_API_TOKEN"):
            config.notion.api_token = os.getenv("NOTION_API_TOKEN")
            
        # Transport configuration
        if os.getenv("TRANSPORT_TYPE"):
            config.transport.type = os.getenv("TRANSPORT_TYPE")
        if os.getenv("TRANSPORT_URI"):
            config.transport.uri = os.getenv("TRANSPORT_URI")
        if os.getenv("TRANSPORT_PORT"):
            config.transport.port = int(os.getenv("TRANSPORT_PORT"))
            
        # Metrics
        if os.getenv("METRICS_ENABLED"):
            config.metrics_enabled = os.getenv("METRICS_ENABLED", "false").lower() == "true"
        if os.getenv("METRICS_PORT"):
            config.metrics_port = int(os.getenv("METRICS_PORT"))
    
    return config


def create_sample_config() -> Dict[str, Any]:
    """Create a sample configuration for reference."""
    return {
        "server_name": "Google-Notion MCP Server",
        "server_version": "0.1.0",
        "debug": False,
        "log_level": "info",
        "tool_timeout": 30.0,
        "max_concurrent_tools": 10,
        "metrics_enabled": False,
        "metrics_port": 8080,
        "transport": {
            "type": "stdio",
            "uri": None,
            "port": None,
            "host": "localhost",
            "connect_timeout": 10.0,
            "read_timeout": 30.0,
            "write_timeout": 10.0,
            "max_connections": 100,
            "max_keepalive": 20,
            "poll_interval": 1.0
        },
        "google": {
            "enabled": False,
            "client_config": {
                "installed": {
                    "client_id": "your-client-id.googleusercontent.com",
                    "client_secret": "your-client-secret",
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            "token_file": "google_token.json",
            "credentials": None,
            "scopes": [
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/gmail.modify",
                "https://www.googleapis.com/auth/spreadsheets"
            ]
        },
        "notion": {
            "enabled": False,
            "api_token": "secret_your-notion-integration-token",
            "timeout_ms": 30000
        }
    }
