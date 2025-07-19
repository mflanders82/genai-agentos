"""Google API integration tools."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import aiofiles
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import structlog

from .base import Tool, ToolError

logger = structlog.get_logger()


class GoogleAPIError(ToolError):
    """Google API specific error."""
    pass


class GoogleBaseTool(Tool):
    """Base class for Google API tools."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.credentials: Optional[Credentials] = None
        self.service = None
        self._scopes: List[str] = []
        
    async def _initialize_impl(self) -> None:
        """Initialize Google API credentials."""
        try:
            await self._load_credentials()
            if not self.credentials or not self.credentials.valid:
                await self._refresh_or_authenticate()
            self.service = await self._build_service()
            
        except Exception as e:
            raise GoogleAPIError(f"Failed to initialize Google API: {e}")
            
    async def _load_credentials(self) -> None:
        """Load credentials from config or file."""
        creds_data = self.config.get("credentials")
        if creds_data:
            self.credentials = Credentials.from_authorized_user_info(
                creds_data, self._scopes
            )
        else:
            # Try to load from file
            token_file = self.config.get("token_file", "token.json")
            try:
                async with aiofiles.open(token_file, "r") as f:
                    content = await f.read()
                    import json
                    creds_data = json.loads(content)
                    self.credentials = Credentials.from_authorized_user_info(
                        creds_data, self._scopes
                    )
            except FileNotFoundError:
                logger.info("No existing credentials found", token_file=token_file)
                
    async def _refresh_or_authenticate(self) -> None:
        """Refresh credentials or start OAuth flow."""
        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            await asyncio.get_event_loop().run_in_executor(
                None, self.credentials.refresh, Request()
            )
            await self._save_credentials()
        else:
            await self._authenticate()
            
    async def _authenticate(self) -> None:
        """Perform OAuth authentication."""
        client_config = self.config.get("client_config")
        if not client_config:
            raise GoogleAPIError("client_config required for authentication")
            
        flow = Flow.from_client_config(
            client_config,
            scopes=self._scopes,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob"
        )
        
        auth_url, _ = flow.authorization_url(prompt="consent")
        
        logger.info("Please visit this URL to authorize the application", url=auth_url)
        
        # In a real implementation, you'd need a way to get the auth code
        # For now, we'll raise an error indicating manual setup is needed
        raise GoogleAPIError(
            "Manual authentication required. Please visit the URL and configure credentials."
        )
        
    async def _save_credentials(self) -> None:
        """Save credentials to file."""
        if not self.credentials:
            return
            
        token_file = self.config.get("token_file", "token.json")
        creds_data = {
            "token": self.credentials.token,
            "refresh_token": self.credentials.refresh_token,
            "token_uri": self.credentials.token_uri,
            "client_id": self.credentials.client_id,
            "client_secret": self.credentials.client_secret,
            "scopes": self.credentials.scopes,
        }
        
        async with aiofiles.open(token_file, "w") as f:
            import json
            await f.write(json.dumps(creds_data, indent=2))
            
    async def _build_service(self):
        """Build Google API service. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement _build_service")
        
    async def _execute_api_call(self, api_call):
        """Execute Google API call with error handling."""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, api_call.execute
            )
        except HttpError as e:
            logger.error("Google API error", error=str(e))
            raise GoogleAPIError(f"Google API error: {e}")


class GoogleCalendarTool(GoogleBaseTool):
    """Google Calendar integration tool."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._scopes = [
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events"
        ]

    @property
    def name(self) -> str:
        return "google_calendar"

    @property
    def description(self) -> str:
        return "Access and manage Google Calendar events"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_events", "create_event", "get_event", "update_event", "delete_event"],
                    "description": "Action to perform"
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID (default: primary)",
                    "default": "primary"
                },
                "event_id": {
                    "type": "string",
                    "description": "Event ID for get/update/delete operations"
                },
                "time_min": {
                    "type": "string",
                    "description": "Start time for event listing (ISO format)"
                },
                "time_max": {
                    "type": "string",
                    "description": "End time for event listing (ISO format)"
                },
                "event_data": {
                    "type": "object",
                    "description": "Event data for create/update operations",
                    "properties": {
                        "summary": {"type": "string"},
                        "description": {"type": "string"},
                        "start": {"type": "object"},
                        "end": {"type": "object"},
                        "attendees": {"type": "array"}
                    }
                }
            },
            "required": ["action"]
        }

    async def _build_service(self):
        """Build Calendar API service."""
        return build("calendar", "v3", credentials=self.credentials)

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute calendar operations."""
        action = arguments["action"]
        calendar_id = arguments.get("calendar_id", "primary")
        
        if action == "list_events":
            return await self._list_events(calendar_id, arguments)
        elif action == "create_event":
            return await self._create_event(calendar_id, arguments)
        elif action == "get_event":
            return await self._get_event(calendar_id, arguments["event_id"])
        elif action == "update_event":
            return await self._update_event(calendar_id, arguments)
        elif action == "delete_event":
            return await self._delete_event(calendar_id, arguments["event_id"])
        else:
            raise ToolError(f"Unknown action: {action}")

    async def _list_events(self, calendar_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """List calendar events."""
        params = {
            "calendarId": calendar_id,
            "timeMin": args.get("time_min", datetime.now(timezone.utc).isoformat()),
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": args.get("max_results", 10)
        }
        
        if "time_max" in args:
            params["timeMax"] = args["time_max"]
            
        events_result = await self._execute_api_call(
            self.service.events().list(**params)
        )
        
        return {
            "events": events_result.get("items", []),
            "next_page_token": events_result.get("nextPageToken")
        }

    async def _create_event(self, calendar_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new event."""
        event_data = args.get("event_data", {})
        
        event = await self._execute_api_call(
            self.service.events().insert(calendarId=calendar_id, body=event_data)
        )
        
        return {"event": event}

    async def _get_event(self, calendar_id: str, event_id: str) -> Dict[str, Any]:
        """Get a specific event."""
        event = await self._execute_api_call(
            self.service.events().get(calendarId=calendar_id, eventId=event_id)
        )
        
        return {"event": event}

    async def _update_event(self, calendar_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing event."""
        event_id = args["event_id"]
        event_data = args.get("event_data", {})
        
        event = await self._execute_api_call(
            self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event_data
            )
        )
        
        return {"event": event}

    async def _delete_event(self, calendar_id: str, event_id: str) -> Dict[str, Any]:
        """Delete an event."""
        await self._execute_api_call(
            self.service.events().delete(calendarId=calendar_id, eventId=event_id)
        )
        
        return {"success": True, "message": f"Event {event_id} deleted"}


class GoogleDriveTool(GoogleBaseTool):
    """Google Drive integration tool."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.file"
        ]

    @property
    def name(self) -> str:
        return "google_drive"

    @property
    def description(self) -> str:
        return "Access and manage Google Drive files"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_files", "get_file", "search", "create_folder", "upload_file"],
                    "description": "Action to perform"
                },
                "file_id": {
                    "type": "string",
                    "description": "File ID for specific operations"
                },
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "folder_name": {
                    "type": "string",
                    "description": "Name for new folder"
                },
                "parent_id": {
                    "type": "string",
                    "description": "Parent folder ID"
                }
            },
            "required": ["action"]
        }

    async def _build_service(self):
        """Build Drive API service."""
        return build("drive", "v3", credentials=self.credentials)

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute drive operations."""
        action = arguments["action"]
        
        if action == "list_files":
            return await self._list_files(arguments)
        elif action == "get_file":
            return await self._get_file(arguments["file_id"])
        elif action == "search":
            return await self._search_files(arguments["query"])
        elif action == "create_folder":
            return await self._create_folder(arguments)
        else:
            raise ToolError(f"Unknown action: {action}")

    async def _list_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List files in Drive."""
        params = {
            "pageSize": args.get("page_size", 10),
            "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, size)"
        }
        
        if "parent_id" in args:
            params["q"] = f"'{args['parent_id']}' in parents"
            
        result = await self._execute_api_call(
            self.service.files().list(**params)
        )
        
        return {
            "files": result.get("files", []),
            "next_page_token": result.get("nextPageToken")
        }

    async def _get_file(self, file_id: str) -> Dict[str, Any]:
        """Get file metadata."""
        file_metadata = await self._execute_api_call(
            self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, modifiedTime, webViewLink"
            )
        )
        
        return {"file": file_metadata}

    async def _search_files(self, query: str) -> Dict[str, Any]:
        """Search for files."""
        result = await self._execute_api_call(
            self.service.files().list(
                q=f"name contains '{query}'",
                fields="files(id, name, mimeType, modifiedTime)"
            )
        )
        
        return {"files": result.get("files", [])}

    async def _create_folder(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new folder."""
        folder_metadata = {
            "name": args["folder_name"],
            "mimeType": "application/vnd.google-apps.folder"
        }
        
        if "parent_id" in args:
            folder_metadata["parents"] = [args["parent_id"]]
            
        folder = await self._execute_api_call(
            self.service.files().create(body=folder_metadata, fields="id, name")
        )
        
        return {"folder": folder}


class GoogleGmailTool(GoogleBaseTool):
    """Gmail integration tool."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send"
        ]

    @property
    def name(self) -> str:
        return "gmail"

    @property
    def description(self) -> str:
        return "Access and manage Gmail messages"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_messages", "get_message", "search", "send_message"],
                    "description": "Action to perform"
                },
                "message_id": {
                    "type": "string",
                    "description": "Message ID for specific operations"
                },
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "to": {
                    "type": "string",
                    "description": "Recipient email address"
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject"
                },
                "body": {
                    "type": "string",
                    "description": "Email body"
                }
            },
            "required": ["action"]
        }

    async def _build_service(self):
        """Build Gmail API service."""
        return build("gmail", "v1", credentials=self.credentials)

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Gmail operations."""
        action = arguments["action"]
        
        if action == "list_messages":
            return await self._list_messages(arguments)
        elif action == "get_message":
            return await self._get_message(arguments["message_id"])
        elif action == "search":
            return await self._search_messages(arguments["query"])
        elif action == "send_message":
            return await self._send_message(arguments)
        else:
            raise ToolError(f"Unknown action: {action}")

    async def _list_messages(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List Gmail messages."""
        params = {
            "userId": "me",
            "maxResults": args.get("max_results", 10)
        }
        
        if "query" in args:
            params["q"] = args["query"]
            
        result = await self._execute_api_call(
            self.service.users().messages().list(**params)
        )
        
        return {
            "messages": result.get("messages", []),
            "next_page_token": result.get("nextPageToken")
        }

    async def _get_message(self, message_id: str) -> Dict[str, Any]:
        """Get a specific message."""
        message = await self._execute_api_call(
            self.service.users().messages().get(userId="me", id=message_id)
        )
        
        return {"message": message}

    async def _search_messages(self, query: str) -> Dict[str, Any]:
        """Search messages."""
        result = await self._execute_api_call(
            self.service.users().messages().list(userId="me", q=query)
        )
        
        return {"messages": result.get("messages", [])}

    async def _send_message(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Send an email message."""
        import base64
        from email.mime.text import MIMEText
        
        message = MIMEText(args["body"])
        message["to"] = args["to"]
        message["subject"] = args["subject"]
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        send_result = await self._execute_api_call(
            self.service.users().messages().send(
                userId="me",
                body={"raw": raw_message}
            )
        )
        
        return {"message_id": send_result["id"], "success": True}


class GoogleSheetsTool(GoogleBaseTool):
    """Google Sheets integration tool."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/spreadsheets"
        ]

    @property
    def name(self) -> str:
        return "google_sheets"

    @property
    def description(self) -> str:
        return "Access and manage Google Sheets"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_values", "update_values", "append_values", "create_sheet"],
                    "description": "Action to perform"
                },
                "spreadsheet_id": {
                    "type": "string",
                    "description": "Spreadsheet ID"
                },
                "range": {
                    "type": "string",
                    "description": "Cell range (e.g., 'A1:B2')"
                },
                "values": {
                    "type": "array",
                    "description": "Values to write"
                },
                "title": {
                    "type": "string",
                    "description": "Title for new spreadsheet"
                }
            },
            "required": ["action"]
        }

    async def _build_service(self):
        """Build Sheets API service."""
        return build("sheets", "v4", credentials=self.credentials)

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Sheets operations."""
        action = arguments["action"]
        
        if action == "get_values":
            return await self._get_values(arguments)
        elif action == "update_values":
            return await self._update_values(arguments)
        elif action == "append_values":
            return await self._append_values(arguments)
        elif action == "create_sheet":
            return await self._create_sheet(arguments)
        else:
            raise ToolError(f"Unknown action: {action}")

    async def _get_values(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get values from a range."""
        result = await self._execute_api_call(
            self.service.spreadsheets().values().get(
                spreadsheetId=args["spreadsheet_id"],
                range=args["range"]
            )
        )
        
        return {
            "values": result.get("values", []),
            "range": result.get("range")
        }

    async def _update_values(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update values in a range."""
        body = {
            "values": args["values"]
        }
        
        result = await self._execute_api_call(
            self.service.spreadsheets().values().update(
                spreadsheetId=args["spreadsheet_id"],
                range=args["range"],
                valueInputOption="RAW",
                body=body
            )
        )
        
        return {"updated_cells": result.get("updatedCells", 0)}

    async def _append_values(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Append values to a sheet."""
        body = {
            "values": args["values"]
        }
        
        result = await self._execute_api_call(
            self.service.spreadsheets().values().append(
                spreadsheetId=args["spreadsheet_id"],
                range=args["range"],
                valueInputOption="RAW",
                body=body
            )
        )
        
        return {"updated_rows": result.get("updates", {}).get("updatedRows", 0)}

    async def _create_sheet(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new spreadsheet."""
        body = {
            "properties": {
                "title": args["title"]
            }
        }
        
        result = await self._execute_api_call(
            self.service.spreadsheets().create(body=body)
        )
        
        return {
            "spreadsheet_id": result["spreadsheetId"],
            "spreadsheet_url": result["spreadsheetUrl"]
        }
