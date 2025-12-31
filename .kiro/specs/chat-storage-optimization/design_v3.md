# Design Document (v3) - Chat Storage Optimization

## 设计概述

v3 方案采用**按模式分表 + 消息索引表**的架构，

- ✅ **按模式隔离**：每个模式（chat/image-gen/video-gen）独立表，避免单表性能瓶颈
- ✅ **快速定位**：通过 `message_index` 索引表，O(1) 定位消息所在表
- ✅ **前端零改动**：保持 UUIDv4 ID 策略，后端通过索引表桥接
- ✅ **扩展性强**：新增模式时预先创建表，无动态 DDL 风险
- ✅ **纯文本存储**：不使用 JSON，metadata 字段拆分为具体列


---

## 总体架构

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│  chat_sessions (会话元数据)                               │
│  id | title | persona_id | mode | created_at             │
└───────────────────┬─────────────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
┌────────▼─────────┐  ┌────────▼──────────────────────┐
│ message_index    │  │  message_attachments          │
│ (快速定位索引表)  │  │  (所有模式共享)                │
│ id               │  │  id | message_id | url | ...  │
│ session_id       │  └───────────────────────────────┘
│ mode             │
│ table_name       │
│ timestamp        │
└────────┬─────────┘
         │
    ┌────┴────┬────────┬────────┬────────┐
    ▼         ▼        ▼        ▼        ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│messages_ │ │messages_ │ │messages_ │ │messages_ │
│  chat    │ │image_gen │ │video_gen │ │audio_gen │
│ (纯文本) │ │ (纯文本) │ │ (纯文本) │ │ (纯文本) │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### 核心思想

1. **message_index 索引表**：作为路由层，存储所有消息的 `(id, session_id, mode, table_name, seq, timestamp, parent_id)`
   - **seq 字段（必须）**：全局顺序字段，解决同毫秒 timestamp 导致的顺序不稳定和 parent_id 断链问题
2. **按模式分表 + 兜底表**：
   - 高频模式有独立优化表（messages_chat, messages_image_gen, messages_video_gen）
   - **messages_generic 兜底表（必须）**：覆盖所有其他模式（image-edit/outpainting/pdf-extract/virtual-try-on/deep-research 等）
3. **混合存储策略**：
   - 稳定字段拆分为具体列（role/content/timestamp 等）
   - **复杂结构使用 metadata_json**（grounding/tool/urlContext 等），避免 schema 膨胀与字段缺失
4. **模式特定字段**：每个专用模式表有其专属字段（如 image_gen 的 image_size/image_style，video_gen 的 video_duration/video_fps）
5. **附件共享表**：所有模式共享 message_attachments 表（附件结构统一）
6. **收敛删除机制（必须）**：支持前端删除消息后的快照写回，避免"消息复活"

---

## 数据库表结构

### 表 1: chat_sessions（会话元数据）

重构后移除 `messages` JSON 字段，消息数据完全存储在新表中：

```sql
-- 重构后结构（移除 messages 字段）
CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    persona_id VARCHAR(36) NULL,
    mode VARCHAR(50) NULL,              -- 最近一次活动模式
    created_at BIGINT NOT NULL
    -- ❌ 移除 messages JSON 字段，消息存储在独立表中
);
```

### 表 2: message_index（消息索引表 - 核心路由层）

```sql
CREATE TABLE IF NOT EXISTS message_index (
    id VARCHAR(36) PRIMARY KEY,          -- 消息 ID（对应前端 Message.id）
    session_id VARCHAR(36) NOT NULL,     -- 会话 ID
    mode VARCHAR(50) NOT NULL,           -- 消息模式（chat/image-gen/video-gen...）
    table_name VARCHAR(50) NOT NULL,     -- 物理表名（messages_chat/messages_image_gen/messages_generic）
    seq INTEGER NOT NULL,                -- ✅ 全局顺序（必须）：按前端 messages[] 数组下标赋值
    timestamp BIGINT NOT NULL,           -- 消息时间戳（ms）
    parent_id VARCHAR(36) NULL           -- 链式关联（同模式内）
);

-- 索引
CREATE INDEX idx_message_index_session_seq ON message_index(session_id, seq);  -- ✅ 主排序索引
CREATE INDEX idx_message_index_session_mode_seq ON message_index(session_id, mode, seq);
CREATE INDEX idx_message_index_parent ON message_index(parent_id);
```

**作用**:
- **快速定位**：通过 `id` 查询，直接获取 `table_name`，O(1) 定位到具体模式表
- **跨模式查询**：通过 `session_id` 查询，获取所有模式的消息索引，再批量查询各模式表
- **链式关系**：保存 `parent_id`，支持对话分支管理
- **顺序稳定性（关键修正）**：`seq` 字段确保消息顺序唯一稳定，解决同毫秒 timestamp 问题

### 表 3: messages_chat（chat 模式消息表）

```sql
CREATE TABLE IF NOT EXISTS messages_chat (
    id VARCHAR(36) PRIMARY KEY,          -- Message.id（前端生成 UUIDv4）
    session_id VARCHAR(36) NOT NULL,     -- 会话 ID
    role VARCHAR(20) NOT NULL,           -- 'user' | 'model' | 'system' ✅ 兼容前端
    content TEXT NOT NULL,               -- ✅ 纯文本消息内容
    timestamp BIGINT NOT NULL,           -- 时间戳（ms）
    is_error BOOLEAN DEFAULT FALSE,      -- Message.isError

    -- ✅ 复杂结构使用 JSON 存储（避免 schema 膨胀）
    metadata_json TEXT                   -- groundingMetadata/urlContextMetadata/toolCalls/toolResults 等
);

-- 索引
CREATE INDEX idx_messages_chat_session ON messages_chat(session_id);
```

**说明**:
- `role` 使用 `'model'` 而非 `'assistant'`，严格兼容前端
- **metadata_json（关键修正）**：grounding/tool/urlContext 等复杂结构存为 JSON 字符串，避免字段缺失和频繁改表

### 表 4: messages_image_gen（image-gen 模式消息表）

```sql
CREATE TABLE IF NOT EXISTS messages_image_gen (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,               -- 提示词或生成结果描述
    timestamp BIGINT NOT NULL,
    is_error BOOLEAN DEFAULT FALSE,

    -- ✅ 图像生成特定字段
    image_size VARCHAR(20),              -- 图片尺寸（1024x1024）
    image_style VARCHAR(50),             -- 风格（vivid/natural）
    image_quality VARCHAR(20),           -- 质量（standard/hd）
    image_count INTEGER DEFAULT 1,       -- 生成数量
    model_name VARCHAR(100),             -- 使用的模型

    -- ✅ 复杂结构使用 JSON 存储（与 messages_chat 保持一致）
    metadata_json TEXT                   -- groundingMetadata/urlContextMetadata/toolCalls/toolResults 等
);

CREATE INDEX idx_messages_image_gen_session ON messages_image_gen(session_id);
```

**说明**:
- image-gen 模式有独立的字段（size/style/quality）
- 不与 chat 模式混在一起，性能和扩展性更好
- **`metadata_json` 字段（必须）**：与其他模式表保持一致，避免 upsert 逻辑分支

### 表 5: messages_video_gen（video-gen 模式消息表）

```sql
CREATE TABLE IF NOT EXISTS messages_video_gen (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,               -- 提示词或生成结果描述
    timestamp BIGINT NOT NULL,
    is_error BOOLEAN DEFAULT FALSE,

    -- ✅ 视频生成特定字段
    video_duration INTEGER,              -- 视频时长（秒）
    video_resolution VARCHAR(20),        -- 分辨率（1920x1080）
    video_fps INTEGER,                   -- 帧率
    model_name VARCHAR(100),             -- 使用的模型

    -- ✅ 复杂结构使用 JSON 存储（与 messages_chat 保持一致）
    metadata_json TEXT                   -- groundingMetadata/urlContextMetadata/toolCalls/toolResults 等
);

CREATE INDEX idx_messages_video_gen_session ON messages_video_gen(session_id);
```

