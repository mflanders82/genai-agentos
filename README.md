# 🐍 GenAI Agents Infrastructure

This repository provides the complete infrastructure for running GenAI agents, including:

* Backend
* Router
* Master Agents
* PostgreSQL Database
* Frontend
* CLI
* Redis
* Celery

## ### 7. Register with GenAI AgentOS
1. Go to the Frontend UI at [http://localhost:3000/](http://localhost:3000/)
2. Navigate to MCP Servers section
3. Add new MCP server with URL: `http://host.docker.internal:8081`

**Note:** When running in Docker, use `http://host.docker.internal:8081` instead of `http://localhost:8081` to allow the GenAI backend to access your local MCP server.

### Alternative: Docker Setup (Recommended)

The MCP Google-Notion server is included in the main docker-compose setup:

```bash
# Configure environment variables in .env file
cp .env-example .env

# Add your Google and Notion credentials to .env:
# GOOGLE_ENABLED=true
# NOTION_ENABLED=true
# NOTION_API_TOKEN=secret_your-notion-integration-token

# Place your google_client_config.json in mcp-google-notion-server/ directory

# Start all services including MCP server
make up
# or
docker compose up
```

The MCP server will be available at:
- **Service URL:** `http://genai-mcp-google-notion:8081` (internal Docker network)
- **External URL:** `http://localhost:8081` (from host machine)
- **GenAI AgentOS URL:** `http://genai-mcp-google-notion:8081` (use this in the UI)

## 💎 Environment Variablesitory Link

👉 [GitHub Repository](https://github.com/genai-works-org/genai-agentos)

## 🛠️ Readme Files

* [CLI](cli/README.md)
* [Backend](backend/README.md)
* [Master Agents](master-agent/README.md)
* [Router](router/README.md)
* [Frontend](frontend/README.md)

## 📄️ License
* [MIT](LICENSE)


## 🧠 Supported Agent Types

The system supports multiple kinds of Agents:

| Agent Type       | Description                                                                                   |
|------------------|-----------------------------------------------------------------------------------------------|
| **GenAI Agents** | Connected via [`genai-protocol`](https://pypi.org/project/genai-protocol/) library interface. |
| **MCP Servers**  | MCP (Model Context Protocol) servers can be added by pasting their URL in the UI. Supports Google APIs and Notion integration via the included `mcp-google-notion-server`. |
| **A2A Servers**  | A2A (Agent to Agent Protocol) servers can be added by pasting their URL in the UI.            |

### 🔌 Built-in MCP Google-Notion Server

The system includes a robust MCP server (`mcp-google-notion-server/`) that provides:

**Google API Integration:**
- Gmail: Read, send, and search emails
- Google Calendar: Manage events and schedules
- Google Drive: Access and manage files
- Google Sheets: Read and write spreadsheet data

**Notion Integration:**
- Database operations and page management
- Search across Notion workspace
- Block-level content management

**Features:**
- HTTP transport support for GenAI AgentOS integration
- Comprehensive error handling and logging
- Performance monitoring with Prometheus metrics
- Connection pooling and retry mechanisms

---

## 📦 Prerequisites

Make sure you have the following installed:

* [Docker](https://www.docker.com/)
* [Docker Compose](https://docs.docker.com/compose/)
* [`make`](https://www.gnu.org/software/make/) (optional)

  * macOS: `brew install make`
  * Linux: `sudo apt-get install make`

## 🚀 Local Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/genai-works-org/genai-agentos.git
   cd genai-agentos/
   ```

2. Create a `.env` file by copying the example (can be empty and customized later):

   ```bash
   cp .env-example .env
   ```

   * A `.env` file **should be present** for configuration.
   * All variables in `.env-example` are commented.
     You can customize any environment setting by **uncommenting** the relevant line and providing a new value.

3. Start Docker desktop and ensure it is running.

4. Start the infrastructure:

   ```bash
   make up
   # or alternatively
   docker compose up
   ```

5. After startup:

   * Frontend UI: [http://localhost:3000/](http://localhost:3000/)
   * Swagger API Docs: [http://localhost:8000/docs#/](http://localhost:8000/docs#/)

## 👾 Supported Providers and Models
* OpenAI: gpt-4o

## 🌐 Ngrok Setup (Optional)

Ngrok can be used to expose the local WebSocket endpoint.

1. Install Ngrok:

   * macOS (Homebrew): `brew install ngrok/ngrok/ngrok`
   * Linux: `sudo snap install ngrok`

2. Authenticate Ngrok:

   * Sign up or log in at [ngrok dashboard](https://dashboard.ngrok.com).
   * Go to the **"Your Authtoken"** section and copy the token.
   * Run the command:

     ```bash
     ngrok config add-authtoken <YOUR_AUTH_TOKEN>
     ```

3. Start a tunnel to local port 8080:

   ```bash
   ngrok http 8080
   ```

4. Copy the generated WebSocket URL and update the `ws_url` field in:

   ```
   genai_session.session.GenAISession
   ```

---

## 🤖GenAI Agent registration quick start (For more data check [CLI](cli/README.md))
```bash
cd cli/

python cli.py signup -u <username> # Register a new user, also available in [UI](http://localhost:3000/)

python cli.py login -u <username> -p <password> # Login to the system, get JWT user token

python cli.py register_agent --name <agent_name> --description <agent_description>

cd agents/

# Run the agent
uv run python <agent_name>.py # or alternatively 
python <agent_name>.py 
```

## � MCP Google-Notion Server Setup

The included MCP Google-Notion server provides integration with Google APIs and Notion. Follow these steps to set it up:

### 1. Navigate to MCP Server Directory
```bash
cd mcp-google-notion-server/
```

### 2. Install Dependencies
```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 3. Configure Environment Variables
Create a `.env` file in the `mcp-google-notion-server/` directory:

```bash
# Google API Configuration
GOOGLE_ENABLED=true
GOOGLE_CLIENT_CONFIG_FILE=google_client_config.json
GOOGLE_TOKEN_FILE=google_token.json

# Notion Configuration  
NOTION_ENABLED=true
NOTION_API_TOKEN=secret_your-notion-integration-token

# Transport Configuration for GenAI AgentOS
TRANSPORT_TYPE=http
TRANSPORT_PORT=8081
TRANSPORT_HOST=0.0.0.0

# Logging
DEBUG=true
LOG_LEVEL=info
```

### 4. Setup Google API Credentials
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable required APIs (Gmail, Calendar, Drive, Sheets)
4. Create OAuth 2.0 credentials
5. Download the credentials JSON file as `google_client_config.json`

### 5. Setup Notion Integration
1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create a new integration
3. Copy the integration token to your `.env` file
4. Share your Notion pages/databases with the integration

### 6. Run the MCP Server
```bash
# Start the server with HTTP transport for GenAI AgentOS
python main.py --transport http --port 8081
```

### 7. Register with GenAI AgentOS
1. Go to the Frontend UI at [http://localhost:3000/](http://localhost:3000/)
2. Navigate to MCP Servers section
3. Add new MCP server with URL: `http://host.docker.internal:8081`

**Note:** When running in Docker, use `http://host.docker.internal:8081` instead of `http://localhost:8081` to allow the GenAI backend to access your local MCP server.

## �💎 Environment Variables

| Variable                    | Description                                                          | Example / Default                                                                       |
|-----------------------------|----------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| `FRONTEND_PORT`             | Port to start a frontend                                             | `3000` - default. Can be changed by run in terminal ` source FRONTEND_PORT=<your_port>` |
| `ROUTER_WS_URL`             | WebSocket URL for the `router` container                             | `ws://genai-router:8080/ws` - host is either `localhost` or `router` container name     |
| `SECRET_KEY`                | Secret key for cryptographic operations - JWT/ LLM config encryption | `$(openssl rand -hex 32)`                                                               |
| `POSTGRES_HOST`             | PostgreSQL Host                                                      | `genai-postgres`                                                                        |
| `POSTGRES_USER`             | PostgreSQL Username                                                  | `postgres`                                                                              |
| `POSTGRES_PASSWORD`         | PostgreSQL Password                                                  | `postgres`                                                                              |
| `POSTGRES_DB`               | PostgreSQL Database Name                                             | `postgres`                                                                              |
| `POSTGRES_PORT`             | PostgreSQL Port                                                      | `5432`                                                                                  |
| `DEBUG`                     | Enable/disable debug mode - Server/ ORM logging                      | `True` / `False`                                                                        |
| `MASTER_AGENT_API_KEY`      | API key for the Master Agent - internal identifier                   | `e1adc3d8-fca1-40b2-b90a-7b48290f2d6a::master_server_ml`                                |
| `MASTER_BE_API_KEY`         | API key for the Master Backend - internal identifier                 | `7a3fd399-3e48-46a0-ab7c-0eaf38020283::master_server_be`                                |
| `BACKEND_CORS_ORIGINS`      | Allowed CORS origins for the `backend`                               | `["*"]`, `["http://localhost"]`                                                         |
| `DEFAULT_FILES_FOLDER_NAME` | Default folder for file storage - Docker file volume path            | `/files`                                                                                |
| `CLI_BACKEND_ORIGIN_URL`    | `backend` URL for CLI access                                         | `http://localhost:8000`                                                                 |

### MCP Google-Notion Server Variables

| Variable                    | Description                                                          | Example / Default                                                                       |
|-----------------------------|----------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| `GOOGLE_ENABLED`            | Enable Google API integration                                        | `true` / `false`                                                                        |
| `GOOGLE_CLIENT_CONFIG_FILE` | Path to Google OAuth client configuration JSON                      | `google_client_config.json`                                                            |
| `GOOGLE_TOKEN_FILE`         | Path to store Google OAuth tokens                                    | `google_token.json`                                                                     |
| `NOTION_ENABLED`            | Enable Notion integration                                            | `true` / `false`                                                                        |
| `NOTION_API_TOKEN`          | Notion integration API token                                         | `secret_your-notion-integration-token`                                                  |
| `TRANSPORT_TYPE`            | MCP transport protocol type                                          | `http` / `stdio` / `websocket`                                                          |
| `TRANSPORT_PORT`            | Port for HTTP transport (for GenAI AgentOS integration)             | `8081`                                                                                  |
| `TRANSPORT_HOST`            | Host binding for HTTP transport                                      | `0.0.0.0` / `localhost`                                                                 |
| `METRICS_ENABLED`           | Enable Prometheus metrics                                            | `true` / `false`                                                                        |
| `METRICS_PORT`              | Port for metrics endpoint                                            | `8082`                                                                                  |

## 🛠️ Troubleshooting

### ❓ MCP server or A2A card URL could not be accessed by the genai-backend
✅ If your MCP server or A2A card is hosted on your local machine, make sure to change the host name from `http://localhost:<your_port>` to `http://host.docker.internal:<your_port>` and try again.

🔎 **Also make sure to pass the full url of your MCP server or A2A card, such as - `http://host.docker.internal:8000/mcp` for MCP or `http://host.docker.internal:10002` for A2A**

⚠️ No need to specify `/.well-known/agent.json` for your A2A card as `genai-backend` will do it for you!

### ❓ My MCP server with valid host cannot be accessed by the genai-backend 
✅ Make sure your MCP server supports `streamable-http` protocol and is remotely accessible.Also make sure that you're specifiying full URL of your server, like - `http://host.docker.internal:8000/mcp`

⚠️ Side note: `sse` protocol is officially deprecated by MCP protocol devs, `stdio` protocol is not supported yet, but stay tuned for future announcements!

### ❓ Google-Notion MCP Server connection issues
✅ Make sure the MCP server is running with HTTP transport:
```bash
cd mcp-google-notion-server/
python main.py --transport http --port 8081
```

✅ Use `http://host.docker.internal:8081` as the MCP server URL in the GenAI AgentOS UI (not `localhost`)

✅ Verify your Google API credentials are properly configured in `google_client_config.json`

✅ Ensure your Notion integration token is valid and the integration has access to your workspace

✅ Check the MCP server logs for authentication or API errors

### ❓ Google API authentication fails
✅ Verify your Google Cloud Console project has the required APIs enabled:
- Gmail API
- Google Calendar API  
- Google Drive API
- Google Sheets API

✅ Make sure your OAuth 2.0 credentials are configured for the correct application type

✅ Check that the `google_client_config.json` file path is correct and the file is readable

### ❓ Notion integration not working
✅ Verify your Notion integration token starts with `secret_` 

✅ Make sure you've shared the relevant Notion pages/databases with your integration

✅ Check that the integration has the required permissions (read/write content, read/write pages)