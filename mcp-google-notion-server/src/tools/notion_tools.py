"""Notion API integration tools."""

import asyncio
from typing import Any, Dict, List, Optional
from notion_client import AsyncClient
from notion_client.errors import APIResponseError, RequestTimeoutError
import structlog

from .base import Tool, ToolError

logger = structlog.get_logger()


class NotionAPIError(ToolError):
    """Notion API specific error."""
    pass


class NotionBaseTool(Tool):
    """Base class for Notion API tools."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.client: Optional[AsyncClient] = None
        
    async def _initialize_impl(self) -> None:
        """Initialize Notion API client."""
        try:
            api_token = self.config.get("api_token")
            if not api_token:
                raise NotionAPIError("Notion API token required in config")
                
            self.client = AsyncClient(
                auth=api_token,
                timeout_ms=self.config.get("timeout_ms", 30000)
            )
            
            # Test connection
            await self.client.users.me()
            logger.info("Notion API client initialized successfully")
            
        except Exception as e:
            raise NotionAPIError(f"Failed to initialize Notion API: {e}")
            
    async def _cleanup_impl(self) -> None:
        """Cleanup Notion client."""
        if self.client:
            # Notion client doesn't need explicit cleanup
            self.client = None
            
    async def _execute_notion_call(self, api_call):
        """Execute Notion API call with error handling."""
        try:
            return await api_call
        except APIResponseError as e:
            logger.error("Notion API error", error=str(e), code=e.code)
            raise NotionAPIError(f"Notion API error {e.code}: {e.message}")
        except RequestTimeoutError as e:
            logger.error("Notion API timeout", error=str(e))
            raise NotionAPIError("Notion API request timed out")
        except Exception as e:
            logger.error("Unexpected Notion error", error=str(e))
            raise NotionAPIError(f"Notion error: {e}")


class NotionDatabaseTool(NotionBaseTool):
    """Notion database operations tool."""

    @property
    def name(self) -> str:
        return "notion_database"

    @property
    def description(self) -> str:
        return "Query and manage Notion databases"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["query", "create_page", "get_database", "list_databases"],
                    "description": "Action to perform"
                },
                "database_id": {
                    "type": "string",
                    "description": "Database ID for operations"
                },
                "filter": {
                    "type": "object",
                    "description": "Filter criteria for database query"
                },
                "sorts": {
                    "type": "array",
                    "description": "Sort criteria for database query"
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "minimum": 1,
                    "maximum": 100
                },
                "properties": {
                    "type": "object",
                    "description": "Properties for new page creation"
                },
                "children": {
                    "type": "array",
                    "description": "Children blocks for new page"
                }
            },
            "required": ["action"]
        }

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database operations."""
        action = arguments["action"]
        
        if action == "query":
            return await self._query_database(arguments)
        elif action == "create_page":
            return await self._create_page(arguments)
        elif action == "get_database":
            return await self._get_database(arguments["database_id"])
        elif action == "list_databases":
            return await self._list_databases()
        else:
            raise ToolError(f"Unknown action: {action}")

    async def _query_database(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Query a Notion database."""
        database_id = args.get("database_id")
        if not database_id:
            raise ToolError("database_id required for query action")
            
        query_params = {}
        
        if "filter" in args:
            query_params["filter"] = args["filter"]
        if "sorts" in args:
            query_params["sorts"] = args["sorts"]
        if "page_size" in args:
            query_params["page_size"] = args["page_size"]
            
        result = await self._execute_notion_call(
            self.client.databases.query(database_id=database_id, **query_params)
        )
        
        return {
            "results": result["results"],
            "has_more": result.get("has_more", False),
            "next_cursor": result.get("next_cursor")
        }

    async def _create_page(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new page in a database."""
        database_id = args.get("database_id")
        if not database_id:
            raise ToolError("database_id required for create_page action")
            
        page_data = {
            "parent": {"database_id": database_id},
            "properties": args.get("properties", {})
        }
        
        if "children" in args:
            page_data["children"] = args["children"]
            
        page = await self._execute_notion_call(
            self.client.pages.create(**page_data)
        )
        
        return {"page": page}

    async def _get_database(self, database_id: str) -> Dict[str, Any]:
        """Get database metadata."""
        database = await self._execute_notion_call(
            self.client.databases.retrieve(database_id=database_id)
        )
        
        return {"database": database}

    async def _list_databases(self) -> Dict[str, Any]:
        """List accessible databases."""
        # Note: This searches for database objects
        search_result = await self._execute_notion_call(
            self.client.search(
                filter={"property": "object", "value": "database"},
                page_size=100
            )
        )
        
        return {
            "databases": search_result["results"],
            "has_more": search_result.get("has_more", False)
        }


class NotionPageTool(NotionBaseTool):
    """Notion page operations tool."""

    @property
    def name(self) -> str:
        return "notion_page"

    @property
    def description(self) -> str:
        return "Manage Notion pages and their content"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "get_page", "update_page", "archive_page", 
                        "get_blocks", "append_blocks", "update_block", "delete_block"
                    ],
                    "description": "Action to perform"
                },
                "page_id": {
                    "type": "string",
                    "description": "Page ID for operations"
                },
                "block_id": {
                    "type": "string",
                    "description": "Block ID for block operations"
                },
                "properties": {
                    "type": "object",
                    "description": "Properties to update"
                },
                "blocks": {
                    "type": "array",
                    "description": "Blocks to append or update"
                },
                "archived": {
                    "type": "boolean",
                    "description": "Archive status for page"
                }
            },
            "required": ["action", "page_id"]
        }

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute page operations."""
        action = arguments["action"]
        page_id = arguments["page_id"]
        
        if action == "get_page":
            return await self._get_page(page_id)
        elif action == "update_page":
            return await self._update_page(page_id, arguments)
        elif action == "archive_page":
            return await self._archive_page(page_id, arguments.get("archived", True))
        elif action == "get_blocks":
            return await self._get_blocks(page_id)
        elif action == "append_blocks":
            return await self._append_blocks(page_id, arguments["blocks"])
        elif action == "update_block":
            return await self._update_block(arguments)
        elif action == "delete_block":
            return await self._delete_block(arguments["block_id"])
        else:
            raise ToolError(f"Unknown action: {action}")

    async def _get_page(self, page_id: str) -> Dict[str, Any]:
        """Get page details."""
        page = await self._execute_notion_call(
            self.client.pages.retrieve(page_id=page_id)
        )
        
        return {"page": page}

    async def _update_page(self, page_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update page properties."""
        update_data = {}
        
        if "properties" in args:
            update_data["properties"] = args["properties"]
        if "archived" in args:
            update_data["archived"] = args["archived"]
            
        page = await self._execute_notion_call(
            self.client.pages.update(page_id=page_id, **update_data)
        )
        
        return {"page": page}

    async def _archive_page(self, page_id: str, archived: bool) -> Dict[str, Any]:
        """Archive or unarchive a page."""
        page = await self._execute_notion_call(
            self.client.pages.update(page_id=page_id, archived=archived)
        )
        
        return {"page": page, "archived": archived}

    async def _get_blocks(self, page_id: str) -> Dict[str, Any]:
        """Get blocks from a page."""
        blocks = await self._execute_notion_call(
            self.client.blocks.children.list(block_id=page_id)
        )
        
        return {
            "blocks": blocks["results"],
            "has_more": blocks.get("has_more", False),
            "next_cursor": blocks.get("next_cursor")
        }

    async def _append_blocks(self, page_id: str, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Append blocks to a page."""
        result = await self._execute_notion_call(
            self.client.blocks.children.append(block_id=page_id, children=blocks)
        )
        
        return {"blocks": result["results"]}

    async def _update_block(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific block."""
        block_id = args["block_id"]
        block_data = args.get("block_data", {})
        
        block = await self._execute_notion_call(
            self.client.blocks.update(block_id=block_id, **block_data)
        )
        
        return {"block": block}

    async def _delete_block(self, block_id: str) -> Dict[str, Any]:
        """Delete a block."""
        block = await self._execute_notion_call(
            self.client.blocks.delete(block_id=block_id)
        )
        
        return {"block": block, "deleted": True}


class NotionSearchTool(NotionBaseTool):
    """Notion search tool."""

    @property
    def name(self) -> str:
        return "notion_search"

    @property
    def description(self) -> str:
        return "Search across Notion workspace"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query text"
                },
                "filter": {
                    "type": "object",
                    "description": "Filter criteria",
                    "properties": {
                        "property": {
                            "type": "string",
                            "enum": ["object"]
                        },
                        "value": {
                            "type": "string",
                            "enum": ["page", "database"]
                        }
                    }
                },
                "sort": {
                    "type": "object",
                    "description": "Sort criteria",
                    "properties": {
                        "direction": {
                            "type": "string",
                            "enum": ["ascending", "descending"]
                        },
                        "timestamp": {
                            "type": "string",
                            "enum": ["last_edited_time"]
                        }
                    }
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "minimum": 1,
                    "maximum": 100
                }
            },
            "required": []
        }

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute search operation."""
        search_params = {}
        
        if "query" in arguments:
            search_params["query"] = arguments["query"]
        if "filter" in arguments:
            search_params["filter"] = arguments["filter"]
        if "sort" in arguments:
            search_params["sort"] = arguments["sort"]
        if "page_size" in arguments:
            search_params["page_size"] = arguments["page_size"]
            
        result = await self._execute_notion_call(
            self.client.search(**search_params)
        )
        
        return {
            "results": result["results"],
            "has_more": result.get("has_more", False),
            "next_cursor": result.get("next_cursor")
        }
