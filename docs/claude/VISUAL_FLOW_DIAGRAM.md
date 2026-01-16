# 可视化流程图

**日期：** 2026-01-15  
**说明：** 使用 Mermaid 图表展示关键流程

---

## 🔐 登录到主页加载完整流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant L as LoginPage
    participant A as useAuth
    participant API as 后端 API
    participant I as useInitData
    participant M as useModels
    participant H as Header
    
    U->>L: 输入邮箱密码
    L->>A: login({ email, password })
    A->>API: POST /api/auth/login
    API-->>A: { user, access_token, refresh_token }
    A->>A: 存储 Token 到 localStorage
    A->>A: setUser(user)
    A->>A: setIsAuthenticated(true)
    
    Note over A,I: 路由守卫触发重定向
    
    A->>I: 触发 useInitData
    I->>API: GET /api/init
    API-->>I: { profiles, sessions, personas, storageConfigs }
    I->>I: setInitData(data)
    I->>I: LLMFactory.initialize()
    
    Note over I,M: App 组件初始化 40+ Hooks
    
    I->>M: useModels 初始化
    M->>M: 检查 cachedModels
    alt 有缓存
        M->>M: 使用 cachedModels
    else 无缓存
        M->>API: GET /api/models/{provider}
        API-->>M: { models: [...] }
        M->>M: 缓存到 IndexedDB
    end
    
    M->>M: filterModelsByAppMode(models, 'chat')
    M->>M: 排除隐藏模型
    M->>M: 生成 visibleModels
    M->>M: 自动选择第一个模型
    M-->>H: 传递 visibleModels, currentModelId
    
    H->>H: 渲染 Header（模型列表）
    H->>U: 显示主页
```

---

## 🔄 模式切换联动流程（优化后）

```mermaid
sequenceDiagram
    participant U as 用户
    participant B as Button (UI)
    participant MS as useModeSwitch
    participant A as App.tsx
    participant UM as useModels
    participant F as filterModelsByAppMode
    participant H as Header
    
    U->>B: 点击 "Image Generation"
    B->>MS: handleModeSwitch('image-gen')
    MS->>A: setAppMode('image-gen')
    
    Note over A,UM: appMode 状态更新触发 useModels
    
    A->>UM: appMode 变化检测
    UM->>UM: appModeChanged = true
    UM->>UM: 清除用户选择标志
    UM->>UM: prevAppModeRef.current = 'image-gen'
    
    UM->>F: filterModelsByAppMode(availableModels, 'image-gen')
    F-->>UM: 过滤后的模型列表
    
    UM->>UM: 智能选择第一个模型
    Note over UM: 优先选择 Imagen 或 Gemini 2.5 Flash Image
    
    UM->>UM: setCurrentModelId(preferredModel.id)
    UM->>UM: visibleModels 自动更新 (useMemo)
    
    UM-->>H: 传递新的 visibleModels, currentModelId
    H->>H: 重新渲染模型列表
    H->>U: 显示新的模型选项
    
    Note over U,H: ✅ 整个流程 < 1ms，无 API 调用
```

---

## 🎨 Chat 消息发送流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant CV as ChatView
    participant A as App.tsx
    participant UC as useChat
    participant S as Strategy
    participant LLM as LLM Service
    participant API as 后端 API
    
    U->>CV: 输入消息 "Hello"
    CV->>A: onSend(text, options, [], 'chat')
    A->>A: 检查 API Key
    A->>A: 检查当前会话
    A->>UC: sendMessage(text, options, [], 'chat', model, protocol)
    
    UC->>UC: 创建 ExecutionContext
    UC->>UC: 预处理（文件上传等）
    UC->>UC: 创建乐观 User Message
    UC->>CV: 更新 UI（显示用户消息）
    
    UC->>S: strategyRegistry.get('chat')
    S->>S: ChatStrategy.execute(context)
    S->>LLM: llmService.sendMessage(prompt, [], model, options)
    
    LLM->>API: POST /api/chat/stream
    API-->>LLM: 流式响应（SSE）
    
    loop 流式响应
        LLM-->>S: chunk { text: "..." }
        S-->>UC: onStreamUpdate({ content, done: false })
        UC->>CV: 更新 UI（显示生成的内容）
    end
    
    LLM-->>S: 流式响应完成
    S-->>UC: 返回完整 Message
    UC->>UC: 保存到会话
    UC->>CV: 最终更新 UI
```

