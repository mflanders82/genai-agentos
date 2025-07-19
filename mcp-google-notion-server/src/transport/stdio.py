"""Standard I/O transport implementation for MCP."""

import asyncio
import json
import sys
from typing import Any, AsyncIterator, Dict, Optional
import structlog

from .base import Transport, ConnectionError, MessageError

logger = structlog.get_logger()


class StdioTransport(Transport):
    """Standard I/O transport for MCP communication."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._stdin_reader: Optional[asyncio.StreamReader] = None
        self._stdout_writer: Optional[asyncio.StreamWriter] = None
        self._receive_task: Optional[asyncio.Task] = None
        
    async def connect(self) -> None:
        """Initialize stdio streams."""
        if self._connected:
            return
            
        try:
            # Create async streams for stdin/stdout
            self._stdin_reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(self._stdin_reader)
            
            # Connect to stdin
            loop = asyncio.get_event_loop()
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)
            
            # Create stdout writer
            transport, protocol = await loop.connect_write_pipe(
                asyncio.streams.FlowControlMixin, sys.stdout
            )
            self._stdout_writer = asyncio.StreamWriter(transport, protocol, None, loop)
            
            self._connected = True
            self._closed = False
            
            # Start message receiving task
            self._receive_task = asyncio.create_task(self._message_receiver())
            
            logger.info("Stdio transport initialized")
            
        except Exception as e:
            logger.error("Failed to initialize stdio transport", error=str(e))
            raise ConnectionError(f"Failed to initialize stdio: {e}")

    async def disconnect(self) -> None:
        """Close stdio transport."""
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
                    
            # Close writer
            if self._stdout_writer:
                self._stdout_writer.close()
                await self._stdout_writer.wait_closed()
                
            # Cancel pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(ConnectionError("Connection closed"))
            self._pending_requests.clear()
            
            logger.info("Stdio transport closed")
            
        except Exception as e:
            logger.error("Error during stdio disconnect", error=str(e))

    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send message via stdout."""
        if not self._connected or not self._stdout_writer:
            raise ConnectionError("Not connected")
            
        try:
            payload = json.dumps(message) + "\n"
            self._stdout_writer.write(payload.encode())
            await self._stdout_writer.drain()
            
            logger.debug(
                "Message sent",
                method=message.get("method"),
                message_id=message.get("id"),
                size=len(payload),
            )
            
        except Exception as e:
            logger.error("Failed to send message", error=str(e))
            raise MessageError(f"Failed to send message: {e}")

    async def receive_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """Receive messages from stdin."""
        if not self._connected or not self._stdin_reader:
            raise ConnectionError("Not connected")
            
        try:
            while not self._closed:
                line = await self._stdin_reader.readline()
                if not line:
                    break
                    
                try:
                    message = json.loads(line.decode().strip())
                    
                    logger.debug(
                        "Message received",
                        method=message.get("method"),
                        message_id=message.get("id"),
                        size=len(line),
                    )
                    
                    yield message
                    
                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON received", error=str(e), line=line.decode().strip())
                    continue
                    
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
