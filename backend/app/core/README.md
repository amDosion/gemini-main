# Core 模块文档

`core` 目录包含应用程序的核心基础设施模块，提供配置管理、数据库连接、认证、加密、日志等基础功能。这些模块被整个应用程序广泛使用，是系统的基础层。

---

## 📁 目录结构

```
core/
├── __init__.py                 # 模块初始化
├── config.py                   # 应用配置管理
├── database.py                 # 数据库连接和会话管理
├── logger.py                   # 日志配置
├── encryption.py               # 数据加密/解密工具
├── jwt_utils.py                # JWT 令牌工具
├── jwt_secret_manager.py       # JWT 密钥安全管理
├── password.py                 # 密码哈希工具
├── dependencies.py             # FastAPI 依赖注入
├── user_context.py             # 用户上下文管理
├── user_scoped_query.py        # 用户范围查询包装器
├── credential_manager.py       # 统一凭证管理器
├── mode_method_mapper.py       # 模式到服务方法映射
└── celery_app.py               # Celery 异步任务配置
```

---

## 📋 模块说明

### 1. `config.py` - 应用配置管理

**功能**：集中管理应用程序的所有配置项，从环境变量读取配置。

**主要配置项**：
- 数据库配置（`DATABASE_URL`）
- Redis 配置（`REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`）
- GCP / Vertex AI 配置（`GCP_PROJECT_ID`, `GCP_LOCATION`）
- 认证配置（`ALLOW_REGISTRATION`, JWT 相关配置）
- 上传队列配置（`UPLOAD_QUEUE_WORKERS` 等）

**使用示例**：
```python
from ..core.config import settings

# 获取 Redis URL
redis_url = settings.redis_url

# 检查是否允许注册
if settings.allow_registration:
    # 允许注册逻辑
    pass
```

**环境变量**：
- `DATABASE_URL`: PostgreSQL 数据库连接字符串（必需）
- `REDIS_HOST`: Redis 主机地址（默认：`localhost`）
- `REDIS_PORT`: Redis 端口（默认：`6379`）
- `ENCRYPTION_KEY`: 数据加密密钥（必需，用于加密 API keys）

---

### 2. `database.py` - 数据库连接管理

**功能**：管理 PostgreSQL 数据库连接、会话和 ORM 基类。

**特性**：
- 自动连接池管理（`pool_pre_ping`, `pool_recycle`）
- FastAPI 依赖注入支持（`get_db()`）
- 仅支持 PostgreSQL 数据库

**使用示例**：
```python
from ..core.database import SessionLocal, Base, get_db

# 在 FastAPI 路由中使用
@router.get("/endpoint")
async def endpoint(db: Session = Depends(get_db)):
    # 使用数据库会话
    users = db.query(User).all()
    return users

# 直接使用（非 FastAPI 场景）
db = SessionLocal()
try:
    # 数据库操作
    pass
finally:
    db.close()
```

**环境变量**：
- `DATABASE_URL`: PostgreSQL 连接字符串（必需）
- `DB_POOL_SIZE`: 连接池大小（默认：`10`）
- `DB_MAX_OVERFLOW`: 最大溢出连接数（默认：`20`）
- `DB_POOL_RECYCLE`: 连接回收时间（秒，默认：`1800`）

---

### 3. `logger.py` - 日志配置

**功能**：配置应用程序的日志系统，提供结构化日志输出。

**特性**：
- 时间戳格式化
- 日志级别管理
- 实时刷新（避免日志缓冲）
- 统一的日志前缀（`LOG_PREFIXES`）

**使用示例**：
```python
from ..core.logger import setup_logger

# 设置日志记录器
logger = setup_logger("my_module", level=logging.INFO)

# 使用日志
logger.info("信息日志")
logger.error("错误日志")
logger.warning("警告日志")
```

**日志前缀**：
- `[OK]`: 成功操作
- `[ERROR]`: 错误信息
- `[WARN]`: 警告信息
- `[INFO]`: 一般信息
- `[SEARCH]`: 搜索相关
- `[BROWSER]`: 浏览器操作
- 等等...

---

### 4. `encryption.py` - 数据加密/解密工具

