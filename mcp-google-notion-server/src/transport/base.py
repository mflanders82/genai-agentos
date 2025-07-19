"""Base transport interface for MCP communication."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Optional
import structlog

logger = structlog.get_logger()


class TransportError(Exception):
    """Base exception for transport-related errors."""
    pass


class ConnectionError(TransportError):
    """Raised when transport connection fails."""
    pass


class MessageError(TransportError):
    """Raised when message handling fails."""
    pass


class Transport(ABC):
    """Abstract base class for MCP transport implementations."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._connected = False
        self._message_id = 0
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._closed = False
        
    @property
    def connected(self) -> bool:
        """Check if transport is connected."""
        return self._connected

    @property
    def closed(self) -> bool:
        """Check if transport is closed."""
        return self._closed

    def _next_message_id(self) -> str:
        """Generate next message ID."""
        self._message_id += 1
        return str(self._message_id)

    @abstractmethod
    async def connect(self) -> None:
        """Establish transport connection."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close transport connection."""
        pass

    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send a message via transport."""
        pass

    @abstractmethod
    async def receive_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """Receive messages from transport."""
        pass

    async def send_request(
        self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Send a request and wait for response."""
        if self._closed:
            raise ConnectionError("Transport is closed")
            
        message_id = self._next_message_id()
        message = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": method,
            "params": params or {},
        }
        
        # Create future for response
        future = asyncio.Future()
        self._pending_requests[message_id] = future
        
        try:
            await self.send_message(message)
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.error("Request timeout", method=method, message_id=message_id)
            raise MessageError(f"Request {method} timed out after {timeout}s")
        finally:
            self._pending_requests.pop(message_id, None)

    async def send_notification(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a notification (no response expected)."""
        if self._closed:
            raise ConnectionError("Transport is closed")
            
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        
        await self.send_message(message)

    def _handle_response(self, message: Dict[str, Any]) -> None:
        """Handle incoming response message."""
        message_id = message.get("id")
        if message_id and message_id in self._pending_requests:
            future = self._pending_requests[message_id]
            
            if "error" in message:
                error = message["error"]
                future.set_exception(
                    MessageError(f"RPC Error {error.get('code')}: {error.get('message')}")
                )
            else:
                future.set_result(message.get("result", {}))

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
