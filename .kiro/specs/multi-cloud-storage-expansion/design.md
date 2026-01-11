# Active Cloud Storage 图片库 Tab 设计方案（逐步流程版）

> 本设计严格对应 `.kiro/specs/multi-cloud-storage-expansion/requirements.md` 的 FR/NFR 与接口约束。

## 1. 概述
在 SettingsModal 中新增一个“Gallery/Images”选项卡，用于展示当前激活云存储（Active Storage）中的图片。该功能覆盖完整端到端链路：前端 UI 入口、后端 API、Provider 适配、分页/搜索/排序和错误处理。

## 2. 名词解释
- Active Storage：当前用户激活的云存储配置（ActiveStorage 表中的 storage_id）。
- Provider：具体的云存储类型，如 lsky、aliyun-oss。
- Gallery：本设计新增的图片列表功能。
- Cursor：分页游标。可为 provider 特定值或 page:n。

## 3. 前置条件
1) 用户已登录（有有效 access token）。
2) 用户至少存在一个 StorageConfig。
3) 用户已在 Storage Tab 选择并激活了某个 StorageConfig。

## 3.1 需求映射（FR/NFR）
- FR-1: SettingsModal 增加 Gallery Tab（见 7.1）
- FR-2: 图片列表展示（见 7.3）
- FR-3: 搜索（见 7.2）
- FR-4: 排序（见 4.3 与 7.2）
- FR-5: 分页加载（见 4.4）
- FR-6: 复制链接/下载（见 7.3）
- FR-7: 空态/错误态（见 4.5）
- NFR-1/NFR-2: 分页与超时策略（见 9 与 6.6）
- NFR-3/NFR-4: 权限与安全（见 10）

## 4. 端到端流程（逐步说明）
### 4.1 打开 Tab 的首次加载流程
1) 用户打开 SettingsModal。
2) 用户点击左侧新增的 `Gallery` Tab。
3) 前端组件初始化 state：
   - items = []
   - loading = true
   - error = null
   - cursor = null
   - hasMore = true
4) 前端读取当前 activeStorageId（来自 SettingsModal props）。
5) 前端调用 `storageGallery.listImages`，组装请求：
   - storage_id = activeStorageId（若为空则不传）
   - limit = 40
   - cursor = null
   - q = ""
   - sort = created_at_desc
6) 前端发送 GET `/api/storage/gallery`，携带 Authorization。
7) 后端路由收到请求，执行用户身份校验。
8) 后端解析 storage_id：
   - 如果请求有 storage_id，则校验归属（UserScopedQuery）。
   - 如果没有 storage_id，则读取 ActiveStorage.user_id == current_user。
9) 如果未设置 ActiveStorage，返回 400。
10) 后端根据 storage.provider 调用 `StorageService.list_images`。
11) Provider 层获取图片列表并映射为统一结构。
12) 后端返回 JSON：
   - storage 元信息
   - items 列表
   - nextCursor / hasMore
13) 前端收到响应：
   - items 替换为结果
   - cursor = nextCursor
   - hasMore = true/false
   - loading = false
14) UI 渲染图片网格。

### 4.2 搜索流程（关键词）
1) 用户在搜索框输入关键词。
2) 前端 debounce 300ms。
3) 触发重新加载：
   - 清空 items
   - cursor = null
   - loading = true
4) 调用 `/api/storage/gallery?q=keyword`。
5) 后端按 provider 规则过滤：
   - Lsky 使用 server-side search
   - OSS 使用前缀或本地过滤（见后端设计）
6) 返回过滤后的 items。
7) 前端渲染搜索结果。

### 4.3 排序流程
1) 用户切换排序选项。
2) 前端清空 items + cursor。
3) 调用 `/api/storage/gallery?sort=created_at_asc|created_at_desc`。
4) 后端使用 provider 原生排序或做近似排序。
5) 前端渲染排序结果。

### 4.4 分页加载流程
1) 用户点击“加载更多”。
2) 前端使用当前 cursor 继续请求：
   - `/api/storage/gallery?cursor=xxx`
3) 后端返回下一页 items + nextCursor。
4) 前端将新 items append 到原列表。
5) 若 hasMore 为 false，隐藏“加载更多”。

### 4.5 错误与空态流程
- 未设置 ActiveStorage：
  1) 后端返回 400。
  2) 前端显示“请先在 Storage 里激活配置”。
- storage_id 非归属：
  1) 后端返回 404。
  2) 前端显示“配置不存在或无权访问”。
- Provider 不支持列表：
  1) 后端返回 501。
  2) 前端显示“不支持该存储的图库列表”。
- Provider 调用失败：
  1) 后端返回 502。
  2) 前端显示错误信息 + “重试”。

## 5. API 设计（详细）
### 5.1 GET /api/storage/gallery
Query 参数：
- storage_id: string (可选)
- limit: number (默认 40，最大 100)
- cursor: string (可选)
- q: string (可选)
- sort: created_at_desc | created_at_asc (可选，默认 desc)

响应结构：
```
{
  "storage": {
    "id": "storage-xxx",
    "name": "My Lsky",
    "provider": "lsky"
  },
  "items": [
    {
      "id": "provider-specific-id-or-object-key",
      "name": "image-123.png",
      "url": "https://...",
      "thumbUrl": "https://... (optional)",
      "size": 123456,
      "contentType": "image/png",
      "createdAt": 1736400000000,
      "provider": "lsky"
    }
  ],
  "nextCursor": "opaque-cursor-or-null",
  "hasMore": true
}
```

