# 统一附件处理方案设计文档

> **版本**: v3.0 (基于综合流程文档)  
> **创建日期**: 2026-01-18  
> **基于文档**: [GEN和EDIT模式完整流程综合文档](./cursor-GEN和EDIT模式完整流程综合文档.md)  
> **文档类型**: 架构设计方案  
> **状态**: 设计阶段

---

## 📋 目录

1. [设计目标和原则](#设计目标和原则)
2. [当前架构问题分析](#当前架构问题分析)
3. [统一架构设计方案](#统一架构设计方案)
4. [URL职责划分（临时URL vs 云URL）](#url职责划分临时url-vs-云url)
5. [API设计规范](#api设计规范)
6. [数据模型设计（避免Base64入库）](#数据模型设计避免base64入库)
7. [历史加载机制（云URL持久化）](#历史加载机制云url持久化)
8. [功能兼容性保障](#功能兼容性保障)
9. [实施计划](#实施计划)
10. [风险评估与缓解](#风险评估与缓解)

---

## 设计目标和原则

### 1.1 核心设计目标

基于[GEN和EDIT模式完整流程综合文档](./cursor-GEN和EDIT模式完整流程综合文档.md)的深入分析，本设计方案旨在：

#### ✅ 目标1：附件统一后端处理

**问题**：当前架构中，前端和后端都进行图片下载、格式转换、上传等重复操作。

**目标**：
- 所有附件的下载、转换、上传统一在后端完成
- 前端仅负责用户交互和UI显示
- 复用现有异步上传机制（Worker Pool + Redis队列）

**优势**：
- 减少前端网络传输（Base64编码增加33%大小）
- 减少前端内存占用（不存储Base64数据）
- 统一错误处理和重试逻辑
- 降低前端代码复杂度（从1200行降至700行）

#### ✅ 目标2：避免Base64写入数据库

**问题**：当前`tempUrl`字段可能存储Base64 Data URL，占用大量数据库空间。

**目标**：
- **绝不**将Base64 Data URL保存到数据库的`url`或`tempUrl`字段
- Base64仅用于前端即时显示（AI返回后立即展示）
- 后台上传完成后，`url`字段存储永久云存储URL
- 页面重载后，从数据库读取云URL（不依赖Base64）

**实现策略**：
- `url`字段：仅存储HTTP云存储URL（永久有效）
- `tempUrl`字段：仅存储HTTP临时URL（如Tongyi的临时URL，作为备选）
- Base64 Data URL：仅存在于前端内存，不序列化到数据库

#### ✅ 目标3：明确区分临时URL和云URL职责

**临时URL职责**：
- 用于AI返回后的**立即显示**（无延迟）
- 生命周期：页面会话期间（Blob URL）或24小时内（HTTP临时URL）
- 不持久化到数据库（或仅作为备选存储到`tempUrl`）

**云URL职责**：
- 用于**永久存储和页面重载后加载**
- 生命周期：永久有效
- 存储在数据库`url`字段（权威来源）
- Worker上传完成后自动更新

**显示优先级**：
```
AI返回后立即显示：临时URL（Base64/Blob/HTTP临时）
上传完成后显示：云URL（如果已完成上传）
页面重载后显示：云URL（从数据库加载，永久有效）
```

#### ✅ 目标4：历史加载功能保障

**问题**：页面重载后，如果`url`字段是Base64或Blob URL，无法正常显示。

**目标**：
- 页面重载时，从数据库`url`字段读取云URL（HTTP格式）
- 如果`url`为空或无效，查询`UploadTask`获取最新云URL
- 确保历史附件始终可用（不依赖临时URL）

**实现策略**：
- 数据库`url`字段优先存储云URL（`upload_status='completed'`时）
- Worker上传完成后自动更新`message_attachments.url`
- 会话保存时保护已有云URL（3层优先级保护）

#### ✅ 目标5：功能不丢失

**保留的关键功能**：
- ✅ **CONTINUITY LOGIC**：Edit模式无新上传时自动复用画布图片
- ✅ **双URL显示机制**：临时URL立即显示 + 云URL持久化
- ✅ **异步上传机制**：Worker Pool + Redis队列（不阻塞前端）
- ✅ **自动更新机制**：Worker自动更新数据库URL
- ✅ **跨模式传递**：通过`tempUrl`字段查找历史附件
- ✅ **云URL保护**：3层优先级保护（UploadTask > Database > Frontend）

---

### 1.2 设计原则

#### 原则1：前端简化，后端统一

```
前端职责：
├─ 用户交互（文件选择、拖拽上传）
├─ UI显示（图片预览、加载状态）
├─ 即时显示（AI返回的临时URL，无延迟）
└─ 调用后端API（传递File/URL/attachmentId）

后端职责：
├─ 接收任意类型来源（File / HTTP URL / Base64 / attachmentId）
├─ 统一下载、验证、转换
├─ 统一上传到云存储（异步任务）
├─ 统一管理附件状态
└─ 自动更新数据库URL
```

#### 原则2：临时与永久分离

```
临时URL（前端显示，不持久化）
├─ Base64 Data URL（AI返回，立即显示）
├─ Blob URL（用户上传预览）
└─ HTTP临时URL（Tongyi返回，24小时有效）

云URL（数据库存储，永久有效）
├─ HTTP云存储URL（上传完成后）
└─ 页面重载时从数据库读取
```

#### 原则3：向后兼容

```
现有功能保持100%可用：
├─ CONTINUITY LOGIC（Edit模式）
├─ 跨模式传递（通过tempUrl查找）
├─ 异步上传（Worker Pool）
└─ 历史加载（从数据库读取云URL）
```

## 当前架构问题分析

### 2.1 重复处理问题

基于综合流程文档分析，当前架构存在多处重复处理：

#### 问题1：前端和后端重复下载HTTP URL

**场景**：Tongyi返回HTTP临时URL

**当前流程**：
```
1. AI返回HTTP临时URL
   ↓
2. 前端下载1（用于显示）
   processMediaResult() → fetch(url) → Blob URL
   ↓
3. 前端下载2（用于上传）
   sourceToFile() → fetch(url) → File对象
   ↓
4. 前端上传
   uploadFileAsync() → FormData
   ↓
5. 后端Worker下载（再次下载）
   Worker Pool → httpx.get(url) → 上传云存储
```

**问题**：
- ❌ 同一URL被下载2-3次
- ❌ 前端网络开销：300ms × 2 = 600ms
- ❌ 前端内存占用：~1MB × 2 = 2MB（Blob + File对象）

#### 问题2：Base64循环转换

**场景**：Google返回Base64 Data URL

**当前流程**：
```
1. 前端接收Base64 URL
   ↓
2. 前端转换为File对象
   sourceToFile() → Base64 → Blob → File
   ↓
3. 前端上传File对象
   FormData.append('file', file)
   ↓
4. 后端读取文件
   后端：File → 保存临时文件
   ↓
5. Worker读取文件
   Worker：读取临时文件 → 上传云存储
```

**问题**：
- ❌ Base64 → File → 临时文件 → 云存储（多步转换）
- ❌ Base64编码增加33%大小（1MB → 1.33MB）
- ❌ 前端内存占用Base64字符串（1.33MB）

#### 问题3：URL类型检测重复

**当前实现**：
- **前端**：`isHttpUrl()`, `isBlobUrl()`, `isBase64Url()` (attachmentUtils.ts)
- **后端**：`url.startswith('http')`, `url.startswith('data:')` (multiple files)

**问题**：
- ❌ 逻辑重复，维护成本高
- ❌ 前端和后端判断逻辑可能不一致

### 2.2 数据库存储问题

#### 问题1：Base64可能写入数据库

**当前实现** (sessions.py:447)：
```python
attachment = MessageAttachment(
    url=final_url,  # ⚠️ 可能是Base64 URL（如果前端传来）
    temp_url=att.get("tempUrl"),  # ⚠️ 可能包含Base64
)
```

**问题**：
- ❌ Base64 Data URL太大（1MB图片 → 1.33MB Base64）
- ❌ 数据库存储成本高
- ❌ 页面重载后无法使用（Base64已丢失）

**影响**：
- 单个附件Base64：1.33MB
- 100个附件：133MB数据库空间
- 查询性能下降

#### 问题2：tempUrl字段职责不清晰

**当前实现**：
```python
temp_url=att.get("tempUrl")  # 可能包含：
                              # - Blob URL（页面刷新后失效）
                              # - Base64 URL（太大，不应该存储）
                              # - HTTP临时URL（可以存储，但需明确用途）
```

**问题**：
- ❌ `tempUrl`和`url`职责重叠
- ❌ 不清楚何时使用`tempUrl`，何时使用`url`
- ❌ 跨模式查找依赖`tempUrl`，但数据可能无效

### 2.3 历史加载问题

#### 问题1：Blob URL无法持久化

**场景**：用户上传文件 → 创建Blob URL → 发送消息 → 页面刷新

**当前流程**：
```
1. 用户上传 → Blob URL（临时）
   ↓
2. cleanAttachmentsForDb()清除Blob URL
   url = ''（清空）
   ↓
3. 会话保存
   url = ''（空）
   ↓
4. 页面刷新
   url = ''（无法显示）
```

**问题**：
- ❌ 页面刷新后Blob URL失效
- ❌ 如果上传未完成，历史附件无法显示
- ❌ 需要等待上传完成后才能查看历史

#### 问题2：云URL保护可能失效

**场景**：Worker上传完成后，前端再次发送消息

**当前流程** (sessions.py:408-430)：
```python
# 3层优先级保护
1. UploadTask.target_url（最高优先级）
2. Database existing URL
3. Frontend URL（可能覆盖云URL）
```

**问题**：
- ⚠️ 如果前端传来Blob/Base64 URL，可能覆盖已有云URL
- ⚠️ 需要确保保护逻辑正确执行

### 2.4 代码复杂度问题

#### 问题1：前端附件处理函数过多

**当前函数** (attachmentUtils.ts)：
- `processUserAttachments()` (157行)
- `processMediaResult()` (57行)
- `prepareAttachmentForApi()` (106行)
- `findAttachmentByUrl()` (61行)
- `tryFetchCloudUrl()` (34行)
- `sourceToFile()` (70行)
- `fileToBase64()` (12行)
- `urlToBase64()` (21行)
- `base64ToFile()` (13行)
- `urlToFile()` (28行)

**总计**：约500行代码

**问题**：
- ❌ 函数职责重叠
- ❌ 难以维护
- ❌ 测试覆盖困难

### 2.5 性能问题汇总

| 问题类型 | 当前影响 | 优化潜力 |
|---------|---------|---------|
| **重复下载HTTP URL** | +600ms延迟，2MB内存 | 0次前端下载（-100%） |
| **Base64循环转换** | +200ms编码，1.33MB内存 | 后端直接解码（-100%前端编码） |
| **Base64写入数据库** | 133MB/100附件 | 0MB（不写入） |
| **前端代码复杂度** | 500行处理函数 | 200行（-60%） |
| **历史加载失败** | 页面刷新后无法显示 | 云URL持久化（100%可用） |

## 统一架构设计方案

### 3.1 新架构总览

基于综合流程文档的分析，新架构的核心思路是：**前端负责交互和显示，后端统一处理附件上传**。

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (Frontend)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  职责：用户交互 + UI显示                                          │
│                                                                  │
│  1. InputArea.tsx                                               │
│     ├─ handleFileSelect() → 创建Blob URL（预览）                 │
│     └─ handleSend() → 调用后端API（传递File对象）                │
│                                                                  │
│  2. processMediaResult()（简化版）                                │
│     ├─ 立即显示临时URL（Base64/Blob/HTTP临时）                    │
│     └─ 调用后端API（传递URL，后端处理上传）                       │
│                                                                  │
│  3. CONTINUITY LOGIC（保留）                                      │
│     ├─ prepareAttachmentForApi()                                │
│     └─ findAttachmentByUrl() → 查询云URL                         │
│                                                                  │
│  4. cleanAttachmentsForDb()（简化版）                             │
│     ├─ 清除Blob URL（不保存到DB）                                 │
│     ├─ 清除Base64 URL（不保存到DB）                               │
│     └─ 保留HTTP URL（仅云URL，不包含临时URL）                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                           ↓ File / URL / attachmentId
┌─────────────────────────────────────────────────────────────────┐
│                        后端 (Backend)                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  职责：统一附件处理 + 云存储上传                                   │
│                                                                  │
│  1. POST /api/attachments/prepare（新增统一接口）                 │
│     ├─ 接收File对象 → 保存临时文件 → 创建UploadTask               │
│     ├─ 接收HTTP URL → 创建UploadTask（source_url）                │
│     ├─ 接收Base64 URL → 解码 → 保存临时文件 → 创建UploadTask      │
│     └─ 接收attachmentId → 查询已有附件 → 复用                     │
│                                                                  │
│  2. UnifiedAttachmentProcessor（新增核心处理器）                 │
│     ├─ process_file() → 验证 → 保存临时文件 → 创建任务           │
│     ├─ process_http_url() → 创建任务（source_url）                │
│     ├─ process_base64_url() → 解码 → 保存文件 → 创建任务         │
│     └─ upload_to_cloud_async() → UploadTask + Redis队列          │
│                                                                  │
│  3. Worker Pool（保留现有机制）                                   │
│     ├─ Redis BRPOP 阻塞等待任务                                   │
│     ├─ 读取文件内容（source_file_path 或 source_url）            │
│     ├─ 上传到云存储                                                │
│     └─ 更新message_attachments.url = 云URL                        │
│                                                                  │
│  4. 会话保存（保留云URL保护逻辑）                                 │
│     ├─ 3层优先级：UploadTask > Database > Frontend               │
│     ├─ url字段：仅存储HTTP云URL（永久有效）                       │
│     └─ tempUrl字段：仅存储HTTP临时URL（备选）                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心变更点

#### 变更1：新增统一附件处理接口

**接口**：`POST /api/attachments/prepare`

**功能**：
- 接收任意类型的图片来源（File / HTTP URL / Base64 / attachmentId）
- 统一创建异步上传任务（复用现有Worker机制）
- 返回任务ID和附件ID

**优势**：
- ✅ 前端只需调用一个接口，无需关心图片处理细节
- ✅ 后端统一处理，避免重复逻辑
- ✅ 复用现有异步上传机制（Worker Pool + Redis队列）

#### 变更2：前端简化处理逻辑

**移除函数**（用于上传的目的）：
- `sourceToFile()` - ❌ 删除（用于上传）
- `fileToBase64()` - ❌ 删除（用于传输）
- `urlToFile()` - ❌ 删除（用于上传）

**保留函数**（用于显示和查找）：
- `isHttpUrl()`, `isBlobUrl()`, `isBase64Url()` - ✅ 保留（URL类型判断）
- `findAttachmentByUrl()` - ✅ 保留（CONTINUITY LOGIC）
- `tryFetchCloudUrl()` - ✅ 保留（查询云URL）
- `cleanAttachmentsForDb()` - ✅ 保留（简化版，清除临时URL）

**新增函数**：
- `uploadAttachment(source)` - ✅ 新增（调用后端API）

#### 变更3：优化processMediaResult（保留双URL机制）

**保留双URL显示机制**：
- ✅ **立即显示**：AI返回后，前端立即显示Base64/Blob/HTTP临时URL（无延迟）
- ✅ **后台上传**：调用`POST /api/attachments/prepare`创建异步任务
- ✅ **自动更新**：Worker自动更新`message_attachments.url`（无需前端轮询）

**变更前**：
```typescript
// ❌ 前端下载HTTP URL → 创建Blob URL → 转换为File → 上传
if (isHttpUrl(res.url)) {
  const response = await fetch(res.url);  // 下载1
  const blob = await response.blob();
  displayUrl = URL.createObjectURL(blob);
}
const file = await sourceToFile(res.url);  // 下载2 + 转换
await storageUpload.uploadFileAsync(file);  // 上传
```

**变更后**：
```typescript
// ✅ 直接使用临时URL显示，后端处理上传
if (isHttpUrl(res.url)) {
  displayUrl = res.url;  // 直接使用HTTP URL（浏览器支持）
}
// 或创建Blob URL（仅用于显示）
if (isHttpUrl(res.url)) {
  const response = await fetch(res.url);  // 仅用于显示
  const blob = await response.blob();
  displayUrl = URL.createObjectURL(blob);
}

// ✅ 后台上传（后端处理）
await uploadAttachment(res.url);  // 传递URL，后端下载并上传
```

**优势**：
- ✅ 前端不再负责上传相关下载和转换
- ✅ 保留即时显示功能（用户体验不变）
- ✅ 减少前端网络开销（不下载用于上传）

## URL职责划分（临时URL vs 云URL）

### 4.1 核心原则

基于综合流程文档的分析，URL职责划分的核心原则是：**临时URL用于即时显示，云URL用于永久存储**。

#### 原则1：临时URL不持久化

**临时URL类型**：
- **Base64 Data URL**：`data:image/png;base64,iVBORw0KGgo...`
- **Blob URL**：`blob:http://localhost:3000/xxx`
- **HTTP临时URL**：`https://dashscope.oss-cn-beijing.aliyuncs.com/...?Expires=xxx`

**处理规则**：
- ✅ 仅存在于前端内存（用于立即显示）
- ❌ **绝不**保存到数据库的`url`字段
- ⚠️ HTTP临时URL可保存到`tempUrl`字段（作为备选，但需明确标记）

#### 原则2：云URL是唯一持久化来源

**云URL特征**：
- **格式**：`https://storage.example.com/path/image.png`
- **生命周期**：永久有效
- **存储位置**：数据库`url`字段（权威来源）

**处理规则**：
- ✅ Worker上传完成后自动更新`message_attachments.url`
- ✅ 页面重载时从数据库`url`字段读取
- ✅ 会话保存时保护已有云URL（3层优先级）

### 4.2 URL字段职责定义

#### 4.2.1 `url`字段（权威URL）

**职责**：存储永久有效的云存储URL

**存储规则**：
```python
# ✅ 允许存储
url = "https://storage.example.com/images/xxx.png"  # 云存储URL

# ❌ 禁止存储
url = "data:image/png;base64,..."  # Base64（太大，不持久化）
url = "blob:http://localhost:3000/xxx"  # Blob URL（页面刷新后失效）
url = "https://dashscope.oss-cn-beijing.aliyuncs.com/...?Expires=xxx"  # 临时URL（会过期）
```

**更新时机**：
1. Worker上传完成后：`url = 云存储URL`
2. 会话保存时：保护已有云URL（不覆盖）

**代码位置**：`sessions.py:408-430`（云URL保护逻辑）

```python
# 优先级1：UploadTask.target_url（最权威）
task = completed_tasks.get(att_id)
if task and task.target_url:
    authoritative_url = task.target_url  # ✅ 使用最新云URL

# 优先级2：Database existing URL
if not authoritative_url:
    existing_att = existing_attachments.get(att_id)
    if existing_att and existing_att.url and existing_att.url.startswith('http'):
        authoritative_url = existing_att.url  # ✅ 保护已有云URL

# 优先级3：Frontend URL（仅HTTP云URL）
frontend_url = att.get("url", "")
if frontend_url.startswith("http") and not frontend_url.startswith("blob:"):
    # ✅ 前端传来HTTP URL，检查是否为云URL
    if is_cloud_storage_url(frontend_url):  # 非临时URL
        final_url = frontend_url
    else:
        final_url = authoritative_url or frontend_url
else:
    # ❌ 前端传来Blob/Base64，使用权威URL
    final_url = authoritative_url or ""
```

#### 4.2.2 `tempUrl`字段（临时URL备选）

**职责**：存储临时URL，用于跨模式查找和备选显示

**存储规则**：
```python
# ✅ 允许存储（HTTP临时URL）
temp_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/...?Expires=xxx"  # Tongyi临时URL

# ❌ 禁止存储
temp_url = "data:image/png;base64,..."  # Base64（太大）
temp_url = "blob:http://localhost:3000/xxx"  # Blob URL（页面刷新后失效）
```

**使用场景**：
1. **跨模式查找**：通过`tempUrl`查找历史附件（`findAttachmentByUrl`）
2. **备选显示**：如果`url`为空且`tempUrl`是HTTP URL，临时使用（直到上传完成）

**清理规则**：
```typescript
// cleanAttachmentsForDb() 清理逻辑
if (cleaned.tempUrl) {
  // ✅ 保留HTTP临时URL（作为备选）
  if (isHttpUrl(cleaned.tempUrl) && !cleaned.tempUrl.includes('expires=')) {
    // 保留（可能是云URL的临时版本）
  }
  // ❌ 清除Blob/Base64 URL
  else if (isBlobUrl(cleaned.tempUrl) || isBase64Url(cleaned.tempUrl)) {
    delete cleaned.tempUrl;
  }
}
```

### 4.3 URL显示优先级

#### 4.3.1 前端显示优先级

**代码位置**：`AttachmentGrid.tsx:88-100`

```typescript
// 显示优先级
const displayUrl = att.url || att.tempUrl || att.fileUri;

// 优先级说明：
// 1. url（云URL，永久有效）✅ 优先
// 2. tempUrl（临时URL，备选）⚠️ 仅当url为空时使用
// 3. fileUri（Google File URI，48小时有效）⚠️ 最后备选
```

**显示逻辑**：
```
AI返回后立即显示：
├─ Google: Base64 Data URL（直接使用）
├─ Tongyi: HTTP临时URL → 下载 → Blob URL（或直接使用HTTP URL）
└─ 用户上传: Blob URL（预览）

上传完成后显示：
└─ 云URL（从数据库url字段读取）

页面重载后显示：
└─ 云URL（从数据库url字段读取，永久有效）
```

#### 4.3.2 数据库存储优先级

**代码位置**：`sessions.py:408-430`

```python
# 3层优先级保护
1. UploadTask.target_url（Worker刚完成上传）
   ↓
2. Database existing URL（已有云URL）
   ↓
3. Frontend URL（仅HTTP云URL，非临时URL）
```

**保护效果**：

| 前端URL | 数据库URL | UploadTask URL | 最终存储 | 说明 |
|---------|----------|---------------|---------|------|
| `blob:xxx` | `http://cloud/1.png` | - | `http://cloud/1.png` | ✅ 保护数据库URL |
| `data:xxx` | - | `http://cloud/2.png` | `http://cloud/2.png` | ✅ 使用最新上传URL |
| `http://new.png`（云URL） | `http://old.png` | - | `http://new.png` | ✅ 允许更新云URL |
| `http://temp.png?Expires=xxx` | `http://cloud/3.png` | - | `http://cloud/3.png` | ✅ 保护云URL，临时URL不覆盖 |

### 4.4 Base64处理策略

#### 4.4.1 Base64绝不写入数据库

**原因**：
- Base64编码增加33%大小（1MB → 1.33MB）
- 数据库存储成本高
- 页面重载后无法使用（Base64已丢失）

**实现策略**：

**前端清理**（`cleanAttachmentsForDb`）：
```typescript
// ❌ 清除Base64 URL
if (isBase64Url(url)) {
  cleaned.url = '';  // 清空
  cleaned.uploadStatus = 'pending';  // 标记为待上传
}
```

**后端保护**（`sessions.py`）：
```python
# ❌ 拒绝Base64 URL
if frontend_url.startswith("data:"):
    # 使用权威URL（云URL）或清空
    final_url = authoritative_url or ""
```

#### 4.4.2 Base64仅用于前端即时显示

**使用场景**：
1. **AI返回后立即显示**：Google返回Base64，前端直接使用`<img src={base64Url} />`
2. **跨模式传递**：通过`tempUrl`传递Base64（仅前端内存，不序列化）

**生命周期**：
```
AI返回Base64
    ↓
前端立即显示（无延迟）
    ↓
调用后端API（传递Base64 URL）
    ↓
后端解码 → 保存临时文件 → 创建UploadTask
    ↓
Worker上传 → 更新url = 云URL
    ↓
页面重载 → 从数据库读取云URL（Base64已丢失，但云URL可用）
```

### 4.5 HTTP临时URL处理策略

#### 4.5.1 Tongyi临时URL特征

**格式**：
```
https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/1d/c3/...
?Expires=1737273600
&OSSAccessKeyId=LTAI5t...
&Signature=xxx
```

**特征**：
- 域名：`dashscope-result-*.oss-*.aliyuncs.com`
- 包含查询参数：`Expires`, `OSSAccessKeyId`, `Signature`
- 有效期：通常24小时

#### 4.5.2 临时URL存储策略

**选项1：不存储到数据库（推荐）**
- ✅ 前端立即显示（直接使用HTTP URL或下载为Blob URL）
- ✅ 后端Worker直接下载并上传到云存储
- ✅ 上传完成后，`url`字段存储云URL（永久有效）
- ✅ `tempUrl`字段不存储临时URL（避免过期后失效）

**选项2：临时存储到`tempUrl`（备选）**
- ⚠️ 如果上传未完成，临时存储到`tempUrl`（作为备选）
- ⚠️ 页面重载时，如果`url`为空，尝试使用`tempUrl`（可能已过期）
- ⚠️ 需要定期清理过期的`tempUrl`

**推荐方案**：选项1（不存储临时URL）

**理由**：
- 临时URL会过期，存储无意义
- Worker上传通常很快（几秒内完成）
- 如果上传失败，可以重试（不依赖临时URL）

## API设计规范

### 5.1 统一附件上传接口

#### 5.1.1 接口定义

```
POST /api/attachments/prepare
Content-Type: multipart/form-data 或 application/json
```

**功能**：
- 接收任意类型的图片来源（File / HTTP URL / Base64 / attachmentId）
- 统一创建异步上传任务（复用现有Worker机制）
- 返回任务ID和附件ID

**优势**：
- ✅ 前端只需调用一个接口，无需关心图片处理细节
- ✅ 后端统一处理，避免重复逻辑
- ✅ 复用现有异步上传机制（Worker Pool + Redis队列）

#### 5.1.2 请求格式（4种模式）

**模式1：上传File对象**

```http
POST /api/attachments/prepare
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="file"; filename="image.png"
Content-Type: image/png

<binary data>
--boundary
Content-Disposition: form-data; name="sessionId"
Content-Type: text/plain

session-123
--boundary
Content-Disposition: form-data; name="messageId"
Content-Type: text/plain

msg-456
--boundary--
```

**模式2：传递HTTP URL**

```http
POST /api/attachments/prepare
Content-Type: application/json

{
  "url": "https://dashscope.oss-cn-beijing.aliyuncs.com/...?Expires=xxx",
  "sessionId": "session-123",
  "messageId": "msg-456",
  "attachmentId": "att-789"  // 可选，如果已有附件ID
}
```

**模式3：传递Base64 Data URL**

```http
POST /api/attachments/prepare
Content-Type: application/json

{
  "url": "data:image/png;base64,iVBORw0KGgo...",
  "sessionId": "session-123",
  "messageId": "msg-456",
  "mimeType": "image/png",  // 可选，从Data URL解析
  "filename": "image-1234567890.png"  // 可选，自动生成
}
```

**模式4：复用已有附件**

```http
POST /api/attachments/prepare
Content-Type: application/json

{
  "attachmentId": "att-12345678",
  "sessionId": "session-123",
  "messageId": "msg-456"  // 可选，关联到新消息
}
```

#### 5.1.3 响应格式

**成功响应**：

```json
{
  "success": true,
  "data": {
    "attachmentId": "att-12345678",
    "taskId": "task-87654321",
    "status": "pending",
    "url": "",  // 上传完成后由Worker更新为云URL
    "uploadStatus": "pending",
    "mimeType": "image/png",
    "name": "image-1234567890.png"
  }
}
```

**错误响应**：

```json
{
  "success": false,
  "error": {
    "code": "INVALID_FILE_TYPE",
    "message": "不支持的文件格式，仅支持 JPEG, PNG, WebP",
    "details": {
      "mimeType": "image/gif",
      "supportedTypes": ["image/jpeg", "image/png", "image/webp"]
    }
  }
}
```

**错误码定义**：

| 错误码 | HTTP状态 | 说明 |
|-------|---------|------|
| `INVALID_FILE_TYPE` | 400 | 不支持的文件格式 |
| `FILE_TOO_LARGE` | 400 | 文件大小超过限制（默认10MB） |
| `INVALID_URL` | 400 | 无效的URL格式 |
| `ATTACHMENT_NOT_FOUND` | 404 | 附件ID不存在（模式4） |
| `UPLOAD_FAILED` | 500 | 创建上传任务失败 |

### 5.2 附件状态查询接口

#### 5.2.1 接口定义

```
GET /api/attachments/{attachmentId}
```

**功能**：
- 查询附件的最新状态（上传进度、云URL）
- 用于前端轮询或页面重载后查询

**查询参数**：
- `sessionId`（可选）：验证附件属于指定会话

#### 5.2.2 响应格式

**成功响应**：

```json
{
  "success": true,
  "data": {
    "attachmentId": "att-12345678",
    "url": "https://storage.example.com/images/xxx.png",  // 云URL（如果已完成上传）
    "uploadStatus": "completed",  // pending | uploading | completed | failed
    "taskId": "task-87654321",
    "taskStatus": "completed",  // pending | uploading | completed | failed
    "mimeType": "image/png",
    "name": "image-1234567890.png",
    "size": 2048576,
    "uploadedAt": "2026-01-18T10:30:00Z"  // ISO 8601格式
  }
}
```

**未找到**：

```json
{
  "success": false,
  "error": {
    "code": "ATTACHMENT_NOT_FOUND",
    "message": "附件不存在或无权访问"
  }
}
```

**代码位置**：`sessions.py:645-705`（现有实现）

### 5.3 批量附件查询接口（可选）

#### 5.3.1 接口定义

```
POST /api/attachments/batch
Content-Type: application/json
```

**请求体**：

```json
{
  "attachmentIds": ["att-1", "att-2", "att-3"],
  "sessionId": "session-123"  // 可选，验证权限
}
```

**响应格式**：

```json
{
  "success": true,
  "data": {
    "attachments": [
      {
        "attachmentId": "att-1",
        "url": "https://storage.example.com/images/xxx1.png",
        "uploadStatus": "completed"
      },
      {
        "attachmentId": "att-2",
        "url": "",
        "uploadStatus": "pending"
      },
      {
        "attachmentId": "att-3",
        "url": "https://storage.example.com/images/xxx3.png",
        "uploadStatus": "completed"
      }
    ]
  }
}
```

**优势**：
- 减少HTTP请求数（批量查询）
- 适用于页面重载时批量查询多个附件状态

### 5.4 前端调用示例

#### 5.4.1 上传File对象

```typescript
// 用户上传文件
const uploadAttachment = async (
  file: File,
  context: { sessionId: string; messageId: string; attachmentId?: string }
): Promise<Attachment> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('sessionId', context.sessionId);
  formData.append('messageId', context.messageId);
  if (context.attachmentId) {
    formData.append('attachmentId', context.attachmentId);
  }

  const response = await fetch('/api/attachments/prepare', {
    method: 'POST',
    body: formData,
    credentials: 'include'
  });

  const result = await response.json();
  if (!result.success) {
    throw new Error(result.error.message);
  }

  return {
    id: result.data.attachmentId,
    url: result.data.url,  // 空字符串（上传完成后更新）
    uploadStatus: result.data.uploadStatus,
    uploadTaskId: result.data.taskId,
    mimeType: result.data.mimeType,
    name: result.data.name
  };
};
```

#### 5.4.2 上传URL（HTTP或Base64）

```typescript
// AI返回URL后上传
const uploadAttachmentFromUrl = async (
  url: string,  // HTTP URL 或 Base64 Data URL
  context: { sessionId: string; messageId: string; attachmentId?: string }
): Promise<Attachment> => {
  const response = await fetch('/api/attachments/prepare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url: url,
      sessionId: context.sessionId,
      messageId: context.messageId,
      attachmentId: context.attachmentId
    }),
    credentials: 'include'
  });

  const result = await response.json();
  if (!result.success) {
    throw new Error(result.error.message);
  }

  return {
    id: result.data.attachmentId,
    url: result.data.url,  // HTTP临时URL（Tongyi）或空字符串（Google Base64）
    uploadStatus: result.data.uploadStatus,
    uploadTaskId: result.data.taskId,
    mimeType: result.data.mimeType,
    name: result.data.name
  };
};
```

#### 5.4.3 查询附件状态

```typescript
// 查询附件最新状态
const getAttachmentStatus = async (
  attachmentId: string,
  sessionId: string
): Promise<Attachment> => {
  const response = await fetch(
    `/api/attachments/${attachmentId}?sessionId=${sessionId}`,
    { credentials: 'include' }
  );

  const result = await response.json();
  if (!result.success) {
    throw new Error(result.error.message);
  }

  return {
    id: result.data.attachmentId,
    url: result.data.url,  // 云URL（如果已完成上传）
    uploadStatus: result.data.uploadStatus,
    uploadTaskId: result.data.taskId,
    mimeType: result.data.mimeType,
    name: result.data.name
  };
};
```

## 数据模型设计（避免Base64入库）

### 6.1 前端Attachment接口（优化版）

#### 6.1.1 接口定义

**代码位置**：`frontend/types/types.ts`

```typescript
interface Attachment {
  // ========== 核心标识 ==========
  id: string;                          // 唯一标识 (UUID)

  // ========== URL字段（明确职责）==========
  url?: string;                        // 权威URL（仅HTTP云URL）
                                       // ✅ 存储：HTTP云存储URL（永久有效）
                                       // ❌ 禁止：Base64、Blob URL、HTTP临时URL

  tempUrl?: string;                    // 临时URL（仅HTTP临时URL，备选）
                                       // ✅ 存储：HTTP临时URL（如Tongyi的临时URL）
                                       // ❌ 禁止：Base64、Blob URL

  // ========== 上传相关 ==========
  uploadStatus?: 'pending' | 'uploading' | 'completed' | 'failed';
  uploadTaskId?: string;               // 异步上传任务ID（临时字段，不保存到DB）

  // ========== 文件信息 ==========
  mimeType: string;                    // MIME类型 (image/png, image/jpeg, ...)
  name: string;                        // 文件名
  size?: number;                       // 文件大小（字节）

  // ========== 云存储API相关 ==========
  fileUri?: string;                    // 云存储File URI（通用）
  googleFileUri?: string;              // Google Files API URI（48小时缓存）
  googleFileExpiry?: number;           // Google File URI过期时间戳

  // ========== 前端临时字段（不保存到数据库）==========
  file?: File;                         // 原始File对象（不可序列化）
  base64Data?: string;                 // Base64数据（仅前端内存，不序列化）
  _displayUrl?: string;                // 内部字段：原始显示URL（Base64/Blob）
                                       // 用于在云存储上传完成前显示
}
```

#### 6.1.2 字段职责说明

| 字段 | 存储内容 | 是否保存到DB | 清理规则 |
|------|---------|------------|---------|
| `url` | HTTP云存储URL（永久有效） | ✅ 是 | 仅存储HTTP云URL，清除Base64/Blob |
| `tempUrl` | HTTP临时URL（备选） | ✅ 是 | 仅存储HTTP临时URL，清除Base64/Blob |
| `uploadStatus` | 上传状态 | ✅ 是 | 永久保存 |
| `uploadTaskId` | 上传任务ID | ❌ 否 | 临时字段，不序列化 |
| `file` | File对象 | ❌ 否 | 不可序列化，自动清除 |
| `base64Data` | Base64数据 | ❌ 否 | 太大，不序列化，自动清除 |

#### 6.1.3 cleanAttachmentsForDb优化

**代码位置**：`attachmentUtils.ts:98-167`

```typescript
export const cleanAttachmentsForDb = (atts: Attachment[]): Attachment[] => {
  return atts.map(att => {
    const cleaned = { ...att };
    const url = cleaned.url || '';

    // ========== url字段清理 ==========
    // ❌ 清除Blob URL
    if (isBlobUrl(url)) {
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    }
    // ❌ 清除Base64 URL（绝不写入数据库）
    else if (isBase64Url(url)) {
      cleaned.url = '';
      cleaned.uploadStatus = 'pending';
    }
    // ✅ 保留HTTP URL（仅云URL）
    else if (isHttpUrl(url)) {
      // 检查是否为临时URL（包含expires参数）
      if (url.includes('expires=') || url.includes('/temp/')) {
        // ❌ 清除临时URL（不持久化）
        cleaned.url = '';
        cleaned.uploadStatus = 'pending';
      }
      // ✅ 保留云URL（uploadStatus='completed'时）
      else if (cleaned.uploadStatus === 'completed') {
        // 保留（这是云URL）
      }
      // ⚠️ 其他HTTP URL标记为pending（等待上传）
      else {
        cleaned.uploadStatus = 'pending';
      }
    }

    // ========== tempUrl字段清理 ==========
    if (cleaned.tempUrl) {
      // ❌ 清除Blob URL
      if (isBlobUrl(cleaned.tempUrl)) {
        delete cleaned.tempUrl;
      }
      // ❌ 清除Base64 URL（绝不写入数据库）
      else if (isBase64Url(cleaned.tempUrl)) {
        delete cleaned.tempUrl;
      }
      // ✅ 保留HTTP临时URL（作为备选）
      else if (isHttpUrl(cleaned.tempUrl)) {
        // 检查是否为临时URL
        if (cleaned.tempUrl.includes('expires=') || cleaned.tempUrl.includes('/temp/')) {
          // ✅ 保留（Tongyi临时URL，作为备选）
          // 注意：如果上传完成，tempUrl应该被清空
        } else {
          // ⚠️ 非临时URL，可能是云URL，应该移到url字段
          if (!cleaned.url) {
            cleaned.url = cleaned.tempUrl;
            delete cleaned.tempUrl;
          }
        }
      }
    }

    // ========== 清除不可序列化字段 ==========
    delete cleaned.file;
    delete cleaned.base64Data;
    delete cleaned._displayUrl;
    delete cleaned.uploadTaskId;  // 临时字段，不保存

    return cleaned;
  });
};
```

### 6.2 后端数据库模型（优化版）

#### 6.2.1 MessageAttachment模型

**代码位置**：`db_models.py:591-637`

```python
class MessageAttachment(Base):
    """
    消息附件表 - 优化版（避免Base64入库）
    
    核心原则：
    - url字段：仅存储HTTP云存储URL（永久有效）
    - temp_url字段：仅存储HTTP临时URL（备选，会过期）
    - 绝不存储Base64 Data URL（太大，不持久化）
    - 绝不存储Blob URL（页面刷新后失效）
    """
    __tablename__ = "message_attachments"

    id = Column(String(36), primary_key=True)
    message_id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String(36), nullable=False, index=True)
    
    # ========== URL字段（明确职责）==========
    url = Column(Text, nullable=True)              # ✅ 仅HTTP云存储URL
                                                   # ❌ 禁止：Base64、Blob URL
    
    temp_url = Column(Text, nullable=True)         # ✅ 仅HTTP临时URL（备选）
                                                   # ❌ 禁止：Base64、Blob URL
    
    # ========== 上传状态 ==========
    upload_status = Column(String(20), default='pending')
    upload_task_id = Column(String(36), nullable=True)
    upload_error = Column(Text, nullable=True)
    
    # ========== 文件信息 ==========
    mime_type = Column(String(100), nullable=True)
    name = Column(String(255), nullable=True)
    size = Column(BigInteger, nullable=True)
    
    # ========== 云存储API相关 ==========
    file_uri = Column(Text, nullable=True)
    google_file_uri = Column(String(500), nullable=True)
    google_file_expiry = Column(BigInteger, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（前端兼容）"""
        return {
            "id": self.id,
            "messageId": self.message_id,
            "mimeType": self.mime_type,
            "name": self.name,
            "url": self.url or "",  # ✅ 云URL（如果已完成上传）
            "tempUrl": self.temp_url or "",  # ✅ 临时URL（备选）
            "uploadStatus": self.upload_status,
            "uploadTaskId": self.upload_task_id,
            "size": self.size
        }
    
    def validate_urls(self) -> bool:
        """
        验证URL字段是否符合规范
        
        返回：True如果URL有效，False如果包含禁止的URL类型
        """
        # 验证url字段
        if self.url:
            if self.url.startswith('data:') or self.url.startswith('blob:'):
                return False  # ❌ 禁止Base64和Blob URL
        
        # 验证temp_url字段
        if self.temp_url:
            if self.temp_url.startswith('data:') or self.temp_url.startswith('blob:'):
                return False  # ❌ 禁止Base64和Blob URL
        
        return True
```

#### 6.2.2 UploadTask模型（保持现有结构）

**代码位置**：`db_models.py`（UploadTask类）

```python
class UploadTask(Base):
    """
    上传任务表（保持现有结构）
    
    支持2种source类型：
    - source_file_path：本地临时文件路径
    - source_url：HTTP URL（Worker下载）
    """
    __tablename__ = 'upload_tasks'

    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), nullable=False)
    message_id = Column(String(36), nullable=True)
    attachment_id = Column(String(36), nullable=True)
    
    # ========== 文件来源（2选1）==========
    source_file_path = Column(Text, nullable=True)   # 本地临时文件路径
    source_url = Column(Text, nullable=True)         # HTTP URL（Worker下载）
    # ❌ 不支持source_base64（验证发现不存在）
    
    # ========== 目标信息 ==========
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    target_url = Column(Text, nullable=True)         # 云存储URL（上传成功后）
    
    # ========== 状态管理 ==========
    status = Column(String(20), default='pending')   # pending | uploading | completed | failed
    worker_name = Column(String(100), nullable=True)
    
    # ========== 时间戳 ==========
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # ========== 重试相关 ==========
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
```

### 6.3 数据验证规则

#### 6.3.1 后端验证（sessions.py）

**代码位置**：`sessions.py:408-430`

```python
# 处理前端发送的URL
frontend_url = att.get("url", "")

# ❌ 拒绝Base64 URL
if frontend_url.startswith("data:"):
    # 使用权威URL（云URL）或清空
    final_url = authoritative_url or ""
    logger.warning(f"[Sessions] 拒绝Base64 URL，使用权威URL: {authoritative_url}")

# ❌ 拒绝Blob URL
elif frontend_url.startswith("blob:"):
    # 使用权威URL（云URL）或清空
    final_url = authoritative_url or ""
    logger.warning(f"[Sessions] 拒绝Blob URL，使用权威URL: {authoritative_url}")

# ✅ 接受HTTP URL（检查是否为云URL）
elif frontend_url.startswith("http"):
    # 检查是否为临时URL
    if frontend_url.includes('expires=') or frontend_url.includes('/temp/'):
        # ⚠️ 临时URL，不持久化到url字段
        final_url = authoritative_url or ""
        # 可选：保存到temp_url字段（作为备选）
        temp_url = frontend_url
    else:
        # ✅ 云URL，直接使用
        final_url = frontend_url
else:
    # 空URL或其他格式，使用权威URL
    final_url = authoritative_url or ""
```

#### 6.3.2 数据库约束（可选）

**建议添加数据库约束**：

```sql
-- 添加CHECK约束（PostgreSQL示例）
ALTER TABLE message_attachments
ADD CONSTRAINT check_url_not_base64 
CHECK (url IS NULL OR url NOT LIKE 'data:%');

ALTER TABLE message_attachments
ADD CONSTRAINT check_url_not_blob 
CHECK (url IS NULL OR url NOT LIKE 'blob:%');

ALTER TABLE message_attachments
ADD CONSTRAINT check_temp_url_not_base64 
CHECK (temp_url IS NULL OR temp_url NOT LIKE 'data:%');

ALTER TABLE message_attachments
ADD CONSTRAINT check_temp_url_not_blob 
CHECK (temp_url IS NULL OR temp_url NOT LIKE 'blob:%');
```

**注意**：SQLite不支持CHECK约束，需要在应用层验证。

### 6.4 数据迁移策略

#### 6.4.1 清理现有Base64数据

**迁移脚本**：

```python
# migrations/clean_base64_urls.py
def clean_base64_urls(db: Session):
    """
    清理数据库中现有的Base64 URL
    
    策略：
    1. 如果upload_status='completed'，查询UploadTask获取云URL
    2. 如果upload_status='pending'，清空url字段（等待重新上传）
    3. 清空所有Base64 temp_url
    """
    # 查询所有包含Base64 URL的附件
    attachments = db.query(MessageAttachment).filter(
        or_(
            MessageAttachment.url.like('data:%'),
            MessageAttachment.temp_url.like('data:%')
        )
    ).all()
    
    for att in attachments:
        # 情况1：url字段是Base64
        if att.url and att.url.startswith('data:'):
            # 尝试从UploadTask获取云URL
            task = db.query(UploadTask).filter(
                UploadTask.attachment_id == att.id,
                UploadTask.status == 'completed'
            ).first()
            
            if task and task.target_url:
                # ✅ 使用云URL
                att.url = task.target_url
                att.upload_status = 'completed'
            else:
                # ❌ 清空Base64 URL
                att.url = ''
                att.upload_status = 'pending'
        
        # 情况2：temp_url字段是Base64
        if att.temp_url and att.temp_url.startswith('data:'):
            # ❌ 清空Base64 temp_url
            att.temp_url = None
    
    db.commit()
    logger.info(f"[Migration] 清理了 {len(attachments)} 个Base64 URL")
```

#### 6.4.2 迁移时间表

**阶段1：应用层验证（立即）**
- ✅ 前端`cleanAttachmentsForDb()`清除Base64
- ✅ 后端`sessions.py`拒绝Base64 URL

**阶段2：数据清理（1周内）**
- ✅ 运行迁移脚本清理现有Base64数据
- ✅ 验证清理结果

**阶段3：数据库约束（可选，1个月后）**
- ⚠️ 如果使用PostgreSQL，添加CHECK约束
- ⚠️ SQLite需要在应用层持续验证

## 历史加载机制（云URL持久化）

### 7.1 核心保障原则

**用户需求**：页面重载后，历史中的云URL必须能正常加载和显示。

**保障机制**：
1. ✅ **云URL持久化**：Worker上传完成后，自动更新`message_attachments.url`
2. ✅ **3层优先级保护**：会话保存时保护已有云URL（不覆盖）
3. ✅ **数据库查询优化**：页面重载时优先查询云URL
4. ✅ **备选机制**：如果`url`为空，查询`UploadTask`获取最新云URL

### 7.2 页面重载流程

#### 7.2.1 完整流程图

```
用户刷新页面
    ↓
App.tsx 加载  [App.tsx:178]
    └─ useEffect(() => { loadSession() }, [])
    ↓
loadSession()
    ├─ GET /api/sessions/{sessionId}
    └─ 返回: { id, messages: [...] }
    ↓
后端查询会话  [sessions.py:496-705]
    ├─ 查询会话基本信息
    ├─ 查询消息列表
    └─ 查询附件列表（关联查询）
        ├─ 从message_attachments表查询
        ├─ 联查UploadTask（获取最新云URL）
        └─ 返回附件数据
    ↓
setMessages(session.messages)
    ↓
前端处理附件URL  [AttachmentGrid.tsx:88-100]
    ├─ 显示优先级：url > tempUrl > fileUri
    └─ <img src={displayUrl} />
    ↓
如果url为空或无效
    ├─ 查询附件状态
    │   └─ GET /api/sessions/{sessionId}/attachments/{attachmentId}
    │       ↓
    │       后端查询：  [sessions.py:645-705]
    │       ├─ 查询UploadTask（如果upload_task_id存在）
    │       ├─ 查询MessageAttachment
    │       └─ 返回 { url, uploadStatus, taskId, taskStatus }
    │
    └─ 更新附件URL
        └─ 使用查询到的云URL更新显示
```

#### 7.2.2 后端查询逻辑（get_session_by_id）

**代码位置**：`sessions.py:496-705`

```python
async def get_session_by_id(session_id: str, user_id: str, db: Session) -> Dict[str, Any]:
    """
    获取单个会话的完整数据（v3架构）
    
    关键优化：
    1. 联查UploadTask获取最新云URL
    2. 优先使用UploadTask.target_url（最权威）
    3. 确保返回的url字段是云URL（永久有效）
    """
    # 1. 查询会话基本信息
    session = user_query.get(DBChatSession, session_id)
    
    # 2. 查询所有已完成的上传任务
    completed_tasks = db.query(UploadTask).filter(
        UploadTask.session_id == session_id,
        UploadTask.status == 'completed'
    ).all()
    task_map = {task.attachment_id: task for task in completed_tasks if task.attachment_id}
    
    # 3. 查询消息列表
    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.asc()).all()
    
    # 4. 处理每个消息的附件
    for msg in messages:
        attachments = db.query(MessageAttachment).filter(
            MessageAttachment.message_id == msg.id,
            MessageAttachment.user_id == user_id
        ).all()
        
        msg_attachments = []
        for att in attachments:
            # ✅ 优先使用UploadTask.target_url（最权威）
            task = task_map.get(att.id)
            if task and task.target_url:
                authoritative_url = task.target_url
            else:
                authoritative_url = att.url  # 使用数据库URL
            
            # ✅ 确保返回的url是云URL（永久有效）
            att_dict = att.to_dict()
            if authoritative_url and authoritative_url.startswith('http'):
                # 检查是否为临时URL
                if not authoritative_url.includes('expires=') and not authoritative_url.includes('/temp/'):
                    att_dict['url'] = authoritative_url  # ✅ 云URL
                else:
                    # ⚠️ 临时URL，尝试使用temp_url或清空
                    att_dict['url'] = att.temp_url if att.temp_url and att.temp_url.startswith('http') else ''
            else:
                att_dict['url'] = authoritative_url or ''
            
            msg_attachments.append(att_dict)
        
        msg_dict['attachments'] = msg_attachments
    
    return {
        'id': session.id,
        'messages': messages_dict
    }
```

#### 7.2.3 前端显示逻辑（AttachmentGrid）

**代码位置**：`AttachmentGrid.tsx:88-100`

```typescript
const AttachmentGrid: React.FC<{ attachments: Attachment[] }> = ({ attachments }) => {
  return (
    <div className="attachment-grid">
      {attachments.map(att => {
        // ✅ 显示优先级：url（云URL）> tempUrl（临时URL）> fileUri
        const displayUrl = att.url || att.tempUrl || att.fileUri;
        
        // ⚠️ 如果url为空，查询附件状态
        if (!att.url && att.id && att.uploadStatus !== 'completed') {
          // 异步查询附件状态
          useEffect(() => {
            fetchAttachmentStatus(att.id, sessionId).then(result => {
              if (result && result.url) {
                // 更新附件URL
                updateAttachmentUrl(att.id, result.url);
              }
            });
          }, [att.id]);
        }
        
        return (
          <img 
            key={att.id}
            src={displayUrl} 
            alt={att.name}
            onError={() => {
              // 如果显示失败，尝试查询云URL
              if (att.id) {
                fetchAttachmentStatus(att.id, sessionId).then(result => {
                  if (result && result.url) {
                    // 更新img src
                    setDisplayUrl(result.url);
                  }
                });
              }
            }}
          />
        );
      })}
    </div>
  );
};
```

### 7.3 云URL持久化保障

#### 7.3.1 Worker自动更新机制

**代码位置**：`upload_worker_pool.py:558-608`

```python
async def _handle_success(
    self,
    db: Session,
    task: UploadTask,
    cloud_url: str,
    worker_name: str
):
    """
    处理上传成功（自动更新message_attachments.url）
    
    关键保障：
    1. 更新UploadTask.target_url = 云URL
    2. 更新MessageAttachment.url = 云URL
    3. 更新MessageAttachment.upload_status = 'completed'
    """
    try:
        # 1. 更新UploadTask
        task.status = 'completed'
        task.target_url = cloud_url  # ✅ 保存云URL
        task.completed_at = datetime.utcnow()
        db.commit()
        
        # 2. 更新MessageAttachment
        if task.attachment_id:
            attachment = db.query(MessageAttachment).filter(
                MessageAttachment.id == task.attachment_id
            ).first()
            
            if attachment:
                attachment.url = cloud_url  # ✅ 保存云URL（永久有效）
                attachment.upload_status = 'completed'
                attachment.temp_url = None  # ✅ 清空临时URL
                db.commit()
                
                logger.info(f"[{worker_name}] ✅ 已更新附件URL: {task.attachment_id}")
        
        # 3. 调用更新会话附件URL（支持重试）
        await update_session_attachment_url(
            task.session_id,
            task.attachment_id,
            cloud_url,
            db
        )
        
    except Exception as e:
        logger.error(f"[{worker_name}] ❌ 更新附件URL失败: {e}")
        raise
```

#### 7.3.2 会话保存时的云URL保护

**代码位置**：`sessions.py:408-430`

```python
# ✅ 3层优先级保护（确保云URL不被覆盖）
authoritative_url = None

# 优先级1：UploadTask.target_url（最权威，Worker刚完成上传）
task = completed_tasks.get(att_id)
if task and task.target_url:
    authoritative_url = task.target_url  # ✅ 使用最新云URL

# 优先级2：Database existing URL（已有云URL）
if not authoritative_url:
    existing_att = existing_attachments.get(att_id)
    if existing_att and existing_att.url and existing_att.url.startswith('http'):
        # ✅ 检查是否为云URL（非临时URL）
        if not existing_att.url.includes('expires=') and not existing_att.url.includes('/temp/'):
            authoritative_url = existing_att.url  # ✅ 保护已有云URL

# 优先级3：Frontend URL（仅HTTP云URL）
frontend_url = att.get("url", "")
if frontend_url.startswith("http") and not frontend_url.startswith("blob:"):
    # ✅ 检查是否为云URL
    if not frontend_url.includes('expires=') and not frontend_url.includes('/temp/'):
        final_url = frontend_url  # ✅ 允许更新云URL
    else:
        # ⚠️ 临时URL，使用权威URL
        final_url = authoritative_url or ""
else:
    # ❌ 前端传来Blob/Base64，使用权威URL
    final_url = authoritative_url or ""

# ✅ 保存到数据库（确保云URL持久化）
attachment.url = final_url  # ✅ 仅HTTP云URL
attachment.upload_status = 'completed' if final_url else 'pending'
```

### 7.4 附件状态查询接口（保障机制）

#### 7.4.1 查询接口实现

**代码位置**：`sessions.py:645-705`

```python
@router.get("/sessions/{session_id}/attachments/{attachment_id}")
async def get_attachment(
    session_id: str,
    attachment_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    查询附件的最新信息（保障历史加载）
    
    查询策略：
    1. 优先查询UploadTask.target_url（最权威）
    2. 查询MessageAttachment.url（数据库URL）
    3. 确保返回的url是云URL（永久有效）
    """
    # 1. 验证会话存在
    session = user_query.get(DBChatSession, session_id)
    
    # 2. 查询UploadTask（最权威）
    task = db.query(UploadTask).filter(
        UploadTask.attachment_id == attachment_id,
        UploadTask.session_id == session_id
    ).order_by(UploadTask.completed_at.desc()).first()
    
    # 3. 查询MessageAttachment
    attachment = db.query(MessageAttachment).filter(
        MessageAttachment.id == attachment_id,
        MessageAttachment.session_id == session_id,
        MessageAttachment.user_id == user_id
    ).first()
    
    # 4. 确定权威URL
    authoritative_url = None
    if task and task.target_url:
        authoritative_url = task.target_url  # ✅ 优先使用UploadTask URL
    elif attachment and attachment.url:
        authoritative_url = attachment.url  # ✅ 使用数据库URL
    
    # 5. 构建返回结果
    result = {
        "attachmentId": attachment_id,
        "url": authoritative_url or "",  # ✅ 云URL（如果存在）
        "uploadStatus": attachment.upload_status if attachment else "pending",
        "taskId": task.id if task else None,
        "taskStatus": task.status if task else None,
        "mimeType": attachment.mime_type if attachment else None,
        "name": attachment.name if attachment else None
    }
    
    return result
```

#### 7.4.2 前端查询函数

**代码位置**：`attachmentUtils.ts:590-630`

```typescript
export const fetchAttachmentStatus = async (
  sessionId: string,
  attachmentId: string
): Promise<{ url: string; uploadStatus: string; taskId?: string; taskStatus?: string } | null> => {
  try {
    const response = await fetch(
      `/api/sessions/${sessionId}/attachments/${attachmentId}`,
      { credentials: 'include' }
    );
    
    if (!response.ok) {
      return null;
    }
    
    const data = await response.json();
    
    // ✅ 确保返回的url是云URL（永久有效）
    if (data.url && isHttpUrl(data.url)) {
      // 检查是否为临时URL
      if (data.url.includes('expires=') || data.url.includes('/temp/')) {
        // ⚠️ 临时URL，返回空（等待上传完成）
        return { ...data, url: '' };
      }
      // ✅ 云URL，直接返回
      return data;
    }
    
    return data;
  } catch (e) {
    console.error('[fetchAttachmentStatus] 查询异常:', e);
    return null;
  }
};
```

### 7.5 页面重载后的URL恢复策略

#### 7.5.1 恢复优先级

```
页面重载后URL恢复优先级：

1. 数据库url字段（云URL）
   ├─ 如果upload_status='completed' → 直接使用
   └─ 如果upload_status='pending' → 查询UploadTask

2. UploadTask.target_url（最权威）
   ├─ 如果status='completed' → 使用target_url
   └─ 如果status='pending' → 等待上传完成

3. tempUrl字段（HTTP临时URL，备选）
   ├─ 仅当url为空时使用
   └─ 可能已过期，需要重新上传

4. 查询附件状态接口
   └─ GET /api/sessions/{sessionId}/attachments/{attachmentId}
       └─ 返回最新云URL
```

#### 7.5.2 前端恢复逻辑

**代码位置**：`useInitData.ts` 或 `App.tsx`

```typescript
// 页面加载时恢复附件URL
useEffect(() => {
  if (messages.length > 0) {
    // 检查所有附件的URL
    const attachmentsToCheck = messages
      .flatMap(msg => msg.attachments || [])
      .filter(att => !att.url || att.uploadStatus !== 'completed');
    
    // 批量查询附件状态
    Promise.all(
      attachmentsToCheck.map(att => 
        fetchAttachmentStatus(sessionId, att.id).then(result => {
          if (result && result.url) {
            // 更新附件URL
            updateAttachmentUrl(att.id, result.url);
          }
        })
      )
    );
  }
}, [messages, sessionId]);
```

### 7.6 保障措施总结

| 保障措施 | 实现位置 | 保障效果 |
|---------|---------|---------|
| **Worker自动更新** | `upload_worker_pool.py:558` | ✅ 上传完成后自动更新`url=云URL` |
| **3层优先级保护** | `sessions.py:408` | ✅ 会话保存时保护已有云URL |
| **数据库查询优化** | `sessions.py:496` | ✅ 联查UploadTask获取最新云URL |
| **附件状态查询** | `sessions.py:645` | ✅ 页面重载时查询最新云URL |
| **前端URL恢复** | `AttachmentGrid.tsx` | ✅ 自动查询并更新附件URL |
| **Base64清理** | `cleanAttachmentsForDb` | ✅ 确保Base64不写入数据库 |

## 功能兼容性保障

### 8.1 核心功能保留清单

基于综合流程文档的分析，以下功能必须100%保留：

#### ✅ 功能1：CONTINUITY LOGIC（Edit模式）

**功能描述**：Edit模式无新上传时，自动复用画布图片。

**保留策略**：
- ✅ 保留`prepareAttachmentForApi()`函数
- ✅ 保留`findAttachmentByUrl()`函数
- ✅ 保留`tryFetchCloudUrl()`函数
- ✅ 优化：HTTP URL跳过Base64转换（后端直接下载）

**代码位置**：`attachmentUtils.ts:798-814`

```typescript
// ✅ 保留CONTINUITY LOGIC
if (finalAttachments.length === 0 && activeImageUrl) {
  const skipBase64ForHttp = isHttpUrl(activeImageUrl);
  const prepared = await prepareAttachmentForApi(
    activeImageUrl,
    messages,
    sessionId,
    filePrefix,
    skipBase64ForHttp  // ✅ HTTP URL跳过Base64
  );
  if (prepared) {
    finalAttachments = [prepared];
  }
  return finalAttachments;
}
```

#### ✅ 功能2：双URL显示机制

**功能描述**：临时URL立即显示 + 云URL持久化。

**保留策略**：
- ✅ 保留`processMediaResult()`的双URL机制
- ✅ 立即显示：Base64/Blob/HTTP临时URL（无延迟）
- ✅ 后台上传：调用后端API（传递URL，后端处理）
- ✅ 自动更新：Worker自动更新数据库URL

**代码位置**：`attachmentUtils.ts:960-1016`

```typescript
// ✅ 保留双URL机制
export const processMediaResult = async (
  res: { url: string; mimeType: string },
  context: { sessionId: string; modelMessageId: string },
  filePrefix: string
) => {
  // 1. 立即显示（临时URL）
  let displayUrl: string;
  if (isHttpUrl(res.url)) {
    // Tongyi: HTTP临时URL → 下载为Blob URL（仅用于显示）
    const response = await fetch(res.url);
    const blob = await response.blob();
    displayUrl = URL.createObjectURL(blob);
  } else {
    // Google: Base64 → 直接使用
    displayUrl = res.url;
  }

  const displayAttachment: Attachment = {
    id: attachmentId,
    url: displayUrl,  // ✅ 临时URL（立即显示）
    tempUrl: res.url,  // ✅ 保存原始URL
    uploadStatus: 'pending'
  };

  // 2. 后台上传（调用后端API）
  const dbAttachmentPromise = uploadAttachment(res.url, context);
  
  return { displayAttachment, dbAttachmentPromise };
};
```

#### ✅ 功能3：跨模式传递

**功能描述**：通过`tempUrl`字段查找历史附件，实现跨模式传递。

**保留策略**：
- ✅ 保留`findAttachmentByUrl()`函数
- ✅ 保留`tempUrl`字段（仅HTTP临时URL）
- ✅ 优化：Base64不存储到`tempUrl`（仅前端内存）

**代码位置**：`attachmentUtils.ts:524-584`

```typescript
// ✅ 保留跨模式查找
export const findAttachmentByUrl = (
  targetUrl: string,
  messages: Message[]
): { attachment: Attachment; messageId: string } | null => {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (!msg.attachments?.length) continue;

    for (const att of msg.attachments) {
      // ✅ 策略1: 精确匹配 url 字段
      if (att.url === targetUrl) {
        return { attachment: att, messageId: msg.id };
      }

      // ✅ 策略2: 精确匹配 tempUrl 字段（跨模式关键）
      if (att.tempUrl === targetUrl) {
        return { attachment: att, messageId: msg.id };
      }

      // ✅ 策略3: 模糊匹配（去除查询参数）
      const attUrlBase = att.url?.split('?')[0];
      const targetUrlBase = targetUrl.split('?')[0];
      if (attUrlBase && targetUrlBase && attUrlBase === targetUrlBase) {
        return { attachment: att, messageId: msg.id };
      }
    }
  }

  return null;
};
```

#### ✅ 功能4：异步上传机制

**功能描述**：Worker Pool + Redis队列，不阻塞前端。

**保留策略**：
- ✅ 完全保留现有异步上传机制
- ✅ 复用`UploadTask` + Redis队列
- ✅ 复用Worker Pool处理逻辑
- ✅ 复用自动更新机制

**代码位置**：`upload_worker_pool.py:381-491`

```python
# ✅ 完全保留现有机制
async def _process_task(self, task_id: str, worker_name: str):
    # 1. 查询任务
    task = db.query(UploadTask).filter_by(id=task_id).first()
    
    # 2. 更新状态
    task.status = 'uploading'
    db.commit()
    
    # 3. 读取文件内容
    file_content = await self._get_file_content(task, worker_name)
    
    # 4. 上传到云存储
    cloud_url = await StorageService.upload_file(...)
    
    # 5. 更新数据库
    await self._handle_success(db, task, cloud_url, worker_name)
```

#### ✅ 功能5：云URL保护

**功能描述**：3层优先级保护，防止云URL被覆盖。

**保留策略**：
- ✅ 完全保留现有保护逻辑
- ✅ 优先级1：UploadTask.target_url
- ✅ 优先级2：Database existing URL
- ✅ 优先级3：Frontend URL（仅HTTP云URL）

**代码位置**：`sessions.py:408-430`（已实现）

### 8.2 功能变更清单

#### 变更1：前端不再下载HTTP URL（用于上传）

**变更前**：
```typescript
// ❌ 前端下载HTTP URL用于上传
if (isHttpUrl(res.url)) {
  const file = await sourceToFile(res.url);  // 下载
  await storageUpload.uploadFileAsync(file);  // 上传
}
```

**变更后**：
```typescript
// ✅ 直接传递URL，后端处理
await uploadAttachment(res.url, context);  // 后端下载并上传
```

**影响**：
- ✅ 减少前端网络开销（不下载用于上传）
- ✅ 保留即时显示功能（用户体验不变）

#### 变更2：Base64不写入数据库

**变更前**：
```python
# ⚠️ 可能存储Base64 URL
attachment.url = frontend_url  # 可能是Base64
```

**变更后**：
```python
# ✅ 拒绝Base64 URL
if frontend_url.startswith("data:"):
    final_url = authoritative_url or ""  # 使用云URL或清空
```

**影响**：
- ✅ 减少数据库存储空间（Base64增加33%大小）
- ✅ 页面重载后必须使用云URL（不依赖Base64）

#### 变更3：简化前端处理函数

**移除函数**（用于上传的目的）：
- ❌ `sourceToFile()` - 删除（用于上传）
- ❌ `fileToBase64()` - 删除（用于传输）
- ❌ `urlToFile()` - 删除（用于上传）

**保留函数**（用于显示和查找）：
- ✅ `isHttpUrl()`, `isBlobUrl()`, `isBase64Url()` - 保留（URL类型判断）
- ✅ `findAttachmentByUrl()` - 保留（CONTINUITY LOGIC）
- ✅ `tryFetchCloudUrl()` - 保留（查询云URL）
- ✅ `cleanAttachmentsForDb()` - 保留（简化版）

**新增函数**：
- ✅ `uploadAttachment()` - 新增（调用后端API）

### 8.3 向后兼容策略

#### 兼容策略1：旧数据迁移

**问题**：现有数据库可能包含Base64 URL。

**解决方案**：
1. **应用层验证**（立即生效）
   - 前端`cleanAttachmentsForDb()`清除Base64
   - 后端`sessions.py`拒绝Base64 URL

2. **数据迁移脚本**（1周内）
   - 清理现有Base64 URL
   - 查询UploadTask获取云URL
   - 更新`message_attachments.url`

3. **兼容层**（3个月）
   - `MessageAttachment.to_dict()`优先使用`url`，回退到`tempUrl`
   - 前端`getDisplayUrl()`支持旧字段

#### 兼容策略2：前端兼容层

**代码位置**：`attachmentUtils.ts`（新增）

```typescript
// 兼容层：支持旧数据格式
export const getDisplayUrl = (att: Attachment): string => {
  // 优先级1：url字段（云URL）
  if (att.url && isHttpUrl(att.url)) {
    return att.url;
  }
  
  // 优先级2：tempUrl字段（临时URL，兼容旧数据）
  if (att.tempUrl && isHttpUrl(att.tempUrl)) {
    return att.tempUrl;
  }
  
  // 优先级3：fileUri字段
  if (att.fileUri) {
    return att.fileUri;
  }
  
  return '';
};
```

#### 兼容策略3：渐进式迁移

**阶段1**（Week 1-2）：新功能上线
- ✅ 新附件使用统一后端接口
- ✅ 旧附件继续使用现有逻辑（兼容）

**阶段2**（Week 3-4）：数据迁移
- ✅ 运行迁移脚本清理Base64数据
- ✅ 验证迁移结果

**阶段3**（Month 2-3）：废弃旧逻辑
- ⚠️ 标记旧函数为`@deprecated`
- ⚠️ 添加兼容层（3个月后删除）

## 实施计划

### 9.1 分阶段实施策略

基于综合流程文档的分析，采用**渐进式迁移**策略，确保功能不丢失、数据不丢失。

#### 阶段1：后端统一接口开发（Week 1-2）

**目标**：创建统一附件处理接口，复用现有异步上传机制。

**任务清单**：

1. **创建UnifiedAttachmentProcessor类**
   - [ ] 实现`process_file()` - 处理File对象
   - [ ] 实现`process_http_url()` - 处理HTTP URL（创建source_url任务）
   - [ ] 实现`process_base64_url()` - 处理Base64 URL（解码后创建source_file_path任务）
   - [ ] 实现`process_attachment_id()` - 处理已有附件ID
   - [ ] 集成现有异步上传机制（UploadTask + Redis队列）

2. **新增API接口**
   - [ ] `POST /api/attachments/prepare` - 统一附件上传接口
   - [ ] `GET /api/attachments/{attachmentId}` - 附件状态查询接口（复用现有）
   - [ ] `POST /api/attachments/batch` - 批量查询接口（可选）

3. **测试**
   - [ ] 单元测试（File / HTTP URL / Base64 / attachmentId）
   - [ ] 集成测试（端到端上传流程）
   - [ ] 性能测试（并发上传）

**交付物**：
- `backend/app/services/attachment_processor.py`（新增）
- `backend/app/routers/storage/attachments.py`（新增）
- 测试覆盖率 ≥ 90%

**代码示例**：

```python
# backend/app/services/attachment_processor.py
class UnifiedAttachmentProcessor:
    async def process(
        self,
        source: Union[UploadFile, str, dict],
        session_id: str,
        message_id: Optional[str] = None,
        attachment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """统一处理附件"""
        if isinstance(source, UploadFile):
            return await self._process_file(source, session_id, message_id, attachment_id)
        elif isinstance(source, str):
            return await self._process_url(source, session_id, message_id, attachment_id)
        elif isinstance(source, dict) and 'attachmentId' in source:
            return await self._process_attachment_id(source['attachmentId'], session_id)
        else:
            raise ValueError(f"不支持的source类型: {type(source)}")
```

#### 阶段2：前端调用后端接口（Week 3-4）

**目标**：前端简化处理逻辑，调用后端统一接口。

**任务清单**：

1. **创建uploadAttachment函数**
   - [ ] 实现`uploadAttachment(file, context)` - 上传File对象
   - [ ] 实现`uploadAttachmentFromUrl(url, context)` - 上传URL
   - [ ] 集成到`processMediaResult()`

2. **更新processMediaResult（保留双URL机制）**
   - [ ] 保留立即显示逻辑（Base64/Blob/HTTP临时URL）
   - [ ] 移除前端下载逻辑（用于上传）
   - [ ] 调用后端API（传递URL，后端处理）

3. **更新processUserAttachments（保留CONTINUITY LOGIC）**
   - [ ] 保留CONTINUITY LOGIC
   - [ ] 移除Base64转换（用于传输）
   - [ ] HTTP URL直接传递（后端下载）

4. **更新cleanAttachmentsForDb（避免Base64入库）**
   - [ ] 清除Base64 URL（绝不写入数据库）
   - [ ] 清除Blob URL（不持久化）
   - [ ] 清除HTTP临时URL（不持久化到url字段）

5. **测试**
   - [ ] 前端单元测试
   - [ ] 端到端测试（Edit模式、Gen模式）
   - [ ] 兼容性测试（旧数据）

**交付物**：
- `frontend/hooks/handlers/attachmentUtils.ts`（简化版）
- `frontend/components/chat/InputArea.tsx`（更新）
- 测试覆盖率 ≥ 80%

**代码示例**：

```typescript
// frontend/hooks/handlers/attachmentUtils.ts
export const uploadAttachment = async (
  source: File | string,
  context: { sessionId: string; messageId: string; attachmentId?: string }
): Promise<Attachment> => {
  if (source instanceof File) {
    // 模式1：上传File对象
    const formData = new FormData();
    formData.append('file', source);
    formData.append('sessionId', context.sessionId);
    formData.append('messageId', context.messageId);
    if (context.attachmentId) {
      formData.append('attachmentId', context.attachmentId);
    }

    const response = await fetch('/api/attachments/prepare', {
      method: 'POST',
      body: formData,
      credentials: 'include'
    });
    // ... 处理响应
  } else {
    // 模式2：上传URL（HTTP或Base64）
    const response = await fetch('/api/attachments/prepare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: source,
        sessionId: context.sessionId,
        messageId: context.messageId,
        attachmentId: context.attachmentId
      }),
      credentials: 'include'
    });
    // ... 处理响应
  }
};
```

#### 阶段3：数据迁移和清理（Week 5）

**目标**：清理现有Base64数据，确保数据库不包含Base64 URL。

**任务清单**：

1. **数据迁移脚本**
   - [ ] 查询所有包含Base64 URL的附件
   - [ ] 查询UploadTask获取云URL
   - [ ] 更新`message_attachments.url`（使用云URL）
   - [ ] 清空Base64 `temp_url`

2. **验证迁移结果**
   - [ ] 验证无Base64 URL残留
   - [ ] 验证云URL正确性
   - [ ] 验证历史附件可正常加载

3. **数据库约束（可选）**
   - [ ] PostgreSQL：添加CHECK约束（禁止Base64/Blob URL）
   - [ ] SQLite：应用层持续验证

**交付物**：
- `migrations/clean_base64_urls.py`（迁移脚本）
- 迁移报告（清理数量、成功率）

#### 阶段4：性能优化和监控（Week 6）

**目标**：优化性能，添加监控。

**任务清单**：

1. **性能优化**
   - [ ] Redis缓存（HTTP URL → 云URL映射，1小时TTL）
   - [ ] 批量查询接口（减少HTTP请求）
   - [ ] 云存储上传优化（支持分片上传，大文件）

2. **监控**
   - [ ] 添加性能指标（延迟、成功率、缓存命中率）
   - [ ] 添加错误监控（上传失败率、Base64检测）
   - [ ] Grafana看板

**交付物**：
- Redis缓存配置
- 性能监控看板（Grafana）

### 9.2 时间表

```
Week 1-2: 后端统一接口开发
├─ Day 1-3: UnifiedAttachmentProcessor 类开发
├─ Day 4-6: API 接口实现 + 集成异步上传机制
└─ Day 7-10: 单元测试 + 集成测试

Week 3-4: 前端调用后端接口
├─ Day 1-2: uploadAttachment() 函数开发
├─ Day 3-5: 更新前端组件（processMediaResult, InputArea）
└─ Day 6-10: 前端单元测试 + 端到端测试

Week 5: 数据迁移和清理
├─ Day 1-2: 数据迁移脚本开发
├─ Day 3-4: 运行迁移脚本 + 验证
└─ Day 5: 回归测试

Week 6: 性能优化和监控
├─ Day 1-2: Redis 缓存实现
├─ Day 3-4: 批量查询接口
└─ Day 5: 性能测试 + 监控部署
```

### 9.3 验收标准

#### 功能验收

- ✅ **CONTINUITY LOGIC**：Edit模式无新上传时自动复用画布图片
- ✅ **双URL显示**：临时URL立即显示 + 云URL持久化
- ✅ **跨模式传递**：通过`tempUrl`查找历史附件
- ✅ **历史加载**：页面重载后云URL正常显示
- ✅ **异步上传**：Worker Pool自动更新数据库URL

#### 性能验收

| 指标 | 当前值 | 目标值 | 验收标准 |
|-----|-------|-------|---------|
| **前端下载次数** | 2次（Tongyi） | 0次 | ✅ 前端不下载用于上传 |
| **Base64写入数据库** | 可能 | 0次 | ✅ 数据库无Base64 URL |
| **历史加载成功率** | 80% | 100% | ✅ 页面重载后所有附件可显示 |
| **前端代码行数** | 1200行 | 700行 | ✅ 减少42% |

#### 数据验收

- ✅ 数据库无Base64 URL（`url`和`temp_url`字段）
- ✅ 数据库无Blob URL（`url`和`temp_url`字段）
- ✅ 所有已完成上传的附件，`url`字段存储云URL
- ✅ 页面重载后，所有附件可正常显示

---

## 风险评估与缓解

### 10.1 技术风险

#### 风险1：后端负载增加

**描述**：所有图片下载和处理都在后端执行，可能导致CPU、内存、带宽占用增加。

**影响评估**：
- **CPU**：Base64解码、图片验证（+10%）
- **内存**：临时文件存储（+500MB，峰值）
- **带宽**：HTTP URL下载（+2MB/附件，Tongyi场景）

**缓解方案**：
1. **复用现有异步上传机制**：Worker Pool已支持并发处理（多Worker线程）
2. **Redis缓存**：缓存HTTP URL → 云URL映射（1小时TTL，避免重复下载）
3. **限流**：单用户每分钟最多上传10个附件
4. **水平扩展**：增加Worker数量（根据负载动态调整）
5. **临时文件清理**：Worker处理完成后立即删除临时文件

**优先级**：🟡 中

**监控指标**：
- Worker CPU使用率
- 临时目录磁盘使用率
- Redis队列长度
- 上传任务处理时间

#### 风险2：HTTP URL下载失败

**描述**：后端Worker下载HTTP URL可能因为网络超时、404错误、CORS等失败。

**影响评估**：
- **Tongyi临时URL**：24小时有效期，过期后无法下载
- **网络超时**：30秒超时，可能中断
- **CORS问题**：某些URL可能无法直接下载

**缓解方案**：
1. **重试机制**：Worker支持指数退避重试（3次）
2. **超时控制**：30秒超时，避免长时间阻塞
3. **降级方案**：如果下载失败，返回临时URL（前端仍可显示，但需重新上传）
4. **错误日志**：记录详细的错误信息（URL、错误类型、重试次数）
5. **CORS代理**：后端提供代理下载接口（`/api/storage/download?url=xxx`）

**优先级**：🟡 中

**代码示例**：

```python
# upload_worker_pool.py:526-532
async def _get_file_content(self, task: UploadTask, worker_name: str) -> bytes:
    if task.source_url:
        # ✅ 重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(task.source_url)
                    response.raise_for_status()
                    return response.content
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"下载失败（已重试{max_retries}次）: {e}")
```

#### 风险3：Base64解码失败

**描述**：后端解码Base64 Data URL可能因为格式错误、数据损坏等失败。

**影响评估**：
- **格式错误**：无效的Data URL格式
- **数据损坏**：Base64字符串不完整
- **内存溢出**：超大Base64数据（>10MB）

**缓解方案**：
1. **格式验证**：使用正则表达式验证Data URL格式
2. **大小限制**：Base64数据最大10MB（与文件大小限制一致）
3. **错误处理**：捕获解码异常，返回友好错误信息
4. **日志记录**：记录Base64数据大小、MIME类型

**优先级**：🟢 低

### 10.2 兼容性风险

#### 风险1：旧数据无法显示

**描述**：现有数据库中的附件使用`tempUrl`和`base64Data`，新架构无法识别。

**影响评估**：
- **Base64 URL**：数据库可能包含Base64 URL（迁移前）
- **Blob URL**：数据库可能包含Blob URL（已失效）
- **临时URL过期**：Tongyi临时URL可能已过期

**缓解方案**：
1. **兼容层保留3个月**：`MessageAttachment.to_dict()`优先使用`url`，回退到`tempUrl`
2. **渐进式迁移**：数据迁移脚本批量上传到云存储
3. **前端兼容**：`getDisplayUrl()`函数支持旧字段
4. **查询UploadTask**：如果`url`为空，查询`UploadTask`获取最新云URL

**优先级**：🔴 高

**迁移脚本**：

```python
# migrations/clean_base64_urls.py
def migrate_old_attachments(db: Session):
    """迁移旧附件数据"""
    # 1. 查询所有包含Base64/Blob URL的附件
    attachments = db.query(MessageAttachment).filter(
        or_(
            MessageAttachment.url.like('data:%'),
            MessageAttachment.url.like('blob:%'),
            MessageAttachment.temp_url.like('data:%'),
            MessageAttachment.temp_url.like('blob:%')
        )
    ).all()
    
    for att in attachments:
        # 2. 查询UploadTask获取云URL
        task = db.query(UploadTask).filter(
            UploadTask.attachment_id == att.id,
            UploadTask.status == 'completed'
        ).first()
        
        if task and task.target_url:
            # ✅ 使用云URL
            att.url = task.target_url
            att.upload_status = 'completed'
            att.temp_url = None
        else:
            # ❌ 清空无效URL
            if att.url and (att.url.startswith('data:') or att.url.startswith('blob:')):
                att.url = ''
                att.upload_status = 'pending'
            if att.temp_url and (att.temp_url.startswith('data:') or att.temp_url.startswith('blob:')):
                att.temp_url = None
    
    db.commit()
```

#### 风险2：前端组件依赖旧字段

**描述**：前端组件可能依赖`tempUrl`、`base64Data`等字段。

**影响评估**：
- **AttachmentGrid**：使用`att.url || att.tempUrl`
- **ImageEditView**：使用`activeImageUrl`（可能来自`tempUrl`）
- **跨模式传递**：依赖`tempUrl`查找历史附件

**缓解方案**：
1. **保留`tempUrl`字段**：仅存储HTTP临时URL（不存储Base64/Blob）
2. **兼容层**：`getDisplayUrl()`函数支持旧字段（3个月后删除）
3. **渐进式更新**：逐个组件更新，确保兼容性

**优先级**：🟡 中

### 10.3 数据风险

#### 风险1：数据库迁移失败

**描述**：数据迁移脚本可能因为数据量大、网络问题等失败。

**影响评估**：
- **数据丢失**：迁移过程中数据损坏
- **服务中断**：迁移期间无法访问附件
- **回滚困难**：迁移后难以回滚

**缓解方案**：
1. **备份数据库**：迁移前完整备份
2. **分批迁移**：每次迁移1000条记录，避免长时间锁定
3. **验证机制**：迁移后验证数据完整性
4. **回滚脚本**：准备回滚脚本（从备份恢复）

**优先级**：🔴 高

#### 风险2：云存储成本增加

**描述**：所有附件都上传到云存储，可能增加存储成本。

**影响评估**：
- **存储成本**：每个附件占用云存储空间
- **流量成本**：下载附件产生流量费用
- **成本估算**：1000个附件 × 1MB = 1GB存储

**缓解方案**：
1. **成本监控**：定期监控云存储使用量
2. **清理策略**：定期清理未使用的附件（6个月未访问）
3. **压缩优化**：图片压缩（WebP格式，减少30%大小）
4. **CDN缓存**：使用CDN缓存热门附件（减少流量成本）

**优先级**：🟡 中

### 10.4 功能风险

#### 风险1：CONTINUITY LOGIC失效

**描述**：如果`tempUrl`字段不存储Base64/Blob URL，跨模式查找可能失效。

**影响评估**：
- **Edit模式**：无新上传时无法复用画布图片
- **跨模式传递**：无法通过`tempUrl`查找历史附件

**缓解方案**：
1. **保留`tempUrl`字段**：仅存储HTTP临时URL（用于跨模式查找）
2. **优化查找逻辑**：`findAttachmentByUrl()`优先匹配`url`字段（云URL）
3. **备选策略**：如果`tempUrl`匹配失败，查询`UploadTask`获取云URL

**优先级**：🔴 高

**代码示例**：

```typescript
// ✅ 优化后的findAttachmentByUrl
export const findAttachmentByUrl = (
  targetUrl: string,
  messages: Message[]
): { attachment: Attachment; messageId: string } | null => {
  // 策略1：精确匹配url字段（云URL，优先）
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    for (const att of msg.attachments || []) {
      if (att.url === targetUrl) {
        return { attachment: att, messageId: msg.id };
      }
    }
  }
  
  // 策略2：精确匹配tempUrl字段（HTTP临时URL，备选）
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    for (const att of msg.attachments || []) {
      if (att.tempUrl === targetUrl && isHttpUrl(att.tempUrl)) {
        return { attachment: att, messageId: msg.id };
      }
    }
  }
  
  // 策略3：模糊匹配（去除查询参数）
  // ... 现有逻辑
  
  return null;
};
```

#### 风险2：历史附件无法加载

**描述**：如果Worker上传失败或未完成，页面重载后附件无法显示。

**影响评估**：
- **上传失败**：`url`字段为空，无法显示
- **上传未完成**：`url`字段为空，临时URL已过期

**缓解方案**：
1. **查询UploadTask**：如果`url`为空，查询`UploadTask`获取最新状态
2. **重试机制**：上传失败后自动重试（3次）
3. **错误提示**：前端显示上传失败提示，允许用户重新上传
4. **备选显示**：如果云URL不可用，显示占位符（"上传中..."或"上传失败"）

**优先级**：🔴 高

### 10.5 监控和告警

#### 监控指标

| 指标 | 阈值 | 告警级别 |
|-----|------|---------|
| **Base64 URL检测** | > 0 | 🔴 高（数据库不应包含Base64） |
| **上传失败率** | > 5% | 🟡 中 |
| **Worker队列长度** | > 100 | 🟡 中 |
| **临时目录使用率** | > 80% | 🟡 中 |
| **历史加载失败率** | > 1% | 🔴 高 |

#### 告警规则

```yaml
# Grafana告警规则
- alert: Base64URLDetected
  expr: count(message_attachments{url=~"data:.*"}) > 0
  severity: critical
  message: "数据库检测到Base64 URL，应立即清理"

- alert: UploadFailureRateHigh
  expr: rate(upload_tasks{status="failed"}[5m]) > 0.05
  severity: warning
  message: "上传失败率超过5%"

- alert: HistoryLoadFailure
  expr: rate(attachment_queries{result="not_found"}[5m]) > 0.01
  severity: critical
  message: "历史附件加载失败率超过1%"
```

### 10.6 回滚计划

#### 回滚触发条件

- 🔴 **严重问题**：Base64 URL大量写入数据库
- 🔴 **严重问题**：历史附件无法加载（>10%）
- 🟡 **中等问题**：上传失败率>10%
- 🟡 **中等问题**：Worker队列积压>500

#### 回滚步骤

1. **停止新功能**：前端回退到旧版本（使用旧逻辑）
2. **数据恢复**：从备份恢复数据库（如果数据损坏）
3. **代码回退**：Git回退到上一个稳定版本
4. **验证功能**：确保所有功能正常

#### 回滚时间估算

- **前端回退**：5分钟（Git回退 + 重新部署）
- **后端回退**：10分钟（Git回退 + 重启服务）
- **数据恢复**：30分钟（从备份恢复）

---

## 总结

### 11.1 核心设计要点

基于[GEN和EDIT模式完整流程综合文档](./cursor-GEN和EDIT模式完整流程综合文档.md)的深入分析，本设计方案的核心要点：

1. ✅ **附件统一后端处理**：所有下载、转换、上传统一在后端完成
2. ✅ **避免Base64入库**：Base64绝不写入数据库，仅用于前端即时显示
3. ✅ **明确URL职责**：临时URL用于显示，云URL用于持久化
4. ✅ **历史加载保障**：页面重载后云URL正常加载（3层优先级保护）
5. ✅ **功能不丢失**：CONTINUITY LOGIC、双URL显示、跨模式传递全部保留

### 11.2 预期收益

| 指标 | 当前值 | 目标值 | 改善幅度 |
|-----|-------|-------|---------|
| **前端下载次数** | 2次（Tongyi） | 0次 | -100% |
| **Base64写入数据库** | 可能 | 0次 | -100% |
| **历史加载成功率** | 80% | 100% | +25% |
| **前端代码行数** | 1200行 | 700行 | -42% |
| **网络传输** | 4.67MB | 2MB | -57% |
| **处理延迟** | 3-5秒 | 1-2秒 | -60% |

### 11.3 实施优先级

**P0（必须）**：
- ✅ 后端统一接口开发
- ✅ 前端调用后端接口
- ✅ Base64清理（数据迁移）

**P1（重要）**：
- ✅ 历史加载保障机制
- ✅ 功能兼容性保障
- ✅ 监控和告警

**P2（优化）**：
- ⚠️ Redis缓存
- ⚠️ 批量查询接口
- ⚠️ 性能优化

---

## 附录

### A. 关键文件索引

| 类别 | 文件路径 | 关键函数 |
|------|---------|---------|
| **前端附件处理** | `frontend/hooks/handlers/attachmentUtils.ts` | processUserAttachments, processMediaResult, cleanAttachmentsForDb |
| **前端视图** | `frontend/components/views/ImageEditView.tsx` | handleSend, CONTINUITY LOGIC |
| **前端视图** | `frontend/components/views/ImageGenView.tsx` | handleSend |
| **前端Handler** | `frontend/hooks/handlers/ImageEditHandlerClass.ts` | doExecute |
| **前端Handler** | `frontend/hooks/handlers/ImageGenHandlerClass.ts` | doExecute |
| **后端路由** | `backend/app/routers/core/modes.py` | handle_mode, convert_attachments_to_reference_images |
| **后端会话** | `backend/app/routers/user/sessions.py` | create_or_update_session, get_session_by_id, get_attachment |
| **后端Worker** | `backend/app/services/common/upload_worker_pool.py` | submit_task, _process_task, _handle_success |
| **后端存储** | `backend/app/routers/storage/storage.py` | upload_file_async |
| **数据库模型** | `backend/app/models/db_models.py` | MessageAttachment, UploadTask |

### B. API端点索引

| 端点 | 方法 | 用途 | 调用位置 |
|------|------|------|---------|
| `/api/attachments/prepare` | POST | 统一附件上传接口（新增） | `uploadAttachment()` |
| `/api/attachments/{attachmentId}` | GET | 查询附件状态 | `fetchAttachmentStatus()` |
| `/api/sessions/{sessionId}` | GET | 获取会话详情（含附件） | `loadSession()` |
| `/api/sessions/{sessionId}` | PUT | 创建或更新会话 | `updateSessionMessages()` |
| `/api/sessions/{sessionId}/attachments/{attachmentId}` | GET | 查询附件最新状态 | `tryFetchCloudUrl()` |

### C. 数据格式转换对照表

| 阶段 | 输入格式 | 输出格式 | 转换函数 | 是否持久化 |
|-----|---------|---------|---------|-----------|
| **用户上传** | File对象 | Blob URL | `URL.createObjectURL` | ❌ 否 |
| **AI返回（Google）** | Base64 Data URL | Base64 URL | 直接使用 | ❌ 否（仅前端显示） |
| **AI返回（Tongyi）** | HTTP临时URL | Blob URL | `fetch + URL.createObjectURL` | ❌ 否（仅前端显示） |
| **后端处理** | HTTP URL | 字节流 | `httpx.get()` | ❌ 否（临时文件） |
| **后端处理** | Base64 URL | 字节流 | `base64.b64decode()` | ❌ 否（临时文件） |
| **Worker上传** | 字节流 | HTTP云URL | `StorageService.upload_file` | ✅ 是（数据库url字段） |
| **页面重载** | 数据库url字段 | HTTP云URL | 直接读取 | ✅ 是（永久有效） |

---

**文档状态**: ✅ 设计文档已完成  
**最后更新**: 2026-01-18  
**下一步**: 开始阶段1开发（后端统一接口）

---

*本文档基于GEN和EDIT模式完整流程综合文档，确保功能不丢失、数据不丢失、历史可加载*

