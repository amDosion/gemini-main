# JWT 认证系统完整使用说明

本文档详细说明 JWT（JSON Web Token）认证系统在项目中的完整使用流程、实现细节和最佳实践。

---

## 📋 目录

1. [JWT 系统概述](#jwt-系统概述)
2. [JWT 在项目中的用途](#jwt-在项目中的用途)
3. [JWT 密钥管理](#jwt-密钥管理)
4. [Token 生成与验证](#token-生成与验证)
5. [前端 Token 管理](#前端-token-管理)
6. [后端 Token 验证](#后端-token-验证)
7. [认证流程详解](#认证流程详解)
8. [Token 刷新机制](#token-刷新机制)
9. [安全机制](#安全机制)
10. [使用示例](#使用示例)
11. [故障排除](#故障排除)

---

## 🔐 JWT 系统概述

### 什么是 JWT？

JWT（JSON Web Token）是一种开放标准（RFC 7519），用于在各方之间安全地传输信息。在我们的项目中，JWT 的**核心作用**是：

**Token 处理**：
1. **生成 Token**：创建 Access Token 和 Refresh Token（使用 JWT Secret Key 签名）
2. **验证 Token**：验证 Token 的有效性和签名（使用 JWT Secret Key 验证）
3. **提取用户信息**：从 Token 中提取 `user_id` 等信息

**通过 Token 实现的功能**：
1. **用户认证**：验证用户身份（通过验证 Token）
2. **授权访问**：控制 API 访问权限（通过 Token 中的 `user_id`）
3. **会话管理**：维护用户登录状态（通过 Token 的有效期）

**重要说明**：
- ✅ JWT 仅用于 Token 的生成和验证
- ❌ JWT Secret Key 不用于数据加密（那是 `ENCRYPTION_KEY` 的工作）
- ❌ JWT Secret Key 不用于密码哈希（那是 `bcrypt` 的工作）

### JWT 结构

JWT 由三部分组成，用 `.` 分隔：

```
Header.Payload.Signature
```

**示例**：
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMTIzIiwidHlwZSI6ImFjY2VzcyIsImV4cCI6MTcwNTI4MDAwMH0.signature
```

---

## 🎯 JWT 在项目中的用途

### 1. **用户认证（Authentication）**

**用途**：验证用户身份，确认"你是谁"

**使用场景**：
- 用户登录后获取 JWT token
- 每次 API 请求携带 token 证明身份
- 后端验证 token 提取 `user_id`

**相关文件**：
- `backend/app/routers/auth/auth.py` - 登录/注册端点
- `backend/app/services/common/auth_service.py` - 认证业务逻辑
- `backend/app/core/jwt_utils.py` - Token 生成/验证

### 2. **API 访问授权（Authorization）**

**用途**：控制哪些用户可以访问哪些资源

**使用场景**：
- 保护需要认证的 API 端点
- 确保用户只能访问自己的数据
- 防止未授权访问

**相关文件**：
- `backend/app/core/dependencies.py` - `require_current_user` 依赖
- `backend/app/core/user_context.py` - 用户上下文提取
- `backend/app/core/user_scoped_query.py` - 用户数据隔离

### 3. **会话管理（Session Management）**

**用途**：维护用户登录状态，避免频繁登录

**使用场景**：
- Access Token：短期会话（15 分钟）
- Refresh Token：长期会话（7 天）
- 自动刷新过期 token

**相关文件**：
- `backend/app/routers/auth/auth.py` - `/refresh` 端点
- `backend/app/models/db_models.py` - `RefreshToken` 模型
- `frontend/services/auth.ts` - Token 刷新逻辑

### 4. **跨标签页同步（Multi-Tab Sync）**

**用途**：在多个浏览器标签页之间同步登录状态

**使用场景**：
- 在一个标签页登录，其他标签页自动登录
- 在一个标签页登出，其他标签页自动登出
- Token 刷新时，所有标签页同步更新

**相关文件**：
- `frontend/services/authSync.ts` - 跨标签页通信
- `frontend/services/auth.ts` - Token 同步监听

---

## 🔑 JWT 密钥管理

### JWT Secret Key 的唯一作用

**⚠️ 重要**：JWT Secret Key **仅用于**签名和验证 JWT Token：

1. **签名 Token**：`jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")`
2. **验证 Token**：`jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])`

**不用于**：
- ❌ 数据加密（使用 `ENCRYPTION_KEY`）
- ❌ API Key 加密（使用 `ENCRYPTION_KEY`）
- ❌ 密码哈希（使用 `bcrypt`）

### 密钥存储位置

JWT Secret Key 存储在 `backend/credentials/.jwt_secret.enc`（加密文件）

**加密方式**：使用 `ENCRYPTION_KEY` 加密存储（Fernet 对称加密）

### 密钥获取优先级

```
1. 加密文件 (.jwt_secret.enc) ← 推荐
   ↓ 不存在
2. 未加密文件 (.jwt_secret) ← 自动升级为加密
   ↓ 不存在
3. 环境变量 (JWT_SECRET_KEY) ← 向后兼容，不推荐
   ↓ 不存在
4. 默认值（仅开发环境，不安全）
```

### 密钥管理工具

使用 CLI 工具管理 JWT 密钥：

```bash
# 查看密钥状态
python -m backend.scripts.manage_jwt_secret status

# 生成新密钥（首次生成）
python -m backend.scripts.manage_jwt_secret generate

# 轮换密钥（安全轮换，会清理所有 refresh tokens）
python -m backend.scripts.manage_jwt_secret rotate

# 查看密钥（部分显示）
python -m backend.scripts.manage_jwt_secret show
```

**相关文件**：
- `backend/app/core/jwt_secret_manager.py` - 密钥管理器
- `backend/scripts/manage_jwt_secret.py` - CLI 工具

**相关文档**：
- [JWT密钥安全管理方案](../../../docs/JWT密钥安全管理方案.md)
- [JWT密钥管理工具使用说明](../../scripts/README_JWT密钥管理工具.md)

---

## 🎫 Token 生成与验证

### Token 类型

#### 1. Access Token（访问令牌）

**用途**：用于 API 请求认证

**特性**：
- 有效期：15 分钟（可配置）
- 存储位置：前端 `localStorage` + Cookie（向后兼容）
- 发送方式：`Authorization: Bearer <token>` header（优先）

**生成代码**：
```python
from ..core.jwt_utils import create_access_token

access_token = create_access_token(user_id="user123")
```

**Payload 结构**：
```json
{
  "sub": "user123",           // 用户 ID
  "type": "access",           // Token 类型
  "exp": 1705280000,          // 过期时间戳
  "iat": 1705279100           // 签发时间戳
}
```

#### 2. Refresh Token（刷新令牌）

**用途**：用于刷新过期的 Access Token

**特性**：
- 有效期：7 天（可配置）
- 存储位置：前端 `localStorage` + Cookie（向后兼容）
- 发送方式：`Authorization: Bearer <token>` header 或 Cookie

**生成代码**：
```python
from ..core.jwt_utils import create_refresh_token

refresh_token = create_refresh_token(user_id="user123")
```

**Payload 结构**：
```json
{
  "sub": "user123",           // 用户 ID
  "type": "refresh",          // Token 类型
  "exp": 1705884800,          // 过期时间戳（7 天后）
  "iat": 1705279100           // 签发时间戳
}
```

#### 3. CSRF Token（CSRF 保护令牌）

**用途**：防止跨站请求伪造（CSRF）攻击

**特性**：
- 有效期：与 Access Token 相同（15 分钟）
- 存储位置：Cookie（JS 可读）
- 验证方式：Cookie 值必须与 `X-CSRF-Token` header 匹配

**生成代码**：
```python
from ..core.jwt_utils import generate_csrf_token

csrf_token = generate_csrf_token()
```

### Token 验证

**验证代码**：
```python
from ..core.jwt_utils import decode_token, TokenPayload

try:
    payload: TokenPayload = decode_token(token)
    user_id = payload.sub
    token_type = payload.type
    expires_at = payload.exp
except JWTError:
    # Token 无效或已过期
    raise HTTPException(status_code=401, detail="Invalid token")
```

**相关文件**：
- `backend/app/core/jwt_utils.py` - Token 生成/验证工具

---

## 💻 前端 Token 管理

### Token 存储

**存储位置**：
- `localStorage.getItem('access_token')` - Access Token
- `localStorage.getItem('refresh_token')` - Refresh Token
- `document.cookie` - Cookie（向后兼容，用于 EventSource）

### Token 发送

**优先级**：
1. `Authorization: Bearer <token>` header（优先）
2. `access_token` cookie（向后兼容）

**发送代码**：
```typescript
// frontend/services/db.ts
const token = getAccessToken();
if (token) {
  headers['Authorization'] = `Bearer ${token}`;
}

// frontend/services/auth.ts
function getHeaders(includeJson = true): HeadersInit {
  const headers: HeadersInit = {};
  if (includeJson) {
    headers['Content-Type'] = 'application/json';
  }
  const token = getAccessToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}
```

### Token 刷新

**自动刷新逻辑**：
```typescript
// frontend/services/auth.ts
async refreshToken(): Promise<void> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error('No refresh token available');
  }

  const response = await fetch('/api/auth/refresh', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${refreshToken}`
    }
  });

  if (response.ok) {
    const data = await response.json();
    setAccessToken(data.access_token);
    setRefreshToken(data.refresh_token);
    // 广播到其他标签页
    broadcastTokenRefresh(data.access_token, data.refresh_token);
  }
}
```

**相关文件**：
- `frontend/services/auth.ts` - 认证服务
- `frontend/services/db.ts` - API 客户端
- `frontend/services/authSync.ts` - 跨标签页同步

---

## 🖥️ 后端 Token 验证

### Token 提取

**提取优先级**：
1. `Authorization: Bearer <token>` header（优先）
2. `access_token` cookie（向后兼容）

**提取代码**：
```python
# backend/app/core/user_context.py
def get_current_user_id(request: Request) -> Optional[str]:
    token = None
    
    # 1. 优先从 Authorization header 获取
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    
    # 2. 从 Cookie 获取（向后兼容）
    if not token:
        token = request.cookies.get("access_token")
    
    if not token:
        return None
    
    # 3. 解码和验证 token
    payload: TokenPayload = decode_token(token)
    if payload.type != "access":
        return None
    
    return payload.sub
```

### 依赖注入认证

**使用 FastAPI 依赖注入**：
```python
from ..core.dependencies import require_current_user

@router.get("/endpoint")
async def endpoint(user_id: str = Depends(require_current_user)):
    # user_id 已自动注入
    return {"user_id": user_id}
```

**相关文件**：
- `backend/app/core/user_context.py` - Token 提取
- `backend/app/core/dependencies.py` - 依赖注入函数

---

## 🔄 认证流程详解

### 1. 用户注册流程

```
用户填写注册表单
    ↓
前端: POST /api/auth/register
    ↓
后端: AuthService.register()
    ↓
后端: 验证邮箱唯一性
    ↓
后端: 哈希密码
    ↓
后端: 创建用户记录
    ↓
后端: 生成 Token 对
    ├─ Access Token (15 分钟)
    ├─ Refresh Token (7 天)
    └─ CSRF Token
    ↓
后端: 返回 Token 和用户信息
    ↓
前端: 存储 Token 到 localStorage
    ↓
前端: 设置 Cookie（向后兼容）
    ↓
前端: 跳转到主页面
```

**相关代码**：
- `backend/app/routers/auth/auth.py` - `@router.post("/register")`
- `backend/app/services/common/auth_service.py` - `AuthService.register()`

### 2. 用户登录流程

```
用户填写登录表单
    ↓
前端: POST /api/auth/login
    ↓
后端: AuthService.login()
    ↓
后端: 验证用户凭证
    ├─ 检查邮箱是否存在
    ├─ 验证密码
    ├─ 检查账户状态
    └─ 防暴力破解检查
    ↓
后端: 记录登录历史（IPLoginHistory）
    ↓
后端: 生成 Token 对
    ├─ Access Token (15 分钟)
    ├─ Refresh Token (7 天)
    └─ CSRF Token
    ↓
后端: 存储 Refresh Token 到数据库
    ↓
后端: 返回 Token 和用户信息
    ↓
前端: 存储 Token 到 localStorage
    ↓
前端: 设置 Cookie（向后兼容）
    ↓
前端: 启动自动刷新定时器（22 小时后）
    ↓
前端: 跳转到主页面
```

**相关代码**：
- `backend/app/routers/auth/auth.py` - `@router.post("/login")`
- `backend/app/services/common/auth_service.py` - `AuthService.login()`

### 3. API 请求认证流程

```
前端发起 API 请求
    ↓
前端: 从 localStorage 获取 access_token
    ↓
前端: 添加 Authorization header
    ├─ Authorization: Bearer <token>
    └─ credentials: 'include' (携带 Cookie)
    ↓
后端: 接收请求
    ↓
后端: require_current_user() 依赖
    ↓
后端: user_context.get_current_user_id()
    ├─ 提取 Authorization header
    ├─ 或提取 access_token cookie
    └─ 解码和验证 token
    ↓
后端: 提取 user_id (payload.sub)
    ↓
后端: 执行业务逻辑
    ↓
后端: 返回响应
```

**相关代码**：
- `backend/app/core/dependencies.py` - `require_current_user`
- `backend/app/core/user_context.py` - `get_current_user_id`

### 4. Token 刷新流程

```
Access Token 过期（或即将过期）
    ↓
前端: 检测 token 过期
    ├─ isTokenExpired(token)
    └─ 提前 5 分钟判断为过期
    ↓
前端: POST /api/auth/refresh
    ├─ Authorization: Bearer <refresh_token>
    └─ 或 Cookie: refresh_token
    ↓
后端: AuthService.refresh_tokens()
    ↓
后端: 验证 Refresh Token
    ├─ 解码 token
    ├─ 检查是否过期
    ├─ 检查是否已撤销
    └─ 验证数据库中的记录
    ↓
后端: 撤销旧 Refresh Token
    ↓
后端: 生成新 Token 对
    ├─ 新 Access Token
    ├─ 新 Refresh Token
    └─ 新 CSRF Token
    ↓
后端: 存储新 Refresh Token 到数据库
    ↓
后端: 返回新 Token 对
    ↓
前端: 更新 localStorage
    ↓
前端: 广播到其他标签页
    ↓
前端: 重试原始请求
```

**相关代码**：
- `backend/app/routers/auth/auth.py` - `@router.post("/refresh")`
- `backend/app/services/common/auth_service.py` - `AuthService.refresh_tokens()`
- `frontend/services/auth.ts` - `refreshToken()`

### 5. 用户登出流程

```
用户点击登出
    ↓
前端: POST /api/auth/logout
    ├─ Authorization: Bearer <access_token>
    └─ 或 Cookie: access_token
    ↓
后端: AuthService.logout()
    ↓
后端: 撤销 Refresh Token
    ├─ 设置 revoked_at
    └─ 记录登出历史（IPLoginHistory）
    ↓
后端: 返回成功响应
    ↓
前端: 清除 localStorage
    ├─ removeAccessToken()
    └─ removeRefreshToken()
    ↓
前端: 清除 Cookie
    ↓
前端: 广播登出事件到其他标签页
    ↓
前端: 跳转到登录页
```

**相关代码**：
- `backend/app/routers/auth/auth.py` - `@router.post("/logout")`
- `backend/app/services/common/auth_service.py` - `AuthService.logout()`
- `frontend/services/auth.ts` - `logout()`

---

## 🔄 Token 刷新机制

### 自动刷新策略

**触发条件**：
1. Access Token 过期（或提前 5 分钟）
2. API 请求返回 401 Unauthorized
3. 定时刷新（22 小时后）

**刷新逻辑**：
```typescript
// frontend/services/auth.ts
async refreshToken(): Promise<void> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error('No refresh token available');
  }

  const response = await fetch('/api/auth/refresh', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${refreshToken}`
    },
    credentials: 'include'
  });

  if (response.ok) {
    const data = await response.json();
    setAccessToken(data.access_token);
    setRefreshToken(data.refresh_token);
    broadcastTokenRefresh(data.access_token, data.refresh_token);
  } else {
    // Refresh Token 也过期，需要重新登录
    removeAccessToken();
    removeRefreshToken();
    window.location.href = '/login';
  }
}
```

### Refresh Token 管理

**数据库存储**：
- 表：`refresh_tokens`
- 字段：
  - `user_id`: 用户 ID
  - `token_hash`: Token 哈希值（SHA256）
  - `expires_at`: 过期时间
  - `revoked_at`: 撤销时间（如果已撤销）

**安全特性**：
- Token 以哈希形式存储（不存储明文）
- 支持撤销（设置 `revoked_at`）
- 自动清理过期/已撤销的记录（超过 7 天）

**相关代码**：
- `backend/app/models/db_models.py` - `RefreshToken` 模型
- `backend/app/services/common/auth_service.py` - `_create_tokens()`, `refresh_tokens()`

---

## 🛡️ 安全机制

### 1. Token 安全

**Access Token**：
- 短期有效（15 分钟）
- 存储在 `localStorage`（前端可访问）
- 通过 HTTPS 传输（生产环境）

**Refresh Token**：
- 长期有效（7 天）
- 存储在 `localStorage` + 数据库
- 支持撤销机制
- 自动清理过期记录

### 2. CSRF 保护

**机制**：
- 生成 CSRF Token
- 存储在 Cookie（JS 可读）
- 状态变更请求（POST/PUT/DELETE）必须验证
- Cookie 值必须与 `X-CSRF-Token` header 匹配

**相关代码**：
- `backend/app/middleware/auth.py` - CSRF 验证
- `backend/app/core/jwt_utils.py` - `generate_csrf_token()`

### 3. 防暴力破解

**机制**：
- 记录登录尝试（`LoginAttempt` 表）
- IP 地址限制（`IPBlocklist` 表）
- 账户锁定（超过失败次数）
- 登录历史记录（`IPLoginHistory` 表）

**相关代码**：
- `backend/app/services/common/auth_service.py` - `_check_login_attempts()`, `_check_ip_blocked()`
- `backend/app/models/db_models.py` - `LoginAttempt`, `IPBlocklist`, `IPLoginHistory`

### 4. 密钥安全

**JWT Secret Key 安全管理**：
- JWT Secret Key 加密存储（使用 `ENCRYPTION_KEY` 加密）
- 自动生成强随机密钥（64 字节）
- 支持密钥轮换（不影响现有 Token，自然失效）
- 密钥文件不在版本控制中

**为什么需要安全管理**：
- 如果 JWT Secret Key 泄露，攻击者可以伪造 Token
- 但无法解密数据（数据加密使用 `ENCRYPTION_KEY`）
- 重要性：高，但不是最高（`ENCRYPTION_KEY` 更重要）

**相关代码**：
- `backend/app/core/jwt_secret_manager.py` - JWT Secret Key 管理器
- `backend/app/core/encryption_key_manager.py` - ENCRYPTION_KEY 管理器（用于加密 JWT Secret Key）

---

## 📝 使用示例

### 后端：创建 Token

```python
from ..core.jwt_utils import create_access_token, create_refresh_token

# 创建 Access Token
access_token = create_access_token(user_id="user123")

# 创建 Refresh Token
refresh_token = create_refresh_token(user_id="user123")
```

### 后端：验证 Token

```python
from ..core.dependencies import require_current_user

@router.get("/protected")
async def protected_endpoint(
    user_id: str = Depends(require_current_user)
):
    # user_id 已自动注入
    return {"message": f"Hello, user {user_id}"}
```

### 后端：可选认证

```python
from ..core.dependencies import get_current_user_optional

@router.get("/public")
async def public_endpoint(
    user_id: Optional[str] = Depends(get_current_user_optional)
):
    if user_id:
        return {"message": f"Hello, authenticated user {user_id}"}
    else:
        return {"message": "Hello, anonymous user"}
```

### 前端：发送 API 请求

```typescript
// 自动添加 Authorization header
const token = getAccessToken();
const response = await fetch('/api/sessions', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  credentials: 'include'
});
```

### 前端：Token 刷新

```typescript
// 检测 token 过期
if (isTokenExpired(accessToken)) {
  await authService.refreshToken();
  // 重试原始请求
}
```

---

## 🐛 故障排除

### 问题 1: "Invalid or expired token"

**可能原因**：
- Token 已过期
- Token 格式错误
- JWT Secret Key 不匹配

**解决方案**：
1. 检查 token 是否过期：`isTokenExpired(token)`
2. 尝试刷新 token：`authService.refreshToken()`
3. 如果刷新失败，重新登录

### 问题 2: "Not authenticated"

**可能原因**：
- 未发送 token
- Token 提取失败
- Token 验证失败

**解决方案**：
1. 检查 `Authorization` header 是否正确设置
2. 检查 `localStorage` 中是否有 `access_token`
3. 检查 token 格式：`Bearer <token>`

### 问题 3: "CSRF validation failed"

**可能原因**：
- CSRF Token 不匹配
- Cookie 和 Header 中的 CSRF Token 不一致

**解决方案**：
1. 确保 `X-CSRF-Token` header 与 Cookie 中的 `csrf_token` 匹配
2. 检查 Cookie 是否正确设置

### 问题 4: "Refresh token expired"

**可能原因**：
- Refresh Token 已过期（7 天）
- Refresh Token 已被撤销

**解决方案**：
1. 清除所有 token
2. 重新登录获取新 token

---

## 📊 JWT 使用位置总结

### JWT Secret Key 的使用位置（仅用于 Token 签名/验证）

| 文件 | 用途 | 函数/类 | JWT Secret Key 使用 |
|------|------|---------|---------------------|
| `jwt_utils.py` | Token 生成/验证 | `create_access_token()`, `create_refresh_token()`, `decode_token()` | ✅ `jwt.encode()` 和 `jwt.decode()` |
| `jwt_secret_manager.py` | 密钥管理 | `JWTSecretManager`, `get_jwt_secret_key()` | ✅ 提供密钥给 `jwt_utils.py` |
| `user_context.py` | Token 提取 | `get_current_user_id()`, `require_user_id()` | ✅ 调用 `decode_token()` |
| `dependencies.py` | 依赖注入 | `require_current_user()`, `get_current_user_optional()` | ✅ 调用 `user_context.py` |
| `auth_service.py` | 认证业务逻辑 | `login()`, `register()`, `refresh_tokens()`, `logout()` | ✅ 调用 `create_access_token()`, `create_refresh_token()` |
| `auth.py` (路由) | 认证端点 | `/login`, `/register`, `/refresh`, `/logout` | ✅ 调用 `auth_service.py` |
| `middleware/auth.py` | 认证中间件 | `AuthMiddleware` | ✅ 调用 `decode_token()` |

**关键点**：
- JWT Secret Key **仅用于** `jwt.encode()` 和 `jwt.decode()`
- 所有其他功能（数据加密、API Key 加密等）使用 `ENCRYPTION_KEY`

### 前端使用位置

| 文件 | 用途 | 函数/类 |
|------|------|---------|
| `auth.ts` | 认证服务 | `AuthService`, `getAccessToken()`, `refreshToken()` |
| `db.ts` | API 客户端 | `getAccessToken()`, 自动添加 Authorization header |
| `authSync.ts` | 跨标签页同步 | `broadcastTokenRefresh()`, `listenTokenRefresh()` |
| `useAuth.ts` | React Hook | `useAuth()`, 自动 token 刷新 |

---

## 🔗 相关文档

- [Core 模块文档](./README.md) - Core 目录完整说明
- [JWT实际作用与密钥管理分析](../../../docs/JWT实际作用与密钥管理分析.md) - JWT 实际作用分析
- [JWT密钥安全管理方案](../../../docs/JWT密钥安全管理方案.md) - 密钥管理详细方案
- [JWT密钥管理工具使用说明](../../scripts/README_JWT密钥管理工具.md) - CLI 工具使用指南
- [统一后端认证处理方案](../../../docs/统一后端认证处理方案.md) - 认证架构设计
- [前端 Token 传递流程文档](../../../docs/AUTHENTICATION_TOKEN_FLOW.md) - 前端 Token 管理

---

## 📝 更新日志

### 2026-01-15
- ✅ 明确 JWT 的实际作用（Token 处理）
- ✅ 明确 JWT Secret Key 的唯一作用（签名/验证 Token）
- ✅ 区分 JWT Secret Key 和 ENCRYPTION_KEY 的不同作用
- ✅ 改进加密/解密错误处理
- ✅ 改进 `is_encrypted()` 函数，通过实际解密判断
- ✅ 添加 `silent` 参数到 `decrypt_data()`，避免兼容性检查时记录错误

### 2026-01-14
- ✅ 实现 JWT 密钥安全管理（`jwt_secret_manager.py`）
- ✅ 将 JWT 密钥存储位置改为 `backend/credentials/` 目录
- ✅ 实现密钥轮换时自动清理 refresh tokens
- ✅ 区分自动生成和手动轮换逻辑

---

## ⚠️ 重要提醒

1. **生产环境**：必须设置 `ENCRYPTION_KEY` 环境变量
2. **密钥安全**：JWT Secret Key 必须安全存储，不要提交到版本控制
3. **Token 过期**：Access Token 短期有效，Refresh Token 长期有效
4. **跨标签页同步**：使用 BroadcastChannel API 同步登录状态
5. **CSRF 保护**：状态变更请求必须验证 CSRF Token

---

## 💡 最佳实践

### ✅ 推荐做法

1. **使用 Authorization header**：优先使用 `Authorization: Bearer <token>` header
2. **自动刷新 Token**：检测 token 过期时自动刷新
3. **错误处理**：401 错误时尝试刷新 token，刷新失败则重新登录
4. **跨标签页同步**：使用 BroadcastChannel 同步登录状态
5. **安全存储**：Token 存储在 `localStorage`，不要存储在 `sessionStorage`

### ❌ 避免的做法

1. **不要硬编码 Token**：不要在代码中硬编码 token
2. **不要共享 Token**：不同用户使用不同的 token
3. **不要忽略过期**：及时处理 token 过期情况
4. **不要跳过 CSRF 验证**：状态变更请求必须验证 CSRF Token
5. **不要使用不安全的传输**：生产环境必须使用 HTTPS
