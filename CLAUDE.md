# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gemini Flux Chat Local is a full-stack AI chat application featuring:
- **Frontend**: React 19 + TypeScript + Vite
- **Backend**: FastAPI (Python) with async support
- **Key Features**: Multi-model support, image generation/editing, PDF extraction, web search, session management, authentication

## Architecture

### Frontend Structure (React + TypeScript)
```
frontend/
├── App.tsx              # Main application component with routing
├── components/          # Reusable UI components
├── hooks/              # Custom React hooks (useSettings, useModels, useChat, etc.)
├── services/           # API clients and service layers
│   ├── llmService.ts   # LLM provider orchestration
│   ├── providers/      # Provider-specific implementations (DashScope, OpenAI, etc.)
│   ├── db.ts           # IndexedDB wrapper
│   └── storage/        # Storage layer abstraction
├── types/              # TypeScript type definitions
└── utils/              # Utility functions

Key Patterns:
- **Service Layer**: All API calls go through service classes (llmService, apiClient, etc.)
- **Custom Hooks**: Business logic separated into hooks for reusability
- **Provider Pattern**: Multi-provider support via abstract interfaces
```

### Backend Structure (FastAPI + Python)
```
backend/app/
├── main.py             # Application entry point with CORS and lifecycle management
├── routers/            # API route handlers
│   ├── auth.py         # Authentication endpoints
│   ├── dashscope_proxy.py  # DashScope API proxy
│   ├── sessions.py     # Session management
│   ├── storage.py      # Data persistence
│   └── research.py     # Research/RAG features
├── services/           # Business logic layer
│   ├── browser.py      # Web scraping with Selenium
│   ├── pdf_extractor.py  # PDF structured extraction
│   ├── redis_queue_service.py  # Async task queue
│   └── storage_service.py  # Database operations
├── models/             # SQLAlchemy ORM models
├── core/               # Core utilities (logger, config)
└── middleware/         # Request/response middleware

Key Patterns:
- **Relative Imports**: Use relative imports (`.services`, `.models`) for package-internal imports
- **Async-First**: All I/O operations use async/await
- **Proxy Pattern**: Backend proxies external APIs to bypass CORS
```

### Data Flow
```
User Action (Frontend)
    ↓
Custom Hook (e.g., useChat)
    ↓
Service Layer (llmService)
    ↓
API Client (fetch to backend)
    ↓
Backend Router (FastAPI endpoint)
    ↓
Service Layer (business logic)
    ↓
Database/External API
```

## Development Commands

### Installation
```bash
# Install frontend dependencies
npm install

# Install backend dependencies
pip install -r backend/requirements.txt
# or for development
pip install -r backend/requirements-dev.txt
```

### Running the Application

**Full Stack (Recommended)**:
```bash
npm run dev
```
This command uses `concurrently` to start both:
- Backend: `uvicorn app.main:app --reload --port 8000`
- Frontend: `vite dev server on port 5173`

**Backend Only**:
```bash
npm run server
# or manually:
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

**Frontend Only** (基础功能):
```bash
# From project root
npx vite
# or
vite
```

### Building
```bash
npm run build  # TypeScript compilation + Vite build
npm run preview  # Preview production build
```

### Testing
```bash
# Backend tests
cd backend
pytest

# Specific test file
pytest tests/test_health.py

