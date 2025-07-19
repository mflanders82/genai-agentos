"""WebSocket transport implementation for MCP."""

import asyncio
import json
from typing import Any, AsyncIterator, Dict, Optional
import websockets
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import Transport, ConnectionError, MessageError

logger = structlog.get_logger()


class WebSocketTransport(Transport):
    """WebSocket-based transport for MCP communication."""

    def __init__(self, uri: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.uri = uri
        self._websocket: Optional[websockets.WebSocketServerProtocol] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._connection_lock = asyncio.Lock()
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, OSError)),
    )
    async def connect(self) -> None:
        """Establish WebSocket connection with retry logic."""
        async with self._connection_lock:
            if self._connected:
                return
                
            try:
                logger.info("Connecting to WebSocket", uri=self.uri)
                self._websocket = await websockets.connect(
                    self.uri,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10,
                )
                self._connected = True
                self._closed = False
                
                # Start message receiving task
                self._receive_task = asyncio.create_task(self._message_receiver())
                
                logger.info("WebSocket connected successfully", uri=self.uri)
                
            except Exception as e:
                logger.error("Failed to connect to WebSocket", uri=self.uri, error=str(e))
                raise ConnectionError(f"Failed to connect to {self.uri}: {e}")

    async def disconnect(self) -> None:
        """Close WebSocket connection and cleanup resources."""
        async with self._connection_lock:
            if not self._connected:
                return
                
            try:
                self._connected = False
                self._closed = True
                
                # Cancel receive task
                if self._receive_task and not self._receive_task.done():
                    self._receive_task.cancel()
                    try:
                        await self._receive_task
                    except asyncio.CancelledError:
                        pass
                        
                # Close WebSocket
                if self._websocket:
                    await self._websocket.close()
                    self._websocket = None
                    
                # Cancel pending requests
                for future in self._pending_requests.values():
                    if not future.done():
                        future.set_exception(ConnectionError("Connection closed"))
                self._pending_requests.clear()
                
                logger.info("WebSocket disconnected", uri=self.uri)
                
            except Exception as e:
                logger.error("Error during disconnect", error=str(e))

    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send message via WebSocket."""
        if not self._connected or not self._websocket:
            raise ConnectionError("Not connected")
            
        try:
            payload = json.dumps(message)
            await self._websocket.send(payload)
            
            logger.debug(
                "Message sent",
                method=message.get("method"),
                message_id=message.get("id"),
                size=len(payload),
            )
            
        except websockets.exceptions.ConnectionClosed:
            self._connected = False
            raise ConnectionError("WebSocket connection closed")
        except Exception as e:
            logger.error("Failed to send message", error=str(e))
            raise MessageError(f"Failed to send message: {e}")

    async def receive_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """Receive messages from WebSocket."""
        if not self._connected or not self._websocket:
            raise ConnectionError("Not connected")
            
        try:
            async for raw_message in self._websocket:
                try:
                    message = json.loads(raw_message)
                    
                    logger.debug(
                        "Message received",
                        method=message.get("method"),
                        message_id=message.get("id"),
                        size=len(raw_message),
                    )
                    
                    yield message
                    
                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON received", error=str(e), raw_message=raw_message)
                    continue
                    
        except websockets.exceptions.ConnectionClosed:
            self._connected = False
            logger.info("WebSocket connection closed by peer")
        except Exception as e:
            logger.error("Error receiving messages", error=str(e))
            raise MessageError(f"Failed to receive messages: {e}")

    async def _message_receiver(self) -> None:
        """Background task to handle incoming messages."""
        try:
            async for message in self.receive_messages():
                # Handle responses to pending requests
                if "id" in message and message["id"] in self._pending_requests:
                    self._handle_response(message)
                    
        except Exception as e:
            logger.error("Message receiver task failed", error=str(e))
        finally:
            logger.debug("Message receiver task stopped")
