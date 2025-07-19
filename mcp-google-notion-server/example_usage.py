#!/usr/bin/env python3
"""Example usage of the Google-Notion MCP Server."""

import asyncio
import json
from src.protocol.server import MCPServer
from src.transport import StdioTransport
from src.config import load_config


async def example_with_google_calendar():
    """Example: Using Google Calendar tool."""
    print("📅 Google Calendar Example")
    print("This would list upcoming events from your primary calendar.")
    
    # Example tool call for Google Calendar
    example_call = {
        "action": "list_events",
        "calendar_id": "primary",
        "max_results": 5
    }
    
    print(f"Tool call: {json.dumps(example_call, indent=2)}")
    print("Expected response: List of upcoming calendar events\n")


async def example_with_notion_database():
    """Example: Using Notion database tool."""
    print("📊 Notion Database Example")
    print("This would query a Notion database for pages.")
    
    # Example tool call for Notion Database
    example_call = {
        "action": "query",
        "database_id": "your-database-id-here",
        "filter": {
            "property": "Status",
            "select": {
                "equals": "In Progress"
            }
        },
        "page_size": 10
    }
    
    print(f"Tool call: {json.dumps(example_call, indent=2)}")
    print("Expected response: Filtered database pages\n")


async def example_server_setup():
    """Example: Setting up the MCP server."""
    print("🚀 Server Setup Example")
    print("This shows how to configure and run the MCP server.")
    
    # Load configuration
    config = load_config()
    
    # Example of enabling Google services
    config.google.enabled = True
    config.google.client_config = {
        "installed": {
            "client_id": "your-client-id.googleusercontent.com",
            "client_secret": "your-client-secret",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }
    
    # Example of enabling Notion services
    config.notion.enabled = True
    config.notion.api_token = "secret_your-notion-integration-token"
    
    print("Configuration ready!")
    print(f"Google enabled: {config.google.enabled}")
    print(f"Notion enabled: {config.notion.enabled}")
    print(f"Transport type: {config.transport.type}")
    print()


async def main():
    """Run all examples."""
    print("🔧 MCP Server Usage Examples\n")
    print("=" * 50)
    
    await example_server_setup()
    await example_with_google_calendar()
    await example_with_notion_database()
    
    print("💡 Tips:")
    print("1. Configure your API credentials in config.json")
    print("2. Use 'python main.py --sample-config' to generate template")
    print("3. Run 'python main.py' to start the server with stdio transport")
    print("4. For WebSocket: TRANSPORT_TYPE=websocket python main.py")
    print("5. Enable metrics with METRICS_ENABLED=true METRICS_PORT=8080")
    print()
    print("🔗 Available Tools:")
    tools = [
        "google_calendar - Manage Google Calendar events",
        "google_drive - Access Google Drive files",
        "gmail - Send and read Gmail messages", 
        "google_sheets - Read/write Google Sheets data",
        "notion_database - Query and manage Notion databases",
        "notion_page - Create and edit Notion pages",
        "notion_search - Search across Notion workspace"
    ]
    
    for i, tool in enumerate(tools, 1):
        print(f"  {i}. {tool}")


if __name__ == "__main__":
    asyncio.run(main())
