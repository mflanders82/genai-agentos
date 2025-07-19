"""HTTP transport implementation for MCP."""

import asyncio
import json
from typing import Any, AsyncIterator, Dict, Optional
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import Transport, ConnectionError, MessageError

logger = structlog.get_logger()


class HttpTransport(Transport):
    """HTTP-based transport for MCP communication."""

    def __init__(self, base_url: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
        self._session_id: Optional[str] = None
        
    async def connect(self) -> None:
        """Initialize HTTP client and establish session."""
        if self._connected:
            return
            
        try:
            timeout = httpx.Timeout(
                connect=self.config.get("connect_timeout", 10.0),
                read=self.config.get("read_timeout", 30.0),
                write=self.config.get("write_timeout", 10.0),
                pool=self.config.get("pool_timeout", 10.0),
            )
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=timeout,
                limits=httpx.Limits(
                    max_keepalive_connections=self.config.get("max_keepalive", 20),
                    max_connections=self.config.get("max_connections", 100),
                ),
            )
            
            # Establish session with server
            await self._establish_session()
            
            self._connected = True
            self._closed = False
            
            logger.info("HTTP transport connected", base_url=self.base_url)
            
        except Exception as e:
            logger.error("Failed to connect HTTP transport", error=str(e))
            raise ConnectionError(f"Failed to connect to {self.base_url}: {e}")

    async def disconnect(self) -> None:
        """Close HTTP client and session."""
        if not self._connected:
            return
            
        try:
            self._connected = False
            self._closed = True
            
            # Close session if established
            if self._session_id and self._client:
                try:
                    await self._client.post(
                        "/session/close",
                        json={"session_id": self._session_id},
                        timeout=5.0,
                    )
                except Exception as e:
                    logger.warning("Failed to close session gracefully", error=str(e))
                    
            # Close HTTP client
            if self._client:
                await self._client.aclose()
                self._client = None
                
            # Cancel pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(ConnectionError("Connection closed"))
            self._pending_requests.clear()
            
            logger.info("HTTP transport disconnected")
            
        except Exception as e:
            logger.error("Error during HTTP disconnect", error=str(e))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
    )
    async def send_message(self, message: Dict[str, Any]) -> None:
        """Send message via HTTP POST."""
        if not self._connected or not self._client:
            raise ConnectionError("Not connected")
            
        try:
            payload = {
                "session_id": self._session_id,
                "message": message,
            }
            
            response = await self._client.post("/message", json=payload)
            response.raise_for_status()
            
            logger.debug(
                "Message sent",
                method=message.get("method"),
                message_id=message.get("id"),
                status_code=response.status_code,
            )
            
        except httpx.HTTPError as e:
            logger.error("HTTP error sending message", error=str(e))
            raise MessageError(f"Failed to send message: {e}")
        except Exception as e:
            logger.error("Failed to send message", error=str(e))
            raise MessageError(f"Failed to send message: {e}")

    async def receive_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """Receive messages via HTTP polling."""
        if not self._connected or not self._client:
            raise ConnectionError("Not connected")
            
        poll_interval = self.config.get("poll_interval", 1.0)
        
        try:
            while not self._closed:
                try:
                    response = await self._client.get(
                        f"/messages?session_id={self._session_id}",
                        timeout=poll_interval + 5.0,
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    messages = data.get("messages", [])
                    
                    for message in messages:
                        logger.debug(
                            "Message received",
                            method=message.get("method"),
                            message_id=message.get("id"),
                        )
                        yield message
                        
                    if not messages:
                        await asyncio.sleep(poll_interval)
                        
                except httpx.HTTPError as e:
                    logger.error("HTTP error receiving messages", error=str(e))
                    await asyncio.sleep(poll_interval)
                    
        except Exception as e:
            logger.error("Error receiving messages", error=str(e))
            raise MessageError(f"Failed to receive messages: {e}")

    async def _establish_session(self) -> None:
        """Establish session with HTTP server."""
        if not self._client:
            raise ConnectionError("Client not initialized")
            
        try:
            response = await self._client.post("/session/create")
            response.raise_for_status()
            
            data = response.json()
            self._session_id = data["session_id"]
            
            logger.info("HTTP session established", session_id=self._session_id)
            
        except Exception as e:
            logger.error("Failed to establish HTTP session", error=str(e))
            raise ConnectionError(f"Failed to establish session: {e}")