**功能**：提供敏感数据的加密和解密功能（如 API keys）。

**特性**：
- 使用 Fernet 对称加密（AES-128-CBC + HMAC-SHA256）
- 自动检测数据是否已加密
- 兼容未加密的历史数据
- 静默模式（`silent=True`）避免在兼容性检查时记录错误

**使用示例**：
```python
from ..core.encryption import encrypt_data, decrypt_data, is_encrypted

# 加密数据
encrypted = encrypt_data("my-api-key")

# 解密数据
decrypted = decrypt_data(encrypted, silent=True)

# 检查是否已加密
if is_encrypted(data):
    decrypted = decrypt_data(data)
```

**环境变量**：
- `ENCRYPTION_KEY`: Fernet 加密密钥（必需）

**安全提示**：
- 加密密钥必须安全存储，不要提交到版本控制
- 使用 `silent=True` 参数在兼容性检查时避免记录错误日志

---

### 5. `jwt_utils.py` - JWT 令牌工具

**功能**：处理 JWT 令牌的生成、验证和解码。

**特性**：
- 创建访问令牌（Access Token，15 分钟有效期）
- 创建刷新令牌（Refresh Token，7 天有效期）
- 令牌解码和验证
- CSRF 令牌生成
- 令牌过期检查

**使用示例**：
```python
from ..core.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token
)

# 创建令牌
access_token = create_access_token(user_id="user123")
refresh_token = create_refresh_token(user_id="user123")

# 解码令牌
payload = decode_token(access_token)
user_id = payload.sub

# 生成 CSRF 令牌
csrf_token = generate_csrf_token()
```

**环境变量**：
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: 访问令牌过期时间（分钟，默认：`15`）
- `JWT_REFRESH_TOKEN_EXPIRE_DAYS`: 刷新令牌过期时间（天，默认：`7`）

**注意**：JWT Secret Key 由 `jwt_secret_manager.py` 管理，不再从环境变量读取。

---

### 6. `jwt_secret_manager.py` - JWT 密钥安全管理

**功能**：安全地管理 JWT Secret Key，提供自动生成、加密存储和密钥轮换功能。

**特性**：
- 自动生成强随机密钥（64 字节）
- 加密存储到 `backend/credentials/.jwt_secret.enc`
- 支持密钥轮换（自动清理 refresh tokens）
- CLI 工具支持（`manage_jwt_secret.py`）

**使用示例**：
```python
from ..core.jwt_secret_manager import JWTSecretManager

# 获取或创建密钥（自动）
secret = JWTSecretManager.get_or_create_secret()

# 生成新密钥
new_secret = JWTSecretManager.generate_secret_key()

# 轮换密钥（会清理所有 refresh tokens）
rotated_secret = JWTSecretManager.rotate_secret(revoke_tokens=True)
```

**CLI 工具**：
```bash
# 查看密钥状态
python -m backend.scripts.manage_jwt_secret status

# 生成新密钥
python -m backend.scripts.manage_jwt_secret generate

# 轮换密钥
python -m backend.scripts.manage_jwt_secret rotate
```

**文件位置**：
- 加密密钥文件：`backend/credentials/.jwt_secret.enc`
- 未加密文件（向后兼容）：`backend/credentials/.jwt_secret`

**环境变量**：
- `ENCRYPTION_KEY`: 用于加密 JWT Secret Key 的主密钥（必需）

**相关文档**：
- [JWT密钥安全管理方案](../../../docs/JWT密钥安全管理方案.md)
- [JWT密钥管理工具使用说明](../../scripts/README_JWT密钥管理工具.md)

---

### 7. `password.py` - 密码哈希工具

**功能**：使用 bcrypt 进行密码哈希和验证。

**特性**：
- 使用 bcrypt 算法（通过 passlib）
- SHA256 预处理（避免 bcrypt 72 字节限制）
- 安全的密码验证

**使用示例**：
```python
from ..core.password import hash_password, verify_password

# 哈希密码
hashed = hash_password("user_password")

# 验证密码
is_valid = verify_password("user_password", hashed)
```

**安全特性**：
- 自动加盐（bcrypt 内置）
- 防止时序攻击
- 支持长密码（通过 SHA256 预处理）