### 表 6: messages_generic（兜底表 - 必须）

```sql
CREATE TABLE IF NOT EXISTS messages_generic (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,           -- 'user' | 'model' | 'system' ✅ 兼容前端
    content TEXT NOT NULL,
    timestamp BIGINT NOT NULL,
    is_error BOOLEAN DEFAULT FALSE,

    -- ✅ 使用 JSON 存储模式特定数据
    metadata_json TEXT                   -- 模式特定字段 + 扩展字段
);

CREATE INDEX idx_messages_generic_session ON messages_generic(session_id);
```

**说明（关键修正）**:
- **兜底表覆盖所有其他模式**：image-edit/image-outpainting/audio-gen/pdf-extract/virtual-try-on/deep-research 等
- 避免为每个模式都建专表，降低维护成本
- 后续可按需将高频模式从 generic 迁移到专表

### 表 7: message_attachments（所有模式共享）

```sql
CREATE TABLE IF NOT EXISTS message_attachments (
    id VARCHAR(36) PRIMARY KEY,          -- Attachment.id
    session_id VARCHAR(36) NOT NULL,     -- ✅ 冗余字段，方便按会话查询
    message_id VARCHAR(36) NOT NULL,     -- 所属消息
    mime_type VARCHAR(100),              -- Attachment.mimeType
    name VARCHAR(255),                   -- Attachment.name
    url TEXT,                            -- ✅ 云端/持久 URL（权威来源）
    temp_url TEXT,                       -- Attachment.tempUrl（blob/data/临时链接）
    file_uri TEXT,                       -- ✅ Attachment.fileUri（Google Files API / 多媒体能力依赖）
    upload_status VARCHAR(20) DEFAULT 'pending', -- pending/uploading/completed/failed
    upload_task_id VARCHAR(36),          -- 关联 UploadTask.id
    upload_error TEXT,                   -- 上传失败原因
    google_file_uri VARCHAR(500),        -- Google Files API URI
    google_file_expiry BIGINT,           -- 过期时间（ms）
    size BIGINT                          -- 文件大小
);

-- 索引
CREATE INDEX idx_attachments_message ON message_attachments(message_id);
CREATE INDEX idx_attachments_session ON message_attachments(session_id);
```

**说明**:
- 附件表所有模式共享（不按模式分表）
- 因为附件结构统一，不需要模式特定字段
- **`file_uri` 字段（必须）**：前端 `AttachmentGrid` 展示 URL 采用 `url || tempUrl || fileUri` 优先级，必须持久化

---

## 核心查询示例

### 示例 1: 加载统一会话的全部模式消息（批量优化版 - 必须）

```python
# 1. 从索引表查询会话的所有消息，按 seq 排序
message_indexes = db.query(MessageIndex).filter(
    MessageIndex.session_id == session_id
).order_by(MessageIndex.seq.asc()).all()  # ✅ 使用 seq 而非 timestamp

# 2. 按 table_name 分组，批量查询各模式表（避免 N+1）
messages_by_table = {}
for table_name in set(idx.table_name for idx in message_indexes):
    table_indexes = [idx for idx in message_indexes if idx.table_name == table_name]
    ids = [idx.id for idx in table_indexes]

    table_class = get_message_table_class_by_name(table_name)  # messages_chat/messages_generic...
    messages = db.query(table_class).filter(table_class.id.in_(ids)).all()
    messages_by_table[table_name] = {msg.id: msg for msg in messages}

# 3. 批量查询所有附件（避免 N+1）
all_message_ids = [idx.id for idx in message_indexes]
attachments = db.query(MessageAttachment).filter(
    MessageAttachment.message_id.in_(all_message_ids)
).all()
attachments_by_message = {}
for att in attachments:
    if att.message_id not in attachments_by_message:
        attachments_by_message[att.message_id] = []
    attachments_by_message[att.message_id].append(att)

# 4. 按索引表的 seq 顺序组装（保证顺序稳定）
assembled_messages = []
for idx in message_indexes:
    msg = messages_by_table[idx.table_name][idx.id]
    msg_dict = msg.to_dict()

    # ✅ 从索引表补回 mode 字段（模式表不存储 mode，前端依赖此字段做过滤）
    msg_dict['mode'] = idx.mode

    # 附加附件
    if idx.id in attachments_by_message:
        msg_dict['attachments'] = [att.to_dict() for att in attachments_by_message[idx.id]]

    assembled_messages.append(msg_dict)
```

**性能分析（关键修正）**:
- 索引表查询：O(1) 单表查询，有 `session_id + seq` 索引
- 模式表查询：O(k) 其中 k 为不同 table_name 数量，每个查询有 `id IN (...)` 批量查询
- 附件查询：O(1) 批量查询，有 `message_id IN (...)` + 索引
- **总体复杂度**: O(n)，且无 N+1 问题

### 示例 2: 查询单条消息（例如附件更新）

```python
# 1. 从索引表定位消息所在表
index = db.query(MessageIndex).filter(MessageIndex.id == message_id).first()
if not index:
    raise HTTPException(status_code=404, detail="消息不存在")

# 2. 根据 table_name 查询具体消息
table_class = get_message_table_class_by_name(index.table_name)
message = db.query(table_class).filter(table_class.id == message_id).first()

# 3. 查询附件
attachments = db.query(MessageAttachment).filter(
    MessageAttachment.message_id == message_id
).all()
```

**性能分析**:
- 索引表查询：O(1) 主键查询
- 模式表查询：O(1) 主键查询
- 附件查询：O(1) 索引查询
- **总体复杂度**: O(1)

### 示例 3: 更新附件 URL（上传 Worker）

```python
# v1/v2: 复杂的 JSON 操作（upload_worker_pool.py:701-749）
messages = copy.deepcopy(session.messages or [])
for msg in messages:
    if msg.get('id') == message_id and msg.get('attachments'):
        for att in msg['attachments']:
            if att.get('id') == attachment_id:
                att['url'] = url  # 找到了！
session.messages = messages
flag_modified(session, 'messages')
db.commit()  # 重写整个 JSON

# v3: 简洁的单行更新
db.query(MessageAttachment).filter(
    MessageAttachment.id == attachment_id
).update({
    "url": url,
    "upload_status": "completed",
    "temp_url": None
})
db.commit()  # 只更新一行
```

**代码复杂度降低**: ~90%（从 50 行深拷贝 + 遍历 + 重试，到 5 行单行 UPDATE）

---

## 模式隔离与链式关联

### 模式隔离示例

```
会话 session-001:

  [chat 模式 - 独立链]
  msg-001 (user, chat)       parent_id=NULL    ← chat 根消息
  msg-002 (model, chat)      parent_id=msg-001
  msg-003 (user, chat)       parent_id=msg-002

  [image-gen 模式 - 独立链]
  msg-004 (user, image-gen)  parent_id=NULL    ← image-gen 根消息
  msg-005 (model, image-gen) parent_id=msg-004

  [video-gen 模式 - 独立链]
  msg-006 (user, video-gen)  parent_id=NULL    ← video-gen 根消息
  msg-007 (model, video-gen) parent_id=msg-006
```

**规则**:
- 每个模式的第一条消息 `parent_id = NULL`
- 同模式内通过 `parent_id` 链式关联
- 查询时按 `(session_id, mode)` 组合获取特定模式的对话链

### parent_id 构建逻辑（基于内存 - 必须）

**⚠️ 重要**：`parent_id` 必须在内存中构建，而非查询数据库。因为在 upsert 循环中，新插入的消息尚未 `flush` 到数据库，查询 DB 会导致 `parent_id` 全为 `NULL`。

