#!/bin/bash

# Startup script for Google-Notion MCP Server with GenAI AgentOS integration
# This script configures and runs the MCP server with HTTP transport

set -e

echo "🚀 Starting Google-Notion MCP Server for GenAI AgentOS..."

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Please run this script from the mcp-google-notion-server directory."
    exit 1
fi

# Check if virtual environment exists and activate it
if [ -d ".venv" ]; then
    echo "🐍 Activating virtual environment..."
    source .venv/bin/activate
elif command -v uv &> /dev/null; then
    echo "🐍 Using uv environment..."
    # uv will handle the virtual environment
else
    echo "⚠️  No virtual environment found. Make sure dependencies are installed."
fi

# Set default environment variables if not already set
export TRANSPORT_TYPE=${TRANSPORT_TYPE:-"http"}
export TRANSPORT_PORT=${TRANSPORT_PORT:-8081}
export TRANSPORT_HOST=${TRANSPORT_HOST:-"0.0.0.0"}
export DEBUG=${DEBUG:-"true"}
export LOG_LEVEL=${LOG_LEVEL:-"info"}
export METRICS_ENABLED=${METRICS_ENABLED:-"true"}
export METRICS_PORT=${METRICS_PORT:-8082}

# Check for required configuration files
if [ ! -f "google_client_config.json" ] && [ "$GOOGLE_ENABLED" = "true" ]; then
    echo "⚠️  Warning: google_client_config.json not found. Google API features will be disabled."
    echo "   Please follow the README instructions to set up Google API credentials."
fi

if [ -z "$NOTION_API_TOKEN" ] && [ "$NOTION_ENABLED" = "true" ]; then
    echo "⚠️  Warning: NOTION_API_TOKEN not set. Notion features will be disabled."
    echo "   Please set your Notion integration token in the .env file."
fi

# Start the server
echo "🌐 Starting MCP server on http://${TRANSPORT_HOST}:${TRANSPORT_PORT}"
echo "📊 Metrics available on http://${TRANSPORT_HOST}:${METRICS_PORT}/metrics"
echo "🔗 Use this URL in GenAI AgentOS: http://host.docker.internal:${TRANSPORT_PORT}"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================="

# Use uv if available, otherwise use python directly
if command -v uv &> /dev/null; then
    uv run python main.py --config config-genai-agentos.json
else
    python main.py --config config-genai-agentos.json
fi