---

### 8. `dependencies.py` - FastAPI 依赖注入

**功能**：提供 FastAPI 依赖注入函数，用于路由中获取服务实例和认证信息。

**主要依赖**：
- `require_current_user`: 要求用户已认证（返回 `user_id`）
- `get_current_user_optional`: 可选认证（返回 `user_id` 或 `None`）
- `get_cache`: 获取 Redis 缓存服务实例
- `get_research_cache`: 获取研究缓存实例
- `get_rate_limiter`: 获取速率限制器
- `get_validator`: 获取提示安全验证器

**使用示例**：
```python
from ..core.dependencies import require_current_user, get_cache

@router.get("/endpoint")
async def endpoint(
    user_id: str = Depends(require_current_user),
    cache = Depends(get_cache)
):
    # user_id 已自动注入
    # cache 是 CacheService 实例
    data = await cache.get("key")
    return {"user_id": user_id, "data": data}
```

**认证流程**：
1. `require_current_user` 从请求中提取 JWT token
2. 验证 token 有效性
3. 提取 `user_id` 并返回
4. 如果未认证，抛出 `401 Unauthorized`

---

### 9. `user_context.py` - 用户上下文管理

**功能**：从 HTTP 请求中提取和管理用户 ID，支持多种认证方式。

**特性**：
- 支持 Authorization header（Bearer token）
- 支持 Cookie 中的 access_token（向后兼容）
- 可选认证（返回 `None` 如果未认证）
- 强制认证（抛出异常如果未认证）

**使用示例**：
```python
from ..core.user_context import get_current_user_id, require_user_id

# 可选认证（不抛出异常）
user_id = get_current_user_id(request)
if user_id:
    # 已认证用户
    pass
else:
    # 未认证用户
    pass

# 强制认证（未认证时抛出异常）
user_id = require_user_id(request)
```

**Token 优先级**：
1. `Authorization: Bearer <token>` header（优先）
2. `access_token` cookie（向后兼容）

---

### 10. `user_scoped_query.py` - 用户范围查询包装器

**功能**：自动为数据库查询添加用户过滤，确保用户只能访问自己的数据。

**特性**：
- 自动添加 `user_id` 过滤条件
- 防止跨用户数据访问
- 支持多种查询方法（`get`, `list`, `create`, `update`, `delete`）
- 支持用户隔离的模型类型

**使用示例**：
```python
from ..core.user_scoped_query import UserScopedQuery
from ..models.db_models import ConfigProfile

# 创建用户范围查询
scoped = UserScopedQuery(db, user_id="user123")

# 查询用户自己的配置
profile = scoped.get(ConfigProfile, profile_id="profile123")

# 列出用户的所有配置
profiles = scoped.list(ConfigProfile)

# 创建新配置（自动设置 user_id）
new_profile = scoped.create(ConfigProfile, {
    "name": "My Profile",
    "provider_id": "google"
})
```

**支持的用户隔离模型**：
- `ChatSession`
- `MessageIndex`
- `ConfigProfile`
- `Persona`
- `StorageConfig`
- `MessageAttachment`
- `MessagesChat`, `MessagesImageGen`, `MessagesVideoGen`, `MessagesGeneric`

---

### 11. `credential_manager.py` - 统一凭证管理器

**功能**：提供统一的 API Key 和 Base URL 获取逻辑，所有路由和服务都应使用此模块。

**特性**：
- 统一的凭证获取接口
- 自动解密 API keys
- 兼容未加密的历史数据
- 支持请求参数覆盖（用于测试）

**使用示例**：
```python
from ..core.credential_manager import get_provider_credentials

# 获取 Provider 凭证
api_key, base_url = await get_provider_credentials(
    provider="google",
    db=db,
    user_id=user_id,
    request_api_key=None,  # 可选，用于测试覆盖
    request_base_url=None   # 可选，用于测试覆盖
)
```

**凭证获取优先级**：
1. 请求参数（`request_api_key`）- 用于测试/验证
2. 数据库配置（`ConfigProfile`）- 正常使用

---

### 12. `mode_method_mapper.py` - 模式到服务方法映射

**功能**：将前端应用模式（mode）映射到后端服务方法名。

