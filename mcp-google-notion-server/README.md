# Google-Notion MCP Server

A robust Model Context Protocol (MCP) server that provides seamless integration with Google APIs and Notion, featuring comprehensive error handling, performance optimization, and debugging capabilities. **Designed for integration with GenAI AgentOS.**

## Features

### Google API Integration
- **Gmail**: Read, send, and search email messages
- **Google Calendar**: Manage events, create meetings, and view schedules
- **Google Drive**: Access files, create folders, and manage documents
- **Google Sheets**: Read and write spreadsheet data

### Notion Integration
- **Database Operations**: Query, create, and manage database pages
- **Page Management**: Create, update, and archive pages
- **Search**: Search across your entire Notion workspace
- **Block Operations**: Manage page content blocks

### MCP Features
- JSON-RPC 2.0 compliant protocol implementation
- Multiple transport layers (stdio, WebSocket, HTTP)
- **HTTP transport optimized for GenAI AgentOS integration**
- Comprehensive error handling and graceful degradation
- Performance monitoring with Prometheus metrics
- Structured logging with configurable levels
- Connection pooling and retry mechanisms
- Resource cleanup and memory management

## Quick Start with GenAI AgentOS

### 1. Using Docker (Recommended)

The MCP server is included in the main GenAI AgentOS docker-compose setup:

```bash
# From the main genai-agentos directory
cp .env-example .env

# Configure your API tokens in .env
# GOOGLE_ENABLED=true
# NOTION_ENABLED=true
# NOTION_API_TOKEN=secret_your-notion-integration-token

# Place google_client_config.json in mcp-google-notion-server/ directory

# Start all services
docker compose up
```

### 2. Standalone Setup

```bash
cd mcp-google-notion-server/

# Install dependencies
uv sync  # or pip install -e .

# Configure environment
cp .env-example .env
# Edit .env with your API credentials

# Start server for GenAI AgentOS
./start-genai-agentos.sh
```

### 3. Register with GenAI AgentOS

1. Open GenAI AgentOS at http://localhost:3000
2. Navigate to MCP Servers
3. Add server URL:
   - **Docker setup**: `http://genai-mcp-google-notion:8081`
   - **Standalone**: `http://host.docker.internal:8081`

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd mcp-google-notion-server

# Install dependencies
uv sync

# Or using pip
pip install -e .
```

## Configuration

### Environment Variables

```bash
# Google API Configuration
GOOGLE_ENABLED=true
GOOGLE_CLIENT_CONFIG_FILE=google_client_config.json
GOOGLE_TOKEN_FILE=google_token.json

# Notion Configuration
NOTION_ENABLED=true
NOTION_API_TOKEN=secret_your-notion-integration-token

# Transport Configuration
TRANSPORT_TYPE=stdio  # stdio, websocket, or http
TRANSPORT_URI=ws://localhost:8080/mcp  # for websocket/http

# Metrics (optional)
METRICS_ENABLED=true
METRICS_PORT=8080

# Logging
LOG_LEVEL=info
DEBUG=false
```

### Configuration File

Generate a sample configuration:

```bash
python main.py --sample-config > config.json
```

Edit the configuration file with your API credentials:

```json
{
  "google": {
    "enabled": true,
    "client_config": {
      "installed": {
        "client_id": "your-client-id.googleusercontent.com",
        "client_secret": "your-client-secret",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
      }
    }
  },
  "notion": {
    "enabled": true,
    "api_token": "secret_your-notion-integration-token"
  }
}
```

## Setup

### Google API Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the required APIs:
   - Gmail API
   - Google Calendar API
   - Google Drive API
   - Google Sheets API
4. Create credentials (OAuth 2.0 Client IDs)
5. Download the client configuration JSON
6. Set `GOOGLE_CLIENT_CONFIG_FILE` to the path of your client config

### Notion API Setup

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create a new integration
3. Copy the Internal Integration Token
4. Set `NOTION_API_TOKEN` to your integration token
5. Share your Notion pages/databases with the integration

## Usage

### Basic Usage

```bash
# Run with stdio transport (default)
python main.py

# Run with custom configuration
python main.py --config config.json

# Run with debug logging
python main.py --debug
```

### Transport Options

#### Standard I/O (Default)
```bash
python main.py
```

#### WebSocket
```bash
TRANSPORT_TYPE=websocket TRANSPORT_URI=ws://localhost:8080/mcp python main.py
```

#### HTTP
```bash
TRANSPORT_TYPE=http TRANSPORT_URI=http://localhost:8080 python main.py
```

### Available Tools

#### Google Calendar
```python
# List upcoming events
{
  "action": "list_events",
  "calendar_id": "primary",
  "time_min": "2024-01-01T00:00:00Z",
  "max_results": 10
}

