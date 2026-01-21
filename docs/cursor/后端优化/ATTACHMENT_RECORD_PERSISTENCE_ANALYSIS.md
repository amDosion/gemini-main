# MessageAttachment 记录持久化设计分析

> **分析日期**: 2026-01-21  
> **分析目的**: 理解为什么上传完成后数据库记录不会被删除

---

## 一、核心发现

**结论**：`MessageAttachment` 记录在上传完成后**必须保留**，因为系统中有多个位置依赖 `attachment_id` 来查询和使用这些记录。

---

## 二、attachment_id 的使用场景分析

### 2.1 场景 1：前端图片显示（临时图片代理端点）

**位置**：`backend/app/routers/core/attachments.py:41-167`

**功能**：`GET /api/temp-images/{attachment_id}`

**用途**：
- 前端使用 `/api/temp-images/{attachment_id}` 作为图片 URL
- 后端通过 `attachment_id` 查询 `MessageAttachment` 表
- 返回图片数据（Base64 解码或 HTTP 重定向）

**代码流程**：
```python
@router.get("/temp-images/{attachment_id}")
async def get_temp_image(attachment_id: str, ...):
    # 1. 通过 attachment_id 查询数据库
    attachment = db.query(MessageAttachment).filter_by(
        id=attachment_id
    ).first()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # 2. 如果上传完成，重定向到云存储 URL
    if attachment.url and attachment.upload_status == 'completed':
        return RedirectResponse(url=attachment.url)
    
    # 3. 如果未上传完成，返回 temp_url（Base64）
    if attachment.temp_url.startswith('data:'):
        image_bytes = base64.b64decode(temp_url)
        return Response(content=image_bytes, media_type=mime_type)
```

**设计原因**：
- ✅ 前端需要持续访问图片（即使上传未完成）
- ✅ 上传完成后，自动重定向到云存储 URL
- ✅ 如果删除记录，前端无法访问图片

---

### 2.2 场景 2：跨模式时查找云存储 URL

**位置**：`backend/app/routers/core/modes.py:389-420`

**功能**：在 Edit/Expand 模式中，通过 `attachment_id` 查找云存储 URL

**代码流程**：
```python
# 如果有 attachment_id，查找数据库中的附件信息
if reference_images and 'raw' in reference_images:
    raw_data = reference_images['raw']
    if isinstance(raw_data, dict) and 'attachment_id' in raw_data:
        attachment_id = raw_data['attachment_id']
        
        # 从数据库查询附件信息
        db_attachment = db.query(MessageAttachment).filter_by(
            id=attachment_id,
            user_id=user_id
        ).first()
        
        if db_attachment:
            # ✅ 如果已上传完成，优先使用 url（云端永久 URL）
            if db_attachment.upload_status == 'completed' and db_attachment.url:
                raw_data['url'] = db_attachment.url
            # ✅ 如果未上传完成，使用 temp_url（Base64）
            elif db_attachment.temp_url:
                raw_data['url'] = db_attachment.temp_url
```

**设计原因**：
- ✅ 跨模式时，需要根据 `attachment_id` 查找云存储 URL
- ✅ 优先使用云存储 URL（如果已上传完成）
- ✅ 如果未上传完成，使用临时 URL（Base64）
- ✅ 如果删除记录，无法查找云存储 URL

---

### 2.3 场景 3：Worker Pool 上传完成后更新附件 URL

**位置**：`backend/app/services/common/upload_worker_pool.py:970-1001`

**功能**：上传完成后，通过 `attachment_id` 更新附件的 `url` 和 `upload_status`

**代码流程**：
```python
async def _update_session_attachment(
    self, db, session_id: str, message_id: str, attachment_id: str, url: str, worker_name: str
):
    """
    更新会话附件 (v3 架构)
    
    v3 架构：直接更新 message_attachments 表
    """
    attachment = db.query(MessageAttachment).filter(
        MessageAttachment.id == attachment_id
    ).first()
    
    if attachment:
        attachment.url = url
        attachment.upload_status = 'completed'
        attachment.temp_url = None  # ✅ 清空 temp_url，因为已上传到云存储
        db.commit()
    else:
        log_print(f"[{worker_name}] ⚠️ 附件不存在: {attachment_id[:8]}...", "WARNING")
```