---

## 🖼️ 图片生成流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant SV as StudioView
    participant A as App.tsx
    participant UC as useChat
    participant S as ImageGenStrategy
    participant API as 后端 API
    participant OSS as 云存储
    
    U->>SV: 输入提示词 "A sunset"
    SV->>A: onSend(prompt, options, [], 'image-gen')
    A->>UC: sendMessage(prompt, options, [], 'image-gen', imagenModel, protocol)
    
    UC->>UC: 创建 ExecutionContext
    UC->>S: strategyRegistry.get('image-gen')
    S->>S: ImageGenStrategy.execute(context)
    
    alt Imagen 模型
        S->>API: POST /api/imagen/generate
        API-->>S: { imageData: base64 }
    else Gemini 2.5 Flash Image
        S->>API: POST /api/chat/stream (原生图像生成)
        API-->>S: { imageUrl: "..." }
    end
    
    S->>OSS: 上传图片到云存储
    OSS-->>S: { url: "https://..." }
    
    S->>UC: 返回 Message with image attachment
    UC->>SV: 更新 UI（显示生成的图片）
    U->>U: 查看生成的图片
```

---

## ✂️ 图片编辑流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant CV as ChatView
    participant A as App.tsx
    participant IH as useImageHandlers
    participant SV as StudioView
    participant UC as useChat
    participant S as ImageEditStrategy
    participant LLM as Vision Model
    participant API as 图片编辑 API
    
    U->>CV: 点击图片的 "Edit" 按钮
    CV->>IH: handleEditImage(imageUrl)
    IH->>A: setAppMode('image-chat-edit')
    IH->>A: setCurrentModelId(visionModel.id)
    IH->>A: setInitialAttachments([{ url: imageUrl }])
    
    Note over A,SV: 模式切换完成
    
    A->>SV: 渲染 StudioView
    SV->>U: 显示图片预览
    U->>SV: 输入编辑指令 "将天空变成紫色"
    
    SV->>A: onSend(editPrompt, options, [imageAttachment], 'image-chat-edit')
    A->>UC: sendMessage(editPrompt, ..., 'image-chat-edit', visionModel, protocol)
    
    UC->>S: strategyRegistry.get('image-chat-edit')
    S->>S: ImageEditStrategy.execute(context)
    
    S->>LLM: Vision 模型分析编辑意图
    LLM-->>S: 结构化编辑指令
    
    S->>API: POST /api/image/edit
    API->>API: 执行图片编辑
    API-->>S: { editedImageData: base64 }
    
    S->>OSS: 上传编辑后的图片
    OSS-->>S: { url: "https://..." }
    
    S->>UC: 返回 Message with edited image
    UC->>SV: 更新 UI（显示编辑后的图片）
    U->>U: 查看编辑效果
```

---

## 📊 Provider 切换流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant H as Header
    participant A as App.tsx
    participant US as useSettings
    participant UM as useModels
    participant API as 后端 API
    participant IDB as IndexedDB
    
    U->>H: 选择 Profile (OpenAI)
    H->>US: activateProfile(openai_profile_id)
    US->>API: PUT /api/profiles/activate
    API-->>US: { success: true }
    US->>US: setActiveProfileId(openai_profile_id)
    US->>US: setActiveProfile(openai_profile)
    
    Note over US,UM: activeProfile 变化触发 useModels
    
    US->>UM: providerId 变化检测
    UM->>UM: providerChanged = true
    UM->>UM: 清空 currentModelId
    UM->>UM: 重置用户选择标志
    
    UM->>IDB: 检查 OpenAI 模型缓存
    alt 有缓存
        IDB-->>UM: cachedModels (OpenAI)
        UM->>UM: 使用缓存
    else 无缓存
        UM->>API: GET /api/models/openai
        API-->>UM: { models: [...] }
        UM->>IDB: 缓存模型列表
    end
    
    UM->>UM: filterModelsByAppMode(models, appMode)
    UM->>UM: 自动选择第一个模型
    UM-->>H: 更新 visibleModels, currentModelId
    H->>H: 重新渲染模型列表
    H->>U: 显示 OpenAI 模型