# Create a new event
{
  "action": "create_event",
  "calendar_id": "primary",
  "event_data": {
    "summary": "Team Meeting",
    "start": {"dateTime": "2024-01-15T10:00:00Z"},
    "end": {"dateTime": "2024-01-15T11:00:00Z"}
  }
}
```

#### Gmail
```python
# Search emails
{
  "action": "search",
  "query": "from:example@gmail.com"
}

# Send email
{
  "action": "send_message",
  "to": "recipient@example.com",
  "subject": "Hello from MCP",
  "body": "This email was sent via MCP!"
}
```

#### Google Drive
```python
# List files
{
  "action": "list_files",
  "page_size": 10
}

# Search files
{
  "action": "search",
  "query": "presentation"
}
```

#### Google Sheets
```python
# Read spreadsheet data
{
  "action": "get_values",
  "spreadsheet_id": "your-spreadsheet-id",
  "range": "Sheet1!A1:B10"
}

# Update cells
{
  "action": "update_values",
  "spreadsheet_id": "your-spreadsheet-id",
  "range": "Sheet1!A1:B2",
  "values": [["Name", "Age"], ["John", "30"]]
}
```

#### Notion Database
```python
# Query database
{
  "action": "query",
  "database_id": "your-database-id",
  "filter": {
    "property": "Status",
    "select": {"equals": "In Progress"}
  }
}

# Create page in database
{
  "action": "create_page",
  "database_id": "your-database-id",
  "properties": {
    "Name": {"title": [{"text": {"content": "New Task"}}]},
    "Status": {"select": {"name": "To Do"}}
  }
}
```

#### Notion Pages
```python
# Get page content
{
  "action": "get_page",
  "page_id": "your-page-id"
}

# Update page
{
  "action": "update_page",
  "page_id": "your-page-id",
  "properties": {
    "Name": {"title": [{"text": {"content": "Updated Title"}}]}
  }
}
```

#### Notion Search
```python
# Search workspace
{
  "query": "meeting notes",
  "filter": {
    "property": "object",
    "value": "page"
  }
}
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_tools.py
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

### Configuration Validation

```bash
# Validate configuration
python main.py --validate-config --config config.json
```

## Monitoring

### Metrics

When metrics are enabled, the server exposes Prometheus metrics on the configured port:

- `mcp_requests_total`: Total number of MCP requests
- `mcp_request_duration_seconds`: Request duration histogram
- `mcp_tool_calls_total`: Total number of tool calls
- `mcp_tool_duration_seconds`: Tool execution duration histogram

### Logging

The server uses structured logging with the following levels:
- `debug`: Detailed debugging information
- `info`: General information about server operation
- `warning`: Warning messages about potential issues
- `error`: Error messages for failed operations

Log format can be JSON (production) or console-friendly (development).

## Error Handling

The server implements comprehensive error handling:

### Connection Management
- Automatic reconnection with exponential backoff
- Circuit breaker pattern for external API failures
- Connection pooling with health checks
- Graceful degradation when services are unavailable

### Tool Execution
- Input validation with detailed error messages
- Timeout handling for long-running operations
- Resource cleanup on failures
- Retry logic for transient failures

### Protocol Compliance
- JSON-RPC 2.0 error codes and messages
- Proper error propagation to clients
- Request/response correlation
- Capability negotiation

## Security

### API Credentials
- Credentials are stored securely and never logged
- OAuth tokens are refreshed automatically
- Support for credential rotation
- Environment variable protection

### Transport Security
- TLS support for WebSocket and HTTP transports
- Input sanitization and validation
- Rate limiting (configurable)
- Request size limits

## Performance

### Optimization Features
- Asynchronous operation throughout
- Connection pooling for external APIs
- Lazy loading of tool instances
- Memory-efficient streaming for large responses
- Configurable timeouts and limits

### Scaling
- Stateless design for horizontal scaling
- Resource monitoring and cleanup
- Configurable concurrency limits
- Background task management

## Troubleshooting

### Common Issues

1. **Google API Authentication**
   - Ensure APIs are enabled in Google Cloud Console
   - Check OAuth consent screen configuration
   - Verify redirect URIs match configuration

2. **Notion Integration**
   - Confirm integration has access to required pages/databases
   - Check API token validity
   - Verify database/page IDs are correct

3. **Transport Issues**
   - For WebSocket: ensure server is reachable and supports WebSocket
   - For HTTP: check firewall and network connectivity
   - For stdio: verify process can read/write standard streams

### Debug Mode

```bash
# Enable verbose logging
python main.py --debug

# Or via environment
DEBUG=true LOG_LEVEL=debug python main.py
```

### Health Checks

The server provides health check endpoints when using HTTP transport:
- `GET /health`: Basic health check
- `GET /metrics`: Prometheus metrics (if enabled)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review logs for error details