**设计原因**：
- ✅ Worker Pool 上传完成后，需要更新附件的 `url` 和 `upload_status`
- ✅ 如果删除记录，无法更新附件 URL
- ✅ 这是导致"附件不存在"警告的根本原因（如果 `attachment_id` 不一致）

---

### 2.4 场景 4：会话保存时查找和保护附件

**位置**：`backend/app/routers/user/sessions.py:327-473`

**功能**：会话保存时，通过 `attachment_id` 查找现有附件，保护云 URL

**代码流程**：
```python
# 查询现有附件
existing_attachments: Dict[str, MessageAttachment] = {}
if current_attachment_ids:
    atts = db.query(MessageAttachment).filter(
        MessageAttachment.id.in_(current_attachment_ids),
        MessageAttachment.user_id == user_id
    ).all()
    existing_attachments = {att.id: att for att in atts}

# 更新附件（保护云 URL）
if not attachment:
    attachment = MessageAttachment(...)
    db.add(attachment)
else:
    # 更新附件（保护云 URL）
    if final_url and final_url.startswith('http'):
        attachment.url = final_url
        attachment.upload_status = 'completed'
        attachment.temp_url = None
    else:
        # 保持原有 URL 不变
        pass
```

**设计原因**：
- ✅ 会话保存时，需要查找现有附件
- ✅ 保护云 URL，避免覆盖
- ✅ 如果删除记录，无法保护云 URL

---

### 2.5 场景 5：初始化服务查询附件

**位置**：`backend/app/services/common/init_service.py:220-226`

**功能**：初始化服务时，批量查询附件信息

**代码流程**：
```python
# 批量查询所有附件
if all_message_ids:
    all_attachments = db.query(MessageAttachment).filter(
        MessageAttachment.message_id.in_(list(all_message_ids)),
        MessageAttachment.user_id == user_id
    ).all()
    
    for att in all_attachments:
        attachments_by_message[att.message_id].append(att)
```

**设计原因**：
- ✅ 初始化服务时，需要查询附件信息
- ✅ 用于组装会话和消息数据
- ✅ 如果删除记录，无法查询附件信息

---

### 2.6 场景 6：获取云存储 URL 端点

**位置**：`backend/app/routers/core/attachments.py:311-353`

**功能**：`GET /api/attachments/{attachment_id}/cloud-url`

**代码流程**：
```python
@router.get("/attachments/{attachment_id}/cloud-url")
async def get_cloud_url(attachment_id: str, ...):
    # 查询附件状态
    attachment = db.query(MessageAttachment).filter_by(
        id=attachment_id,
        user_id=user_id
    ).first()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    return CloudUrlResponse(
        url=cloud_url,
        uploadStatus=attachment.upload_status or "pending"
    )
```

**设计原因**：
- ✅ 前端需要查询附件的云存储 URL
- ✅ 用于替代前端的 `tryFetchCloudUrl`
- ✅ 如果删除记录，无法查询云存储 URL

---

## 三、设计原因总结

### 3.1 为什么不能删除 MessageAttachment 记录？

1. **前端持续访问需求**：
   - 前端使用 `/api/temp-images/{attachment_id}` 作为图片 URL
   - 即使上传未完成，前端也需要访问图片
   - 如果删除记录，前端无法访问图片

2. **跨模式 URL 查找**：
   - 跨模式时，需要根据 `attachment_id` 查找云存储 URL
   - 优先使用云存储 URL（如果已上传完成）
   - 如果删除记录，无法查找云存储 URL

3. **Worker Pool 更新需求**：
   - Worker Pool 上传完成后，需要更新附件的 `url` 和 `upload_status`
   - 如果删除记录，无法更新附件 URL
   - **这是导致"附件不存在"警告的根本原因**

4. **会话保存保护**：
   - 会话保存时，需要查找现有附件，保护云 URL
   - 如果删除记录，无法保护云 URL

5. **初始化服务查询**：
   - 初始化服务时，需要批量查询附件信息
   - 用于组装会话和消息数据
   - 如果删除记录，无法查询附件信息

### 3.2 MessageAttachment 的生命周期

**创建时机**：
- 用户上传文件时（`AttachmentService.process_user_upload()`）
- AI 生成图片时（`AttachmentService.process_ai_result()`）

