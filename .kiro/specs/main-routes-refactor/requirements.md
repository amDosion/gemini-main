# Requirements Document

## Introduction

本文档定义了将 `backend/app/main.py` 中的内联路由重构到 `backend/app/routers/` 目录的需求。当前 `main.py` 文件包含约 800 行代码，其中大量是路由定义和辅助函数，违反了 FastAPI 的最佳实践（路由应分离到独立模块）。

## Glossary

- **Router**：FastAPI 的 `APIRouter` 实例，用于组织相关路由
- **Endpoint**：单个 API 路由处理函数
- **SSE**：Server-Sent Events，服务器推送事件
- **Progress Tracker**：进度追踪服务，用于实时推送操作进度
- **Lifespan**：FastAPI 应用生命周期管理器

## Requirements

### Requirement 1

**User Story:** As a developer, I want `main.py` to only contain application initialization and router registration, so that the codebase follows FastAPI best practices and is easier to maintain.

#### Acceptance Criteria

1. WHEN the application starts THEN `main.py` SHALL only contain FastAPI app initialization, middleware configuration, lifespan management, and router registration
2. WHEN reviewing `main.py` THEN the file SHALL NOT contain any `@app.get()` or `@app.post()` decorated endpoint functions
3. WHEN reviewing `main.py` THEN the file SHALL NOT contain any Pydantic request/response models for specific endpoints

### Requirement 2

**User Story:** As a developer, I want browse-related routes to be in `routers/browse.py`, so that all webpage browsing functionality is organized in one place.

#### Acceptance Criteria

1. WHEN a client requests `POST /api/browse` THEN `routers/browse.py` SHALL handle the request with full functionality including progress tracking and screenshot capture
2. WHEN a client requests `GET /api/browse/progress/{operation_id}` THEN `routers/browse.py` SHALL provide SSE streaming for real-time progress updates
3. WHEN a client requests `POST /api/search` THEN `routers/browse.py` SHALL handle the web search request
4. WHEN the browse router is imported THEN it SHALL include all helper functions (`extract_title_from_html`, `html_to_markdown`, `take_screenshot_selenium`)

### Requirement 3

**User Story:** As a developer, I want PDF extraction routes to remain in `routers/pdf.py`, so that PDF functionality is properly isolated.

#### Acceptance Criteria

1. WHEN a client requests `GET /api/pdf/templates` THEN `routers/pdf.py` SHALL return available templates
2. WHEN a client requests `POST /api/pdf/extract` THEN `routers/pdf.py` SHALL process the PDF with the `model_id` parameter

### Requirement 4

**User Story:** As a developer, I want embedding/RAG routes to use `routers/embedding.py` exclusively, so that there is no duplicate code in `main.py`.

#### Acceptance Criteria

1. WHEN embedding routes are registered THEN `main.py` SHALL use `embedding.router` without any inline endpoint definitions
2. WHEN the embedding router is imported THEN it SHALL contain all request/response models (`AddDocumentRequest`, `SearchRequest`)

### Requirement 5

**User Story:** As a developer, I want health check routes to be in `routers/health.py`, so that application status endpoints are centralized.

#### Acceptance Criteria

1. WHEN a client requests `GET /` THEN `routers/health.py` SHALL return the root health check response with service availability flags
2. WHEN a client requests `GET /health` THEN `routers/health.py` SHALL return detailed health information
3. WHEN service availability changes THEN `health.py` SHALL reflect the current status via `set_availability()` function

### Requirement 6

**User Story:** As a developer, I want the refactored code to maintain backward compatibility, so that existing frontend clients continue to work without changes.

#### Acceptance Criteria

1. WHEN the refactoring is complete THEN all existing API endpoints SHALL respond with the same URL paths as before
2. WHEN the refactoring is complete THEN all existing API endpoints SHALL accept the same request parameters as before
3. WHEN the refactoring is complete THEN all existing API endpoints SHALL return the same response structures as before
