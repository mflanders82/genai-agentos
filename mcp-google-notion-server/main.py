#!/usr/bin/env python3
"""Main entry point for Google-Notion MCP Server."""

import asyncio
import argparse
import json
import os
import sys
from typing import Optional
import structlog
from structlog.contextvars import clear_contextvars

from src.config import load_config, create_sample_config
from src.protocol.server import MCPServer
from src.transport import WebSocketTransport, StdioTransport, HttpTransport


def setup_logging(level: str = "info", debug: bool = False) -> None:
    """Setup structured logging."""
    log_level = getattr(structlog.stdlib.logging, level.upper(), structlog.stdlib.logging.INFO)
    
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    if debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Set root logger level
    import logging
    logging.basicConfig(level=log_level, format="%(message)s")


def create_transport(config):
    """Create transport instance based on configuration."""
    transport_config = config.transport
    
    if transport_config.type == "stdio":
        return StdioTransport(transport_config.model_dump())
    elif transport_config.type == "websocket":
        if not transport_config.uri:
            raise ValueError("WebSocket URI required for websocket transport")
        return WebSocketTransport(transport_config.uri, transport_config.model_dump())
    elif transport_config.type == "http":
        if not transport_config.uri:
            base_url = f"http://{transport_config.host}:{transport_config.port or 8080}"
        else:
            base_url = transport_config.uri
        return HttpTransport(base_url, transport_config.model_dump())
    else:
        raise ValueError(f"Unknown transport type: {transport_config.type}")


async def run_server(config_file: Optional[str] = None) -> None:
    """Run the MCP server."""
    # Load configuration
    config = load_config(config_file)
    
    # Setup logging
    setup_logging(config.log_level, config.debug)
    logger = structlog.get_logger()
    
    logger.info(
        "Starting MCP server",
        server_name=config.server_name,
        version=config.server_version,
        transport_type=config.transport.type
    )
    
    try:
        # Create transport
        transport = create_transport(config)
        
        # Create and run server
        async with MCPServer(transport, config.to_dict()) as server:
            logger.info("MCP server running")
            await server.run_forever()
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down")
    except Exception as e:
        logger.error("Server error", error=str(e), exc_info=True)
        sys.exit(1)
    finally:
        clear_contextvars()
        logger.info("MCP server stopped")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Google-Notion MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with stdio transport (default)
  python main.py
  
  # Run with custom config file
  python main.py --config config.json
  
  # Generate sample config
  python main.py --sample-config
  
  # Run with WebSocket transport
  TRANSPORT_TYPE=websocket TRANSPORT_URI=ws://localhost:8080/mcp python main.py
  
  # Run with Google and Notion enabled
  GOOGLE_ENABLED=true NOTION_ENABLED=true python main.py
"""
    )
    
    parser.add_argument(
        "--config", 
        "-c", 
        help="Configuration file path (JSON format)"
    )
    parser.add_argument(
        "--sample-config",
        action="store_true",
        help="Generate sample configuration and exit"
    )
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate configuration and exit"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    if args.sample_config:
        # Generate sample configuration
        sample_config = create_sample_config()
        print(json.dumps(sample_config, indent=2))
        return
    
    if args.validate_config:
        # Validate configuration
        try:
            config = load_config(args.config)
            print("Configuration is valid")
            print(json.dumps(config.to_dict(), indent=2))
        except Exception as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            sys.exit(1)
        return
    
    # Set debug from command line if specified
    if args.debug:
        os.environ["DEBUG"] = "true"
        os.environ["LOG_LEVEL"] = "debug"
    
    # Run the server
    try:
        asyncio.run(run_server(args.config))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
