# 完整附件处理与存储配置架构 - 设计文档

> **项目名称**: 完整附件处理与存储配置架构优化
> **版本**: v1.0
> **创建日期**: 2026-01-19
> **设计负责人**: 架构团队

---

## 目录

1. [系统架构设计](#1-系统架构设计)
2. [后端统一工具架构](#2-后端统一工具架构)
3. [前端图片显示与跨模式流程](#3-前端图片显示与跨模式流程)
4. [存储配置管理架构](#4-存储配置管理架构)
5. [加密文件合并设计](#5-加密文件合并设计)
6. [数据流设计](#6-数据流设计)
7. [API设计](#7-api设计)
8. [关键技术方案](#8-关键技术方案)
9. [安全性设计](#9-安全性设计)
10. [监控和日志设计](#10-监控和日志设计)

---

## 1. 系统架构设计

### 1.1 整体架构原则

#### 原则 1：统一配置管理

**目标**: 所有存储配置操作统一使用 `StorageManager` 或 `decrypt_config()`

**实施**:
1. **优先使用 `StorageManager`**: 所有需要存储配置的操作都应该通过 `StorageManager`
2. **直接查询时使用 `decrypt_config()`**: 如果必须直接查询数据库，应该使用 `core.encryption.decrypt_config()` 解密
3. **禁止直接使用 `config.config`**: 禁止在未解密的情况下使用 `config.config`

#### 原则 2：附件显示与上传状态解耦

**目标**: 附件显示逻辑只依赖URL有效性，不依赖上传状态

**实施**:
1. **URL 直接使用传入值**: `newAttachment.url = url`（不检查上传状态）
2. **显示逻辑只检查URL有效性**: `att.url && att.url.length > 0`
3. **不检查上传状态**: 不在显示逻辑中检查 `uploadStatus`

#### 原则 3：统一认证处理

**目标**: 所有需要认证的路由都使用统一的认证依赖

**实施**:
1. **使用 `Depends(require_current_user)`**: 所有需要认证的路由都应该使用这个依赖
2. **统一请求头处理**: 使用 `user_context.get_current_user_id()` 或 `require_user_id()`
3. **避免重复实现**: 不在每个路由中重复实现认证逻辑

#### 原则 4：统一加密管理

**目标**: 所有加密功能统一在 `core/encryption.py` 中

**实施**:
1. **合并加密文件**: 将 `utils/encryption.py` 合并到 `core/encryption.py`
2. **统一导入路径**: 所有加密相关功能都从 `core.encryption` 导入
3. **统一实现**: 统一 `is_encrypted()` 实现，使用更准确的实现

---

### 1.2 架构分层

```
┌─────────────────────────────────────────────────┐
│                  前端层                          │
├─────────────────────────────────────────────────┤
│  ImageGenView.tsx                                │
│  ImageEditView.tsx                               │
│  InputArea.tsx                                   │
│  useImageHandlers.ts                             │
│  attachmentUtils.ts (getUrlType)                 │
└──────────────┬───────────────────────────────────┘
               │ HTTP API
               ↓
┌─────────────────────────────────────────────────┐
│                  API 层                          │
├─────────────────────────────────────────────────┤
│  modes.py (统一模式处理)                         │
│  storage.py (存储配置管理)                       │
│  attachments.py (附件端点)                       │
└──────────────┬───────────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────────┐
│                服务层                            │
├─────────────────────────────────────────────────┤
│  StorageManager (统一配置管理)                   │
│  AttachmentService (统一附件处理)               │
│  UploadWorkerPool (异步上传)                     │
└──────────────┬───────────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────────┐
│                核心层                            │
├─────────────────────────────────────────────────┤
│  core/encryption.py (统一加密管理)               │
│  core/user_context.py (用户上下文)               │
│  core/dependencies.py (依赖注入)                 │
└─────────────────────────────────────────────────┘
```

---

## 2. 后端统一工具架构

### 2.1 统一的加密/解密工具

#### 2.1.1 加密密钥管理 (`backend/app/core/encryption.py`)

**功能**: 提供统一的加密密钥管理（ENCRYPTION_KEY）和所有加密/解密功能

**合并后的结构**:
```python
# ==================== ENCRYPTION_KEY 管理 ====================
class EncryptionKeyManager:
    """ENCRYPTION_KEY 管理器"""
    @staticmethod
    def generate_key() -> str: ...
    @staticmethod
    def save_key(key: str) -> None: ...
    @staticmethod
    def load_key_from_file() -> Optional[str]: ...
    @staticmethod
    def get_or_create_key() -> str: ...

def get_encryption_key() -> str:
    """获取 ENCRYPTION_KEY（供其他模块使用）"""
    ...

# ==================== 单个字符串加密/解密 ====================
def encrypt_data(data: str) -> str:
    """加密单个字符串（如 API keys）"""
    ...

def decrypt_data(encrypted_data: str, silent: bool = False) -> str:
    """解密单个字符串"""
    ...

def is_encrypted(data: str) -> bool:
    """
    统一的加密检查函数（通过实际解密尝试）
    
    通过尝试实际解密来判断数据是否加密，而不是仅检查 base64 格式。
    这样可以避免将明文 API key（可能是 base64 格式）误判为加密数据。
    """
    ...

# ==================== 配置字典加密/解密 ====================
SENSITIVE_FIELDS: Set[str] = {
    "token",
    "accessKeyId",
    "accessKeySecret",
    "secretId",
    "secretKey",
    "clientSecret",
    "refreshToken",
    "apiKey",
    "password",
}

def encrypt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    加密配置字典中的敏感字段（递归处理嵌套字典）
    
    Only encrypts fields listed in SENSITIVE_FIELDS. Other fields are left unchanged.
    Handles nested dictionaries recursively.
    """
    ...

def decrypt_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    解密配置字典中的敏感字段（递归处理嵌套字典）
    
    Only decrypts fields listed in SENSITIVE_FIELDS. Other fields are left unchanged.
    Handles nested dictionaries recursively.
    """
    ...

def mask_sensitive_fields(config: Dict[str, Any], mask: str = "***") -> Dict[str, Any]:
    """
    掩码敏感字段，用于安全日志记录
    
    Replaces sensitive field values with a mask string. Handles nested dictionaries.
    """
    ...
```

**关键设计决策**:
- ✅ 统一 `is_encrypted()` 实现：使用 `core/encryption.py` 中的实现（通过实际解密尝试），更准确
- ✅ 移除 `_get_encryption_key()` 函数：直接使用 `get_encryption_key()` 和 `_get_encryption_key_bytes()`
- ✅ 统一导入路径：所有加密功能从 `core.encryption` 导入

---

### 2.2 统一的请求头处理

#### 2.2.1 用户上下文管理 (`backend/app/core/user_context.py`)

**功能**: 从 HTTP 请求中提取和管理用户 ID

**核心函数**:
- `get_current_user_id(request: Request) -> Optional[str]`: 可选认证
- `require_user_id(request: Request) -> str`: 强制认证

**Token 处理**:
- 使用 `jwt_utils.decode_token()` 解码 JWT token
- 验证 token 类型（必须是 `access` 类型）
- 提取 `user_id`（`payload.sub`）

#### 2.2.2 依赖注入 (`backend/app/core/dependencies.py`)

**功能**: 提供 FastAPI 依赖注入函数

**核心依赖**:
- `require_current_user(request: Request) -> str`: 统一认证依赖（110+ 个路由使用）
- `get_current_user_optional(request: Request) -> Optional[str]`: 可选认证依赖

**使用示例**:
```python
from ...core.dependencies import require_current_user

@router.post("/endpoint")
async def endpoint(
    user_id: str = Depends(require_current_user),  # ✅ 自动注入 user_id
    ...
):
    pass
```

---

## 3. 前端图片显示与跨模式流程

### 3.1 AI生成图片后的前端显示流程

#### 3.1.1 后端返回结果格式

**位置**: `backend/app/services/common/attachment_service.py` → `process_ai_result()`

后端返回的图片结果包含：
```python
{
    "url": "/api/temp-images/{attachment_id}",  # 临时代理URL（用于前端显示）
    "mimeType": "image/png",
    "filename": "generated-xxx.png",
    "attachmentId": "uuid",
    "uploadStatus": "pending",
    "taskId": "upload_task_uuid"
}
```

**关键点**:
- `url` 字段是 `/api/temp-images/{attachment_id}` 格式（不是 Base64 或 HTTP URL）
- 这是后端创建的**临时代理端点**，用于前端立即显示
- 后端同时创建了上传任务（Worker Pool），异步上传到云存储

#### 3.1.2 数据库存储格式

**位置**: `backend/app/models/db_models.py` → `MessageAttachment` 模型

**数据库字段**:
```python
class MessageAttachment(Base):
    id = Column(String(36), primary_key=True)
    message_id = Column(String(36), primary_key=True)
    temp_url = Column(Text, nullable=True)  # ✅ 存储完整的 Base64 Data URL
    url = Column(Text, nullable=True)       # 云存储URL（上传完成后更新）
    upload_status = Column(String(20))     # pending/uploading/completed/failed
    # ...
```

**存储内容**:
- `temp_url` 字段存储的是**完整的 Base64 Data URL**（格式：`data:image/png;base64,iVBORw0KGgo...`）
- **不是**只存储 Base64 字符串，而是完整的 Data URL 格式

#### 3.1.3 后端临时端点响应

**位置**: `backend/app/routers/core/attachments.py` → `/api/temp-images/{attachment_id}`

**处理流程**:
1. 从数据库查询附件
2. 读取 `temp_url`（完整的 Base64 Data URL）
3. 解析 Base64 Data URL，提取 MIME 类型和 Base64 字符串
4. 解码为图片字节流
5. 返回图片字节流给前端（HTTP 响应）

**关键点**:
- 后端从数据库 `temp_url` 字段读取**完整的 Base64 Data URL**
- 使用 `parse_data_url()` 解析 Data URL
- 使用 `base64.b64decode()` 解码为图片字节流
- 直接返回图片字节流，前端可以立即显示
- **不需要**等待上传完成

---

### 3.2 跨模式流程（点击编辑按钮）

#### 3.2.1 用户点击编辑按钮

**位置**: `frontend/components/views/ImageGenView.tsx`

**传入的 URL**: `/api/temp-images/{attachment_id}` 或云存储URL `https://...`

#### 3.2.2 handleEditImage 处理

**位置**: `frontend/hooks/useImageHandlers.ts`

**关键流程**:
1. **查找附件**: 使用 `findAttachmentByUrl()` 在 `messages` 中查找匹配的附件
2. **复用信息**: 复用原附件的 `id`、`mimeType`、`name`、`uploadStatus`
3. **设置URL**: `newAttachment.url = url`（传入的URL，可能是临时URL或云URL）
4. **查询云URL（可选）**: 如果 `uploadStatus === 'pending'`，调用 `tryFetchCloudUrl()` 查询后端
5. **设置状态**: 调用 `setInitialAttachments([newAttachment])` 和 `setAppMode('image-chat-edit')`

**关键设计原则**:
- ✅ **上传状态与跨模式附件显示无关**：无论 `uploadStatus` 如何，都不影响显示
- ✅ **URL 直接使用传入值**：`newAttachment.url = url`（可能是临时URL或云URL）
- ✅ **显示逻辑只依赖URL有效性**：只要 `att.url` 存在且有效，就能显示

#### 3.2.3 InputArea 显示附件

**位置**: `frontend/components/chat/InputArea.tsx` 和 `frontend/components/chat/input/AttachmentPreview.tsx`

**显示逻辑**:
```typescript
{att.mimeType.startsWith('image/') && att.url ? (
    <img src={att.url} alt={att.name} className="w-full h-full object-cover" />
) : (
    // 文件图标占位符
)}
```

**关键点**:
- `InputArea` 通过 `useEffect` 监听 `initialAttachments`，调用 `updateAttachments()` 更新本地附件状态
- `AttachmentPreview` 使用 `<img src={att.url} />` 显示附件图片
- ✅ **无论上传状态如何**，只要 `att.url` 存在，附件栏就能显示

---

### 3.3 URL类型判断统一化

#### 3.3.1 统一函数设计

**创建统一函数**: `frontend/hooks/handlers/attachmentUtils.ts`

```typescript
export const getUrlType = (url: string | undefined, uploadStatus?: string): string => {
  if (!url) return '空URL';
  
  if (url.startsWith('data:')) {
    return 'Base64 Data URL (AI原始返回)';
  }
  
  if (url.startsWith('blob:')) {
    return 'Blob URL (处理后的本地URL)';
  }
  
  if (url.startsWith('/api/temp-images/')) {
    return '临时代理URL (后端创建)';
  }
  
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return uploadStatus === 'completed' 
      ? '云存储URL (已上传完成)' 
      : 'HTTP临时URL (AI原始返回)';
  }
  
  return '未知类型';
};
```

**使用位置**:
- `frontend/hooks/useChat.ts`
- `frontend/components/views/ImageGenView.tsx`
- `frontend/components/views/ImageEditView.tsx`

---

## 4. 存储配置管理架构

### 4.1 存储配置处理流程

#### 4.1.1 配置保存流程（前端 → 后端）

```
前端保存存储配置
    ↓
POST /api/storage/configs
    ↓
StorageManager.create_config()
    ↓
encrypt_config(config.config)  ✅ 加密敏感字段
    ↓
保存到数据库 (StorageConfig.config = encrypted_config)
```

#### 4.1.2 配置读取流程（后端 → 前端）

```
前端请求存储配置
    ↓
GET /api/storage/configs
    ↓
StorageManager.get_all_configs()
    ↓
decrypt_config(config.config)  ✅ 解密敏感字段
    ↓
返回给前端 (明文配置)
```

#### 4.1.3 配置使用流程（后端内部）

```
后端需要使用存储配置
    ↓
查询数据库 (StorageConfig)
    ↓
decrypt_config(config.config)  ✅ 解密敏感字段
    ↓
传递给 StorageService.upload_file()
```

---

### 4.2 统一配置获取方法设计

#### 4.2.1 方案 A：使用 StorageManager（推荐）

**优势**:
- ✅ 统一管理，自动处理加密/解密
- ✅ 支持用户作用域查询
- ✅ 更好的错误处理和日志记录
- ✅ 代码更简洁

**使用方式**:
```python
# 在任何需要存储配置的地方
manager = StorageManager(db, user_id)
result = await manager.upload_file(
    filename=filename,
    content=content,
    content_type=content_type,
    storage_id=storage_id  # 可选，如果不提供则使用激活的配置
)
```

#### 4.2.2 方案 B：直接使用 `decrypt_config()`（快速修复）

**使用场景**: 必须直接查询数据库的场景

**使用方式**:
```python
from ...core.encryption import decrypt_config

# 在需要直接查询数据库的场景
config = db.query(StorageConfig).filter(...).first()
decrypted_config = decrypt_config(config.config)
result = await StorageService.upload_file(
    filename=filename,
    content=content,
    content_type=content_type,
    provider=config.provider,
    config=decrypted_config
)
```

---

## 5. 加密文件合并设计

### 5.1 合并方案

#### 5.1.1 合并到 `core/encryption.py`

**理由**:
1. **统一入口**: 所有加密功能统一在 `core/encryption.py`，减少混淆
2. **架构清晰**: `core` 是基础层，所有加密相关功能应该在这里
3. **实现统一**: 统一 `is_encrypted()` 实现，使用更准确的实现
4. **维护简单**: 只需要维护一个文件，减少重复代码

#### 5.1.2 合并后的结构

```python
# backend/app/core/encryption.py

"""
Encryption utilities for sensitive data storage and configuration management.

This module provides:
1. ENCRYPTION_KEY management (generation, storage, retrieval)
2. Single string encryption/decryption (API keys, credentials)
3. Configuration dictionary encryption/decryption (storage configs)
"""

# ==================== ENCRYPTION_KEY 管理 ====================
class EncryptionKeyManager: ...
def get_encryption_key() -> str: ...

# ==================== 单个字符串加密/解密 ====================
def encrypt_data(data: str) -> str: ...
def decrypt_data(encrypted_data: str, silent: bool = False) -> str: ...
def is_encrypted(data: str) -> bool: ...  # 统一的实现

# ==================== 配置字典加密/解密 ====================
SENSITIVE_FIELDS: Set[str] = {...}
def encrypt_config(config: Dict[str, Any]) -> Dict[str, Any]: ...
def decrypt_config(config: Dict[str, Any]) -> Dict[str, Any]: ...
def mask_sensitive_fields(config: Dict[str, Any], mask: str = "***") -> Dict[str, Any]: ...
```

#### 5.1.3 关键修改点

**1. 统一 `is_encrypted()` 实现**

合并后，`encrypt_config()` 和 `decrypt_config()` 将使用 `core/encryption.py` 中的 `is_encrypted()` 实现（通过实际解密尝试），而不是 `utils/encryption.py` 中的格式检查实现。

**2. 移除 `_get_encryption_key()` 函数**

`utils/encryption.py` 中的 `_get_encryption_key()` 函数将被移除，直接使用 `core/encryption.py` 中的 `get_encryption_key()` 和 `_get_encryption_key_bytes()`。

**3. 更新导入路径**

所有使用 `utils.encryption` 的文件将更新为使用 `core.encryption`。

---

## 6. 数据流设计

### 6.1 AI生成图片完整流程

```
用户发送图片生成请求
    ↓
后端调用 AI API
    ↓
AI 返回图片结果
    ├─ Google: Base64 Data URL (data:image/png;base64,...)
    └─ 通义: HTTP 临时 URL (https://dashscope.oss-cn-xxx...)
    ↓
AttachmentService.process_ai_result()
    ├─ 创建 MessageAttachment 记录
    │   ├─ temp_url = ai_url (完整的 Base64 Data URL)
    │   ├─ url = '' (待上传)
    │   └─ upload_status = 'pending'
    ├─ 创建 UploadTask 记录
    │   ├─ source_ai_url = ai_url
    │   └─ status = 'pending'
    └─ 返回给前端
        ├─ url = '/api/temp-images/{attachment_id}'
        ├─ attachmentId = attachment.id
        ├─ uploadStatus = 'pending'
        └─ taskId = task.id
    ↓
前端接收响应
    ├─ ImageGenHandler 创建 displayAttachment
    │   └─ url = '/api/temp-images/{attachment_id}'
    ├─ useChat 更新 messages
    └─ ImageGenView 显示图片
        └─ <img src="/api/temp-images/{attachment_id}">
    ↓
浏览器请求临时端点
    ↓
GET /api/temp-images/{attachment_id}
    ├─ 查询数据库 (MessageAttachment)
    ├─ 读取 temp_url (完整的 Base64 Data URL)
    ├─ 解析 Base64 Data URL
    ├─ 解码为图片字节流
    └─ 返回图片字节流 (HTTP 响应)
    ↓
前端立即显示图片 ✅
    ↓
后台异步上传 (Worker Pool)
    ├─ Worker Pool 从 Redis 队列获取任务
    ├─ _get_storage_config() 解密配置 ✅
    ├─ _get_file_content() 读取文件内容
    │   └─ 从 source_ai_url (Base64 Data URL) 解码
    ├─ StorageService.upload_file() 上传到云存储
    │   └─ 使用已解密的配置 ✅
    └─ 更新 MessageAttachment
        ├─ url = 云存储URL
        └─ upload_status = 'completed'
```

### 6.2 跨模式切换完整流程

```
用户在 ImageGenView 中点击编辑按钮
    ↓
onEditImage(att.url!)  // url = '/api/temp-images/{id}' 或云存储URL
    ↓
handleEditImage(url)
    ├─ setAppMode('image-chat-edit')
    ├─ findAttachmentByUrl(url, messages)  // 查找原附件
    ├─ 创建 newAttachment
    │   └─ url = url  // ✅ 直接使用传入的URL，不依赖上传状态
    ├─ tryFetchCloudUrl() (可选)
    │   └─ 如果 uploadStatus === 'pending'，查询后端
    │       └─ 如果查询成功，更新为云存储URL
    └─ setInitialAttachments([newAttachment])
    ↓
ImageEditView 接收 initialAttachments
    ├─ useEffect 监听 initialAttachments
    ├─ setActiveAttachments(initialAttachments)
    └─ setActiveImageUrl(getStableCanvasUrlFromAttachment(...))
    ↓
InputArea 接收 initialAttachments
    ├─ useEffect 监听 initialAttachments
    └─ updateAttachments(initialAttachments)
    ↓
AttachmentPreview 显示附件
    └─ <img src={att.url} />  // ✅ 只要 url 存在且有效，就能显示
    ↓
附件栏显示图片 ✅
```

**关键设计原则**:
- ✅ **上传状态不影响显示**：无论 `uploadStatus` 是 `pending`、`failed` 还是 `completed`，都能显示
- ✅ **临时URL和云URL都能显示**：只要 `att.url` 存在且有效，就能显示
- ✅ **显示逻辑只依赖URL有效性**：不检查上传状态

---

## 7. API设计

### 7.1 存储配置API

#### 7.1.1 获取存储配置

**端点**: `GET /api/storage/configs`

**响应**: 返回所有存储配置（已解密）

```json
{
  "configs": [
    {
      "id": "config-uuid",
      "provider": "lsky",
      "config": {
        "accessKeyId": "decrypted-key",  // ✅ 已解密
        "accessKeySecret": "decrypted-secret",  // ✅ 已解密
        "domain": "https://example.com"
      },
      "enabled": true
    }
  ]
}
```

#### 7.1.2 创建存储配置

**端点**: `POST /api/storage/configs`

**请求**: 配置数据（敏感字段将被加密）

**处理流程**:
1. 接收配置数据
2. 使用 `encrypt_config()` 加密敏感字段
3. 保存到数据库

#### 7.1.3 上传文件

**端点**: `POST /api/storage/upload-async`

**处理流程**:
1. 接收文件内容
2. 获取存储配置（自动解密）
3. 调用 `StorageService.upload_file()` 上传
4. 返回上传结果

---

### 7.2 附件API

#### 7.2.1 临时图片端点

**端点**: `GET /api/temp-images/{attachment_id}`

**处理流程**:
1. 查询数据库获取附件
2. 读取 `temp_url`（完整的 Base64 Data URL）
3. 解析 Base64 Data URL
4. 解码为图片字节流
5. 返回图片字节流（HTTP 响应）

**响应**: 图片字节流（`image/png`、`image/jpeg` 等）

---

## 8. 关键技术方案

### 8.1 配置解密方案

#### 方案 1：在 `storage.py` 中添加解密逻辑（快速修复）

**修改位置**: `backend/app/routers/storage/storage.py`

```python
# ✅ 解密配置
from ...core.encryption import decrypt_config
try:
    decrypted_config = decrypt_config(config.config)
    logger.debug(f"[Storage] 已解密存储配置: {config.id} (provider={config.provider})")
except Exception as e:
    logger.error(f"[Storage] 解密存储配置失败: {e}")
    logger.warning(f"[Storage] 使用未解密的配置（可能是历史数据）: {config.id}")
    decrypted_config = config.config  # 降级：使用原配置

# ✅ 使用解密后的配置
result = await StorageService.upload_file(
    filename=filename,
    content=content,
    content_type=content_type,
    provider=config.provider,
    config=decrypted_config
)
```

#### 方案 2：使用 `StorageManager`（推荐，长期方案）

**优势**:
- ✅ 统一使用 `StorageManager`，自动处理加密/解密
- ✅ 代码更简洁，减少重复逻辑
- ✅ 更好的错误处理和日志记录
- ✅ 支持用户作用域查询（`UserScopedQuery`）

**修改方式**:
```python
async def upload_to_active_storage_async(content: bytes, filename: str, content_type: str, user_id: Optional[str] = None) -> dict:
    """异步上传文件到当前激活的存储配置"""
    db = SessionLocal()
    try:
        resolved_user_id = user_id or "default"
        logger.info(f"[Storage] Async upload for user: {resolved_user_id}, file: {filename}")

        # ✅ 使用 StorageManager（自动处理解密）
        manager = StorageManager(db, resolved_user_id)
        result = await manager.upload_file(
            filename=filename,
            content=content,
            content_type=content_type,
            storage_id=None  # 使用激活的配置
        )

        return result
    except Exception as e:
        logger.error(f"[Storage] Async upload error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()
```

---

### 8.2 前端URL类型判断方案

#### 统一函数设计

**创建统一函数**: `frontend/hooks/handlers/attachmentUtils.ts`

```typescript
export const getUrlType = (url: string | undefined, uploadStatus?: string): string => {
  if (!url) return '空URL';
  
  if (url.startsWith('data:')) {
    return 'Base64 Data URL (AI原始返回)';
  }
  
  if (url.startsWith('blob:')) {
    return 'Blob URL (处理后的本地URL)';
  }
  
  if (url.startsWith('/api/temp-images/')) {
    return '临时代理URL (后端创建)';
  }
  
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return uploadStatus === 'completed' 
      ? '云存储URL (已上传完成)' 
      : 'HTTP临时URL (AI原始返回)';
  }
  
  return '未知类型';
};
```

**使用位置**:
- `frontend/hooks/useChat.ts`
- `frontend/components/views/ImageGenView.tsx`
- `frontend/components/views/ImageEditView.tsx`

---

### 8.3 加密文件合并方案

#### 合并步骤

**步骤 1: 合并函数到 `core/encryption.py`**

需要添加的内容:
1. `SENSITIVE_FIELDS` 常量
2. `encrypt_config()` 函数
3. `decrypt_config()` 函数
4. `mask_sensitive_fields()` 函数

**步骤 2: 更新所有导入**

- `backend/app/services/common/upload_worker_pool.py`
- `backend/app/tasks/upload_tasks.py`
- `backend/app/services/storage/storage_manager.py`

**步骤 3: 删除 `utils/encryption.py`**

合并完成后，删除 `backend/app/utils/encryption.py` 文件。

---

## 9. 安全性设计

### 9.1 密钥管理

- **统一密钥**: 使用 `ENCRYPTION_KEY` 作为主密钥
- **密钥存储**: 优先从环境变量读取，文件存储时使用文件权限保护（`0o600`）
- **密钥获取**: 统一使用 `core.encryption.get_encryption_key()` 获取密钥

### 9.2 敏感数据保护

- **加密存储**: 所有敏感字段（`accessKeyId`、`accessKeySecret` 等）都加密存储
- **日志掩码**: 使用 `mask_sensitive_fields()` 掩码敏感字段，用于安全日志记录
- **传输安全**: 所有敏感数据在传输前都加密

### 9.3 认证和授权

- **统一认证**: 所有需要认证的路由使用 `Depends(require_current_user)`
- **用户隔离**: 使用 `UserScopedQuery` 确保用户只能访问自己的数据
- **Token 验证**: 使用 `jwt_utils.decode_token()` 验证 JWT token

---

## 10. 监控和日志设计

### 10.1 日志记录

#### 配置解密日志

```python
logger.debug(f"[Storage] 已解密存储配置: {config.id} (provider={config.provider})")
logger.error(f"[Storage] 解密存储配置失败: {e}")
logger.warning(f"[Storage] 使用未解密的配置（可能是历史数据）: {config.id}")
```

#### 附件处理日志

```typescript
console.log('[handleEditImage] ========== 跨模式切换开始 ==========');
console.log('[handleEditImage] 接收到的 URL:', url);
console.log('[handleEditImage] 查找附件结果:', {...});
console.log('[ImageEditView] 同步 initialAttachments:', initialAttachments);
console.log('[InputArea] 同步 initialAttachments:', initialAttachments);
```

### 10.2 监控指标

- **配置解密成功率**: 监控配置解密失败的情况
- **附件显示成功率**: 监控跨模式切换时附件显示的情况
- **上传任务成功率**: 监控 Worker Pool 上传任务的成功率

---

**文档版本**: 1.0  
**创建日期**: 2026-01-19  
**最后更新**: 2026-01-19
