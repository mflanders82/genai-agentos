# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Infrastructure
- Start all services: `make up` or `docker compose up --build`
- Build containers: `make build` or `docker compose build`
- Expose local WebSocket via ngrok: `make remote` (uses port 8080 by default)

### Backend (Python FastAPI)
- Navigate to: `cd backend/`
- Install dependencies: `uv sync`
- Run development server: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- Run database migrations: `alembic upgrade head`
- Lint: `ruff check` and `ruff format`

### Frontend (React TypeScript)
- Navigate to: `cd frontend/`
- Install dependencies: `npm install`
- Start dev server: `npm run dev`
- Build for production: `npm run build`
- Run linting: `npm run lint`
- Run tests: `npm test`

### CLI Tool
- Navigate to: `cd cli/`
- Install dependencies: `uv sync`
- Register user: `python cli.py signup -u <username>`
- Login: `python cli.py login -u <username> -p <password>`
- Register agent: `python cli.py register_agent --name <name> --description <description>`

### Master Agent
- Navigate to: `cd master-agent/`
- Install dependencies: `uv sync`
- Run: `python main.py`

### Router
- Navigate to: `cd router/`
- Install dependencies: `uv sync`
- Run: `python main.py`

### Testing
- Navigate to: `cd tests/`
- Install dependencies: `uv sync`
- Run all tests: `pytest`
- Run with multiple workers: `pytest -n auto`

## Architecture Overview

### System Components
The system is a multi-service architecture for orchestrating GenAI agents:

1. **Backend** (`backend/`): FastAPI application that serves as the main API and database interface
   - Uses SQLAlchemy with PostgreSQL for data persistence
   - WebSocket support for real-time communication
   - JWT authentication system
   - Celery for background task processing

2. **Frontend** (`frontend/`): React TypeScript application with modern UI components
   - Vite build system
   - Tailwind CSS for styling
   - React Router for navigation
   - WebSocket integration for real-time updates

3. **Router** (`router/`): WebSocket message routing service that coordinates communication between agents

4. **Master Agent** (`master-agent/`): LangGraph-based orchestration agent that manages other agents
   - Implements ReAct pattern for agent coordination
   - Supports multiple LLM providers (OpenAI, Azure OpenAI, Ollama)

5. **CLI** (`cli/`): Command-line interface for agent management and registration

### Agent Types Supported
- **GenAI Agents**: Connected via `genai-protocol` library
- **MCP Servers**: Model Context Protocol servers
- **A2A Servers**: Agent-to-Agent Protocol servers

### Key Directories
- `src/routes/`: API endpoint definitions organized by feature
- `src/repositories/`: Database access layer
- `src/schemas/`: Pydantic models for request/response validation
- `src/utils/`: Shared utilities and helpers
- `frontend/src/components/`: React components organized by feature
- `frontend/src/services/`: API client and service layer

### Database
- PostgreSQL with Alembic migrations
- Models defined in `backend/src/models/`
- Database session management via middleware

### Authentication
- JWT-based authentication system
- User registration and login endpoints
- Protected routes with dependency injection

### WebSocket Communication
- Real-time messaging between frontend and backend
- Agent registration and status updates
- Chat message streaming

### Environment Configuration
Key environment variables are defined in `.env` file. Critical ones include:
- `ROUTER_WS_URL`: WebSocket URL for router communication
- `SECRET_KEY`: JWT signing key
- Database connection settings
- LLM provider API keys

### Local Development with Docker
- Uses `host.docker.internal` for local service communication
- Shared volumes for file storage between services
- Network isolation via `local-genai-network`

## Important Notes

- Always check that services are running via `docker compose ps` before development
- Frontend connects to backend via WebSocket at `ws://backend:8000` in Docker environment
- For local MCP/A2A servers, use `http://host.docker.internal:<port>` instead of `localhost`
- The system requires PostgreSQL, Redis, and all core services to be running for full functionality
- Agent registration requires authentication - use CLI or frontend to create accounts first