```

---

## 🔍 模型过滤决策树

```mermaid
graph TD
    A[获取完整模型列表] --> B{appMode?}
    
    B -->|chat| C1[排除媒体生成模型]
    C1 --> C2[排除 Embedding 模型]
    C2 --> Z1[chat 模型列表]
    
    B -->|image-gen| D1[只包含图像生成模型]
    D1 --> D2[Imagen / Dall-E / Flux]
    D2 --> D3[或 Gemini 2.x Flash Image]
    D3 --> Z2[image-gen 模型列表]
    
    B -->|image-edit| E1[需要 Vision 能力]
    E1 --> E2[排除纯文生图模型]
    E2 --> E3[Gemini / GPT-4o Vision]
    E3 --> Z3[image-edit 模型列表]
    
    B -->|video-gen| F1[只包含视频生成模型]
    F1 --> F2[Veo / Sora / Luma]
    F2 --> Z4[video-gen 模型列表]
    
    B -->|audio-gen| G1[只包含音频生成模型]
    G1 --> G2[TTS / Audio Models]
    G2 --> Z5[audio-gen 模型列表]
    
    B -->|pdf-extract| H1[排除媒体生成模型]
    H1 --> H2[优先推理能力模型]
    H2 --> H3[优先 Vision 能力]
    H3 --> Z6[pdf-extract 模型列表]
    
    B -->|deep-research| I1[需要搜索或推理能力]
    I1 --> I2[Gemini Pro / GPT-4o]
    I2 --> Z7[deep-research 模型列表]
    
    Z1 --> J[排除隐藏模型]
    Z2 --> J
    Z3 --> J
    Z4 --> J
    Z5 --> J
    Z6 --> J
    Z7 --> J
    
    J --> K[visibleModels]
    K --> L[智能选择第一个模型]
    L --> M[setCurrentModelId]
```

---

## ⚡ 性能优化对比

```mermaid
graph LR
    subgraph "优化前（每次都调用 API）"
        A1[用户切换模式] --> B1[setAppMode]
        B1 --> C1[调用 API]
        C1 --> D1[等待响应 200-500ms]
        D1 --> E1[后端过滤]
        E1 --> F1[返回过滤后的模型]
        F1 --> G1[前端再次过滤]
        G1 --> H1[显示模型列表]
    end
    
    subgraph "优化后（前端过滤）"
        A2[用户切换模式] --> B2[setAppMode]
        B2 --> C2[前端过滤 < 1ms]
        C2 --> D2[自动选择模型]
        D2 --> E2[显示模型列表]
    end
    
    style A1 fill:#ff6b6b
    style C1 fill:#ff6b6b
    style D1 fill:#ff6b6b
    
    style A2 fill:#51cf66
    style C2 fill:#51cf66
    style D2 fill:#51cf66
```

**性能对比：**
- 优化前：200-500ms（API 调用 + 网络延迟）
- 优化后：< 1ms（纯前端操作）
- 提升：200-500x

---

## 🎯 关键数据流总结

### 登录流程
```
LoginPage → useAuth → API (POST /api/auth/login)
    ↓
存储 Token → setIsAuthenticated(true)
    ↓
路由重定向到主页
```

### 初始化流程
```
useInitData → API (GET /api/init)
    ↓
{ profiles, sessions, personas, storageConfigs }
    ↓
useSettings / useSessions / usePersonas / useStorageConfigs
    ↓
LLMFactory.initialize()
```

### 模型加载流程
```
useModels → 检查 cachedModels
    ↓
有缓存 → 使用缓存
无缓存 → API (GET /api/models/{provider})
    ↓
filterModelsByAppMode(models, appMode)  // 前端过滤
    ↓
排除隐藏模型 → visibleModels
    ↓
自动选择第一个模型 → currentModelId
```

### 模式切换流程
```
useModeSwitch → setAppMode('image-gen')
    ↓
useModels 检测 appModeChanged
    ↓
前端过滤 (< 1ms)
    ↓
自动选择新模式下的第一个模型
    ↓
Header 重新渲染
```

### 消息发送流程
```
onSend → useChat.sendMessage
    ↓
创建 ExecutionContext
    ↓
预处理（文件上传等）
    ↓
策略模式执行（ChatStrategy / ImageGenStrategy / ...）
    ↓
LLM Service 流式响应
    ↓
更新 UI（实时显示生成内容）
```

---

**文档创建时间：** 2026-01-15  
**工具：** Mermaid Diagrams
