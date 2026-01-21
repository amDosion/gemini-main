# 跨模式附件显示问题（基于当前代码）

## 范围
- 仅基于仓库现有代码路径分析跨模式（image-gen -> edit/expand）附件显示与复用问题。
- 不包含任何代码修改建议，仅说明“问题点 + 证据 + 影响”。

## 代码路径概览（与实际调用一致）
1) `ImageGenView` 展示图片，并把 `att.url` 作为点击 Edit/Expand 的入参。
2) `App` 使用 `useViewMessages` 过滤消息，按 `appMode` 传入 `StudioView`。
3) `ImageEditView` / `ImageExpandView` 使用 `initialAttachments` 显示画布，但在发送时调用 `processUserAttachments`，它依赖 `messages` 进行 CONTINUITY 查找。
4) `prepareAttachmentForApi` 首先调用后端 `/api/attachments/resolve-continuity`，后端用 `messages` 匹配 URL。

## 问题点与证据（逐条对应真实代码）
1) 跨模式后 `messages` 被按模式过滤，CONTINUITY 失去 image-gen 附件上下文。
   - 证据: `useViewMessages` 只保留 `message.mode === appMode`，导致 edit/expand 视图的 `messages` 不含 image-gen 记录。路径: `frontend/hooks/useViewMessages.ts`。
   - 证据: `App` 把 `currentViewMessages` 传进 `StudioView`，而 edit/expand 视图的 `processUserAttachments` 依赖 `messages`。路径: `frontend/App.tsx`、`frontend/components/views/StudioView.tsx`、`frontend/hooks/handlers/attachmentUtils.ts`。
   - 影响: 当 edit/expand 仅依赖“画布已有图片”时，CONTINUITY 查找无法命中 image-gen 的原附件，导致复用失败或退化为“新附件”。

2) 后端 CONTINUITY 解析只依赖传入的 `messages`，对 Base64/HTTP 没有数据库兜底。
   - 证据: `resolve_continuity_attachment` 先在 `messages` 中找 `attachment_id`，兜底仅针对 Blob URL（查最近上传图片）。路径: `backend/app/services/common/attachment_service.py`。
   - 影响: 当 `messages` 被过滤且 `active_image_url` 是 Base64/HTTP，后端无法找到原附件，复用中断。

3) `ImageGenView` 只渲染 `att.url`，忽略 `tempUrl`。
   - 证据: `displayImages` 只过滤 `att.url`，渲染 `<img src={att.url}>`。路径: `frontend/components/views/ImageGenView.tsx`。
   - 影响: 如果附件来自数据库且仅有 `tempUrl`（`url` 为空），image-gen 历史会显示空白，无法跨模式点击进入。

4) 本地缓存清理会清空 Base64/Blob 的 `url`，导致重载后 image-gen 看不到附件。
   - 证据: `cleanAttachmentsForDb` 会清空 Base64/Blob `url` 并删除非 HTTP 的 `tempUrl`。路径: `frontend/hooks/handlers/attachmentUtils.ts`。
   - 证据: `updateSessionMessages` 在图片相关模式中调用该清理并保存到本地缓存。路径: `frontend/hooks/useSessions.ts`。
   - 影响: 刷新或会话切换后，image-gen 历史中附件 `url` 为空，`ImageGenView` 无法显示。

5) `/api/temp-images` 依赖 cookie 鉴权，`<img>` 无法携带 Authorization header。
   - 证据: `/api/temp-images/{attachment_id}` 由 `require_current_user` 校验 `attachment.user_id`。路径: `backend/app/routers/core/attachments.py`。
   - 影响: 如果前端使用 `/api/temp-images/...` 作为显示 URL（日志显示确实发生），一旦 cookie 身份与 token 身份不一致，图片请求直接 404，跨模式显示全部失败。

6) 预览组件仅使用 `att.url`，忽略 `tempUrl`。
   - 证据: `AttachmentPreview` 渲染 `<img src={att.url}>`。路径: `frontend/components/chat/input/AttachmentPreview.tsx`。
   - 影响: edit/expand 模式的附件预览 chip 可能为空，即使 `tempUrl` 存在。

## 直接可观察到的表现
- image-gen 历史在刷新/切换会话后显示空白缩略图。
- 点击 Edit/Expand 后画布为空，或预览缺失。
- edit/expand 发送时无法复用原附件（attachment_id 变化、重复上传）。

## 备注
- 上述每条均有对应代码路径，不依赖“概率推测”。
- 日志里的 404 与 `/api/temp-images` 的鉴权逻辑完全一致。
