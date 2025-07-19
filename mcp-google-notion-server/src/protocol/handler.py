"""Protocol handler for MCP message processing."""

import asyncio
import json
from typing import Any, Callable, Dict, Optional, Set
import structlog
from pydantic import ValidationError

from .messages import (
    MCPMessage,
    MCPRequest,
    MCPResponse,
    MCPNotification,
    MCPError,
    ErrorCode,
    MCPMethods,
)
from ..transport.base import Transport, MessageError

logger = structlog.get_logger()


class ProtocolHandler:
    """Handles MCP protocol message routing and validation."""

    def __init__(self, transport: Transport):
        self.transport = transport
        self._request_handlers: Dict[str, Callable] = {}
        self._notification_handlers: Dict[str, Callable] = {}
        self._running = False
        self._message_task: Optional[asyncio.Task] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._sequence_number = 0
        
    def register_request_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for request messages."""
        self._request_handlers[method] = handler
        logger.debug("Registered request handler", method=method)
        
    def register_notification_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for notification messages."""
        self._notification_handlers[method] = handler
        logger.debug("Registered notification handler", method=method)
        
    def unregister_handler(self, method: str) -> None:
        """Unregister handlers for a method."""
        self._request_handlers.pop(method, None)
        self._notification_handlers.pop(method, None)
        logger.debug("Unregistered handlers", method=method)
        
    async def start(self) -> None:
        """Start the protocol handler."""
        if self._running:
            return
            
        self._running = True
        self._message_task = asyncio.create_task(self._message_loop())
        logger.info("Protocol handler started")
        
    async def stop(self) -> None:
        """Stop the protocol handler."""
        if not self._running:
            return
            
        self._running = False
        
        if self._message_task and not self._message_task.done():
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass
                
        # Cancel pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(MessageError("Protocol handler stopped"))
        self._pending_requests.clear()
        
        logger.info("Protocol handler stopped")
        
    async def send_request(
        self, 
        method: str, 
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Send a request and wait for response."""
        if not self._running:
            raise MessageError("Protocol handler not running")
            
        request_id = self._next_sequence_number()
        request = MCPRequest(id=request_id, method=method, params=params)
        
        # Create future for response
        future = asyncio.Future()
        self._pending_requests[str(request_id)] = future
        
        try:
            await self.transport.send_message(request.model_dump(exclude_none=True))
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.error("Request timeout", method=method, request_id=request_id)
            raise MessageError(f"Request {method} timed out after {timeout}s")
        finally:
            self._pending_requests.pop(str(request_id), None)
            
    async def send_notification(
        self, 
        method: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send a notification (no response expected)."""
        if not self._running:
            raise MessageError("Protocol handler not running")
            
        notification = MCPNotification(method=method, params=params)
        await self.transport.send_message(notification.model_dump(exclude_none=True))
        
    async def send_response(
        self, 
        request_id: str, 
        result: Optional[Dict[str, Any]] = None,
        error: Optional[MCPError] = None
    ) -> None:
        """Send a response to a request."""
        if not self._running:
            raise MessageError("Protocol handler not running")
            
        response = MCPResponse(id=request_id, result=result, error=error)
        await self.transport.send_message(response.model_dump(exclude_none=True))
        
    def _next_sequence_number(self) -> int:
        """Get next sequence number for request IDs."""
        self._sequence_number += 1
        return self._sequence_number
        
    async def _message_loop(self) -> None:
        """Main message processing loop."""
        try:
            async for raw_message in self.transport.receive_messages():
                try:
                    await self._process_message(raw_message)
                except Exception as e:
                    logger.error("Error processing message", error=str(e), message=raw_message)
                    
        except Exception as e:
            logger.error("Message loop failed", error=str(e))
        finally:
            logger.debug("Message loop stopped")
            
    async def _process_message(self, raw_message: Dict[str, Any]) -> None:
        """Process a single message."""
        try:
            # Validate basic JSON-RPC structure
            if not isinstance(raw_message, dict):
                raise ValueError("Message must be a JSON object")
                
            if raw_message.get("jsonrpc") != "2.0":
                raise ValueError("Invalid JSON-RPC version")
                
            # Determine message type and process
            if "id" in raw_message:
                if "method" in raw_message:
                    # Request message
                    await self._handle_request(raw_message)
                else:
                    # Response message
                    await self._handle_response(raw_message)
            elif "method" in raw_message:
                # Notification message
                await self._handle_notification(raw_message)
            else:
                raise ValueError("Invalid message structure")
                
        except ValidationError as e:
            logger.error("Message validation failed", error=str(e))
            await self._send_error_response(
                raw_message.get("id"),
                ErrorCode.INVALID_REQUEST,
                "Invalid request",
                {"validation_errors": e.errors()}
            )
        except Exception as e:
            logger.error("Message processing failed", error=str(e))
            await self._send_error_response(
                raw_message.get("id"),
                ErrorCode.INTERNAL_ERROR,
                "Internal error"
            )
            
    async def _handle_request(self, raw_message: Dict[str, Any]) -> None:
        """Handle incoming request message."""
        try:
            request = MCPRequest.model_validate(raw_message)
            
            logger.debug(
                "Request received",
                method=request.method,
                request_id=request.id
            )
            
            # Find handler
            handler = self._request_handlers.get(request.method)
            if not handler:
                await self._send_error_response(
                    request.id,
                    ErrorCode.METHOD_NOT_FOUND,
                    f"Method '{request.method}' not found"
                )
                return
                
            # Execute handler
            try:
                result = await handler(request.params or {})
                await self.send_response(str(request.id), result=result)
                
            except Exception as e:
                logger.error(
                    "Request handler failed",
                    method=request.method,
                    error=str(e)
                )
                await self._send_error_response(
                    request.id,
                    ErrorCode.INTERNAL_ERROR,
                    str(e)
                )
                
        except ValidationError as e:
            logger.error("Invalid request format", error=str(e))
            await self._send_error_response(
                raw_message.get("id"),
                ErrorCode.INVALID_REQUEST,
                "Invalid request format"
            )
            
    async def _handle_response(self, raw_message: Dict[str, Any]) -> None:
        """Handle incoming response message."""
        try:
            response = MCPResponse.model_validate(raw_message)
            
            logger.debug(
                "Response received",
                response_id=response.id
            )
            
            # Find pending request
            future = self._pending_requests.get(str(response.id))
            if not future or future.done():
                logger.warning("Unexpected response", response_id=response.id)
                return
                
            # Complete the future
            if response.error:
                future.set_exception(
                    MessageError(f"RPC Error {response.error.code}: {response.error.message}")
                )
            else:
                future.set_result(response.result or {})
                
        except ValidationError as e:
            logger.error("Invalid response format", error=str(e))
            
    async def _handle_notification(self, raw_message: Dict[str, Any]) -> None:
        """Handle incoming notification message."""
        try:
            notification = MCPNotification.model_validate(raw_message)
            
            logger.debug(
                "Notification received",
                method=notification.method
            )
            
            # Find handler
            handler = self._notification_handlers.get(notification.method)
            if not handler:
                logger.warning("No handler for notification", method=notification.method)
                return
                
            # Execute handler (fire and forget)
            try:
                await handler(notification.params or {})
            except Exception as e:
                logger.error(
                    "Notification handler failed",
                    method=notification.method,
                    error=str(e)
                )
                
        except ValidationError as e:
            logger.error("Invalid notification format", error=str(e))
            
    async def _send_error_response(
        self,
        request_id: Optional[str],
        code: ErrorCode,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send an error response."""
        if request_id is None:
            return  # Can't respond to notification
            
        error = MCPError(code=code, message=message, data=data)
        await self.send_response(request_id, error=error)
