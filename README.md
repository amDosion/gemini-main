# Gemini Flux Chat

A full-featured AI image generation, editing, and multi-modal chat platform powered by Google Gemini, Imagen, and other leading AI providers.

Built with **React 19 + TypeScript + Tailwind CSS** on the frontend and **FastAPI + SQLAlchemy + PostgreSQL** on the backend, the application provides a unified interface for text-to-image generation, conversational image editing, video/audio generation, deep research, multi-agent workflows, and more.

---

## ✨ Features

### 🎨 Image Generation
- **Imagen 4 / 4 Ultra / 4 Fast** — Google's latest text-to-image models (up to 4 images per batch)
- **Nano Banana 2** (`gemini-3.1-flash-image-preview`) — 14 aspect ratios, 512/1K/2K/4K resolution, up to 8 concurrent images
- **Nano Banana Pro** (`gemini-3-pro-image-preview`) — Professional asset production with Thinking mode
- **Nano Banana** (`gemini-2.5-flash-image`) — High-speed, low-latency generation
- **Tongyi Wanx** — Alibaba's image generation models
- Concurrent multi-image generation with `asyncio.gather` (parallel, not serial)
- AI prompt enhancement (two-stage: separate text model rewrites your prompt)
- Model-specific parameter panels (aspect ratios, resolutions auto-adapt per model)
- Partial success support — failed images don't break the batch
- Multi-API-Key rotation for rate limit avoidance

### ✏️ Image Editing (7 Modes)
- **Chat Edit** — Multi-turn conversational editing with Gemini native models (describe changes in natural language)
- **Mask Edit** — Draw masks for targeted inpainting via Vertex AI Imagen
- **Inpainting** — AI-powered content-aware fill
- **Background Edit** — Replace or modify backgrounds
- **Outpainting** — Extend images beyond borders (ratio/scale/offset/upscale modes)
- **Recontext** — Place products in new environments
- **Virtual Try-On** — Clothing try-on powered by Vertex AI
- Cross-mode image transfer (Gen → Edit with one click)
- Before/after image comparison slider
- Canvas zoom, pan, and fullscreen support

### 🎬 Video Generation
- **Veo 3.1** — Google's latest video generation model
- **Veo 3.1 Fast** — Optimized for speed
- Video extension (续写/延长) — extend existing videos
- Storyboard mode — multi-shot video with per-shot prompts
- Audio track generation with video
- Subtitle generation (多语言字幕)
- Multiple aspect ratios (16:9, 9:16, 1:1) and resolutions
- Video download and cloud storage upload

### 🔊 Audio Generation
- **Text-to-Speech** with multiple voice options (Puck, Charon, Kore, Fenrir, Aoede, Leda, Orus, Zephyr)
- Voice preview and selection
- Audio file download

### 🌐 Multi-Provider Support
- **Google Gemini** — Gemini 2.5 Flash/Pro, Gemini 3 Pro, Gemini 3.1 Flash
- **Google Imagen** — Imagen 3, Imagen 4, Imagen 4 Ultra
- **Google Nano Banana** — Nano Banana (2.5 Flash Image), Nano Banana Pro (3 Pro Image), Nano Banana 2 (3.1 Flash Image)
- **Google Veo** — Veo 3.1, Veo 3.1 Fast
- **OpenAI** — GPT-4o, GPT-4.1, o1, o3, DALL-E
- **Tongyi Qianwen** (通义千问) — Qwen series, Wanx image generation
- **Ollama** — Local model deployment with built-in model manager
- **OpenRouter** — Access 100+ models through unified API
- **Custom Providers** — Any OpenAI-compatible API endpoint

### 💬 AI Chat
- Streaming responses with Markdown rendering and code syntax highlighting
- Thinking mode (显示思考过程) for supported models
- Google Search grounding — real-time data in responses
- URL context — analyze web pages in conversation
- Code execution — run Python code in sandbox
- Browser integration — AI-controlled web browsing
- Persona / system prompt presets with 17+ categories
- Session management with history search and favorites
- Message editing and deletion