**更新时机**：
- Worker Pool 上传完成后（更新 `url` 和 `upload_status`）
- 会话保存时（保护云 URL）

**删除时机**：
- 会话被删除时（`sessions.py:625`）
- 消息被删除时（`sessions.py:313`）

**关键点**：
- ✅ **上传完成后不会删除记录**
- ✅ **记录与消息生命周期绑定**（不是与上传任务绑定）
- ✅ **记录用于存储 URL（临时和永久）、上传状态等信息**

---

## 四、问题确认

### 4.1 当前问题

**问题**：`UploadAsync` 端点更新了 `MessageAttachment.id`，但没有同步更新 `UploadTask.attachment_id`

**影响**：
- Worker Pool 使用 `UploadTask.attachment_id` 查找 `MessageAttachment` 时，找不到记录
- 导致"附件不存在"警告
- 附件 URL 无法更新到数据库

### 4.2 为什么需要同步更新？

**原因**：
- `MessageAttachment` 记录必须保留（用于前端访问、跨模式查找等）
- Worker Pool 需要通过 `attachment_id` 更新附件 URL
- 如果 `UploadTask.attachment_id` 与 `MessageAttachment.id` 不一致，Worker 无法找到记录

### 4.3 设计文档中的方案仍然有效

**方案**：在 `UploadAsync` 端点的"向后兼容"逻辑中，同步更新 `UploadTask.attachment_id`

**理由**：
- ✅ 确保 `UploadTask.attachment_id` 与 `MessageAttachment.id` 保持一致
- ✅ Worker Pool 能够找到附件记录并更新 URL
- ✅ 不影响其他使用 `attachment_id` 的场景

---

## 五、结论

1. **MessageAttachment 记录必须保留**：
   - 前端通过 `/api/temp-images/{attachment_id}` 访问图片
   - 跨模式时通过 `attachment_id` 查找云存储 URL
   - Worker Pool 上传完成后通过 `attachment_id` 更新附件 URL
   - 会话保存时通过 `attachment_id` 查找和保护附件

2. **设计文档中的问题分析正确**：
   - 问题确实存在：`UploadTask.attachment_id` 与 `MessageAttachment.id` 不一致
   - 方案仍然有效：需要同步更新 `UploadTask.attachment_id`

3. **"上传之后删除原始附件"的理解**：
   - Worker 删除的是**临时文件**（`upload_worker_pool.py:828-844`）
   - **不会删除数据库记录**
   - 数据库记录与消息生命周期绑定，不是与上传任务绑定

---

## 六、相关代码位置

1. **临时图片代理端点**：`backend/app/routers/core/attachments.py:41-167`
2. **跨模式 URL 查找**：`backend/app/routers/core/modes.py:389-420`
3. **Worker Pool 更新附件**：`backend/app/services/common/upload_worker_pool.py:970-1001`
4. **会话保存保护**：`backend/app/routers/user/sessions.py:327-473`
5. **初始化服务查询**：`backend/app/services/common/init_service.py:220-226`
6. **获取云存储 URL**：`backend/app/routers/core/attachments.py:311-353`

---

## 七、验证方法

1. **验证前端访问**：
   - 前端使用 `/api/temp-images/{attachment_id}` 访问图片
   - 后端通过 `attachment_id` 查询数据库

2. **验证跨模式查找**：
   - 跨模式时，通过 `attachment_id` 查找云存储 URL
   - 优先使用云存储 URL（如果已上传完成）

3. **验证 Worker Pool 更新**：
   - Worker Pool 上传完成后，通过 `attachment_id` 更新附件 URL
   - 如果 `attachment_id` 不一致，无法找到记录

4. **验证会话保存**：
   - 会话保存时，通过 `attachment_id` 查找现有附件
   - 保护云 URL，避免覆盖

---

## 八、总结

**核心结论**：
- ✅ `MessageAttachment` 记录必须保留，因为系统中有多个位置依赖 `attachment_id`
- ✅ 上传完成后不会删除记录，记录与消息生命周期绑定
- ✅ 设计文档中的问题分析和方案仍然有效
- ✅ 需要同步更新 `UploadTask.attachment_id`，确保 Worker Pool 能够找到附件记录
