<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/drive/1K5TLsCsB4rnxBYmJMABefQgD6nA_mrid

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`


# Gemini Flux Chat - 完整项目深度分析与架构说明

本文档对 `Gemini Flux Chat` 项目进行了深入的代码级分析，涵盖了架构设计、核心功能模块、数据流向以及完整的项目目录结构。该项目是一个现代化的、高性能的 AI 前端应用，集成了多模态能力（文本、图像、视频、音频、PDF 处理），并采用混合架构（React 前端 + Python FastAPI 后端）。


项目设计易于扩展。要添加新的 AI 提供商：
在 frontend/services/providers/ 下创建新目录。
实现 ILLMProvider 接口。
在 frontend/config/aiProviders.ts 中注册静态配置。

---

## 1. 核心架构分析

### 1.1 技术栈概览
- **前端**: React 19, TypeScript, Vite, Tailwind CSS (Glassmorphism 设计风格).
- **后端**: Python FastAPI (用于 PDF 解析、Selenium 网页浏览、RAG 向量化).
- **数据层**: IndexedDB (Blob 存储), LocalStorage (配置/会话), SQLite/PostgreSQL (后端持久化).
- **AI SDK**: `@google/genai` (官方 SDK), `fetch` (OpenAI 兼容协议).

### 1.2 设计模式与架构亮点

#### A. 提供商适配器模式 (Provider Pattern)
项目通过 `LLMFactory` (`frontend/services/LLMFactory.ts`) 实现了工厂模式，统一管理不同的 AI 模型提供商。
- **接口定义**: `ILLMProvider` 定义了 `sendMessageStream`, `generateImage`, `generateVideo` 等统一接口。
- **实现类**: 
  - `GoogleProvider`: 原生集成 Gemini 功能（Search Grounding, Thinking, File API）。
  - `OpenAIProvider`: 通用适配器，支持 DeepSeek, Moonshot, SiliconFlow, Ollama 等兼容 OpenAI 协议的服务。
  - `DashScopeProvider`: 阿里通义千问专用适配器，处理其特有的异步任务轮询机制（WanX 生图/修图）。

#### B. 混合存储策略 (Hybrid Storage Strategy)
数据存储层 (`frontend/services/db.ts`) 实现了 `HybridDB` 类，具备自动降级能力：
1. **优先 API**: 尝试连接后端 `/api/sessions` 等端点进行数据持久化。
2. **离线降级**: 如果后端不可用，自动切换至浏览器的 `LocalStorage`。
3. **Blob 存储**: 大文件（生成的图片、音频）使用 `BlobStorageService` 存入浏览器的 IndexedDB，避免 LocalStorage 容量溢出。

#### C. 模式驱动视图 (Mode-Driven Architecture)
`App.tsx` 不仅仅是一个聊天窗口，而是根据 `appMode` 状态切换不同的工作台视图：
- **ChatView**: 传统的线性对话流，支持多轮上下文。
- **StudioView**: 包含 `ImageGenView`, `ImageEditView`, `VideoGenView`, `PdfExtractView`。这些视图针对特定任务优化，例如 `ImageEditView` 提供了 Canvas 交互和历史版本对比功能。

#### D. 流式处理与上下文管理
- **MessagePreparer**: 负责在发送请求前对历史消息进行压缩、系统提示词注入和格式化。
- **ContextManager**: 计算 Token 估算，智能截断过长的历史记录。
- **StreamManager**: 集中管理 `AbortController`，支持中断正在进行的流式响应。

---

## 2. 核心功能模块解析

### 2.1 深度研究 (Deep Research)
- **前端**: 用户激活 `Deep Research` 模式。
- **通信**: `GoogleProvider` 拦截请求，调用后端 `/api/chat/deep-research`。
- **流式渲染**: 后端返回自定义的 SSE/NDJSON 流，包含 `{ phase: "WebResearch" }` 或 `{ text: "..." }`。
- **UI 呈现**: 前端将阶段状态转换为 Markdown 引用块 (`> 🔍 Analyzing...`)，在 `MessageItem` 中渲染为可视化的思考过程。

### 2.2 PDF 结构化提取
- **混合逻辑**: `PdfExtractionService` 首先检查后端健康状态。
- **执行**: 
  - 如果后端在线，上传文件至 FastAPI，利用 Gemini 的 Function Calling 能力提取 JSON 数据。
  - 前端 `PdfExtractView` 组件动态渲染提取到的 JSON 数据，支持折叠/展开和导出。

### 2.3 多模态生成工作室 (Studio)
- **文生图/修图**: 支持 Google Imagen 3 和 WanX。前端实现了 Canvas 拖拽、缩放逻辑 (`ImageEditView`)，支持基于掩码或全图的编辑。
- **视频生成**: 集成 Google Veo 模型。`VideoGenView` 处理异步任务轮询，显示生成进度。
- **实时语音 (TTS)**: 使用 Gemini 2.5 Flash Audio。前端实现了卡拉OK式的歌词/单词高亮显示 (`AudioGenView`)，通过计算字符密度估算时间戳。

### 2.4 浏览器自动化 (Browser Automation)
- **实现**: `backend/browser.py` 使用 Selenium。
- **流程**: LLM 决定调用 `browse_webpage` 工具 -> 前端拦截并请求后端 -> 后端启动无头浏览器抓取截图和 Markdown -> 返回给 LLM -> LLM 基于内容回答。
- **实时反馈**: 利用 Server-Sent Events (SSE) 向前端推送浏览器操作步骤（"正在滚动", "点击按钮"...）。

---

## 3. 数据流向图 (Data Flow)

1. **用户输入** -> `InputArea.tsx` (处理附件、链接)
2. **状态更新** -> `useChat.ts` (创建乐观 UI 消息)
3. **服务调用** -> `llmService.ts` (单例)
4. **策略路由** -> `LLMFactory` -> `GoogleProvider` / `OpenAIProvider`
5. **网络请求**:
   - **Google**: 直接调用 `generativelanguage.googleapis.com` 或上传文件到 File API。
   - **Backend Features**: 调用本地 Python 后端 (`/api/pdf`, `/api/browse`).
6. **响应处理** -> `StreamManager` (处理流式块) -> 更新 React State。
7. **持久化** -> `useSessions` -> `db.ts` (异步保存到 DB 或 LocalStorage)。

---

## 4. 完整项目目录结构

```text
root/
├── backend/                                  # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py                           # 后端入口，API 路由定义
│   │   ├── pdf_extractor.py                  # PDF 解析与结构化提取逻辑
│   │   ├── embedding_service.py              # RAG 向量化与搜索服务
│   │   ├── logger_config.py                  # 日志配置
│   │   └── __init__.py
│   ├── browser.py                            # Selenium 浏览器自动化工具
│   ├── progress_tracker.py                   # 任务进度跟踪 (SSE)
│   ├── requirements.txt                      # Python 依赖
│   ├── BROWSER_README.md                     # 浏览器功能文档
│   ├── INTEGRATION_GUIDE.md                  # 集成指南
│   ├── LOGGING_GUIDE.md                      # 日志指南
│   └── WINDOWS_COMPATIBILITY.md              # Windows 兼容性说明
│
├── frontend/                                 # React 前端
│   ├── components/                           # UI 组件库
│   │   ├── auth/
│   │   │   └── LoginPage.tsx                 # 登录页面
│   │   ├── chat/
│   │   │   ├── input/                        # 输入区域组件
│   │   │   │   ├── AdvancedSettings.tsx      # (已弃用) 高级设置
│   │   │   │   ├── AttachmentPreview.tsx     # 附件预览
│   │   │   │   ├── ChatControls.tsx          # 聊天功能开关 (Search, Think, etc.)
│   │   │   │   ├── GenerationControls.tsx    # 生成参数控制 (AspectRatio, Styles)
│   │   │   │   ├── ModeSelector.tsx          # 模式切换器
│   │   │   │   └── PromptInput.tsx           # 文本输入框
│   │   │   ├── InputArea.tsx                 # 输入区域容器
│   │   │   ├── MarkdownRenderer.tsx          # Markdown 代码高亮渲染
│   │   │   └── MessageItem.tsx               # 单条消息渲染
│   │   ├── layout/                           # 布局组件
│   │   │   ├── AppLayout.tsx                 # 主布局容器
│   │   │   ├── Header.tsx                    # 顶部导航栏
│   │   │   ├── RightSidebar.tsx              # 右侧 Persona 栏
│   │   │   ├── Sidebar.tsx                   # 左侧历史记录栏
│   │   │   └── WelcomeScreen.tsx             # 欢迎页
│   │   ├── message/                          # 消息体子组件
│   │   │   ├── AttachmentGrid.tsx            # 媒体附件网格
│   │   │   ├── GroundingSources.tsx          # 搜索来源引用
│   │   │   ├── SearchProcess.tsx             # 搜索过程可视化
│   │   │   ├── ThinkingBlock.tsx             # 思维链折叠块
│   │   │   └── UrlContextStatus.tsx          # URL 读取状态
│   │   ├── modals/                           # 弹窗组件
│   │   │   ├── settings/                     # 设置弹窗子标签
│   │   │   │   ├── EditorTab.tsx             # 配置编辑器
│   │   │   │   └── ProfilesTab.tsx           # 配置列表
│   │   │   ├── DocumentsModal.tsx            # RAG 文档管理
│   │   │   ├── ImageModal.tsx                # 图片全屏预览
│   │   │   ├── PersonaModal.tsx              # 角色编辑
│   │   │   └── SettingsModal.tsx             # 设置主弹窗
│   │   ├── pdf/
│   │   │   └── PdfExtractionResult.tsx       # PDF 提取结果展示
│   │   ├── views/                            # 核心业务视图
│   │   │   ├── AudioGenView.tsx              # 语音生成视图 (含卡拉OK效果)
│   │   │   ├── ChatView.tsx                  # 标准聊天视图
│   │   │   ├── ImageEditView.tsx             # 图片编辑视图 (Canvas)
│   │   │   ├── ImageExpandView.tsx           # 图片扩展视图 (Outpainting)
│   │   │   ├── ImageGenView.tsx              # 图片生成视图
│   │   │   ├── PdfExtractView.tsx            # PDF 提取视图
│   │   │   ├── StudioView.tsx                # 工作室模式路由容器
│   │   │   └── VideoGenView.tsx              # 视频生成视图
│   │   ├── workspaces/                       # (遗留/备用) 工作区组件
│   │   │   ├── ChatWorkspace.tsx
│   │   │   └── GenWorkspace.tsx
│   │   ├── BrowserProgressIndicator.tsx      # 浏览器任务进度条
│   │   └── index.ts                          # 组件导出索引
│   ├── config/                               # 静态配置
│   │   ├── aiProviders.ts                    # AI 提供商预设列表
│   │   └── personas.ts                       # 预设 AI 角色
│   ├── hooks/                                # 自定义 Hooks
│   │   ├── index.ts
│   │   ├── useChat.ts                        # 核心对话逻辑
│   │   ├── useMessageProcessor.ts            # 消息解析与渲染逻辑
│   │   ├── useModels.ts                      # 模型列表获取与缓存
│   │   ├── usePersonas.ts                    # 角色管理
│   │   ├── useSessions.ts                    # 会话管理
│   │   └── useSettings.ts                    # 设置管理
│   ├── services/                             # 业务逻辑层
│   │   ├── ai_chat/
│   │   │   └── MessagePreparer.ts            # 消息构建与上下文优化
│   │   ├── ai_tools/
│   │   │   └── ContextManager.ts             # Token 计算与截断
│   │   ├── media/                            # 媒体生成策略
│   │   │   ├── MediaFactory.ts               # 媒体工厂
│   │   │   └── utils.ts                      # 媒体工具函数
│   │   ├── providers/                        # LLM 提供商实现
│   │   │   ├── deepseek/
│   │   │   │   ├── DeepSeekProvider.ts
│   │   │   │   └── models.ts
│   │   │   ├── google/                       # Google Provider 深度实现
│   │   │   │   ├── media/                    # Google 媒体生成逻辑
│   │   │   │   │   ├── audio.ts
│   │   │   │   │   ├── image-edit.ts
│   │   │   │   │   ├── image-gen.ts
│   │   │   │   │   ├── index.ts
│   │   │   │   │   └── video.ts
│   │   │   │   ├── fileService.ts            # Google File API 上传
│   │   │   │   ├── GoogleProvider.ts         # 主类
│   │   │   │   ├── models.ts                 # 模型列表获取
│   │   │   │   ├── parser.ts                 # 流式响应解析
│   │   │   │   └── utils.ts
│   │   │   ├── moonshot/
│   │   │   │   ├── MoonshotProvider.ts
│   │   │   │   └── models.ts
│   │   │   ├── ollama/
│   │   │   │   ├── OllamaProvider.ts
│   │   │   │   └── models.ts
│   │   │   ├── openai/
│   │   │   │   └── OpenAIProvider.ts         # 通用 OpenAI 兼容类
│   │   │   ├── siliconflow/
│   │   │   │   ├── SiliconFlowProvider.ts
│   │   │   │   └── models.ts
│   │   │   ├── tongyi/                       # 阿里通义千问实现
│   │   │   │   ├── api.ts                    # API 路由
│   │   │   │   ├── chat.ts                   # 原生流式对话
│   │   │   │   ├── DashScopeProvider.ts
│   │   │   │   ├── image-edit.ts
│   │   │   │   ├── image-expand.ts
│   │   │   │   ├── image-gen.ts
│   │   │   │   ├── image-utils.ts
│   │   │   │   ├── image.ts
│   │   │   │   └── models.ts
│   │   │   ├── zhipu/
│   │   │   │   ├── ZhiPuProvider.ts
│   │   │   │   └── models.ts
│   │   │   └── interfaces.ts                 # Provider 接口定义
│   │   ├── storage/
│   │   │   └── BlobStorageService.ts         # IndexedDB 封装
│   │   ├── stream/
│   │   │   └── StreamManager.ts              # 流任务管理 (AbortSignal)
│   │   ├── browserProgressService.ts         # 浏览器进度 SSE 客户端
│   │   ├── configurationService.ts           # 配置服务
│   │   ├── db.ts                             # 混合数据库适配器
│   │   ├── embeddingService.ts               # RAG 服务客户端
│   │   ├── LLMFactory.ts                     # Provider 工厂
│   │   ├── llmService.ts                     # 统一 LLM 服务门面
│   │   └── pdfExtractionService.ts           # PDF 提取服务客户端
│   ├── utils/                                # 工具函数
│   │   ├── groundingUtils.ts                 # 搜索引用处理
│   │   └── iconUtils.ts                      # 图标映射
│   ├── App.tsx                               # 根组件
│   └── main.tsx                              # 入口文件
├── docs/                                     # 项目文档
├── public/                                   # 静态资源
├── .env.tsx                                  # 环境变量 (模板)
├── .gitignore
├── index.html                                # HTML 入口
├── index.tsx                                 # (可能的遗留入口)
├── manifest.json                             # PWA/Extension 配置
├── metadata.json                             # 应用元数据
├── package-lock.json
├── package.json
├── pnpm-lock.yaml
├── README.md
├── star.txt                                  # 启动命令备忘
├── tsconfig.json                             # TypeScript 配置
├── types.ts                                  # 全局类型定义
└── vite.config.ts                            # Vite 构建配置