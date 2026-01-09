# Google Gemini 图片编辑流程（端到端）

## 范围

本文追踪以下端到端流程：
1) 选择 Google Gemini 提供商，
2) 切换到图片编辑模式，
3) 输入提示词并发送，
4) 最终在前端渲染生成结果。

流程基于当前代码实现，并在每一步给出文件级引用。

## 1) 选择并激活提供商

1. 用户打开设置并激活或编辑 Google Gemini 配置。
   - 配置列表激活：`frontend/components/modals/settings/ProfilesTab.tsx`
   - 配置编辑/保存：`frontend/components/modals/settings/EditorTab.tsx`
2. Settings 弹窗将操作绑定到应用状态。
   - `frontend/components/modals/SettingsModal.tsx`
3. 激活与持久化逻辑（前端）。
   - `useSettings.activateProfile` 更新本地状态并调用后端：
     `frontend/hooks/useSettings.ts`
4. 后端保存当前激活配置。
   - `/api/active-profile` 与 `/api/profiles`：
     `backend/app/routers/profiles.py`
5. 激活配置驱动运行时配置与模型列表。
   - `useSettings.refreshSettings` 调用 `llmService.setConfig`：
     `frontend/hooks/useSettings.ts`
   - `useModels` 从后端获取模型列表：
     `frontend/hooks/useModels.ts`
   - 模型列表端点：`/api/models/google`（经 `UnifiedProviderClient`）：
     `frontend/services/providers/UnifiedProviderClient.ts`

## 2) 切换到图片编辑模式

1. 通过 UI 控件切换模式。
   - 输入栏的模式选择器：
     `frontend/components/chat/input/ModeSelector.tsx`
2. 模式切换更新应用状态，并选择可用的视觉模型。
   - `handleModeSwitch` 选择 `image-edit` 和兼容模型：
     `frontend/App.tsx`
3. 渲染编辑视图。
   - `StudioView` 路由到 `ImageEditView`：
     `frontend/components/views/StudioView.tsx`
   - 编辑 UI 位于：
     `frontend/components/views/ImageEditView.tsx`

## 3) 用户输入与附件准备

1. 用户上传图片并输入编辑提示词。
   - 文件选择与提示词输入：
     `frontend/components/chat/InputArea.tsx`
2. 点击发送时，InputArea 将 Blob URL 转换为 Base64 以保证持久化展示。
   - `InputArea.tsx` 的 `handleSend`
3. ImageEditView 进一步规范附件数据。
   - `ImageEditView.tsx` 的 `handleSend` 调用：
     `frontend/hooks/handlers/attachmentUtils.ts` 中的 `processUserAttachments`
   - 该函数处理连续编辑（复用画布图片）并按需将 URL 转为 `File` 或 Base64。

## 4) 进入应用消息发送流水线

1. ImageEditView 调用 App 级 `onSend`。
   - `frontend/components/views/ImageEditView.tsx`
2. App 校验配置并通过消息管线发送。
   - API Key 校验与会话创建：
     `frontend/App.tsx`
3. `useChat.sendMessage` 建立执行上下文。
   - 创建用户/模型消息并设置加载状态：
     `frontend/hooks/useChat.ts`
4. 策略注册表选择图片编辑处理器。
   - `strategyRegistry` 选择 `ImageEditHandler`：
     `frontend/hooks/handlers/strategyConfig.ts`

## 5) 图片编辑生成请求

1. Handler 执行图片编辑流程。
   - `ImageEditHandler` 调用 `llmService.generateImage`：
     `frontend/hooks/handlers/ImageEditHandlerClass.ts`
2. LLM 服务使用当前 Provider 进行生成。
   - `llmService.generateImage`：
     `frontend/services/llmService.ts`
3. Google + 协议 `google` 时使用后端客户端。
   - `LLMFactory.getProvider` 返回 `UnifiedProviderClient('google')`：
     `frontend/services/LLMFactory.ts`
4. 发送请求到后端。
   - `UnifiedProviderClient.generateImage` 发起：
     `POST /api/generate/google/image`
     `frontend/services/providers/UnifiedProviderClient.ts`
   - 请求体包含 `modelId`、`prompt`、`referenceImages`、`options`、`apiKey`。

## 6) 后端图片生成

1. 后端端点处理图像生成。
   - `/api/generate/{provider}/image`：
     `backend/app/routers/generate.py`
2. API Key 解析优先级（请求体 -> 数据库 -> 环境变量）。
   - `generate.py` 中的 `get_api_key`
3. 创建 Provider 服务实例。
   - `ProviderFactory.create('google', api_key)`：
     `backend/app/services/provider_factory.py`
4. Google 服务委派给 ImageGenerator。
   - `GoogleService.generate_image`：
     `backend/app/services/gemini/google_service.py`
5. ImageGenerator 使用 ImagenCoordinator。
   - `ImageGenerator.generate_image`：
     `backend/app/services/gemini/image_generator.py`
   - `ImagenCoordinator` 决定 Gemini API 或 Vertex AI：
     `backend/app/services/gemini/imagen_coordinator.py`

## 7) 结果处理与前端展示

1. 后端返回 `images` 列表。
   - `generate.py` 格式化响应为 `{ images: [...] }`。
2. Handler 将结果转换为 UI 附件。
   - `processMediaResult` 创建展示附件并触发上传：
     `frontend/hooks/handlers/attachmentUtils.ts`
3. `useChat` 用最终结果替换模型占位消息。
   - `frontend/hooks/useChat.ts`
4. ImageEditView 自动选择最新结果。
   - `ImageEditView.tsx` 中的 `useEffect` 在新模型消息到达时设置 `activeImageUrl`。
5. 画布显示结果并支持对比模式。
   - `ImageEditMainCanvas` 位于 `ImageEditView.tsx`。

## 流程备注（行为细节）

1. 前端收集 reference images 并放入请求体，但当前后端 `generate.py` 未使用 `referenceImages`。
2. ImageEditView 具备“连续编辑”逻辑：用户不重新上传时复用当前画布图像。
3. 生成结果会转换为可展示的 URL，并异步上传到云存储，消息中以 `uploadStatus` 跟踪上传状态。