**特性**：
- 统一的模式到方法映射
- 流式模式检测
- 图片编辑模式检测

**使用示例**：
```python
from ..core.mode_method_mapper import (
    get_service_method,
    is_streaming_mode,
    is_image_edit_mode
)

# 获取服务方法名
method = get_service_method("chat")  # 返回 "stream_chat"
method = get_service_method("image-gen")  # 返回 "generate_image"

# 检查是否为流式模式
if is_streaming_mode("chat"):
    # 使用流式处理
    pass

# 检查是否为图片编辑模式
if is_image_edit_mode("image-chat-edit"):
    # 使用图片编辑逻辑
    pass
```

**模式映射表**：
- `chat` → `stream_chat`
- `image-gen` → `generate_image`
- `image-chat-edit` → `edit_image`
- `image-mask-edit` → `edit_image`
- `image-inpainting` → `edit_image`
- `image-background-edit` → `edit_image`
- `image-recontext` → `edit_image`
- `image-outpainting` → `expand_image`
- `video-gen` → `generate_video`
- `audio-gen` → `generate_speech`
- `deep-research` → `deep_research`
- `multi-agent` → `multi_agent`
- 等等...

---

### 13. `celery_app.py` - Celery 异步任务配置

**功能**：配置 Celery 异步任务队列，用于处理后台任务（如文件上传）。

**特性**：
- Redis 作为消息代理和结果后端
- 自动发现任务模块
- 任务序列化配置

**使用示例**：
```python
from ..core.celery_app import celery_app

# 定义异步任务
@celery_app.task
def process_file(file_path: str):
    # 处理文件
    pass

# 调用异步任务
result = process_file.delay("path/to/file")
```

**环境变量**：
- `REDIS_HOST`: Redis 主机地址（默认：`localhost`）
- `REDIS_PORT`: Redis 端口（默认：`6379`）
- `REDIS_DB`: Redis 数据库编号（默认：`0`）
- `REDIS_PASSWORD`: Redis 密码（可选）

---

## 🔗 模块依赖关系

```
config.py
  ↓
database.py ──→ SessionLocal, Base, get_db()
  ↓
logger.py ──→ setup_logger()
  ↓
encryption.py ──→ encrypt_data(), decrypt_data()
  ↓
jwt_secret_manager.py ──→ get_jwt_secret_key()
  ↓
jwt_utils.py ──→ create_access_token(), decode_token()
  ↓
user_context.py ──→ get_current_user_id(), require_user_id()
  ↓
dependencies.py ──→ require_current_user(), get_cache()
  ↓
user_scoped_query.py ──→ UserScopedQuery
  ↓
credential_manager.py ──→ get_provider_credentials()
  ↓
mode_method_mapper.py ──→ get_service_method()
```

---

## 🚀 快速开始

### 1. 基本配置

确保 `.env` 文件包含必要的环境变量：

```bash
# 数据库配置（必需）
DATABASE_URL=postgresql+psycopg2://user:password@host:port/database

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

# 加密密钥（必需）
ENCRYPTION_KEY=your-encryption-key-here

# JWT 配置（可选，有默认值）
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 2. 在路由中使用

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..core.dependencies import require_current_user, get_cache
from ..core.database import get_db

router = APIRouter()

@router.get("/example")
async def example(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db),
    cache = Depends(get_cache)
):
    # user_id 已自动注入
    # db 是数据库会话
    # cache 是缓存服务
    return {"user_id": user_id}
```

### 3. 加密敏感数据

```python
from ..core.encryption import encrypt_data, decrypt_data

# 加密 API key
encrypted_key = encrypt_data("sk-1234567890")

# 解密 API key
decrypted_key = decrypt_data(encrypted_key, silent=True)
```

---

## 🔐 安全最佳实践

### 1. 环境变量管理

- ✅ 使用 `.env` 文件存储敏感配置
- ✅ 确保 `.env` 文件在 `.gitignore` 中
- ✅ 生产环境使用环境变量或密钥管理服务

### 2. 密码安全

- ✅ 使用 `hash_password()` 存储密码
- ✅ 使用 `verify_password()` 验证密码
- ✅ 不要存储明文密码

