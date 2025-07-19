"""Tests for tool implementations."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.tools.base import Tool, ToolRegistry, ToolError
from src.tools.google_tools import GoogleCalendarTool
from src.tools.notion_tools import NotionDatabaseTool


class MockTool(Tool):
    """Mock tool for testing."""
    
    @property
    def name(self) -> str:
        return "mock_tool"
    
    @property
    def description(self) -> str:
        return "A mock tool for testing"
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string"}
            },
            "required": ["message"]
        }
    
    async def execute(self, arguments: dict) -> dict:
        return {"response": f"Hello {arguments['message']}"}


class TestToolRegistry:
    """Test tool registry functionality."""
    
    def test_register_tool_class(self):
        """Test tool class registration."""
        registry = ToolRegistry()
        registry.register_tool_class(MockTool)
        
        tool = registry.create_tool("mock_tool")
        assert isinstance(tool, MockTool)
        assert tool.name == "mock_tool"
    
    def test_create_unknown_tool(self):
        """Test creating unknown tool raises error."""
        registry = ToolRegistry()
        
        with pytest.raises(ValueError, match="Unknown tool"):
            registry.create_tool("unknown_tool")
    
    def test_list_tools(self):
        """Test listing available tools."""
        registry = ToolRegistry()
        registry.register_tool_class(MockTool)
        
        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "mock_tool"
    
    @pytest.mark.asyncio
    async def test_initialize_all(self):
        """Test initializing all tools."""
        registry = ToolRegistry()
        registry.register_tool_class(MockTool)
        
        tool = registry.create_tool("mock_tool")
        assert not tool._initialized
        
        await registry.initialize_all()
        assert tool._initialized
    
    @pytest.mark.asyncio
    async def test_cleanup_all(self):
        """Test cleaning up all tools."""
        registry = ToolRegistry()
        registry.register_tool_class(MockTool)
        
        tool = registry.create_tool("mock_tool")
        await tool.initialize()
        assert tool._initialized
        
        await registry.cleanup_all()
        assert not tool._initialized


class TestBaseTool:
    """Test base tool functionality."""
    
    @pytest.mark.asyncio
    async def test_tool_initialization(self):
        """Test tool initialization."""
        tool = MockTool()
        assert not tool._initialized
        
        await tool.initialize()
        assert tool._initialized
    
    @pytest.mark.asyncio
    async def test_tool_cleanup(self):
        """Test tool cleanup."""
        tool = MockTool()
        await tool.initialize()
        assert tool._initialized
        
        await tool.cleanup()
        assert not tool._initialized
    
    @pytest.mark.asyncio
    async def test_tool_call_success(self):
        """Test successful tool call."""
        tool = MockTool()
        
        result = await tool.call({"message": "World"})
        
        assert not result.isError
        assert len(result.content) == 1
        assert "Hello World" in result.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_tool_call_validation_error(self):
        """Test tool call with validation error."""
        tool = MockTool()
        
        with pytest.raises(ToolError):
            await tool.call({})  # Missing required 'message' field
    
    @pytest.mark.asyncio
    async def test_tool_call_timeout(self):
        """Test tool call timeout."""
        tool = MockTool()
        
        # Mock execute to simulate long-running operation
        async def slow_execute(arguments):
            import asyncio
            await asyncio.sleep(2)
            return {"response": "slow"}
        
        tool.execute = slow_execute
        
        with pytest.raises(ToolError, match="timed out"):
            await tool.call({"message": "test"}, timeout=0.1)
    
    def test_get_definition(self):
        """Test getting tool definition."""
        tool = MockTool()
        definition = tool.get_definition()
        
        assert definition.name == "mock_tool"
        assert definition.description == "A mock tool for testing"
        assert definition.inputSchema["type"] == "object"


class TestGoogleCalendarTool:
    """Test Google Calendar tool."""
    
    @pytest.fixture
    def calendar_tool(self):
        """Create calendar tool with mock config."""
        config = {
            "client_config": {
                "installed": {
                    "client_id": "test-client-id",
                    "client_secret": "test-secret"
                }
            }
        }
        return GoogleCalendarTool(config)
    
    def test_tool_properties(self, calendar_tool):
        """Test tool properties."""
        assert calendar_tool.name == "google_calendar"
        assert "Calendar" in calendar_tool.description
        assert "action" in calendar_tool.input_schema["properties"]
    
    @pytest.mark.asyncio
    @patch('src.tools.google_tools.build')
    @patch('src.tools.google_tools.Credentials')
    async def test_list_events(self, mock_credentials, mock_build, calendar_tool):
        """Test listing calendar events."""
        # Mock Google API service
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_list = MagicMock()
        
        mock_build.return_value = mock_service
        mock_service.events.return_value = mock_events
        mock_events.list.return_value = mock_list
        mock_list.execute.return_value = {
            "items": [
                {"id": "1", "summary": "Test Event"}
            ]
        }
        
        # Mock credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_credentials.from_authorized_user_info.return_value = mock_creds
        calendar_tool.credentials = mock_creds
        calendar_tool.service = mock_service
        calendar_tool._initialized = True
        
        result = await calendar_tool.execute({
            "action": "list_events",
            "calendar_id": "primary"
        })
        
        assert "events" in result
        assert len(result["events"]) == 1
        assert result["events"][0]["summary"] == "Test Event"


class TestNotionDatabaseTool:
    """Test Notion database tool."""
    
    @pytest.fixture
    def notion_tool(self):
        """Create notion tool with mock config."""
        config = {
            "api_token": "secret_test-token"
        }
        return NotionDatabaseTool(config)
    
    def test_tool_properties(self, notion_tool):
        """Test tool properties."""
        assert notion_tool.name == "notion_database"
        assert "database" in notion_tool.description.lower()
        assert "action" in notion_tool.input_schema["properties"]
    
    @pytest.mark.asyncio
    @patch('src.tools.notion_tools.AsyncClient')
    async def test_query_database(self, mock_client_class, notion_tool):
        """Test querying notion database."""
        # Mock Notion client
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Mock query response
        mock_client.databases.query.return_value = {
            "results": [
                {"id": "page-1", "properties": {}}
            ],
            "has_more": False
        }
        
        notion_tool.client = mock_client
        notion_tool._initialized = True
        
        result = await notion_tool.execute({
            "action": "query",
            "database_id": "test-db-id"
        })
        
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["id"] == "page-1"
        
        # Verify client was called correctly
        mock_client.databases.query.assert_called_once_with(
            database_id="test-db-id"
        )
    
    @pytest.mark.asyncio
    async def test_missing_database_id(self, notion_tool):
        """Test error when database_id is missing."""
        notion_tool._initialized = True
        
        with pytest.raises(ToolError, match="database_id required"):
            await notion_tool.execute({"action": "query"})


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_tool_execution_error(self):
        """Test handling of tool execution errors."""
        class FailingTool(Tool):
            @property
            def name(self) -> str:
                return "failing_tool"
            
            @property
            def description(self) -> str:
                return "A tool that always fails"
            
            @property
            def input_schema(self) -> dict:
                return {"type": "object", "properties": {}}
            
            async def execute(self, arguments: dict) -> dict:
                raise RuntimeError("Tool failed")
        
        tool = FailingTool()
        
        with pytest.raises(ToolError, match="Tool failing_tool execution failed"):
            await tool.call({})
    
    @pytest.mark.asyncio
    async def test_initialization_error(self):
        """Test handling of initialization errors."""
        class InitFailTool(Tool):
            @property
            def name(self) -> str:
                return "init_fail_tool"
            
            @property
            def description(self) -> str:
                return "A tool that fails to initialize"
            
            @property
            def input_schema(self) -> dict:
                return {"type": "object", "properties": {}}
            
            async def _initialize_impl(self) -> None:
                raise RuntimeError("Initialization failed")
            
            async def execute(self, arguments: dict) -> dict:
                return {}
        
        tool = InitFailTool()
        
        with pytest.raises(ToolError, match="Failed to initialize"):
            await tool.initialize()