### 🔍 Deep Research
- AI-powered multi-step research with real-time SSE streaming
- Web browsing & scraping (Selenium-based)
- PDF document extraction and analysis
- Required-action cards for human-in-the-loop decisions

### 🤖 Multi-Agent Workflows
- Visual drag-and-drop workflow editor built on **ReactFlow / XYFlow**
- Component library with pre-built node types
- Agent registry — create, configure, and reuse agents
- **ADK (Agent Development Kit)** integration with Vertex AI Agent Engine
- Stage replay & undo/redo support
- Workflow templates — save, load, and share workflows
- Excel / data analysis workflow nodes (Pandas + Matplotlib)
- Execution log panel with detailed step tracking

### 🔌 MCP (Model Context Protocol)
- Connect external tools via MCP stdio and SSE transports
- Configurable command allowlist for security
- Tool call display in chat UI

### 📄 Document Processing
- PDF structured data extraction with customizable templates
- Table analysis and data extraction
- Batch job processing

### 🔊 Live API
- Real-time Gemini Live API integration

### ☁️ Cloud Storage (Multi-Provider)
- **Lsky Pro** — self-hosted image hosting
- **Aliyun OSS** (阿里云对象存储)
- **Tencent COS** (腾讯云对象存储)
- **Google Drive**
- **AWS S3** and S3-compatible storage
- **Local filesystem**
- Async upload queue with Redis-based worker pool (configurable concurrency, retries, rate limiting)

### 🔐 Authentication & Security
- JWT-based auth with access + refresh token rotation
- User registration control (`ALLOW_REGISTRATION`)
- Global auth boundary with per-route granularity
- MCP stdio command execution policy (allowlist / deny_all / allow_all)
- Workflow local file reference security controls

### 🎯 Performance & Architecture
- **CacheManager** — unified frontend cache with `BoundedRecordCache`
- Optimized Vite build with manual chunk splitting (React, Router, UI, Flow, Markdown, GenAI vendors)
- Gzip middleware on the backend
- Source map generation for production debugging
- HMR with WSS support behind reverse proxy

---

## 🏗️ Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 19, TypeScript, Tailwind CSS, Vite 7, ReactFlow / XYFlow |
| **Backend** | Python, FastAPI, Uvicorn, SQLAlchemy (async), Pydantic v2 |
| **Database** | PostgreSQL (via psycopg2), Redis (task queue + cache) |
| **AI Providers** | Google Gemini SDK, Vertex AI, OpenAI SDK, DashScope (Tongyi), Ollama |
| **Storage** | Aliyun OSS, Tencent COS, Google Drive, AWS S3, Lsky Pro, Local |
| **Testing** | Vitest + Testing Library (frontend), Pytest (backend), GitHub Actions CI |
| **Other** | MCP SDK, Selenium, Pillow, Pandas, Matplotlib, google-adk |

---

## 🚀 Quick Start

### Prerequisites

- **Node.js** >= 20
- **Python** >= 3.11
- **PostgreSQL** (running instance)
- **Redis** (for async upload queue and task workers)

### One-Command Setup

```bash
# Clone the repository
git clone git@github.com:amDosion/gemini-main.git
cd gemini-main

# Automated setup: creates venv, installs deps, starts both servers
./scripts/start_all.sh
```

The script will:
1. Create a Python virtual environment in `backend/.venv`
2. Install backend dependencies from `backend/requirements.txt`
3. Install frontend dependencies via `npm ci`
4. Start the backend (Uvicorn on port **21574**) and frontend (Vite dev server on port **21573**) concurrently

### Manual Setup

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Initialize database
python init_db.py

# Start backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 21574

# Frontend (in another terminal)
cd ..
npm install
npm run dev
```

### Environment Variables

Create a `.env` file in the project root (or `backend/.env`):

```env
# Required
DATABASE_URL=postgresql://user:pass@localhost:5432/gemini_flux_chat

