# 附件处理统一后端化 - 设计文档

> **项目名称**: 附件处理统一后端化重构
> **版本**: v1.0
> **创建日期**: 2026-01-18
> **设计负责人**: 后端架构团队

---

## 目录

1. [系统架构设计](#1-系统架构设计)
2. [核心组件设计](#2-核心组件设计)
3. [显示URL与云URL机制](#3-显示url与云url机制)
4. [API设计](#4-api设计)
5. [数据模型设计](#5-数据模型设计)
6. [数据流设计](#6-数据流设计)
7. [关键技术方案](#7-关键技术方案)
8. [性能优化设计](#8-性能优化设计)
9. [安全性设计](#9-安全性设计)
10. [监控和日志设计](#10-监控和日志设计)

---

## 1. 系统架构设计

### 1.1 整体架构对比

#### 当前架构（分散式）:
```
┌─────────────────────────────────────────────────┐
│                    前端                          │
├─────────────────────────────────────────────────┤
│  attachmentUtils.ts (1016行) - 职责过重          │
│  ├─ processUserAttachments                      │
│  ├─ processMediaResult                          │
│  ├─ sourceToFile (3层降级)                       │
│  ├─ findAttachmentByUrl                         │
│  ├─ tryFetchCloudUrl                            │
│  └─ cleanAttachmentsForDb                       │
│                                                  │
│  storageUpload.ts                                │
│  └─ uploadFileAsync (FormData上传)              │
└──────────────┬───────────────────────────────────┘
               │ FormData上传 (可能很大)
               ↓
┌─────────────────────────────────────────────────┐
│                    后端                          │
├─────────────────────────────────────────────────┤
│  storage.py (临时文件管理)                       │
│  upload_worker_pool.py (异步上传)                │
│  sessions.py (云URL保护)                         │
│  conversational_image_edit_service.py (下载)     │
└─────────────────────────────────────────────────┘

问题:
❌ 前端1016行附件处理代码
❌ 后端分散在4个文件
❌ 前端FormData上传大文件
❌ 重复下载、重复处理
```

#### 新架构（统一后端式）:
```
┌─────────────────────────────────────────────────┐
│                    前端                          │
├─────────────────────────────────────────────────┤
│  attachmentUtils.ts (轻量化 ~400行)              │
│  ├─ handleFileSelect (仅文件选择)                │
│  ├─ createBlobPreview (仅创建预览)               │
│  └─ submitAttachmentMeta (仅提交元数据)          │
│                                                  │
│  【删除】processUserAttachments                  │
│  【删除】processMediaResult                      │
│  【删除】sourceToFile                            │
│  【删除】findAttachmentByUrl                     │
│  【删除】tryFetchCloudUrl                        │
│  【删除】cleanAttachmentsForDb                   │
└──────────────┬───────────────────────────────────┘
               │ 仅元数据 (JSON, <1KB)
               ↓
┌─────────────────────────────────────────────────┐
│             后端 - 统一附件处理服务               │
├─────────────────────────────────────────────────┤
│  【新增】attachment_service.py (核心服务)        │
│  ├─ process_user_upload (处理用户上传)           │
│  ├─ process_ai_result (处理AI返回)              │
│  ├─ resolve_continuity_attachment (CONTINUITY)  │
│  └─ get_cloud_url (统一云URL管理)               │
│                                                  │
│  【增强】upload_worker_pool.py                   │
│  ├─ source_file_path (已有)                     │
│  ├─ source_url (已有)                           │
│  ├─ source_ai_url (新增 - AI返回URL)            │
│  └─ source_attachment_id (新增 - 复用附件)      │
│                                                  │
│  modes.py (调用统一服务)                         │
└─────────────────────────────────────────────────┘

优势:
✅ 前端减少60%代码 (1016→400行)
✅ 后端统一服务（单一职责）
✅ 仅传输元数据（<1KB vs 可能>1MB）
✅ 消除重复下载
```

### 1.2 分层架构

```
┌──────────────────────────────────────────────────────┐
│                    表现层 (Frontend)                  │
├──────────────────────────────────────────────────────┤
│  - 文件选择 UI                                        │
│  - 图片预览显示                                       │
│  - 上传进度显示                                       │
└──────────────────┬───────────────────────────────────┘
                   │ HTTP/JSON
                   ↓
┌──────────────────────────────────────────────────────┐
│                   应用层 (Backend API)                │
├──────────────────────────────────────────────────────┤
│  - modes.py (统一路由)                                │
│  - attachments.py (临时代理端点)                      │
│  - sessions.py (会话管理)                             │
└──────────────────┬───────────────────────────────────┘
                   │ Service Call
                   ↓
┌──────────────────────────────────────────────────────┐
│                   业务层 (Services)                   │
├──────────────────────────────────────────────────────┤
│  - AttachmentService (附件处理核心)                   │
│  - GoogleService / TongyiService (AI服务)            │
│  - UploadWorkerPool (异步上传)                        │
└──────────────────┬───────────────────────────────────┘
                   │ Data Access
                   ↓
┌──────────────────────────────────────────────────────┐
│                   数据层 (Data Access)                │
├──────────────────────────────────────────────────────┤
│  - MessageAttachment Model                            │
│  - UploadTask Model                                   │
│  - Session Model                                      │
└──────────────────┬───────────────────────────────────┘
                   │ Database/Storage
                   ↓
┌──────────────────────────────────────────────────────┐
│                 基础设施层 (Infrastructure)           │
├──────────────────────────────────────────────────────┤
│  - PostgreSQL (数据库)                                │
│  - Redis (Worker Pool队列)                           │
│  - OSS/S3 (云存储)                                    │
│  - Google/Tongyi API (外部服务)                       │
└──────────────────────────────────────────────────────┘
```

---

## 2. 核心组件设计

### 2.1 AttachmentService 设计

**文件位置**: `backend/app/services/common/attachment_service.py`

**职责**:
1. 统一处理所有来源的附件（用户上传、AI返回、CONTINUITY LOGIC）
2. 统一云URL管理
3. 调度Worker Pool异步上传
4. 管理附件生命周期

**核心方法**:

```python
class AttachmentService:
    def __init__(self, db: Session):
        self.db = db

    async def process_user_upload(
        self,
        file_path: str,
        filename: str,
        mime_type: str,
        session_id: str,
        message_id: str
    ) -> Dict[str, Any]:
        """处理用户上传的文件"""
        pass

    async def process_ai_result(
        self,
        ai_url: str,
        mime_type: str,
        session_id: str,
        message_id: str,
        prefix: str = 'generated'
    ) -> Dict[str, Any]:
        """处理AI返回的图片URL（Base64或HTTP）"""
        pass

    async def resolve_continuity_attachment(
        self,
        active_image_url: str,
        session_id: str,
        messages: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """解析CONTINUITY LOGIC的附件"""
        pass

    async def get_cloud_url(
        self,
        attachment_id: str
    ) -> Optional[str]:
        """获取附件的云存储URL"""
        pass
```

### 2.2 Worker Pool增强

**文件位置**: `backend/app/services/common/upload_worker_pool.py`

**新增Source类型**:
- `source_ai_url`: AI返回的URL（Base64 Data URL 或 HTTP临时URL）
- `source_attachment_id`: 复用已有附件的ID（CONTINUITY LOGIC）

**增强方法**:

```python
async def _get_file_content(self, task: UploadTask) -> Optional[bytes]:
    """
    获取文件内容 - 支持4种source类型
    
    返回None表示无需上传（复用已有附件）
    """
    # 类型1: source_file_path（已有）
    if task.source_file_path:
        # ... 读取本地文件 ...
    
    # 类型2: source_url（已有）
    elif task.source_url:
        # ... HTTP下载 ...
    
    # 类型3: source_ai_url（新增）
    elif task.source_ai_url:
        if task.source_ai_url.startswith('data:'):
            # Base64 Data URL → 解码
            return base64.b64decode(parse_data_url(task.source_ai_url)[1])
        else:
            # HTTP URL → 下载
            async with httpx.AsyncClient() as client:
                response = await client.get(task.source_ai_url)
                return response.content
    
    # 类型4: source_attachment_id（新增）
    elif task.source_attachment_id:
        # 查询已有附件
        existing = db.query(MessageAttachment).filter_by(
            id=task.source_attachment_id
        ).first()
        
        if existing and existing.url and existing.upload_status == 'completed':
            # 已有云URL → 直接复用（不重新上传）
            return None  # 特殊标记：无需上传
```

---

## 3. 显示URL与云URL机制

### 3.1 核心概念

#### 3.1.1 什么是显示URL（Display URL）

**定义**: 临时HTTP URL，用于前端**立即显示**图片，生命周期短。

**特征**:
- ✅ HTTP协议（非Base64）
- ✅ 可以立即使用（<img src={displayUrl} />）
- ❌ 临时有效（可能几分钟到几小时）
- ❌ 不能保存到数据库
- ❌ 不能用于页面重载

**类型**:
1. **Tongyi临时URL**: `http://dashscope.aliyuncs.com/api/v1/tasks/.../output?expires=...`
   - 有效期: 通常1-24小时
   - 来源: AI API直接返回

2. **临时代理URL**: `/api/temp-images/{attachment_id}`
   - 有效期: 直到Worker Pool上传完成或会话结束
   - 来源: 后端为Base64创建的代理端点
   - 用途: **避免向前端传输Base64**

#### 3.1.2 什么是云URL（Cloud URL）

**定义**: 永久云存储URL，用于**数据库保存**和**页面重载**，生命周期长。

**特征**:
- ✅ HTTP协议
- ✅ 永久有效（或有效期>1年）
- ✅ 保存到数据库（url字段）
- ✅ 用于页面重载
- ✅ 可以跨会话访问

**类型**:
1. **阿里云OSS URL**: `https://{bucket}.oss-{region}.aliyuncs.com/{key}?Expires=...&OSSAccessKeyId=...`
   - 有效期: 通常1年或永久

2. **自建存储URL**: `https://storage.example.com/uploads/{session_id}/{filename}`
   - 有效期: 永久

#### 3.1.3 为什么需要两种URL

**问题**: 为什么不能只用一种URL？

1. **立即显示需求** vs **永久存储需求**
   - 用户期望: AI生成图片后**立即看到**（不能等上传完成）
   - 系统需求: 重载时**必须有图**（临时URL可能已过期）

2. **性能优化** vs **数据持久化**
   - Tongyi临时URL: 可以立即使用，无需等待上传
   - 云URL: 需要等Worker Pool上传完成（可能几秒）

3. **避免Base64传输** vs **数据完整性**
   - Google返回Base64: 不能直接传给前端（太大）
   - 临时代理URL: 让前端立即显示
   - 云URL: 上传后替换，保证数据完整

### 3.2 字段映射

#### 3.2.1 数据库表字段

**MessageAttachment 表**:
```python
class MessageAttachment(Base):
    id = Column(String, primary_key=True)
    message_id = Column(String, ForeignKey('messages.id'))

    # ❗ 显示URL（临时，不保存到此字段）
    temp_url = Column(Text, nullable=True)
    # 用途: 保存原始URL（可能是Base64、Tongyi临时URL）
    # 生命周期: 仅在上传前使用，上传完成后可清空

    # ❗ 云URL（永久，保存到此字段）
    url = Column(String, nullable=False)
    # 用途: 云存储永久URL
    # 生命周期: Worker Pool上传完成后写入，永久保留

    upload_status = Column(String)  # 'pending' | 'uploading' | 'completed'
    # pending: 等待上传，url为空，temp_url有值
    # uploading: 正在上传
    # completed: 上传完成，url有值（云URL）
```

**UploadTask 表**:
```python
class UploadTask(Base):
    id = Column(String, primary_key=True)
    attachment_id = Column(String, ForeignKey('message_attachments.id'))

    # Source字段（仅用于Worker Pool获取文件）
    source_file_path = Column(String)     # 用户上传的临时文件路径
    source_url = Column(String)           # HTTP URL
    source_ai_url = Column(Text)          # AI返回的URL（可能是Base64）
    source_attachment_id = Column(String) # 复用已有附件

    # ❗ 上传目标URL（云URL）
    target_url = Column(String, nullable=True)
    # 用途: 上传完成后的云存储URL
    # 生命周期: 上传完成后写入

    status = Column(String)  # 'pending' | 'processing' | 'completed' | 'failed'
```

### 3.3 临时代理端点实现

**端点**: `GET /api/temp-images/{attachment_id}`

**用途**: 为Base64创建临时HTTP代理端点，避免向前端传输Base64

**实现**:
```python
@router.get("/temp-images/{attachment_id}")
async def get_temp_image(
    attachment_id: str,
    db: Session = Depends(get_db)
):
    """
    临时图片代理端点
    
    用途: 将存储在temp_url中的Base64 Data URL转为HTTP响应
    生命周期: 直到Worker Pool上传完成或会话结束
    """
    # 查询附件
    attachment = db.query(MessageAttachment).filter_by(
        id=attachment_id
    ).first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # 检查temp_url
    if not attachment.temp_url:
        # temp_url为空 → 可能已上传完成，返回云URL重定向
        if attachment.url and attachment.upload_status == 'completed':
            return RedirectResponse(url=attachment.url)
        else:
            raise HTTPException(status_code=404, detail="Temp URL not available")

    # 判断temp_url类型
    temp_url = attachment.temp_url

    if temp_url.startswith('data:'):
        # Base64 Data URL → 解码并返回
        mime_type, base64_str = parse_data_url(temp_url)
        image_bytes = base64.b64decode(base64_str)

        return Response(
            content=image_bytes,
            media_type=mime_type,
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
    elif temp_url.startswith('http'):
        # HTTP URL → 重定向（Tongyi临时URL）
        return RedirectResponse(url=temp_url)
    else:
        raise HTTPException(status_code=400, detail="Invalid temp URL format")
```

**优势**:
- ✅ **避免Base64传输**: 前端通过HTTP请求获取图片字节流，而非接收Base64字符串
- ✅ **浏览器缓存**: 浏览器可以缓存图片（Base64不能）
- ✅ **内存优化**: 前端不需要存储大量Base64字符串
- ✅ **渐进加载**: 图片可以渐进加载（Base64必须全部下载）

---

## 4. API设计

### 4.1 新增API

#### 4.1.1 临时图片代理端点（新增）

**端点**: `GET /api/temp-images/{attachment_id}`

**用途**: ❗ **核心功能** - 避免向前端传输Base64 Data URL

**优势**:
- 避免Base64传输（体积+33%）
- 浏览器可缓存
- 渐进加载

#### 4.1.2 解析CONTINUITY附件

**端点**: `POST /api/attachments/resolve-continuity`

**用途**: Edit模式CONTINUITY LOGIC - 后端负责查找和解析

**请求体**:
```json
{
  "activeImageUrl": "blob:http://localhost:3000/xxx",
  "sessionId": "session-123",
  "messages": [...]  // 可选，如果不传则后端从数据库查询
}
```

**响应**:
```json
{
  "attachmentId": "att-123",
  "url": "https://storage.example.com/xxx.png",  // 云URL
  "status": "completed",
  "taskId": null
}
```

#### 4.1.3 获取云URL

**端点**: `GET /api/attachments/{attachmentId}/cloud-url`

**用途**: 替代前端的tryFetchCloudUrl

**响应**:
```json
{
  "url": "https://storage.example.com/xxx.png",
  "uploadStatus": "completed"
}
```

### 4.2 修改现有API

#### 4.2.1 modes API增强

**端点**: `POST /api/modes/{provider}/{mode}`

**请求体增强**:
```json
{
  "prompt": "...",
  "modelId": "...",

  // ✅ Edit模式新增字段
  "activeImageUrl": "blob:xxx",  // CONTINUITY LOGIC用

  // 现有字段保留
  "attachments": [...],
  "options": {
    "frontend_session_id": "...",
    "message_id": "..."
  }
}
```

**响应增强**:
```json
{
  "images": [
    {
      "url": "https://...",           // display_url - 前端立即显示
      "attachmentId": "att-123",      // 附件ID
      "uploadStatus": "pending",      // 上传状态
      "taskId": "task-456"            // Worker Pool任务ID
    }
  ],
  "thoughts": "..."  // Edit模式独有
}
```

---

## 5. 数据模型设计

### 5.1 MessageAttachment 模型

**文件位置**: `backend/app/models/db_models.py`

**关键字段**:
```python
class MessageAttachment(Base):
    __tablename__ = 'message_attachments'
    
    id = Column(String, primary_key=True)
    message_id = Column(String, ForeignKey('messages.id'))
    name = Column(String)
    mime_type = Column(String)
    
    # ❗ 显示URL（临时，不保存到此字段）
    temp_url = Column(Text, nullable=True)
    # 用途: 保存原始URL（可能是Base64、Tongyi临时URL）
    # 生命周期: 仅在上传前使用，上传完成后可清空
    
    # ❗ 云URL（永久，保存到此字段）
    url = Column(String, nullable=False)
    # 用途: 云存储永久URL
    # 生命周期: Worker Pool上传完成后写入，永久保留
    
    upload_status = Column(String)  # 'pending' | 'uploading' | 'completed' | 'failed'
    upload_task_id = Column(String, ForeignKey('upload_tasks.id'), nullable=True)
    
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

### 5.2 UploadTask 模型增强

**新增字段**:
```python
class UploadTask(Base):
    __tablename__ = 'upload_tasks'
    
    # 现有source（保留）
    source_file_path = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    
    # 【新增】source字段
    source_ai_url = Column(Text, nullable=True)         # AI返回URL（Base64或HTTP）
    source_attachment_id = Column(String, nullable=True)  # 复用已有附件ID
    
    # ❗ 上传目标URL（云URL）
    target_url = Column(String, nullable=True)
    # 用途: 上传完成后的云存储URL
    # 生命周期: 上传完成后写入
    
    status = Column(String)  # 'pending' | 'processing' | 'completed' | 'failed'
```

### 5.3 数据库迁移脚本

```sql
-- 添加新source字段到upload_tasks表
ALTER TABLE upload_tasks ADD COLUMN source_ai_url TEXT;
ALTER TABLE upload_tasks ADD COLUMN source_attachment_id VARCHAR(255);

-- 添加索引
CREATE INDEX idx_upload_tasks_source_ai_url ON upload_tasks(source_ai_url);
CREATE INDEX idx_upload_tasks_source_attachment_id ON upload_tasks(source_attachment_id);
```

---

## 6. 数据流设计

### 6.1 Gen模式 - Tongyi

#### 当前流程（2次下载）:
```
[Google Gemini API]
    ↓ 返回 HTTP临时URL
[前端] ❌ 下载1: fetch(url) → Blob (显示)               +300ms
    ↓
[前端] ❌ 下载2: sourceToFile → fetch(url) → File      +300ms
    ↓
[前端] ❌ FormData上传: File → 后端                     +200ms (1MB文件)
    ↓
[后端] 保存临时文件: /tmp/uploads/xxx
    ↓
[Worker Pool] 读取临时文件 → 上传云存储                 +500ms
    ↓
[Worker Pool] 删除临时文件

总延迟: ~1300ms
网络请求: 4次（下载2次 + 上传1次 + 云存储1次）
```

#### 新流程（1次下载）:
```
[Google Gemini API]
    ↓ 返回 HTTP临时URL
[后端] ✅ 调用 attachment_service.process_ai_result()
    ├─ 创建附件记录（temp_url=HTTP URL）
    └─ 提交Worker Pool任务（source_ai_url=HTTP URL）
    ↓ 返回 display_url=HTTP URL
[前端] ✅ 直接显示: <img src={display_url} />           +0ms (无下载)
    ↓
[Worker Pool] ✅ 下载1: httpx.get(source_ai_url)        +300ms
    ↓
[Worker Pool] 上传云存储                                 +500ms
    ↓
[Worker Pool] 更新附件URL

总延迟: ~800ms
网络请求: 2次（下载1次 + 云存储1次）
```

**收益**:
- ✅ 延迟减少: **1300ms → 800ms** (-500ms, **-38%**)
- ✅ 网络请求: **4次 → 2次** (-2次, **-50%**)
- ✅ 前端无下载: **0次** (之前2次)
- ✅ 前端无上传: **0MB** (之前可能>1MB)

### 6.2 Gen模式 - Google

#### 当前流程（Base64传输）:
```
[Google Gemini API]
    ↓ 返回 Base64 Data URL (~1.33MB for 1MB图片)
[前端] ❌ 接收 Base64                                    +200ms (传输1.33MB)
    ↓
[前端] 直接显示: displayUrl = res.url (Base64)          +0ms
    ↓
[前端] ❌ sourceToFile: Base64 → File                    +100ms (CPU)
    ↓
[前端] ❌ FormData上传: File → 后端                      +400ms (再传1.33MB)
    ↓
[后端] 保存临时文件
    ↓
[Worker Pool] 读取临时文件 → 上传云存储                 +500ms

总延迟: ~1200ms
传输数据: ~2.66MB (前端接收1.33MB + 前端上传1.33MB)
❌ Base64双向传输浪费
```

#### 新流程（❗ 避免Base64传输 - 使用代理URL）:
```
[Google Gemini API]
    ↓ 返回 Base64 Data URL (~1.33MB)
[后端] ✅ 调用 attachment_service.process_ai_result()
    ├─ 检测到Base64 → 创建代理URL
    ├─ display_url = /api/temp-images/att-123  ← ❗ 关键：避免传Base64
    ├─ temp_url = Base64 (保存到数据库)
    └─ 提交Worker Pool任务（source_ai_url=Base64）
    ↓ 返回 display_url=/api/temp-images/att-123 (仅URL字符串，~40字节)
[前端] ✅ 请求代理URL: <img src="/api/temp-images/att-123" />
    ↓
GET /api/temp-images/att-123
    ↓
[后端] ✅ 读取temp_url → Base64解码 → 返回图片字节流    +50ms
    ↓
[前端] 显示图片                                          +0ms
    ↓ (异步)
[Worker Pool] ✅ base64.b64decode(source_ai_url)         +50ms (CPU)
    ↓
[Worker Pool] 上传云存储                                 +500ms
    ↓
[Worker Pool] 更新: url=云URL, temp_url='' (清空Base64)

总延迟: ~550ms
传输数据: ~1MB (仅图片字节流，无Base64编码开销)
✅ 避免Base64传输，节省 ~1.66MB (66% 数据量)
```

**收益**:
- ✅ 延迟减少: **1200ms → 550ms** (-650ms, **-54%**)
- ✅ 前端CPU: **-100ms** (无Base64→File转换)
- ✅ 前端接收: **-1.33MB** (从1.33MB Base64 → 40字节URL)
- ✅ 前端上传: **-1.33MB** (无FormData上传)
- ✅ 后端临时文件: **0次IO** (直接从Base64解码)
- ✅ **总节省数据传输**: **-1.66MB** (66%减少)

### 6.3 Edit模式 - CONTINUITY LOGIC

#### 当前流程（前端查找）:
```
[前端] ❌ findAttachmentByUrl(activeImageUrl, messages)  +50ms (遍历)
    ├─ 遍历所有消息（可能很多）
    └─ 精确匹配url或tempUrl
    ↓
[前端] ❌ tryFetchCloudUrl(sessionId, attachmentId)      +100ms (API)
    ↓
GET /api/sessions/{sessionId}/attachments/{attachmentId}
    ↓
[后端] 查询数据库 → 返回云URL                           +50ms (DB)
    ↓
[前端] 使用云URL

总延迟: ~200ms
前端代码: 200行（findAttachmentByUrl + tryFetchCloudUrl）
```

#### 新流程（后端查找）:
```
[前端] ✅ 仅发送: activeImageUrl                         +0ms
    ↓
POST /api/modes/google/image-chat-edit {
  activeImageUrl: "blob:xxx"
}
    ↓
[后端] ✅ attachment_service.resolve_continuity_attachment()
    ├─ _find_attachment_by_url()  (后端查找，更快)       +10ms
    ├─ 查询数据库                                        +50ms
    └─ 返回云URL或提交Worker Pool任务
    ↓
[前端] 直接使用返回的URL

总延迟: ~60ms
前端代码: 0行（后端负责）
```

**收益**:
- ✅ 延迟减少: **200ms → 60ms** (-140ms, **-70%**)
- ✅ 前端代码: **-200行** (删除findAttachmentByUrl和tryFetchCloudUrl)
- ✅ API调用: **2次 → 1次** (合并到modes API)
- ✅ 前端逻辑: **完全移除**

---

## 7. 关键技术方案

### 7.1 统一附件处理服务

**核心类**: `AttachmentService`

**主要方法**:
1. `process_user_upload()` - 处理用户上传
2. `process_ai_result()` - 处理AI返回（Base64或HTTP）
3. `resolve_continuity_attachment()` - CONTINUITY LOGIC
4. `get_cloud_url()` - 获取云URL

**关键特性**:
- ✅ 统一入口，所有模式复用
- ✅ 自动检测URL类型（Base64 vs HTTP）
- ✅ 自动创建临时代理URL（避免Base64传输）
- ✅ 自动调度Worker Pool异步上传

### 7.2 Worker Pool增强

**新增Source类型**:
- `source_ai_url`: AI返回的URL（Base64或HTTP）
- `source_attachment_id`: 复用已有附件ID

**关键实现**:
```python
async def _get_file_content(self, task: UploadTask) -> Optional[bytes]:
    """支持4种source类型，返回None表示复用附件"""
    if task.source_ai_url:
        if task.source_ai_url.startswith('data:'):
            # Base64解码
            return base64.b64decode(parse_data_url(task.source_ai_url)[1])
        else:
            # HTTP下载
            async with httpx.AsyncClient() as client:
                return (await client.get(task.source_ai_url)).content
    
    elif task.source_attachment_id:
        # 复用已有附件
        existing = db.query(MessageAttachment).filter_by(
            id=task.source_attachment_id
        ).first()
        if existing.url and existing.upload_status == 'completed':
            return None  # 无需上传，直接复用
```

### 7.3 临时代理端点

**端点**: `GET /api/temp-images/{attachment_id}`

**实现逻辑**:
1. 查询MessageAttachment
2. 读取temp_url（Base64或HTTP）
3. Base64解码并返回图片字节流
4. HTTP URL重定向

**优势**:
- ✅ 避免Base64传输（体积+33%）
- ✅ 浏览器可缓存
- ✅ 渐进加载

---

## 8. 页面重载流程

### 8.1 核心要求

❗ **关键要求**: 页面重载时，**必须从云URL加载图片**，否则对话历史没有图片。

**为什么重要**:
1. **显示URL可能已过期**
   - Tongyi临时URL: 1-24小时有效期
   - 临时代理URL: 会话结束后失效
   - Base64: 不能保存到数据库（太大）

2. **云URL是唯一可靠来源**
   - 永久有效（或>1年有效期）
   - 保存在数据库 `message_attachments.url` 字段
   - Worker Pool上传完成后写入

3. **没有后端异步上传 = 重载没图**
   - 如果没有Worker Pool异步上传到云存储
   - 数据库中 `url` 字段为空
   - 重载时无法加载图片

### 8.2 完整重载流程

#### 场景：用户刷新页面或重新打开会话

```
┌─────────────────────────────────────────────────────────────┐
│ 阶段1: 前端请求会话消息                                      │
├─────────────────────────────────────────────────────────────┤
│ 用户刷新页面 或 打开历史会话                                │
│ ↓                                                            │
│ GET /api/sessions/{sessionId}/messages                       │
│ ↓                                                            │
│ 后端查询数据库:                                              │
│   SELECT * FROM messages WHERE session_id = ?               │
│   JOIN message_attachments ON messages.id = message_id      │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 阶段2: 后端返回消息（❗ 只返回云URL）                        │
├─────────────────────────────────────────────────────────────┤
│ 关键查询逻辑:                                                │
│                                                              │
│ for attachment in message_attachments:                       │
│     if attachment.upload_status == 'completed':              │
│         # ✅ 已上传完成 → 返回云URL                          │
│         return {                                             │
│             'id': attachment.id,                             │
│             'url': attachment.url,  # 云URL                  │
│             'uploadStatus': 'completed'                      │
│         }                                                    │
│     else:                                                    │
│         # ❌ 未上传完成 → 跳过或返回pending                  │
│         return {                                             │
│             'id': attachment.id,                             │
│             'url': '',                                       │
│             'uploadStatus': 'pending'                        │
│         }                                                    │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 阶段3: 前端显示历史图片                                      │
├─────────────────────────────────────────────────────────────┤
│ 前端接收消息列表:                                            │
│                                                              │
│ messages.forEach(msg => {                                    │
│   msg.attachments.forEach(att => {                           │
│     if (att.uploadStatus === 'completed' && att.url) {       │
│       // ✅ 显示云URL                                        │
│       <img src={att.url} />                                  │
│     } else {                                                 │
│       // ❌ 未上传完成 → 显示占位符或错误                    │
│       <div>图片上传中或失败</div>                            │
│     }                                                        │
│   })                                                         │
│ })                                                           │
└─────────────────────────────────────────────────────────────┘
```

### 8.3 关键代码实现

#### 8.3.1 后端：返回会话消息

```python
@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    获取会话消息列表
    
    ❗ 关键: 只返回upload_status='completed'的附件云URL
    """
    messages = db.query(Message).filter_by(
        session_id=session_id
    ).order_by(Message.created_at.asc()).all()

    result = []
    for msg in messages:
        attachments = []
        for att in msg.attachments:
            # ❗ 关键过滤逻辑
            if att.upload_status == 'completed' and att.url:
                # ✅ 已上传 → 返回云URL
                attachments.append({
                    'id': att.id,
                    'name': att.name,
                    'mimeType': att.mime_type,
                    'url': att.url,  # ❗ 云URL（永久有效）
                    'uploadStatus': 'completed',
                })
            else:
                # ❌ 未上传完成 → 返回pending状态
                attachments.append({
                    'id': att.id,
                    'name': att.name,
                    'mimeType': att.mime_type,
                    'url': '',
                    'uploadStatus': att.upload_status or 'failed',
                })

        result.append({
            'id': msg.id,
            'role': msg.role,
            'content': msg.content,
            'attachments': attachments,
        })

    return result
```

#### 8.3.2 前端：显示历史消息

```typescript
function MessageItem({ message }: { message: Message }) {
  return (
    <div>
      <p>{message.content}</p>

      {/* 显示附件 */}
      {message.attachments?.map(att => (
        <div key={att.id}>
          {att.uploadStatus === 'completed' && att.url ? (
            // ✅ 显示云URL
            <img
              src={att.url}
              alt={att.name}
              // att.url = https://bucket.oss.aliyuncs.com/xxx.png
            />
          ) : (
            // ❌ 未上传完成
            <div className="placeholder">
              {att.uploadStatus === 'pending' && '图片上传中...'}
              {att.uploadStatus === 'failed' && '图片上传失败'}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

### 8.4 异常场景处理

#### 场景1: Worker Pool上传失败

**问题**: AI生成图片后，Worker Pool上传云存储失败

**解决方案**:
1. **重试机制**: Worker Pool自动重试3次
2. **手动重试**: 前端提供"重新上传"按钮
3. **监控告警**: 上传失败率>1%时告警

#### 场景2: Worker Pool上传中（用户过早刷新）

**问题**: 用户在Worker Pool上传完成前刷新页面

**解决方案**:
1. **WebSocket监听**: 监听上传完成事件，实时更新
2. **轮询查询**: 定时查询附件状态（每2秒，30秒超时）

#### 场景3: 临时URL过期（极端情况）

**问题**: Worker Pool上传失败且temp_url已过期

**预防措施**:
1. **提高上传优先级**: Worker Pool优先处理图片上传
2. **监控告警**: 上传失败率>1%时告警
3. **备份策略**: 保存原始图片到临时存储（24小时）

---

## 9. 性能优化设计

### 9.1 延迟优化

**目标**: 平均延迟减少40%

**具体措施**:
1. **消除重复下载**: Tongyi模式从2次下载 → 1次下载（-500ms）
2. **避免Base64传输**: Google模式从Base64传输 → 代理URL（-650ms）
3. **后端统一查找**: CONTINUITY LOGIC从前端查找 → 后端查找（-140ms）

**预期收益**:
- Tongyi模式: 1300ms → 800ms（-38%）
- Google模式: 1200ms → 550ms（-54%）
- CONTINUITY LOGIC: 200ms → 60ms（-70%）

### 9.2 网络请求优化

**目标**: 网络请求减少50%

**具体措施**:
1. **前端不下载**: Tongyi临时URL直接使用（-2次下载）
2. **合并API调用**: CONTINUITY LOGIC合并到modes API（-1次查询）
3. **避免FormData上传**: AI返回图片不通过前端上传（-1次上传）

**预期收益**:
- Tongyi: 4次 → 2次（-50%）
- Google: 3次 → 2次（-33%）
- CONTINUITY: 2次 → 1次（-50%）

### 9.3 数据传输优化

**目标**: 数据传输减少67%-100%

**具体措施**:
1. **避免Base64传输**: Google模式从1.33MB Base64 → 40字节URL（-100%）
2. **前端不下载**: Tongyi模式前端不下载（-1MB）
3. **前端不上传**: AI返回图片不通过前端上传（-1.33MB）

**预期收益**:
- Tongyi: 3MB → 1MB（-67%）
- Google: 2.66MB → 0MB（-100%）

### 9.4 服务器资源优化

**目标**: 服务器IO和带宽减少50%-67%

**具体措施**:
1. **减少临时文件IO**: 仅用户上传需要临时文件（-67% IO）
2. **减少网络带宽**: 前端不上传AI返回图片（-50% 带宽）
3. **优化Worker Pool**: 支持4种source类型，提高灵活性

**预期收益**:
- 临时文件IO: -67%
- 网络带宽: -50%
- Worker Pool效率: +100%灵活性

---

## 10. 安全性设计

### 10.1 临时代理端点安全

**端点**: `GET /api/temp-images/{attachment_id}`

**安全措施**:
1. **身份验证**: 需要用户登录（JWT token）
2. **权限检查**: 验证用户是否有权限访问该附件
3. **会话验证**: 验证附件属于当前用户的会话
4. **访问控制**: 限制访问频率（防止滥用）

**实现**:
```python
@router.get("/temp-images/{attachment_id}")
async def get_temp_image(
    attachment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ 身份验证
):
    # ✅ 权限检查
    attachment = db.query(MessageAttachment).filter_by(
        id=attachment_id
    ).first()
    
    if not attachment:
        raise HTTPException(status_code=404)
    
    # ✅ 会话验证
    message = db.query(Message).filter_by(id=attachment.message_id).first()
    if message.session.user_id != current_user.id:
        raise HTTPException(status_code=403)
    
    # ... 返回图片 ...
```

### 10.2 数据安全

**措施**:
1. **Base64不传输**: Base64数据仅在后端内部处理，不传输给前端
2. **临时URL过期**: 临时代理URL在Worker Pool上传完成后失效
3. **云URL权限**: 云存储URL使用签名URL，设置过期时间

### 10.3 输入验证

**措施**:
1. **URL验证**: 验证AI返回的URL格式（Base64或HTTP）
2. **文件大小限制**: 限制单张图片大小（< 10MB）
3. **MIME类型验证**: 只允许图片类型（image/png, image/jpeg等）

---

## 11. 监控和日志设计

### 11.1 关键指标监控

**必须监控**:
1. **API响应时间**: P50, P90, P99延迟
2. **Worker Pool队列长度**: 实时队列长度
3. **上传成功率**: 上传成功/失败比例
4. **前端错误率**: 前端错误日志
5. **用户投诉数量**: 用户反馈统计

### 11.2 告警阈值

**告警规则**:
- API P99延迟 > 2000ms → 告警
- Worker Pool队列 > 100 → 告警
- 上传失败率 > 1% → 告警
- 前端错误率 > 0.5% → 告警

### 11.3 日志设计

**日志级别**:
- **INFO**: 正常操作（附件创建、上传完成）
- **WARNING**: 警告（上传重试、临时URL过期）
- **ERROR**: 错误（上传失败、API错误）

**日志内容**:
```python
logger.info(f"Attachment created: {attachment_id}, source: {source_type}")
logger.warning(f"Upload retry: task_id={task_id}, attempt={attempt}")
logger.error(f"Upload failed: task_id={task_id}, error={error}")
```

### 11.4 性能监控

**监控工具**:
- **APM**: 应用性能监控（如New Relic, Datadog）
- **日志聚合**: 日志收集和分析（如ELK Stack）
- **指标收集**: Prometheus + Grafana

**关键指标**:
- 请求延迟分布
- 错误率趋势
- Worker Pool吞吐量
- 云存储上传速度

---

**文档版本**: v1.0
**最后更新**: 2026-01-18
