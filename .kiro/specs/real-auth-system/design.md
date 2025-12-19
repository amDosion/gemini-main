# Design Document

## Overview

本设计文档描述了将现有 Mock 登录系统升级为真实认证系统的技术方案。

**核心设计决策**：
- **Token 存储**：httpOnly Cookie（防 XSS）
- **账号模式**：预置账号（不开放注册）
- **数据模式**：共享数据（单租户）
- **降级模式**：仅开发环境可用

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────────────┐                   │
│  │ LoginPage   │  │ ProtectedRoute          │                   │
│  │ Component   │  │ (Auth Guard)            │                   │
│  └──────┬──────┘  └───────────┬─────────────┘                   │
│         │                     │                                  │
│         └─────────┬───────────┘                                  │
│                   │                                              │
│            ┌──────▼──────┐                                       │
│            │  useAuth    │                                       │
│            │  Hook       │                                       │
│            └──────┬──────┘                                       │
│                   │                                              │
│            ┌──────▼──────┐                                       │
│            │ AuthService │  ← fetch with credentials: 'include'  │
│            └─────────────┘                                       │
└─────────────────────────────────────────────────────────────────┘
                           │
                           │ HTTPS (httpOnly Cookie)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Backend (FastAPI)                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Auth Router                           │    │
│  │  POST /api/auth/login     (set cookies)                  │    │
│  │  POST /api/auth/logout    (clear cookies)                │    │
│  │  POST /api/auth/refresh   (refresh access token)         │    │
│  │  GET  /api/auth/me        (get current user)             │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                    │
│  ┌──────────────────────────▼──────────────────────────────┐    │
│  │                    Auth Middleware                       │    │
│  │  - 验证 access_token cookie                              │    │
│  │  - 验证 CSRF token                                       │    │
│  │  - 注入 current_user 到 request.state                    │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                    │
│                      ┌──────▼──────┐                             │
│                      │ AuthService │                             │
│                      └──────┬──────┘                             │
│                             │                                    │
│              ┌──────────────┼──────────────┐                     │
│              │              │              │                     │
│       ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐               │
│       │ UserRepo    │ │ JWTUtils  │ │PasswordHash│              │
│       └─────────────┘ └───────────┘ └───────────┘               │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Database   │
                    │  (SQLite)   │
                    └─────────────┘
```

## Components and Interfaces

### Backend Components

#### 1. Auth Router (`backend/app/routers/auth.py`)

| Endpoint | Method | Description | Cookies Set |
|----------|--------|-------------|-------------|
| `/api/auth/config` | GET | 获取认证配置（注册开关等） | - |
| `/api/auth/register` | POST | 用户注册（受开关控制） | `access_token`, `refresh_token`, `csrf_token` |
| `/api/auth/login` | POST | 用户登录 | `access_token`, `refresh_token`, `csrf_token` |
| `/api/auth/logout` | POST | 用户登出 | Clear all |
| `/api/auth/refresh` | POST | 刷新令牌 | `access_token` |
| `/api/auth/me` | GET | 获取当前用户 | - |

#### 2. Auth Service (`backend/app/services/auth_service.py`)

```python
class AuthService:
    def is_registration_enabled(self) -> bool  # 读取 ALLOW_REGISTRATION 环境变量
    async def register(self, email: str, password: str, name: str) -> User
    async def login(self, email: str, password: str) -> User
    async def validate_token(self, token: str) -> TokenPayload
    async def get_user_by_id(self, user_id: str) -> User
    async def invalidate_refresh_token(self, token: str) -> None
```

#### 3. JWT Utils (`backend/app/core/jwt_utils.py`)

```python
class JWTUtils:
    def create_access_token(self, user_id: str) -> str   # 15 min
    def create_refresh_token(self, user_id: str) -> str  # 7 days
    def decode_token(self, token: str) -> TokenPayload
    def generate_csrf_token(self) -> str
```

#### 4. Auth Middleware (`backend/app/middleware/auth.py`)

```python
async def auth_middleware(request: Request, call_next):
    # 1. 从 cookie 读取 access_token
    # 2. 验证 token
    # 3. 对于 POST/PUT/DELETE 验证 CSRF token
    # 4. 注入 request.state.user
```

### Frontend Components

#### 1. AuthService (`frontend/services/auth.ts`)

```typescript
interface AuthConfig {
  allowRegistration: boolean;
}

