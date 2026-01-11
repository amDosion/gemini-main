# Active Cloud Storage 图片库 Tab 需求说明

## 1. 目标
为当前用户的 Active Storage 提供一个可视化图片列表入口，支持查看、搜索、排序、分页，并可复制链接/下载图片，用于验证配置有效性与快速访问内容。

## 2. 术语
- Active Storage：当前用户激活的存储配置（ActiveStorage.storage_id）。
- Provider：具体的存储服务类型（lsky / aliyun-oss）。
- Gallery：本需求新增的图片列表界面。

## 3. 适用范围
### 3.1 包含
- SettingsModal 新增 Gallery Tab。
- 后端新增图片列表接口。
- Provider 适配：Lsky Pro V2、Aliyun OSS。

### 3.2 不包含
- 跨 provider 合并列表。
- 复杂媒体管理（批量编辑、标签、分类）。
- 资产元数据增强（AI 标签/识别）。

## 4. 用户流程（逐步说明）
### 4.1 首次进入 Gallery
1) 用户打开 SettingsModal。
2) 用户点击 Gallery Tab。
3) 前端获取 activeStorageId。
4) 发起 GET `/api/storage/gallery` 请求。
5) 后端校验用户身份和 storage 权限。
6) 后端读取 ActiveStorage 并调用对应 provider 列表接口。
7) 前端渲染图片网格或空态。

### 4.2 搜索
1) 用户输入关键词。
2) 前端 debounce 300ms。
3) 重新请求 `/api/storage/gallery?q=keyword` 并刷新列表。

### 4.3 排序
1) 用户切换排序（创建时间升/降）。
2) 前端重置列表并重新请求。

### 4.4 分页加载
1) 用户点击“加载更多”或触底触发。
2) 前端带 cursor 请求下一页。
3) 列表追加显示。

### 4.5 错误处理
1) ActiveStorage 未设置 -> 提示“请先激活存储配置”。
2) provider 不支持列表 -> 提示“不支持该存储的图库列表”。
3) provider 调用失败 -> 显示错误 + 重试。

## 5. 功能需求
- FR-1：Gallery Tab 在 SettingsModal 中可见，并可切换。
- FR-2：展示 Active Storage 图片列表（缩略图、文件名、时间）。
- FR-3：支持搜索（文件名/URL 关键字）。
- FR-4：支持排序（created_at_desc / created_at_asc）。
- FR-5：支持分页加载（cursor）。
- FR-6：支持复制链接与下载。
- FR-7：空态、错误态提示清晰可理解。

## 6. 非功能需求
- NFR-1：首屏加载 <= 2s（limit=40）。
- NFR-2：单次接口超时 <= 10s。
- NFR-3：请求必须认证，严格用户隔离。
- NFR-4：不会暴露任何存储凭证。

## 7. API 需求
### 7.1 GET /api/storage/gallery
请求参数：
- storage_id: string (可选)
- limit: number (默认 40，最大 100)
- cursor: string (可选)
- q: string (可选)
- sort: created_at_desc | created_at_asc (可选)

响应：
```
{
  "storage": { "id": "...", "name": "...", "provider": "lsky" },
  "items": [
    {
      "id": "string",
      "name": "string",
      "url": "string",
      "thumbUrl": "string|null",
      "size": 123,
      "contentType": "image/png",
      "createdAt": 1736400000000,
      "provider": "lsky"
    }
  ],
  "nextCursor": "string|null",
  "hasMore": true
}
```

错误返回：
- 400 未设置 ActiveStorage
- 404 storage_id 不属于当前用户
- 501 provider 不支持列表
- 502 provider 调用失败

## 8. Provider 适配需求
### 8.1 Lsky
- 使用 Lsky 的 list API。
- 支持分页与 search。
- 返回 url + thumbUrl。

### 8.2 Aliyun OSS
- 使用 list_objects_v2。
- 支持 continuation token。
- URL 生成规则：
  - customDomain 或 domain 存在 -> https://{domain}/{Key}
  - 否则 -> https://{bucket}.{endpoint}/{Key}
- 私有 bucket 可返回签名 URL（TTL 10 min）。

### 8.3 不支持列表的 provider
- 明确返回 501。

## 9. 权限与安全
- 必须携带 Authorization。
- storage_id 必须属于当前用户。
- 不返回密钥/Token。

## 10. UI/UX 需求
- Grid 自适应布局（移动 2 列，桌面 3-4 列）。
- 搜索框支持清空。
- 排序下拉或切换按钮。
- 图片卡片提供复制链接/下载。

## 11. 依赖与约束
- 依赖 ActiveStorage 表记录。
- provider 配置中的 domain/customDomain 需保持统一命名。

## 12. 验收标准
- 能看到激活存储的图片列表。
- 搜索/排序/分页可用。
- 错误提示准确且可重试。
- 未激活存储时提示明确。