```python
# ❌ 错误方式：查询数据库（会导致 parent_id 全为 NULL）
def build_parent_id_wrong(session_id: str, mode: str, new_seq: int, db: Session) -> str | None:
    """
    ❌ 不要使用此方式！
    在 upsert 循环中查询 DB，新插入的消息尚未 flush，会导致 parent_id 断链
    """
    last_message = db.query(MessageIndex).filter(
        MessageIndex.session_id == session_id,
        MessageIndex.mode == mode,
        MessageIndex.seq < new_seq
    ).order_by(MessageIndex.seq.desc()).first()
    return last_message.id if last_message else None


# ✅ 正确方式：在内存中追踪每个模式的最后一条消息
# 在 save_session 函数中使用 mode_last_msg 字典
mode_last_msg: dict[str, str] = {}  # {mode: last_msg_id}

for seq, msg in enumerate(new_messages):
    mode = msg.get("mode", "chat")
    
    # ✅ 从内存获取 parent_id（同模式的上一条消息）
    parent_id = mode_last_msg.get(mode)  # 第一条消息为 None
    
    # ... upsert 逻辑 ...
    
    # ✅ 更新内存记录
    mode_last_msg[mode] = msg["id"]
```

**关键修正说明**:
- ✅ 使用内存字典 `mode_last_msg` 追踪每个模式的最后一条消息 ID
- ✅ 避免在 upsert 循环中查询数据库，解决时序问题
- ✅ `seq` 按前端 `messages[]` 数组下标赋值，确保顺序唯一稳定
- ✅ 每个模式的第一条消息 `parent_id = None`，后续消息指向同模式的上一条

### 消息删除与编辑场景（关键修正 - 必须）

#### 场景 1：删除消息（成对删除 - 当前前端行为）

**设计原则**：当前前端删除消息采用**成对删除**策略：删除 MODEL 消息时会连同前一条同 mode 的 USER 消息一起删除，但**不会级联删除后续消息**。后端应当能正确收敛任意子集删除，并对剩余消息重建 `seq/parent_id`。

**前端行为**（当前实现 - `App.tsx` `handleDeleteMessage`）：
```typescript
// 用户删除某条消息（成对删除）
function handleDeleteMessage(sessionId: string, messageId: string) {
    const session = getSession(sessionId);
    const msgIndex = session.messages.findIndex(m => m.id === messageId);
    const msg = session.messages[msgIndex];

    // ✅ 成对删除：如果是 MODEL 消息，连同前一条同 mode 的 USER 消息一起删除
    let idsToDelete = [messageId];
    if (msg.role === 'model' && msgIndex > 0) {
        const prevMsg = session.messages[msgIndex - 1];
        if (prevMsg.role === 'user' && prevMsg.mode === msg.mode) {
            idsToDelete.push(prevMsg.id);
        }
    }

    // 过滤掉要删除的消息（不删除后续消息）
    const newMessages = session.messages.filter(m => !idsToDelete.includes(m.id));

    // 发送新快照
    await saveSession({
        ...session,
        messages: newMessages
    });
}
```

**后端行为**（收敛删除机制 - 适配任意删除模式）：
```python
# 1. 计算需要删除的消息 ID（以前端快照为准）
posted_ids = {msg["id"] for msg in new_messages}
existing_indexes = db.query(MessageIndex).filter(
    MessageIndex.session_id == session_id
).all()
existing_ids = {idx.id for idx in existing_indexes}

deleted_ids = existing_ids - posted_ids  # ✅ 自动检测出前端已删除的消息

# 2. 批量删除（无论前端是成对删除还是级联删除，后端统一处理）
if deleted_ids:
    # 按 table_name 分组批量删除模式表消息
    for table_name, ids in tables_to_delete.items():
        table_class = get_message_table_class_by_name(table_name)
        db.query(table_class).filter(table_class.id.in_(ids)).delete(synchronize_session=False)

    # 删除索引表
    db.query(MessageIndex).filter(MessageIndex.id.in_(deleted_ids)).delete(synchronize_session=False)

    # 级联删除附件
    db.query(MessageAttachment).filter(MessageAttachment.message_id.in_(deleted_ids)).delete(synchronize_session=False)

# 3. 为保留消息重建 seq 和 parent_id 链
for seq, msg in enumerate(new_messages):
    index = db.query(MessageIndex).get(msg["id"])
    if index:
        index.seq = seq  # ✅ 按新顺序更新 seq
        # parent_id 在内存中重建（见 mode_last_msg 逻辑）
```

**示例流程（成对删除）**：
```
初始状态（seq=0-3）：
  msg-001 (user, chat)  seq=0, parent_id=NULL
  msg-002 (model, chat) seq=1, parent_id=msg-001
  msg-003 (user, chat)  seq=2, parent_id=msg-002
  msg-004 (model, chat) seq=3, parent_id=msg-003

用户删除 msg-004（MODEL）后：
  前端操作：成对删除 msg-003(USER) + msg-004(MODEL)
  前端发送：[msg-001, msg-002]

后端处理：
  计算 deleted_ids = {msg-003, msg-004}
  批量删除：msg-003, msg-004（含附件）
  重建 seq：msg-001.seq=0, msg-002.seq=1
  重建 parent_id：msg-002.parent_id=msg-001（保持不变）

最终状态（seq=0-1）：
  msg-001 (user, chat)  seq=0, parent_id=NULL
  msg-002 (model, chat) seq=1, parent_id=msg-001
```

**关键点**：
- ✅ **后端以快照为准**：无论前端是成对删除、级联删除还是任意删除，后端统一按 `existing_ids - posted_ids` 处理
- ✅ **重建 seq/parent_id**：对剩余消息按新顺序重建，确保链式关系正确
- ✅ **模式隔离**：每个模式维护独立的 `parent_id` 链，删除互不影响
- ⚠️ **注意**：当前前端是"成对删除"，不是"级联删除后续"，后端设计应兼容两种模式

#### 场景 2：编辑消息内容（保持后续消息）

**设计原则**：用户编辑某条消息的文本内容时，不影响后续消息，仅更新该消息本身。

**前端行为**：
```typescript
// 用户编辑 msg-002 的内容
function editMessage(sessionId: string, messageId: string, newContent: string) {
    const session = getSession(sessionId);

    // ✅ 更新目标消息内容
    const updatedMessages = session.messages.map(msg =>
        msg.id === messageId
            ? { ...msg, content: newContent }
            : msg
    );

    // 发送完整快照（包含所有消息，目标消息的 content 已更新）
    await saveSession({
        ...session,
        messages: updatedMessages
    });
}
```

**后端行为**（upsert 更新）：
```python
# 1. 没有消息被删除（posted_ids == existing_ids）
posted_ids = {msg["id"] for msg in new_messages}
existing_ids = {idx.id for idx in existing_indexes}
deleted_ids = existing_ids - posted_ids  # 空集合

# 2. upsert 更新消息内容
for seq, msg in enumerate(new_messages):
    msg_id = msg["id"]

    # upsert 模式表
    table_class = get_message_table_class_by_name(index.table_name)
    message = db.query(table_class).get(msg_id)
    if message:
        message.content = msg["content"]  # ✅ 更新内容
        message.is_error = msg.get("isError", False)
        message.metadata_json = json.dumps(extract_metadata(msg))

    # parent_id 链保持不变（seq 未变）
    index = db.query(MessageIndex).get(msg_id)
    if index:
        index.seq = seq  # seq 未变
        index.parent_id = build_parent_id(session_id, index.mode, seq)  # parent_id 未变
```

**示例流程**：
```
初始状态：
  msg-001 (user, chat)  content="你好"
  msg-002 (model, chat) content="你好！"
  msg-003 (user, chat)  content="再见"
  msg-004 (model, chat) content="再见！"

用户编辑 msg-003 内容为"谢谢"：
  前端操作：msg-003.content = "谢谢"
  前端发送：[msg-001, msg-002, msg-003(谢谢), msg-004]

后端处理：
  计算 deleted_ids = {} （空集合）
  upsert msg-003: content="谢谢"
  parent_id 链保持不变

最终状态：
  msg-001 (user, chat)  content="你好"
  msg-002 (model, chat) content="你好！"
  msg-003 (user, chat)  content="谢谢" ✅ 已更新
  msg-004 (model, chat) content="再见！"
```