class AuthService {
  async getConfig(): Promise<AuthConfig>  // 获取注册开关状态
  async register(email: string, password: string, name?: string): Promise<User>
  async login(email: string, password: string): Promise<User>
  async logout(): Promise<void>
  async getCurrentUser(): Promise<User | null>
  async refreshToken(): Promise<void>
}
```

#### 2. useAuth Hook (`frontend/hooks/useAuth.ts`)

```typescript
interface UseAuthReturn {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  allowRegistration: boolean;  // 是否显示注册按钮
  register: (email: string, password: string, name?: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}
```

## Data Models

### Database Schema

```sql
-- 用户表（预置账号）
CREATE TABLE users (
    id TEXT PRIMARY KEY,           -- gemini2026_xxxxxxxx
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Refresh Token 表（用于服务端失效）
CREATE TABLE refresh_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Pydantic Models

```python
class AuthConfigResponse(BaseModel):
    allow_registration: bool

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    confirm_password: str
    name: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    is_active: bool

class TokenPayload(BaseModel):
    sub: str  # user_id
    exp: int
    type: str  # 'access' | 'refresh'
```

### Environment Variables

```bash
# backend/.env
ALLOW_REGISTRATION=false  # 是否允许新用户注册，默认关闭
JWT_SECRET_KEY=your-secret-key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

## Cookie Configuration

```python
# Access Token Cookie
response.set_cookie(
    key="access_token",
    value=access_token,
    httponly=True,
    secure=True,           # HTTPS only
    samesite="strict",     # CSRF protection
    max_age=15 * 60,       # 15 minutes
    path="/"
)

# Refresh Token Cookie
response.set_cookie(
    key="refresh_token",
    value=refresh_token,
    httponly=True,
    secure=True,
    samesite="strict",
    max_age=7 * 24 * 60 * 60,  # 7 days
    path="/api/auth/refresh"    # 仅 refresh 端点可用
)

# CSRF Token Cookie (JS 可读)
response.set_cookie(
    key="csrf_token",
    value=csrf_token,
    httponly=False,        # JS 需要读取
    secure=True,
    samesite="strict",
    max_age=15 * 60
)
```

## CORS Configuration

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-domain.com",
        "http://localhost:5173",  # 开发环境
    ],
    allow_credentials=True,  # 允许 Cookie
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
```

## Security Considerations

### CSRF Protection

1. 登录时生成 `csrf_token` 并设置为非 httpOnly cookie
2. 前端在 POST/PUT/DELETE 请求时读取 cookie 并放入 `X-CSRF-Token` header
3. 后端中间件验证 header 与 cookie 中的 token 匹配

```typescript
// 前端发送请求
const csrfToken = document.cookie
  .split('; ')
  .find(row => row.startsWith('csrf_token='))
  ?.split('=')[1];

fetch('/api/some-endpoint', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken || ''
  }
});
```

### Token Refresh Flow

```
1. 前端请求 API
2. 后端返回 401 (access_token 过期)
3. 前端自动调用 /api/auth/refresh
4. 后端验证 refresh_token cookie
5. 后端返回新的 access_token cookie
6. 前端重试原请求
```

## CLI Script for Account Management

```bash
# 创建账号
python -m backend.scripts.create_user \
  --email admin@example.com \
  --password "secure_password" \
  --name "Admin User"

# 禁用账号
python -m backend.scripts.manage_user \
  --email admin@example.com \
  --disable

# 重置密码
python -m backend.scripts.manage_user \
  --email admin@example.com \
  --reset-password "new_password"
```

## Error Handling

| Error | HTTP Code | Response |
|-------|-----------|----------|
| Invalid credentials | 401 | `{"detail": "Invalid email or password"}` |
| Token expired | 401 | `{"detail": "Token expired"}` |
| CSRF validation failed | 403 | `{"detail": "CSRF validation failed"}` |
| Account disabled | 403 | `{"detail": "Account is disabled"}` |
| Rate limited | 429 | `{"detail": "Too many attempts", "retry_after": 60}` |

## Development Mode (Optional)

当 `VITE_DEV_MODE=true` 且后端不可用时，可启用本地 Mock 模式：

```typescript
// frontend/services/auth.ts
class AuthService {
  private async checkBackendAvailable(): Promise<boolean> {
    if (import.meta.env.VITE_DEV_MODE !== 'true') return true;
    try {
      await fetch('/health');
      return true;
    } catch {
      console.warn('⚠️ Backend unavailable - using mock auth (DEV ONLY)');
      return false;
    }
  }
}
```

**注意**：生产环境必须禁用此功能。
