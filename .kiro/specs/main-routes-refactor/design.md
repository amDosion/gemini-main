# Design Document

## Overview

本设计文档描述了将 `backend/app/main.py` 中的内联路由重构到 `backend/app/routers/` 目录的技术方案。重构后，`main.py` 将仅负责应用初始化、中间件配置和路由注册，所有业务逻辑将分散到对应的 Router 模块中。

## Architecture

### 重构前架构

```
main.py (800+ lines)
├── Imports & Module Loading
├── Lifespan Management
├── FastAPI App Creation
├── CORS Middleware
├── Pydantic Models (BrowseRequest, BrowseResponse, etc.)
├── Helper Functions (extract_title_from_html, html_to_markdown, take_screenshot_selenium)
├── Inline Endpoints (@app.get, @app.post)
│   ├── GET /
│   ├── GET /health
│   ├── GET /api/browse/progress/{operation_id}
│   ├── POST /api/browse
│   ├── POST /api/search
│   ├── GET /api/pdf/templates
│   ├── POST /api/pdf/extract
│   └── POST /api/embedding/* (5 endpoints)
└── Router Registration (partial)
```

### 重构后架构

```
main.py (~200 lines)
├── Imports & Module Loading
├── Lifespan Management
├── FastAPI App Creation
├── CORS Middleware
└── Router Registration (complete)

routers/
├── health.py      - GET /, GET /health
├── browse.py      - POST /api/browse, GET /api/browse/progress/{operation_id}, POST /api/search
├── pdf.py         - GET /api/pdf/templates, POST /api/pdf/extract
├── embedding.py   - POST /api/embedding/* (5 endpoints)
└── ... (existing routers unchanged)
```

## Components and Interfaces

### 1. main.py (Application Entry Point)

**职责**：
- FastAPI 应用实例化
- 生命周期管理（Worker Pool 启动/停止）
- CORS 中间件配置
- 路由注册
- 服务可用性标志设置

**接口**：
```python
# 无对外接口，仅作为应用入口
app = FastAPI(...)
```

### 2. routers/health.py

**职责**：
- 根路径健康检查
- 详细健康状态

**接口**：
```python
router = APIRouter(tags=["health"])

def set_availability(selenium: bool, pdf: bool, embedding: bool, worker_pool: bool) -> None
```

**端点**：
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | 根健康检查 |
| GET | `/health` | 详细健康状态 |

### 3. routers/browse.py

**职责**：
- 网页浏览与内容提取
- 实时进度追踪（SSE）
- 截图捕获
- 网页搜索

**接口**：
```python
router = APIRouter(prefix="/api", tags=["browse"])

def set_browser_service(
    browse_func: Callable,
    read_func: Callable,
    search_func: Callable,
    available: bool
) -> None
```

**端点**：
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/browse` | 浏览网页并返回 Markdown + 截图 |
| GET | `/api/browse/progress/{operation_id}` | SSE 进度流 |
| POST | `/api/search` | 网页搜索 |

**内部函数**：
- `extract_title_from_html(html: str) -> str`
- `html_to_markdown(html: str) -> str`
- `take_screenshot_selenium(url: str) -> Optional[str]`

### 4. routers/pdf.py

**职责**：
- PDF 模板管理
- PDF 结构化数据提取

**接口**：
```python
router = APIRouter(prefix="/api/pdf", tags=["pdf"])

def set_pdf_service(
    extract_func: Callable,
    templates_func: Callable,
    available: bool
) -> None
```

**端点**：
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/pdf/templates` | 获取可用模板 |
| POST | `/api/pdf/extract` | 提取 PDF 数据 |

### 5. routers/embedding.py

**职责**：
- 文档向量化存储
- 语义搜索
- 文档管理

**接口**：
```python
router = APIRouter(prefix="/api/embedding", tags=["embedding"])

def set_embedding_service(service: Any, available: bool) -> None
```

**端点**：
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/embedding/add-document` | 添加文档 |
| POST | `/api/embedding/search` | 语义搜索 |
| GET | `/api/embedding/documents/{user_id}` | 获取用户文档 |
| DELETE | `/api/embedding/document/{user_id}/{document_id}` | 删除文档 |
| DELETE | `/api/embedding/documents/{user_id}` | 清空用户文档 |

## Data Models

### BrowseRequest / BrowseResponse

```python
# 位置: routers/browse.py

class BrowseRequest(BaseModel):
    url: str
    operation_id: Optional[str] = None

class BrowseResponse(BaseModel):
    markdown: str
    title: str
    screenshot: Optional[str] = None
```

### AddDocumentRequest / SearchRequest

```python
# 位置: routers/embedding.py

class AddDocumentRequest(BaseModel):
    user_id: str
    filename: str
    content: str
    api_key: str
    chunk_size: int = 500
    chunk_overlap: int = 100

class SearchRequest(BaseModel):
    user_id: str
    query: str
    api_key: str
    top_k: int = 3
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Browse endpoint returns valid response structure

*For any* valid URL input to `POST /api/browse`, the response SHALL contain `markdown` (string), `title` (string), and optionally `screenshot` (string or null) fields.

**Validates: Requirements 2.1, 6.3**

### Property 2: Health endpoint reflects service availability

*For any* combination of service availability flags (selenium, pdf, embedding, worker_pool), the `GET /` and `GET /health` endpoints SHALL return responses that accurately reflect the current availability state.

**Validates: Requirements 5.1, 5.2, 5.3**

### Property 3: API backward compatibility - URL paths preserved

*For any* endpoint that existed before refactoring, the same URL path SHALL continue to be accessible after refactoring.

**Validates: Requirements 6.1**

### Property 4: API backward compatibility - request parameters preserved

*For any* endpoint that existed before refactoring, the same request parameters SHALL be accepted after refactoring.

**Validates: Requirements 6.2**

### Property 5: API backward compatibility - response structure preserved

*For any* endpoint that existed before refactoring, the response structure SHALL remain identical after refactoring.

**Validates: Requirements 6.3**

## Error Handling

### HTTP 错误码映射

| 场景 | 状态码 | 描述 |
|------|--------|------|
| 服务不可用 | 503 | Selenium/PDF/Embedding 服务未加载 |
| 请求超时 | 504 | 网页访问超时 |
| 无效请求 | 400 | 文件类型错误、空文件等 |
| 资源未找到 | 404 | 文档不存在 |
| 服务器错误 | 500 | 内部处理异常 |

### 错误响应格式

```python
{
    "detail": "Error message describing the issue"
}
```

## Testing Strategy

### 单元测试

1. **Router 模块测试**
   - 验证每个 Router 的端点注册正确
   - 验证 `set_*_service()` 函数正确设置服务引用

2. **辅助函数测试**
   - `extract_title_from_html()` - 各种 HTML 输入
   - `html_to_markdown()` - HTML 转换正确性

### 属性测试

使用 `pytest` + `hypothesis` 进行属性测试：

1. **Property 1**: Browse 响应结构验证
2. **Property 2**: Health 端点可用性反映
3. **Property 3-5**: API 向后兼容性

### 集成测试

1. **端到端测试**
   - 启动应用，验证所有端点可访问
   - 验证 SSE 进度流正常工作

2. **回归测试**
   - 对比重构前后的 API 响应