**关键点**：
- ✅ **只更新消息内容**：`content`、`isError`、`metadata_json` 等字段
- ✅ **保持所有消息**：前端发送完整快照，后端无删除操作
- ✅ **parent_id 链不变**：seq 顺序未变，链式关系维持
- ⚠️ **注意**：如果编辑后希望重新生成 AI 回答，应删除后续消息（走场景 1）

#### 场景 3：跨模式删除（独立链不影响）

**设计原则**：删除某个模式的消息时，不影响其他模式的对话链。

**示例流程**：
```
会话 session-001:
  [chat 模式]
  msg-001 (user, chat)  seq=0
  msg-002 (model, chat) seq=1

  [image-gen 模式]
  msg-003 (user, image-gen)  seq=2
  msg-004 (model, image-gen) seq=3

用户删除 msg-003（image-gen 模式）：
  前端操作：filter(msg => msg.id !== 'msg-003' && msg.id !== 'msg-004')
  前端发送：[msg-001, msg-002]

后端处理：
  deleted_ids = {msg-003, msg-004}
  删除 messages_image_gen 表中的 msg-003, msg-004
  chat 模式链不受影响（msg-001, msg-002 保持不变）

最终状态：
  [chat 模式] ✅ 完整保留
  msg-001 (user, chat)  seq=0
  msg-002 (model, chat) seq=1

  [image-gen 模式] ✅ 已清空
  （无消息）
```

**关键点**：
- ✅ **模式隔离**：每个模式维护独立的 `parent_id` 链，删除互不影响
- ✅ **收敛删除机制自动处理**：后端无需感知模式，只需检测 `existing_ids - posted_ids`

---

## API 兼容策略（前端零改动）

### GET /api/sessions

返回结构保持不变：

```json
[
  {
    "id": "xxx",
    "title": "xxx",
    "messages": [...],  // 从 message_index + 各模式表 + message_attachments 组装
    "createdAt": 123,
    "personaId": "xxx",
    "mode": "chat"
  }
]
```

**后端实现要点**:
- 会话列表来自 `chat_sessions`
- `messages` 由 `message_index` 路由到各模式表，组装时合并所有模式
- 附件通过 `message_attachments` 批量 JOIN（避免 N+1）
- **按 `seq ASC` 排序确保顺序正确**（关键修正：不是 timestamp）

### POST /api/sessions（保存会话 + 收敛删除 - 必须）

保持接收前端原始结构不变，内部实现收敛删除 + 增量 upsert：

```python
def save_session(session_data: dict, db: Session):
    session_id = session_data["id"]
    new_messages = session_data.get("messages", [])

    # 1. upsert chat_sessions
    session = db.query(ChatSession).get(session_id)
    if not session:
        session = ChatSession(
            id=session_id,
            title=session_data["title"],
            persona_id=session_data.get("personaId"),
            mode=session_data.get("mode"),
            created_at=session_data["createdAt"]
        )
        db.add(session)
    else:
        session.title = session_data["title"]

    # 2. 收敛删除（必须）：以前端快照为权威
    posted_ids = {msg["id"] for msg in new_messages}

    # 查询数据库现有消息 ID
    existing_indexes = db.query(MessageIndex).filter(
        MessageIndex.session_id == session_id
    ).all()
    existing_ids = {idx.id for idx in existing_indexes}

    # 删除前端已移除的消息
    deleted_ids = existing_ids - posted_ids
    if deleted_ids:
        # 按 table_name 分组批量删除
        deleted_indexes = [idx for idx in existing_indexes if idx.id in deleted_ids]
        tables_to_delete = {}
        for idx in deleted_indexes:
            if idx.table_name not in tables_to_delete:
                tables_to_delete[idx.table_name] = []
            tables_to_delete[idx.table_name].append(idx.id)

        # ✅ 先查询需要取消的上传任务（必须在删除附件之前）
        deleted_attachment_ids = [att.id for att in db.query(MessageAttachment).filter(
            MessageAttachment.message_id.in_(deleted_ids)
        ).all()]

        # ✅ 取消关联的上传任务（避免孤儿记录）
        if deleted_attachment_ids:
            db.query(UploadTask).filter(
                UploadTask.attachment_id.in_(deleted_attachment_ids)
            ).update({
                "status": "cancelled",
                "error_message": "附件已被删除"
            }, synchronize_session=False)

        # 删除模式表消息
        for table_name, ids in tables_to_delete.items():
            table_class = get_message_table_class_by_name(table_name)
            db.query(table_class).filter(table_class.id.in_(ids)).delete(synchronize_session=False)

        # 删除索引表和附件（在取消 UploadTask 之后）
        db.query(MessageIndex).filter(MessageIndex.id.in_(deleted_ids)).delete(synchronize_session=False)
        db.query(MessageAttachment).filter(MessageAttachment.message_id.in_(deleted_ids)).delete(synchronize_session=False)

    # 3. 增量 upsert 消息（使用内存构建 parent_id）
    mode_last_msg: dict[str, str] = {}  # ✅ 内存追踪每个模式的最后一条消息 ID

    for seq, msg in enumerate(new_messages):
        msg_id = msg["id"]
        mode = msg.get("mode", "chat")
        timestamp = msg["timestamp"]

        # 确定 table_name
        table_name = get_table_name_for_mode(mode)  # 'messages_chat'/'messages_generic'...

        # ✅ 从内存获取 parent_id（而非查询 DB）
        parent_id = mode_last_msg.get(mode)  # 同模式的上一条消息，第一条为 None

        # upsert message_index
        index = db.query(MessageIndex).get(msg_id)
        if not index:
            index = MessageIndex(
                id=msg_id,
                session_id=session_id,
                mode=mode,
                table_name=table_name,
                seq=seq,  # ✅ 使用数组下标
                timestamp=timestamp,
                parent_id=parent_id
            )
            db.add(index)
        else:
            index.seq = seq
            index.parent_id = parent_id

        # upsert 模式表
        table_class = get_message_table_class_by_name(table_name)
        message = db.query(table_class).get(msg_id)
        if not message:
            message = table_class(
                id=msg_id,
                session_id=session_id,
                role=msg["role"],
                content=msg["content"],
                timestamp=timestamp,
                is_error=msg.get("isError", False),
                metadata_json=json.dumps(extract_metadata(msg))  # ✅ 存为 JSON 字符串
            )
            db.add(message)
        else:
            message.content = msg["content"]
            message.is_error = msg.get("isError", False)
            message.metadata_json = json.dumps(extract_metadata(msg))

        # upsert 附件（关键修正：强化云 URL 保护）
        for att in msg.get("attachments", []):
            att_id = att["id"]

            # ✅ 步骤 1：从 UploadTask 查询权威云 URL（最高优先级）
            task = db.query(UploadTask).filter(
                UploadTask.session_id == session_id,
                UploadTask.attachment_id == att_id,
                UploadTask.status == 'completed',
                UploadTask.target_url.isnot(None)
            ).first()

            # ✅ 步骤 2：确定权威 URL（优先级：UploadTask > 旧附件 > 前端）
            attachment = db.query(MessageAttachment).get(att_id)

            authoritative_url = None
            if task and task.target_url:
                authoritative_url = task.target_url  # ✅ 最高优先级：已完成的上传任务
            elif attachment and attachment.url and attachment.url.startswith('http'):
                authoritative_url = attachment.url  # ✅ 次优先级：数据库已有的云 URL

            # ✅ 步骤 3：处理前端发送的 URL
            new_url = att.get("url", "")
            # 如果前端 URL 是临时 URL（blob/data），使用权威 URL
            if not new_url or new_url.startswith("blob:") or new_url.startswith("data:"):
                final_url = authoritative_url or new_url  # 有权威 URL 则使用，否则保留临时 URL
            else:
                # 前端发送的是永久 URL（http/https），直接使用
                final_url = new_url

            # ✅ 步骤 4：upsert 附件表
            if not attachment:
                # 创建新附件
                attachment = MessageAttachment(
                    id=att_id,
                    session_id=session_id,
                    message_id=msg_id,
                    mime_type=att.get("mimeType"),
                    name=att.get("name"),
                    url=final_url,  # ✅ 使用权威 URL
                    temp_url=att.get("tempUrl"),
                    upload_status=att.get("uploadStatus", "pending"),
                    upload_task_id=task.id if task else None,
                    google_file_uri=att.get("googleFileUri"),
                    google_file_expiry=att.get("googleFileExpiry"),
                    size=att.get("size")
                )
                db.add(attachment)
            else:
                # 更新附件（只在有云 URL 时更新）
                if final_url and final_url.startswith('http'):
                    attachment.url = final_url
                    attachment.upload_status = 'completed'
                    attachment.temp_url = None  # 清除临时 URL
                # 如果 final_url 仍是 blob/data，保持原有 URL 不变

        # ✅ 更新内存记录
        mode_last_msg[mode] = msg_id

    db.commit()
```