# With coverage
pytest --cov=app tests/
```

## Port Configuration

| Service | Port | Purpose |
|---------|------|---------|
| Frontend Dev Server | 5173 | Vite development server |
| Backend API | 8000 | FastAPI application |
| Vite Proxy | - | `/api/*` → `http://localhost:8000/api/*` |

**Important**: Frontend proxies all `/api/*` requests to backend (see `vite.config.ts`).

## Environment Variables

### Frontend (.env.local)
```bash
VITE_DASHSCOPE_API_KEY=sk-xxx  # Optional, can configure in UI
```

### Backend (backend/.env)
```bash
DATABASE_URL=sqlite:///./test.db  # or PostgreSQL URL
DASHSCOPE_API_KEY=sk-xxx  # Optional
REDIS_URL=redis://localhost:6379  # For queue service
```

## Critical Architecture Decisions

### 1. Import Strategy (Backend)
**Primary**: Relative imports (`.services`, `.models`)
**Fallback**: Absolute imports for direct execution compatibility
```python
try:
    from .services.browser import read_webpage  # Module execution
except ImportError:
    from services.browser import read_webpage  # Direct execution
```

### 2. CORS Proxy Pattern
Backend acts as proxy for external APIs (DashScope) to bypass browser CORS restrictions. Frontend **must** use backend for:
- Image generation/editing
- PDF extraction
- Web search

### 3. Storage Layer Abstraction
- **Frontend**: Dual storage (IndexedDB + optional backend)
- **Backend**: Database-agnostic (SQLAlchemy ORM)
- Sessions can sync between local and cloud storage

### 4. Multi-Model Support
`llmService` dynamically routes to different providers based on model configuration:
- DashScope (Qwen models)
- OpenAI compatible APIs
- Custom providers via adapter pattern

### 5. Async Queue System
Redis-based queue for long-running tasks (image uploads, PDF processing):
```python
from .services.redis_queue_service import RedisQueueService
queue = RedisQueueService()
await queue.enqueue_task(task_id, task_data)
```

## Code Style Guidelines

### Frontend (TypeScript)
- **Hooks**: Prefix with `use` (e.g., `useSettings`, `useChat`)
- **Components**: PascalCase, functional components with TypeScript interfaces
- **Services**: Singleton classes with static methods where appropriate
- **Types**: Define in `types/` directory, use strict typing

### Backend (Python)
- **Routing**: Use FastAPI dependency injection
- **Async**: Always use `async def` for I/O operations
- **Logging**: Use structured logger from `core.logger`
- **Error Handling**: Use FastAPI HTTPException with proper status codes

### Import Order
**Frontend**:
1. React/third-party
2. Internal types
3. Internal services/hooks
4. Internal components

**Backend**:
1. Standard library
2. Third-party
3. Internal (relative imports)

## Database Migrations

```bash
cd backend
python run_migration.py  # Run pending migrations
python run_research_migration.py  # Research-specific migrations
```

## Common Development Patterns

### Adding a New API Endpoint

1. Create router in `backend/app/routers/`
2. Define Pydantic models for request/response
3. Implement service logic in `backend/app/services/`
4. Register router in `main.py`
5. Create frontend service method in `frontend/services/`
6. Use service method in component via custom hook

### Adding a New LLM Provider

1. Create provider class in `frontend/services/providers/`
2. Implement required interface methods
3. Register in `LLMFactory.ts`
4. Add provider-specific config in settings

### Debugging

**Frontend**:
- React DevTools
- Browser Network tab for API calls
- IndexedDB viewer for local storage

**Backend**:
- FastAPI auto-docs: `http://localhost:8000/docs`
- Structured logs in console
- Health check: `http://localhost:8000/health`

## MCP Collaboration Mode

This project uses multiple MCP servers for AI-assisted development. See:
- `.kiro/steering/claude-mcp-collaboration.md` - Workflow and collaboration rules
- `.kiro/steering/mcp-usage-guide.md` - MCP tool API reference

**MCP Responsibilities**:
- **Codex**: Backend development (Python/FastAPI)
- **Gemini**: Frontend development (TypeScript/React)
- **Desktop Commander**: File operations
- **Claude Code**: Code review and analysis

**Critical Constraints**:
- Codex/Gemini generate code only, never write files directly
- All file operations via Desktop Commander
- Code must be reviewed before implementation
- Use Sequential Thinking for complex analysis

## Project-Specific Notes

### Image Generation Pipeline
1. Frontend requests via `llmService`
2. Backend proxies to DashScope API
3. Upload to cloud storage (async via Redis queue)
4. Return local blob URL immediately for UI responsiveness
5. Background worker uploads and updates with cloud URL

### Authentication Flow
- JWT-based authentication
- Tokens stored in IndexedDB
- Backend validates via `auth_service.py`
- Protected routes use FastAPI dependencies

### Session Management
- Sessions stored in IndexedDB (frontend) and PostgreSQL/SQLite (backend)
- Real-time sync via WebSocket (optional)
- Lazy loading for performance

## Troubleshooting

**Port Conflicts**:
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Change backend port
npm run server -- --port 8001
# Update vite.config.ts proxy target accordingly
```

**Backend Import Errors**:
Always run backend as module from project root:
```bash
cd backend
python -m uvicorn app.main:app --reload
```

**Frontend Build Errors**:
```bash
# Clear Vite cache
rm -rf node_modules/.vite
npm run build
```