### 5.2 错误返回
- 400: {"detail": "未设置存储配置"}
- 404: {"detail": "存储配置不存在或无权访问"}
- 501: {"detail": "该存储暂不支持列表"}
- 502: {"detail": "存储服务调用失败"}

## 6. 后端设计（逐步说明）
### 6.1 Router 层步骤（storage.py）
1) 解析 request，调用 `require_user_id`。
2) 获取 storage_id：
   - 有 storage_id：使用 UserScopedQuery 校验。
   - 无 storage_id：查 ActiveStorage.user_id == current_user。
3) 若 active_storage 为空 -> return 400。
4) 读取 StorageConfig.provider + config。
5) 调用 StorageService.list_images。
6) 返回统一结构 + 分页信息。

### 6.2 StorageService.list_images 总控流程
1) 判断 provider 类型。
2) 路由到对应 provider 适配函数。
3) 将 provider 原始响应归一化为 items。
4) 返回标准结构。

### 6.3 Lsky 列表步骤
1) 读取 config.domain / config.token。
2) 构造请求 `GET {domain}/api/v1/images`。
3) 参数：
   - page / per_page
   - search (q)
   - sort
4) 解析返回的 images 列表：
   - id -> item.id
   - name -> item.name
   - links.url -> item.url
   - links.thumbnail_url -> item.thumbUrl
   - created_at -> item.createdAt
5) 根据 page/per_page 计算 hasMore + nextCursor=page:n。

### 6.4 OSS 列表步骤
1) 读取 config.accessKeyId / config.accessKeySecret / bucket / endpoint。
2) 使用 list_objects_v2：
   - MaxKeys = limit
   - ContinuationToken = cursor
   - Prefix = "uploads/" (可配置)
3) 解析 objects：
   - Key -> item.id / item.name
   - LastModified -> item.createdAt
   - Size -> item.size
4) URL 生成：
   - customDomain 或 domain 存在 -> 使用该域名（去协议/尾部斜杠）: https://{domain}/{Key}
   - 否则 -> https://{bucket}.{endpoint}/{Key}
5) 若私有 bucket -> 使用签名 URL（TTL 10 min）。
6) nextCursor = NextContinuationToken，hasMore = IsTruncated。

### 6.5 搜索与排序差异处理
- Lsky：使用 API 原生 search。
- OSS：仅支持 Prefix，可实现：
  - 若 q 为空 -> 直接 list
  - 若 q 非空 -> prefix = q 或全量 list + 本地过滤（需注意性能）
- 排序：
  - Lsky 原生排序
  - OSS 默认字典序，可选择：
    - 仅支持 created_at_desc（按 LastModified 排序）
    - 或保持 provider 返回顺序并注明限制

### 6.6 日志与错误
1) 记录 provider 调用耗时。
2) 捕获 provider 异常 -> 502。
3) provider 不支持列表 -> 501。

## 7. 前端设计（逐步说明）
### 7.1 SettingsModal 变更步骤
1) 在 SettingsTab union 加入 `storage-gallery`。
2) 在 nav 增加 TabButton。
3) content 区新增 `<StorageGalleryTab />`。

### 7.2 StorageGalleryTab 组件步骤
1) 初始化 state（items/loading/error/cursor/hasMore/search/sort）。
2) useEffect 监听 activeStorageId 或 tab 激活：
   - 重置 state
   - 调用 listImages
3) 搜索输入 -> debounce -> 重载
4) 排序切换 -> 重载
5) 加载更多 -> append

### 7.3 UI 行为细节
- loading=true 时展示 skeleton。
- error 不为空时展示错误卡片。
- 空列表时展示空态。
- 点击图片：调用 ImageModal 或新建 Preview 组件。
- 复制按钮：调用 clipboard API。
- 下载按钮：a 标签 download 或直接打开 url。

## 8. 类型定义与数据模型
### 前端类型
```
type StorageGalleryItem = {
  id: string;
  name: string;
  url: string;
  thumbUrl?: string;
  size?: number;
  contentType?: string;
  createdAt?: number;
  provider: string;
};
```

### 后端统一模型
```
{
  storage: { id, name, provider },
  items: StorageGalleryItem[],
  nextCursor: string | null,
  hasMore: boolean
}
```

## 9. 性能与缓存策略
- limit 默认 40，最大 100。
- 前端可缓存 30 秒，避免频繁刷新。
- 搜索时不复用缓存。

## 10. 安全与权限
- 必须认证 (Authorization header)。
- storage_id 必须归属当前用户。
- 任何响应不包含凭证字段。

## 11. 验收标准
1) 激活存储后能正常看到图片列表。
2) 搜索/排序/分页均可工作。
3) 未设置 ActiveStorage 时提示清晰。
4) provider 不支持列表时提示清晰。
5) 401/403/404/502 都能正确展示。

## 12. 测试计划
### 后端
- Lsky 正常 list
- OSS 正常 list
- 未设置 ActiveStorage
- storage_id 非归属
- provider 不支持

### 前端
- Tab 切换加载
- 搜索/排序/分页
- 空态/错误态
- 复制/下载

## 13. 里程碑
1) 后端 API + provider list 适配完成
2) 前端 Gallery Tab + UI 完成
3) 联调与验收

## 14. 开放问题
1) OSS 搜索是否仅支持 prefix？
2) 私有 bucket 是否强制签名 URL？
3) 是否需要限制返回条数以避免费用过高？