**关键修正说明**:
- **收敛删除（必须）**：计算 `existing_ids - posted_ids`，删除前端已移除的消息
- **seq 赋值（必须）**：使用数组下标 `enumerate(new_messages)` 作为 seq
- **parent_id 内存构建（必须）**：使用 `mode_last_msg` 字典在内存中追踪每个模式的最后一条消息 ID，避免查询未 flush 的数据库
- **UploadTask 级联处理（必须）**：收敛删除时同时取消关联的上传任务，避免孤儿记录

### GET /api/sessions/{id}/attachments/{att_id}

不再扫描 `session.messages` JSON；直接查询 `message_attachments`：

```python
# 直接定位附件
attachment = db.query(MessageAttachment).filter(
    MessageAttachment.session_id == session_id,
    MessageAttachment.id == attachment_id
).first()

if not attachment:
    raise HTTPException(status_code=404, detail="附件不存在")

# 若存在 upload_task_id，可联查 UploadTask 追加任务状态
if attachment.upload_task_id:
    task = db.query(UploadTask).filter(
        UploadTask.id == attachment.upload_task_id
    ).first()
    if task and task.status == 'completed' and task.target_url:
        attachment.url = task.target_url

return attachment.to_dict()
```

---

## 云 URL 写入逻辑（关键修正 - 必须）

### 问题描述

**核心矛盾**：Worker 完成上传后写入云 URL 的时机 vs 前端保存会话的时机不同步。

**时间线问题**：
```
T1: 前端发送消息（附件 URL 为 blob:xxx）
T2: 后端保存会话到 message_attachments（url = blob:xxx）
T3: Worker 完成上传（url = https://img.dicry.com/xxx.png）
T4: Worker 更新 message_attachments 表
T5: 前端再次保存会话（可能用 blob URL 覆盖云 URL）❌ 风险
```

### URL 权威来源优先级（必须严格遵守）

**优先级规则**：
1. **UploadTask.target_url**（最高优先级）- Worker 完成上传后的云 URL
2. **MessageAttachment.url**（次优先级）- 数据库已有的云 URL
3. **前端发送的 URL**（最低优先级）- 可能是 blob/data 临时 URL

**判断逻辑**：
```python
def get_authoritative_url(session_id: str, attachment_id: str, frontend_url: str, db: Session) -> str:
    """
    获取附件的权威 URL

    优先级：UploadTask > MessageAttachment > frontend_url
    """
    # 1. 查询 UploadTask（最高优先级）
    task = db.query(UploadTask).filter(
        UploadTask.session_id == session_id,
        UploadTask.attachment_id == attachment_id,
        UploadTask.status == 'completed',
        UploadTask.target_url.isnot(None)
    ).first()

    if task and task.target_url:
        return task.target_url  # ✅ 使用 Worker 上传的云 URL

    # 2. 查询 MessageAttachment（次优先级）
    attachment = db.query(MessageAttachment).get(attachment_id)
    if attachment and attachment.url and attachment.url.startswith('http'):
        return attachment.url  # ✅ 使用数据库已有的云 URL

    # 3. 前端 URL（最低优先级）
    if frontend_url and frontend_url.startswith('http'):
        return frontend_url  # ✅ 前端发送的是永久 URL

    # 4. 保留临时 URL（无云 URL 可用时）
    return frontend_url  # blob/data URL
```

### POST /api/sessions 云 URL 保护逻辑

**基于当前代码优化**（参考 `current_cloud_url_write_analysis.md`）：

**当前代码逻辑** (`sessions.py:53-126`):
```python
# 步骤 1：收集当前活动的附件 ID
current_attachment_keys = set()  # (msg_id, att_id)
for msg in new_messages:
    msg_id = msg.get('id')
    for att in msg.get('attachments', []):
        att_id = att.get('id')
        if att_id:
            current_attachment_keys.add((msg_id, att_id))

# 步骤 2：从旧消息中提取当前活动附件的云 URL
old_attachment_urls = {}
for msg in old_messages:
    msg_id = msg.get('id')
    for att in msg.get('attachments', []):
        att_id = att.get('id')
        key = (msg_id, att_id)
        if key in current_attachment_keys:  # ✅ 只处理当前存在的附件
            att_url = att.get('url', '')
            if att_url and att_url.startswith('http'):  # ✅ 只保存云 URL
                old_attachment_urls[key] = {
                    'url': att_url,
                    'status': att.get('uploadStatus', 'completed')
                }

# 步骤 3：从 UploadTask 补充云 URL（❌ 当前优先级过低）
current_attachment_ids = [key[1] for key in current_attachment_keys]
if current_attachment_ids:
    completed_tasks = db.query(UploadTask).filter(
        UploadTask.session_id == session_id,
        UploadTask.attachment_id.in_(current_attachment_ids),
        UploadTask.status == 'completed',
        UploadTask.target_url.isnot(None)
    ).all()

    for task in completed_tasks:
        key = (task.message_id, task.attachment_id)
        if key not in old_attachment_urls:  # ❌ 只在不存在时添加
            old_attachment_urls[key] = {
                'url': task.target_url,
                'status': 'completed'
            }
```

**✅ 优化后逻辑**（UploadTask 最高优先级）:
```python
# 步骤 3（优化）：从 UploadTask 补充/覆盖云 URL（最高优先级）
current_attachment_ids = [key[1] for key in current_attachment_keys]
if current_attachment_ids:
    completed_tasks = db.query(UploadTask).filter(
        UploadTask.session_id == session_id,
        UploadTask.attachment_id.in_(current_attachment_ids),
        UploadTask.status == 'completed',
        UploadTask.target_url.isnot(None)
    ).all()

    for task in completed_tasks:
        key = (task.message_id, task.attachment_id)
        # ✅ 无条件覆盖，UploadTask 是权威来源
        old_attachment_urls[key] = {
            'url': task.target_url,
            'status': 'completed',
            'source': 'upload_task'  # 标记来源
        }

# 步骤 4：合并新消息，保留已上传的云 URL（保持不变）
merged_messages = []
merge_count = 0
for msg in new_messages:
    msg_copy = copy.deepcopy(msg)
    msg_id = msg_copy.get('id')

    for att in msg_copy.get('attachments', []):
        att_id = att.get('id')
        key = (msg_id, att_id)

        if key in old_attachment_urls:
            new_url = att.get('url', '')
            old_data = old_attachment_urls[key]
            # ✅ 新 URL 为空、Blob URL 或 Base64 时，使用云 URL
            if not new_url or new_url.startswith('blob:') or new_url.startswith('data:'):
                att['url'] = old_data['url']
                att['uploadStatus'] = 'completed'
                merge_count += 1

    merged_messages.append(msg_copy)

session.messages = merged_messages
```

