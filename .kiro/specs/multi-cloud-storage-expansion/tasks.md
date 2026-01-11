# Active Cloud Storage 图片库 Tab 任务清单

## 0. 约定与准备
- [ ] 确认需求文档与设计文档已锁定：`requirements.md` + `design.md`
- [ ] 明确 OSS 配置字段命名（`customDomain` / `domain` / `endpoint`）
- [ ] 确认 Lsky 列表 API 路径与参数（page/per_page/search/sort）

## 1. 后端 API 任务
### 1.1 路由层
- [ ] 在 `backend/app/routers/storage.py` 新增 `GET /api/storage/gallery`
- [ ] 解析 query 参数：`storage_id`, `limit`, `cursor`, `q`, `sort`
- [ ] 使用 `require_user_id` 获取 user_id
- [ ] 校验 storage_id 归属（UserScopedQuery）
- [ ] 若未传 storage_id，读取 ActiveStorage（无则返回 400）
- [ ] 统一错误返回：400/404/501/502

### 1.2 Provider 适配层
- [ ] 在 `backend/app/services/storage_service.py` 新增 `list_images(...)`
- [ ] Lsky：实现列表请求与映射（id/name/url/thumbUrl/createdAt）
- [ ] OSS：实现 list_objects_v2 + continuation token
- [ ] OSS URL 生成：优先 `customDomain`/`domain`，否则 bucket.endpoint
- [ ] 私有 bucket 返回签名 URL（TTL 10 min）
- [ ] Provider 不支持列表时抛 501

### 1.3 归一化与响应
- [ ] 将 provider 返回映射为统一 items 结构
- [ ] 返回 `storage` 元信息 + `items` + `nextCursor` + `hasMore`
- [ ] 添加必要日志（耗时/错误码/返回条数）

## 2. 前端 UI 任务
### 2.1 SettingsModal 集成
- [ ] `SettingsTab` union 增加 `storage-gallery`
- [ ] nav 增加 Gallery TabButton
- [ ] content 区增加 `<StorageGalleryTab />`

### 2.2 Gallery 组件
- [ ] 新建 `frontend/components/modals/settings/StorageGalleryTab.tsx`
- [ ] 状态：items/loading/error/cursor/hasMore/search/sort
- [ ] 组件挂载或 activeStorageId 变化时加载列表
- [ ] 搜索输入 debounce 300ms 触发重载
- [ ] 排序切换重载
- [ ] “加载更多”追加 items
- [ ] 空态/错误态 UI

### 2.3 前端服务层
- [ ] 新建 `frontend/services/storage/storageGallery.ts`
- [ ] 实现 `listImages({ storageId, limit, cursor, q, sort })`
- [ ] 统一附加 Authorization header

### 2.4 UI 行为细节
- [ ] 图片卡片：缩略图 + 文件名 + 时间
- [ ] 操作按钮：复制链接、下载
- [ ] 点击图片：使用现有 ImageModal 或简化预览

## 3. 联调与兼容性
- [ ] Lsky 列表联调（含分页/搜索）
- [ ] OSS 列表联调（含 continuation token）
- [ ] 未设置 ActiveStorage 时提示
- [ ] provider 不支持列表提示

## 4. 测试与验收
- [ ] 后端：400/404/501/502 分支覆盖
- [ ] 前端：搜索/排序/分页/空态/错误态
- [ ] 验收对照 `requirements.md` 的 FR/NFR

## 5. 文档与收尾
- [ ] 更新 `design.md` 中的实现备注（如字段命名最终确认）
- [ ] 记录 API 示例与必要说明