### 3. JWT 安全

- ✅ 使用 `jwt_secret_manager.py` 管理密钥
- ✅ 定期轮换 JWT 密钥（建议每 90 天）
- ✅ 使用强随机密钥

### 4. 数据加密

- ✅ 使用 `encrypt_data()` 加密敏感数据（API keys）
- ✅ 确保 `ENCRYPTION_KEY` 安全存储
- ✅ 不要硬编码加密密钥

### 5. 用户数据隔离

- ✅ 使用 `UserScopedQuery` 确保用户数据隔离
- ✅ 在查询中始终包含 `user_id` 过滤
- ✅ 验证用户权限

---

## 🐛 故障排除

### 问题 1: "DATABASE_URL 环境变量未设置"

**解决方案**：
1. 检查 `.env` 文件是否存在
2. 确认 `DATABASE_URL` 已设置
3. 验证连接字符串格式：`postgresql+psycopg2://user:password@host:port/database`

### 问题 2: "ENCRYPTION_KEY 未设置"

**解决方案**：
1. 生成加密密钥：
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
2. 添加到 `.env` 文件：
   ```bash
   ENCRYPTION_KEY=your-generated-key-here
   ```

### 问题 3: "JWT Secret Key 解密失败"

**解决方案**：
1. 检查 `ENCRYPTION_KEY` 是否正确
2. 验证 `backend/credentials/.jwt_secret.enc` 文件是否存在
3. 使用 CLI 工具检查密钥状态：
   ```bash
   python -m backend.scripts.manage_jwt_secret status
   ```

### 问题 4: "API key decryption failed"

**可能原因**：
- `ENCRYPTION_KEY` 未设置或已更改
- 数据库中存储的 API key 是用旧密钥加密的
- 历史数据未加密（这是正常的，会被兼容处理）

**解决方案**：
- 如果看到 WARNING 日志，检查 `ENCRYPTION_KEY` 配置
- 如果看到 DEBUG 日志，这是正常的兼容性处理，可以忽略
- 如果需要重新加密，更新 API key 时会自动加密

---

## 📚 相关文档

- [JWT密钥安全管理方案](../../../docs/JWT密钥安全管理方案.md)
- [JWT密钥管理工具使用说明](../../scripts/README_JWT密钥管理工具.md)
- [路由与逻辑分离架构设计文档](../../../docs/路由与逻辑分离架构设计文档.md)

---

## 🔄 更新日志

### 2026-01-15
- ✅ 改进 `encryption.py` 的错误处理，区分配置问题和兼容性问题
- ✅ 改进 `is_encrypted()` 函数，通过实际解密判断数据是否加密
- ✅ 添加 `silent` 参数到 `decrypt_data()`，避免在兼容性检查时记录错误
- ✅ 更新所有使用 `decrypt_data()` 的地方，使用 `silent=True`

### 2026-01-14
- ✅ 实现 JWT 密钥安全管理（`jwt_secret_manager.py`）
- ✅ 将 JWT 密钥存储位置改为 `backend/credentials/` 目录
- ✅ 实现密钥轮换时自动清理 refresh tokens
- ✅ 区分自动生成和手动轮换逻辑

---

## 📝 注意事项

1. **环境变量加载顺序**：`config.py`、`database.py`、`jwt_utils.py` 都会加载 `.env` 文件，确保在模块导入前环境变量已设置。

2. **循环依赖**：`jwt_utils.py` 使用延迟导入避免与 `jwt_secret_manager.py` 的循环依赖。

3. **数据库连接**：使用 `get_db()` 依赖注入时，会话会在请求结束后自动关闭。

4. **加密兼容性**：系统兼容未加密的历史数据，解密失败时会返回原始值。

5. **用户数据隔离**：始终使用 `UserScopedQuery` 或手动添加 `user_id` 过滤，确保用户数据隔离。

---

## 🤝 贡献指南

添加新的 core 模块时：
1. 在本文档中添加模块说明
2. 提供使用示例
3. 说明环境变量要求
4. 更新依赖关系图

修改现有模块时：
1. 更新本文档中的相关说明
2. 在更新日志中记录变更
3. 确保向后兼容性（如可能）