**关键优化点**：
1. ✅ **UploadTask 最高优先级**：无条件覆盖旧消息 URL（是权威来源）
2. ✅ **解决 Worker 更新失败补偿**：即使 Worker 未更新成功，下次保存时自动修复
3. ✅ **三重保护机制**：旧消息 URL → UploadTask 覆盖 → 合并保护
4. ✅ **只处理当前活动附件**：避免处理已删除的历史附件（性能优化）

**v3 新表实现**（与当前逻辑对齐）:
```python
# upsert 附件（v3 新表实现）
for att in msg.get("attachments", []):
    att_id = att["id"]

    # ✅ 步骤 1：从 UploadTask 查询权威云 URL（最高优先级）
    task = db.query(UploadTask).filter(
        UploadTask.session_id == session_id,
        UploadTask.attachment_id == att_id,
        UploadTask.status == 'completed',
        UploadTask.target_url.isnot(None)
    ).first()

    # ✅ 步骤 2：确定权威 URL（优先级：UploadTask > 旧附件 > 前端）
    attachment = db.query(MessageAttachment).get(att_id)

    authoritative_url = None
    if task and task.target_url:
        authoritative_url = task.target_url  # ✅ 最高优先级：UploadTask
    elif attachment and attachment.url and attachment.url.startswith('http'):
        authoritative_url = attachment.url  # ✅ 次优先级：数据库已有云 URL

    # ✅ 步骤 3：处理前端发送的 URL
    new_url = att.get("url", "")
    if not new_url or new_url.startswith("blob:") or new_url.startswith("data:"):
        final_url = authoritative_url or new_url  # 优先使用权威 URL
    else:
        final_url = new_url  # 前端发送的是永久 URL

    # ✅ 步骤 4：upsert 附件表
    if not attachment:
        attachment = MessageAttachment(
            id=att_id,
            session_id=session_id,
            message_id=msg_id,
            url=final_url,  # ✅ 使用权威 URL
            upload_task_id=task.id if task else None,
            # ...
        )
        db.add(attachment)
    else:
        # 只在有云 URL 时更新
        if final_url and final_url.startswith('http'):
            attachment.url = final_url
            attachment.upload_status = 'completed'
            attachment.temp_url = None
        # ❌ 如果 final_url 仍是 blob/data，保持原有 URL 不变
```

### Worker 云 URL 更新逻辑

**upload_worker_pool.py 修改**（简化版 - 直接更新新表）：

```python
async def _update_session_attachment(
    self, db, session_id: str, message_id: str, attachment_id: str, url: str, worker_name: str
):
    """
    更新会话附件（直接更新新表）

    重构后只需更新 message_attachments 表，无需处理旧 JSON
    """
    from ..models.db_models import MessageAttachment

    # ✅ 单行更新，替代原来 50+ 行复杂逻辑
    updated_count = db.query(MessageAttachment).filter(
        MessageAttachment.id == attachment_id
    ).update({
        "url": url,  # ✅ 云 URL
        "upload_status": "completed",
        "temp_url": None  # 清除临时 URL
    })

    if updated_count > 0:
        db.commit()
        log_print(f"[{worker_name}] ✅ 附件 URL 已更新: {url[:60]}...")
    else:
        log_print(f"[{worker_name}] ⚠️ 未找到附件 {attachment_id[:8]}...", "WARNING")
```

**收益**：
- 代码行数：50+ 行 → 10 行
- 复杂度：深拷贝 + 遍历 + 重试 → 单行 UPDATE
- 性能：O(n) JSON 解析 → O(1) 索引更新
- 无需处理 JSON 字段的并发更新问题
### 验证云 URL 正确性

**验证脚本**：
```python
def verify_cloud_urls(session_id: str, db: Session) -> bool:
    """
    验证会话中所有附件都有云 URL

    返回：True 表示所有附件都有云 URL，False 表示有附件缺失云 URL
    """
    attachments = db.query(MessageAttachment).filter(
        MessageAttachment.session_id == session_id
    ).all()

    missing_cloud_urls = []
    for att in attachments:
        if not att.url or not att.url.startswith('http'):
            missing_cloud_urls.append({
                'id': att.id,
                'url': att.url,
                'upload_status': att.upload_status,
                'upload_task_id': att.upload_task_id
            })

    if missing_cloud_urls:
        print(f"⚠️ 会话 {session_id[:8]}... 有 {len(missing_cloud_urls)} 个附件缺失云 URL:")
        for att in missing_cloud_urls:
            print(f"  - {att['id'][:8]}...: url={att['url'][:30] if att['url'] else 'None'}..., status={att['upload_status']}")
        return False

    print(f"✅ 会话 {session_id[:8]}... 所有 {len(attachments)} 个附件都有云 URL")
    return True
```

### 常见问题排查

**问题 1：历史对话图片无法加载**

**原因**：`message_attachments.url` 仍是 blob URL

**排查**：
```sql
-- 查询所有非云 URL 的附件
SELECT id, url, upload_status, upload_task_id
FROM message_attachments
WHERE url NOT LIKE 'http%' OR url IS NULL;
```

**修复**：
```python
# 从 UploadTask 回填云 URL
attachments = db.query(MessageAttachment).filter(
    or_(
        MessageAttachment.url.is_(None),
        MessageAttachment.url.notlike('http%')
    )
).all()

for att in attachments:
    task = db.query(UploadTask).filter(
        UploadTask.attachment_id == att.id,
        UploadTask.status == 'completed',
        UploadTask.target_url.isnot(None)
    ).first()

    if task and task.target_url:
        att.url = task.target_url
        att.upload_status = 'completed'
        print(f"✅ 回填云 URL: {att.id[:8]}... -> {task.target_url[:60]}...")

db.commit()
```

**问题 2：Worker 更新后前端仍显示 blob URL**

**原因**：前端保存会话时用 blob URL 覆盖了云 URL

**排查**：检查 `POST /api/sessions` 是否正确实现云 URL 保护逻辑

**修复**：确保 `sessions.py` 附件 upsert 逻辑查询 `UploadTask` 获取权威 URL

---

## 与 UploadTask/异步上传的集成

### Worker 更新逻辑（简化版）

重构后 Worker 只需更新 `message_attachments` 表：

1. Worker 完成上传后更新 `UploadTask.target_url/status`（保持不变）
2. **更新新表**：`message_attachments.url/upload_status`
3. **无需处理旧 JSON**：消息数据完全存储在新表中

```python
def update_attachment_url(attachment_id: str, url: str, db: Session):
    """更新附件 URL（简化版）"""
    db.query(MessageAttachment).filter(
        MessageAttachment.id == attachment_id
    ).update({
        "url": url,
        "upload_status": "completed",
        "temp_url": None
    })
    db.commit()
```

**收益**:
- 代码行数：50+ 行 → 5 行
- 复杂度：深拷贝 + 遍历 + 重试 → 单行 UPDATE
- 性能：O(n) JSON 解析 → O(1) 索引更新
- 无并发更新冲突风险

---

## 数据迁移策略（直接迁移方案）

### 迁移流程概述

采用**直接迁移**方案，无双写期：

```
阶段 A（准备）：创建新表
├─ 创建 6 个新表（DDL）
├─ 备份数据库（必须）
└─ 准备迁移脚本

阶段 B（迁移）：停机迁移
├─ 停止后端服务
├─ 执行迁移脚本：旧 JSON → 新表
├─ 删除 chat_sessions.messages 字段
└─ 部署新代码

阶段 C（上线）：启动服务
├─ 启动后端服务
├─ 验证功能正常
└─ 监控性能指标
```