# Redis (defaults shown)
REDIS_HOST=localhost
REDIS_PORT=6379

# GCP / Vertex AI (for Imagen, Virtual Try-On, ADK)
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Auth
ENVIRONMENT=production          # or "development"
ALLOW_REGISTRATION=false        # set to "true" to allow new user signups

# Upload queue tuning
UPLOAD_QUEUE_WORKERS=5
UPLOAD_QUEUE_MAX_RETRIES=3
```

See `backend/app/core/config.py` for the full list of configurable settings.

---

## 📁 Project Structure

```
gemini-main/
├── frontend/                   # React 19 + TypeScript SPA
│   ├── components/
│   │   ├── auth/               # Login, Register, ProtectedRoute
│   │   ├── chat/               # ChatInputArea, MessageItem, MarkdownRenderer
│   │   ├── common/             # Shared UI (Toast, Dialogs, Skeleton, etc.)
│   │   ├── layout/             # AppLayout, Header, SessionList, Navigation
│   │   ├── live/               # Gemini Live API view
│   │   ├── modals/             # Settings (Storage, MCP, Profiles, Ollama, etc.)
│   │   ├── multiagent/         # Workflow editor, nodes, panels, templates
│   │   └── research/           # Deep Research UI
│   ├── controls/modes/         # Mode-specific controls (Google, OpenAI, Tongyi)
│   ├── services/               # API client, auth, cache, LLM factory, storage
│   ├── hooks/                  # Custom React hooks
│   ├── contexts/               # React contexts
│   └── types/                  # TypeScript type definitions
├── backend/
│   ├── app/
│   │   ├── core/               # Config, database, dependencies, logging
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── routers/
│   │   │   ├── ai/             # Chat, image gen, research, workflows, embedding
│   │   │   ├── auth/           # JWT auth endpoints
│   │   │   ├── storage/        # Cloud storage management
│   │   │   ├── tools/          # PDF, browse, live API, batch jobs, table analysis
│   │   │   └── system/         # Health, admin
│   │   ├── services/
│   │   │   ├── agent/          # ADK, workflow engine, execution, export
│   │   │   ├── gemini/         # Gemini-specific services
│   │   │   ├── llm/            # Multi-provider LLM abstraction
│   │   │   ├── mcp/            # MCP client, manager, schema utils
│   │   │   ├── ollama/         # Ollama integration
│   │   │   ├── openai/         # OpenAI integration
│   │   │   ├── storage/        # Storage providers (OSS, COS, S3, GDrive, etc.)
│   │   │   └── tongyi/         # Tongyi Qianwen integration
│   │   ├── middleware/         # Auth middleware, CORS, Gzip
│   │   └── tasks/              # Background task definitions
│   └── tests/                  # Pytest test suite
├── scripts/
│   ├── start_all.sh / .py      # Cross-platform bootstrap & run
│   ├── ci/                     # CI contract-check scripts
│   └── e2e/                    # End-to-end test scripts
├── .github/workflows/          # GitHub Actions CI
├── vite.config.ts              # Vite build configuration
├── tsconfig.json               # TypeScript configuration
└── package.json                # Frontend dependencies & scripts
```

---

## 🧪 Testing

```bash
# Frontend unit tests (Vitest + jsdom)
npm test

# Backend unit tests (Pytest)
npm run test:backend

# Backend with coverage
npm run test:backend:cov

# E2E agent workflow test
npm run e2e:agent
```

CI runs automatically on push and pull requests via GitHub Actions (`.github/workflows/ci.yml`).

---

## 🛠️ Development

```bash
# Start dev servers with hot reload
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

The Vite dev server proxies `/api/*` requests to the FastAPI backend automatically. HMR is configured for WSS behind a reverse proxy (port 443).

---

## 📝 License

MIT

---

<p align="center">
  Built with ❤️ using Google Gemini, React, and FastAPI
</p>
