#!/usr/bin/env python3
"""Basic integration test for the MCP server."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

# Test basic imports
def test_imports():
    """Test that all modules can be imported."""
    from src.config import load_config, create_sample_config
    from src.protocol.server import MCPServer
    from src.transport import StdioTransport
    from src.tools import ToolRegistry
    print("✓ All imports successful")

# Test configuration
def test_config():
    """Test configuration loading."""
    from src.config import load_config, create_sample_config
    
    # Test sample config generation
    sample = create_sample_config()
    assert isinstance(sample, dict)
    assert "google" in sample
    assert "notion" in sample
    print("✓ Configuration system working")

# Test server initialization (mock transport)
async def test_server_init():
    """Test server initialization with mock transport."""
    from src.protocol.server import MCPServer
    from src.config import load_config
    
    # Create mock transport
    mock_transport = AsyncMock()
    mock_transport.connected = True
    mock_transport.closed = False
    
    config = load_config()
    config_dict = config.to_dict()
    
    # Initialize server (without starting)
    server = MCPServer(mock_transport, config_dict)
    
    # Test that server has expected components
    assert server.tool_registry is not None
    assert server.protocol_handler is not None
    assert server._server_info["name"] == "Google-Notion MCP Server"
    
    print("✓ Server initialization successful")

# Test tool registry
def test_tool_registry():
    """Test tool registry functionality."""
    from src.tools import ToolRegistry
    from src.tools.google_tools import GoogleCalendarTool
    from src.tools.notion_tools import NotionDatabaseTool
    
    registry = ToolRegistry()
    
    # Register tools
    registry.register_tool_class(GoogleCalendarTool)
    registry.register_tool_class(NotionDatabaseTool)
    
    # List tools
    tools = registry.list_tools()
    assert len(tools) >= 2
    
    tool_names = [tool.name for tool in tools]
    assert "google_calendar" in tool_names
    assert "notion_database" in tool_names
    
    print(f"✓ Tool registry working with {len(tools)} tools")

async def test_message_handling():
    """Test protocol message handling."""
    from src.protocol.handler import ProtocolHandler
    from src.protocol.messages import MCPMethods
    
    # Create mock transport
    mock_transport = AsyncMock()
    mock_transport.connected = True
    mock_transport.closed = False
    
    handler = ProtocolHandler(mock_transport)
    
    # Test handler registration
    test_handler = AsyncMock()
    handler.register_request_handler("test_method", test_handler)
    
    assert "test_method" in handler._request_handlers
    print("✓ Protocol handler working")

async def main():
    """Run all tests."""
    print("🧪 Running basic integration tests...\n")
    
    try:
        # Run synchronous tests
        test_imports()
        test_config()
        test_tool_registry()
        
        # Run asynchronous tests
        await test_server_init()
        await test_message_handling()
        
        print("\n🎉 All tests passed! The MCP server is ready for use.")
        print("\n📝 To get started:")
        print("1. Generate a config: python main.py --sample-config > config.json")
        print("2. Edit config.json with your API credentials")
        print("3. Run server: python main.py --config config.json")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