### 阶段 A: 创建新表

```sql
-- 1. 创建 message_index 索引表
CREATE TABLE IF NOT EXISTS message_index (...);

-- 2. 创建模式表
CREATE TABLE IF NOT EXISTS messages_chat (...);
CREATE TABLE IF NOT EXISTS messages_image_gen (...);
CREATE TABLE IF NOT EXISTS messages_video_gen (...);
CREATE TABLE IF NOT EXISTS messages_generic (...);

-- 3. 创建附件表
CREATE TABLE IF NOT EXISTS message_attachments (...);
```

### 阶段 B: 全量迁移

编写迁移脚本 `run_chat_storage_migration_v3.py`：

```python
def migrate_session_to_v3(session: ChatSession, db: Session):
    """迁移单个会话"""
    messages = session.messages or []
    if not messages:
        return

    # 内存追踪每个模式的最后一条消息 ID
    mode_last_msg: dict[str, str] = {}

    for seq, msg in enumerate(messages):
        msg_id = msg['id']
        mode = msg.get('mode', 'chat')
        timestamp = msg['timestamp']
        table_name = get_table_name_for_mode(mode)

        # ✅ 从内存获取 parent_id
        parent_id = mode_last_msg.get(mode)

        # 插入索引表
        db.add(MessageIndex(
            id=msg_id,
            session_id=session.id,
            mode=mode,
            table_name=table_name,
            seq=seq,
            timestamp=timestamp,
            parent_id=parent_id
        ))

        # 插入模式表
        table_class = get_message_table_class_by_name(table_name)
        db.add(table_class(
            id=msg_id,
            session_id=session.id,
            role=msg['role'],
            content=msg['content'],
            timestamp=timestamp,
            is_error=msg.get('isError', False),
            metadata_json=json.dumps(extract_metadata(msg))
        ))

        # 迁移附件
        for att in msg.get('attachments', []):
            db.add(MessageAttachment(
                id=att['id'],
                session_id=session.id,
                message_id=msg_id,
                mime_type=att.get('mimeType'),
                name=att.get('name'),
                url=att.get('url'),
                temp_url=att.get('tempUrl'),
                upload_status=att.get('uploadStatus', 'pending'),
                google_file_uri=att.get('googleFileUri'),
                google_file_expiry=att.get('googleFileExpiry'),
                size=att.get('size')
            ))

        # ✅ 更新内存记录
        mode_last_msg[mode] = msg_id

    db.commit()


def run_migration(db: Session):
    """执行全量迁移"""
    sessions = db.query(ChatSession).all()
    total = len(sessions)
    
    for i, session in enumerate(sessions):
        try:
            migrate_session_to_v3(session, db)
            print(f"[{i+1}/{total}] ✅ 迁移会话 {session.id[:8]}...")
        except Exception as e:
            print(f"[{i+1}/{total}] ❌ 迁移失败 {session.id[:8]}...: {e}")
            db.rollback()
            raise
    
    print(f"✅ 全部 {total} 个会话迁移完成")
```

### 阶段 C: 删除旧字段

迁移完成后，删除 `chat_sessions.messages` 字段：

```sql
-- 确认迁移成功后执行
ALTER TABLE chat_sessions DROP COLUMN messages;
```

#### SQLite 兼容性说明

⚠️ **SQLite 版本限制**：`DROP COLUMN` 语法仅在 SQLite 3.35.0+ (2021-03-12) 支持。

**检查 SQLite 版本**：
```python
import sqlite3
print(sqlite3.sqlite_version)  # 需要 >= 3.35.0
```

**低版本 SQLite 替代方案**（若版本 < 3.35.0）：
```sql
-- 1. 创建不含 messages 字段的新表
CREATE TABLE chat_sessions_new (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255),
    persona_id VARCHAR(36),
    mode VARCHAR(50),
    created_at BIGINT
);

-- 2. 复制数据
INSERT INTO chat_sessions_new (id, title, persona_id, mode, created_at)
SELECT id, title, persona_id, mode, created_at FROM chat_sessions;

-- 3. 删除旧表
DROP TABLE chat_sessions;

-- 4. 重命名新表
ALTER TABLE chat_sessions_new RENAME TO chat_sessions;

-- 5. 重建索引（如有）
CREATE INDEX idx_chat_sessions_persona ON chat_sessions(persona_id);
```

**建议**：迁移脚本应自动检测 SQLite 版本，选择合适的删除策略。

---

## 扩展性考虑

### 新增模式

假设需要新增 `audio-gen` 模式：

1. **创建模式表**：
```sql
CREATE TABLE IF NOT EXISTS messages_audio_gen (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    timestamp BIGINT NOT NULL,
    is_error BOOLEAN DEFAULT FALSE,

    -- ✅ 音频生成特定字段
    audio_duration INTEGER,
    audio_format VARCHAR(20),
    audio_bitrate INTEGER,
    model_name VARCHAR(100)
);
CREATE INDEX idx_messages_audio_gen_session ON messages_audio_gen(session_id, timestamp);
```

2. **注册模式映射**：
```python
MODE_TABLE_MAP = {
    'chat': 'messages_chat',
    'image-gen': 'messages_image_gen',
    'video-gen': 'messages_video_gen',
    'audio-gen': 'messages_audio_gen',  # ✅ 新增
}
```

3. **无需修改索引表或附件表**，完全向后兼容

### 对话分支管理

当前设计已预留 `parent_id` 字段，未来若实现 UI 级分支管理：

1. 允许某条消息出现多个子消息
2. 新增 `message_index.active_tip_id` 字段表示"当前分支"
3. 查询时按 `active_tip_id` 回溯 `parent_id` 链，重建当前分支的消息序列

**注意**：这不影响现阶段落地，现在仍然是线性链（每个模式内只有一个活动分支）

---

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 迁移失败 | 中 | 高 | 迁移前备份数据库，迁移脚本支持断点续传 |
| 性能下降 | 低 | 中 | 索引优化，批量查询各模式表 |
| 新表创建失败 | 低 | 高 | 预先建表（非动态 DDL），自动重试 |
| parent_id 循环引用 | 低 | 中 | 查询时检测并中断，迁移时验证 |
| 跨模式查询性能 | 低 | 中 | `message_index` 索引优化，缓存会话索引 |

### 回滚方案

**触发条件**:
- 迁移后数据验证失败
- 新表查询错误率 > 5%
- 新表查询耗时 > 旧方案 2 倍

**回滚步骤**:
1. 停止后端服务
2. 从备份恢复数据库（包含 `messages` JSON 字段）
3. 部署旧版本代码
4. 启动服务

**注意**：直接迁移方案依赖数据库备份进行回滚，务必在迁移前完成备份。

---

## 最小可上线改造清单（MVP - 必须）

v3 必须完成以下 4 点才能上线：

### 1. ✅ message_index 增加 seq 字段（全局顺序）

- **问题**：同毫秒 timestamp 导致顺序不稳定 + parent_id 断链
- **解决**：增加 `seq INTEGER NOT NULL` 字段，按前端 `messages[]` 数组下标赋值
- **影响**：DDL、索引、查询排序逻辑

### 2. ✅ 增加 messages_generic 兜底表

- **问题**：v3 初版只覆盖 chat/image-gen/video-gen，实际有 9+ 模式
- **解决**：创建 `messages_generic` 表，覆盖所有未做专表优化的模式
- **影响**：DDL、模式映射逻辑

### 3. ✅ POST /api/sessions 实现收敛删除

- **问题**：增量 upsert 无法处理前端删除消息，会导致"消息复活"
- **解决**：计算 `existing_ids - posted_ids`，删除前端已移除的消息（级联删除附件）
- **影响**：sessions.py 保存逻辑

### 4. ✅ GET /api/sessions 实现批量组装（避免 N+1）

- **问题**：为每条消息单独查附件会形成 N+1 查询
- **解决**：批量查 message_index → 按 table_name 批量查模式表 → 批量查附件 → 内存组装
- **影响**：sessions.py 查询逻辑、性能

**达到以上 4 点后，v3 才具备"上线不炸"的可行性基础。**

---

## 总结

v3 方案通过**按模式分表 + 消息索引表（含 seq）+ 兜底表 + 收敛删除**的架构，彻底解决了当前 JSON 膨胀的性能问题，同时：

- ✅ **前端零改动**（API 完全兼容）
- ✅ **支持多模式独立对话链**
- ✅ **直接迁移**（无双写期，简化实现）
- ✅ **性能大幅提升**（O(1) 定位 + 批量查询 + 无 N+1）
- ✅ **极大简化上传 Worker**（90%+ 代码复杂度降低）
- ✅ **扩展性强**（新增模式只需创建新表或走 generic）
- ✅ **顺序稳定性**（seq 字段确保唯一顺序）
- ✅ **收敛删除**（避免"消息复活"）


---

## 可行性分析补充（2024-12-30）

### 风险评估详情

#### 风险 1：迁移数据一致性（概率：中，影响：高）

**风险描述**：
- 迁移过程中数据丢失或不一致
- 迁移脚本执行中断导致部分数据未迁移

**缓解措施**：
1. 迁移前备份数据库（必须）
2. 迁移脚本支持断点续传（记录已迁移的 `session_id`）
3. 编写验证脚本确认迁移完整性
4. 迁移失败时从备份恢复

**验证脚本示例**：
```python
def verify_migration(session_id: str, db: Session) -> bool:
    """验证单个会话迁移一致性"""
    # 从新表组装消息
    new_messages = assemble_messages_from_new_tables(session_id, db)
    
    # 验证消息数量和关键字段
    if not new_messages:
        return True  # 空会话
    
    for msg in new_messages:
        if not msg.get('id') or not msg.get('content'):
            return False
    
    return True
```

#### 风险 2：批量查询性能（概率：低，影响：中）

**风险描述**：
- 跨模式查询时多表 `JOIN` 性能下降
- `IN (...)` 查询在大量 ID 时性能退化
- 内存组装时消息数过多导致 OOM

**缓解措施**：
1. 索引优化：`(session_id, seq)` 主排序索引
2. 批量查询分组：按 `table_name` 分组，每组独立 `IN` 查询
3. 分页加载：单会话消息数 > 1000 时分页
4. 监控告警：查询耗时 > 500ms 时告警

**性能基准**：
| 场景 | 消息数 | 预期耗时 |
|------|--------|----------|
| 小会话 | < 100 | < 50ms |
| 中会话 | 100-500 | < 200ms |
| 大会话 | 500-1000 | < 500ms |
| 超大会话 | > 1000 | 分页加载 |

#### 风险 3：`parent_id` 链式关联（概率：低，影响：中）

**风险描述**：
- `parent_id` 构建逻辑复杂，可能出现断链
- 迁移时 `timestamp` 相同导致 `parent_id` 错误
- 循环引用导致查询死循环

**缓解措施**：
1. 基于 `seq` 构建 `parent_id`（而非 `timestamp`），确保顺序唯一
2. 迁移时验证链式完整性
3. 查询时检测循环引用（最大深度限制）
4. 断链时降级为 `parent_id = NULL`

**链式完整性验证**：
```python
def verify_parent_chain(session_id: str, mode: str, db: Session) -> bool:
    """验证同模式内的 parent_id 链完整性"""
    indexes = db.query(MessageIndex).filter(
        MessageIndex.session_id == session_id,
        MessageIndex.mode == mode
    ).order_by(MessageIndex.seq.asc()).all()
    
    if not indexes:
        return True
    
    # 第一条消息 parent_id 必须为 NULL
    if indexes[0].parent_id is not None:
        return False
    
    # 后续消息 parent_id 必须指向前一条
    for i in range(1, len(indexes)):
        if indexes[i].parent_id != indexes[i-1].id:
            return False
    
    return True
```

#### 风险 4：数据更新失败（概率：低，影响：中）

**风险描述**：
- `Worker` 更新新表失败导致附件 URL 为空
- 数据库事务失败导致数据不一致

**缓解措施**：
1. 更新逻辑使用事务，确保原子性
2. 更新失败时记录日志，后台补偿任务修复
3. 迁移前完整备份数据库

**更新事务示例**：
```python
def update_attachment_url(attachment_id: str, url: str, db: Session):
    try:
        db.query(MessageAttachment).filter(
            MessageAttachment.id == attachment_id
        ).update({
            "url": url,
            "upload_status": "completed"
        })
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"更新失败: {e}")
        enqueue_compensation_task(attachment_id, url)
        raise
```

#### 风险 5：模式映射遗漏（概率：低，影响：高）

**风险描述**：
- 新增模式未注册到 `MODE_TABLE_MAP`
- 消息写入时 `table_name` 为空导致失败
- 查询时无法定位消息所在表

**缓解措施**：
1. `messages_generic` 兜底表覆盖所有未注册模式
2. `get_table_name_for_mode()` 函数默认返回 `'messages_generic'`
3. 启动时校验 `MODE_TABLE_MAP` 覆盖所有 `AppMode` 枚举值
4. 新增模式时强制更新映射表

**模式映射函数**：
```python
MODE_TABLE_MAP = {
    'chat': 'messages_chat',
    'image-gen': 'messages_image_gen',
    'video-gen': 'messages_video_gen',
    # 其他模式走 generic
}

def get_table_name_for_mode(mode: str) -> str:
    """获取模式对应的表名，未注册模式走 generic"""
    return MODE_TABLE_MAP.get(mode, 'messages_generic')
```

---

### 实施建议

#### 推荐实施顺序

```
阶段 A（准备，1 天）：创建新表 + 迁移脚本
├─ 创建 6 个新表（DDL）
├─ 编写迁移脚本 run_chat_storage_migration_v3.py
└─ 完整备份数据库

阶段 B（停机迁移，2-3 小时）：
├─ 停止服务
├─ 执行全量迁移
├─ 验证脚本对比数据一致性
└─ 删除旧 messages 字段

阶段 C（上线，1 天）：
├─ 部署新代码（直接使用新表）
├─ 启动服务
└─ 观察监控指标
```

#### 关键代码改动点

| 文件 | 改动 |
|------|------|
| `backend/app/models/db_models.py` | 新增 6 个模型类 |
| `backend/app/routers/sessions.py` | 重写 `GET`/`POST` 逻辑（直接使用新表） |
| `backend/app/services/upload_worker_pool.py` | 更新逻辑（直接写新表） |
| `backend/migrations/xxx_v3_tables.sql` | 新表 DDL |
| `backend/run_chat_storage_migration_v3.py` | 迁移脚本 |

#### 监控指标

| 指标 | 阈值 | 告警级别 |
|------|------|----------|
| 新表查询耗时 | > 500ms | WARNING |
| 新表查询错误率 | > 1% | ERROR |
| 写入失败率 | > 0.1% | ERROR |
| 迁移进度 | < 预期 | INFO |

---

### 总体评估

| 维度 | 评分 | 说明 |
|------|------|------|
| **架构合理性** | ⭐⭐⭐⭐⭐ | 索引表 + 分表 + 兜底表设计清晰 |
| **兼容性** | ⭐⭐⭐⭐⭐ | 前端零改动，API 完全兼容 |
| **性能提升** | ⭐⭐⭐⭐⭐ | O(1) 定位 + 批量查询 + 无 N+1 |
| **实现复杂度** | ⭐⭐⭐⭐ | 中等，需要重写查询/保存逻辑 |
| **风险可控性** | ⭐⭐⭐⭐ | 数据库备份 + 回滚方案 + 验证脚本 |

**结论：推荐采用 v3 方案进行实施。**
