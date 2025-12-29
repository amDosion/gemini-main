# Header.tsx 模型选择器数据流向分析

## 1. 分析概览

本文档详细追踪了 `Header.tsx` 中模型选择器的数据来源，完整梳理了从 API 获取到 UI 展示的整个数据流程。

**涉及文件：**
- `frontend/components/layout/Header.tsx` - 模型选择器 UI 组件
- `frontend/hooks/useModels.ts` - 模型管理 Hook
- `frontend/services/llmService.ts` - LLM 服务层
- `frontend/services/LLMFactory.ts` - Provider 工厂
- `frontend/services/providers/google/GoogleProvider.ts` - Google Provider 实现
- `frontend/services/providers/google/models.ts` - Google 模型获取逻辑

---

## 2. 完整数据流向

### 阶段 0：Profile 验证和保存（数据库缓存建立）

```
用户在设置页面点击"Verify Connection"
    ↓
EditorTab.handleVerify()
    ↓
LLMFactory.getProvider().getAvailableModels(apiKey, baseUrl)
    ↓
获取模型列表 ModelConfig[]
    ↓
setFormData({ savedModels: models, cachedModelCount: models.length })
    ↓
用户点击"Save"
    ↓
db.saveProfile(profileToSave)
    ↓
Profile.savedModels 存入数据库（HybridDB）
```

### 阶段 1：用户配置激活

```
用户选择 Profile (配置文件)
    ↓
onActivateProfile(profileId)
    ↓
llmService.setConfig(apiKey, baseUrl, protocol, providerId)
    ↓
触发 useModels Hook 重新加载
```

### 阶段 2：模型列表获取（三层缓存策略）

```
useModels Hook
    ↓
useEffect 监听 configReady, providerId, apiKey 变化
    ↓
检查数据库缓存 (cachedModels = activeProfile?.savedModels)
    ├─ 有数据库缓存 → 直接使用，跳过 API 调用
    │   ↓
    │   setAvailableModels(cachedModels)
    │   ↓
    │   自动选择最佳模型
    │
    └─ 无数据库缓存 → 调用 llmService.getAvailableModels(useCache=true)
        ↓
        检查内存缓存 (5分钟 TTL)
        ├─ 有内存缓存 → 返回缓存数据
        └─ 无内存缓存 → 调用 Provider
            ↓
            LLMFactory.getProvider(protocol, providerId)
            ↓
            根据 providerId 返回对应 Provider 实例
            ├─ 'google' → GoogleProvider
            ├─ 'tongyi' → DashScopeProvider
            ├─ 'deepseek' → DeepSeekProvider
            ├─ 'openai' → OpenAIProvider
            └─ 其他 → 根据 protocol 决定
                ↓
            Provider.getAvailableModels(apiKey, baseUrl)
            ↓
            存入内存缓存 (5分钟有效期)
```

### 阶段 3：Google Provider 模型获取详情

```
GoogleProvider.getAvailableModels()
    ↓
调用 getGoogleModels(apiKey, baseUrl)
    ↓
构建 API 端点
    ├─ 官方 API: https://generativelanguage.googleapis.com/v1beta/models?key={apiKey}
    └─ 代理 API: {baseUrl}/v1beta/models?key={apiKey}
        ↓
发送 HTTP GET 请求
    ↓
解析响应数据
    ├─ data.models (标准 Google 格式)
    ├─ data.data (OpenAI 包装格式)
    └─ Array (原始数组)
        ↓
过滤和转换模型
    ├─ 检查 supportedGenerationMethods (generateContent / generateVideos / predict)
    ├─ 提取 modelId (去除 'models/' 前缀)
    ├─ 判断能力标签
    │   ├─ vision: 多模态模型
    │   ├─ search: 支持搜索
    │   ├─ reasoning: 推理模型 (优化后:明确指定 pro 版本)
    │   └─ coding: 编码能力
    └─ 应用 CAPABILITY_OVERRIDES (已优化)
        ↓
排序模型列表
    ├─ gemini-3-pro: 100分
    ├─ gemini-2.5-pro: 90分
    ├─ 2.5-flash-image: 11分
    ├─ 2.5-flash: 10分
    ├─ thinking: 9分
    ├─ imagen: 8分
    └─ veo: 1分
        ↓
返回 ModelConfig[] 数组
```

### 阶段 4：模型过滤和选择

```
useModels Hook 接收 availableModels
    ↓
计算 visibleModels (过滤隐藏模型)
    ↓
visibleModels = availableModels.filter(m => !hiddenModelIds.includes(m.id))
    ↓
自动选择最佳模型 (selectBestModel)
    ├─ Google: 优先 reasoning > search > flash
    ├─ OpenAI: 优先 gpt-4o
    ├─ DeepSeek: 优先 chat
    └─ 其他: 第一个可见模型
        ↓
设置 currentModelId
    ↓
计算 activeModelConfig
```

### 阶段 5：Header 组件展示

```
Header 组件接收 props
    ├─ visibleModels: ModelConfig[]
    ├─ currentModelId: string
    ├─ activeModelConfig: ModelConfig
    └─ appMode: AppMode
        ↓
根据 appMode 过滤模型 (filteredModels)
    ├─ 'video-gen': veo, sora, video, luma
    ├─ 'audio-gen': tts, audio, speech
    ├─ 'image-gen': image, dall, wanx, flux, midjourney
    ├─ 'image-edit': vision 模型
    ├─ 'pdf-extract': 排除媒体生成模型
    └─ 'chat': 排除 veo, tts, wanx
        ↓
渲染模型选择器下拉菜单
    ├─ 显示当前模型名称和图标
    ├─ 显示能力标签 (search, reasoning, vision)
    └─ 点击切换模型 → onModelSelect(modelId)
```

---

## 3. 关键数据结构

### ModelConfig 接口

```typescript
interface ModelConfig {
  id: string;                    // 模型唯一标识 (如 'gemini-2.0-flash')
  name: string;                  // 显示名称
  description: string;           // 描述
  capabilities: {
    vision: boolean;             // 支持图像输入
    search: boolean;             // 支持搜索
    reasoning: boolean;          // 推理能力
    coding: boolean;             // 编码能力
  };
  baseModelId: string;           // 基础模型 ID
}
```

### 能力覆盖配置（已优化）

```typescript
const CAPABILITY_OVERRIDES: Record<string, Partial<ModelConfig['capabilities']>> = {
    'gemini-2.0-flash-thinking': { reasoning: true, search: false },
    'gemini-2.5-pro': { reasoning: true },  // ✅ 优化:明确指定 2.5 pro 版本
    'gemini-3-pro': { reasoning: true },
    'veo': { vision: true }
};
```

**优化说明**（2025-12-28 更新）：
- **修改前**: `'gemini-2.5': { reasoning: true }` 会匹配所有 2.5 系列模型
- **修改后**: `'gemini-2.5-pro': { reasoning: true }` 仅匹配 pro 版本
- **影响**: `gemini-2.5-flash` 不再被错误标记为推理模型

### 推理能力判断逻辑（已优化）

```typescript
// 优化后的推理模型判断 (models.ts:89-94)
const isThinking = modelId.includes('thinking') ||
                   modelId.includes('reasoning') ||
                   modelId.includes('2.5-pro') ||    // 明确 2.5 pro 版本
                   modelId.includes('3-pro') ||
                   modelId.includes('3.0-pro');      // 明确 3.0 pro 版本
```

**优化说明**：
- **修改前**: 使用 `'2.5'` 和 `'3.0'` 作为判断条件,过度宽泛
- **修改后**: 明确指定 `'2.5-pro'` 和 `'3.0-pro'`,避免误匹配
- **原因**: 避免未来的 `gemini-3.0-flash` 等非推理模型被错误识别

---

## 4. 三层缓存机制

模型列表采用三层缓存策略，优先级从高到低：

### 4.1 数据库缓存（Profile.savedModels）

**存储位置**：`ConfigProfile.savedModels` 字段（数据库持久化）

**触发时机**：用户在设置页面点击"Verify Connection"按钮后

**验证流程**（EditorTab.tsx）：
```typescript
const handleVerify = async () => {
    // 1. 调用 Provider 获取模型列表
    const models = await providerInstance.getAvailableModels(apiKey, baseUrl);
    
    // 2. 保存到 formData（待保存状态）
    setFormData(prev => ({
        ...prev,
        cachedModelCount: models.length,
        savedModels: models,  // ✅ 关键：保存完整模型列表
        hiddenModels: nextHidden
    }));
};

// 3. 用户点击"Save"后，Profile 连同 savedModels 一起存入数据库
await db.saveProfile(profileToSave);
```

**使用流程**（App.tsx）：
```typescript
// 1. 从 activeProfile 获取缓存的模型列表
const cachedModels = useMemo(() => activeProfile?.savedModels, [activeProfile?.savedModels]);

// 2. 传递给 useModels Hook
const { visibleModels, currentModelId } = useModels(
    true, 
    hiddenModelIds, 
    config.providerId, 
    cachedModels,  // ✅ 优先使用数据库缓存
    config.apiKey
);
```

**优势**：
- 持久化存储，刷新页面不丢失
- 无需每次启动都调用 API
- 支持离线使用（如果已验证过）

---

### 4.2 内存缓存（LLMService.modelCache）

**存储位置**：`llmService` 内存 Map

**缓存策略**：
```typescript
private modelCache = new Map<string, ModelCache>();
const CACHE_TTL = 5 * 60 * 1000; // 5分钟

interface ModelCache {
  models: ModelConfig[];
  timestamp: number;
  providerId: string;
}

// 缓存键格式
const cacheKey = `${providerId}_${apiKey}`;
```

**缓存逻辑**：
1. 首次加载：从 API 获取 → 存入缓存
2. 5分钟内：直接返回缓存数据
3. 超过5分钟：重新请求 API → 更新缓存
4. 请求失败：返回过期缓存（降级策略）

**触发条件**：
- 没有数据库缓存（`cachedModels` 为空）
- 用户手动刷新模型列表

---

### 4.3 API 调用（实时获取）

**触发条件**：
- 数据库缓存不存在
- 内存缓存过期（超过 5 分钟）
- 用户手动刷新（`refreshModels()`）

**调用流程**：
```
llmService.getAvailableModels(useCache=false)
    ↓
LLMFactory.getProvider(protocol, providerId)
    ↓
Provider.getAvailableModels(apiKey, baseUrl)
    ↓
HTTP GET 请求到 API 端点
    ↓
返回 ModelConfig[] 数组
```

---

### 4.4 缓存优先级总结

| 优先级 | 缓存类型 | 有效期 | 触发条件 | 优势 |
|-------|---------|-------|---------|------|
| 1 | 数据库缓存 | 永久 | Profile 验证后保存 | 持久化、离线可用 |
| 2 | 内存缓存 | 5分钟 | 首次 API 调用后 | 快速响应、减少 API 调用 |
| 3 | API 调用 | 实时 | 缓存不存在或过期 | 数据最新、支持动态更新 |

**实际使用场景**：

1. **首次使用**：
   - 用户创建 Profile → 点击"Verify Connection" → API 调用 → 保存到数据库
   - 下次启动：直接从数据库加载，无需 API 调用

2. **切换 Profile**：
   - 如果新 Profile 有 `savedModels`：直接使用数据库缓存
   - 如果新 Profile 没有 `savedModels`：调用 API → 存入内存缓存

3. **手动刷新**：
   - 用户点击刷新按钮 → 绕过所有缓存 → 直接调用 API → 更新内存缓存

4. **API 失败降级**：
   - 数据库缓存存在 → 使用数据库缓存
   - 内存缓存存在 → 使用过期的内存缓存
   - 都不存在 → 显示错误提示


---

## 5. 模型自动选择逻辑

```typescript
// Google Provider 优先级
candidate = visible.find(m => m.capabilities.reasoning)      // 1. 推理模型
         || visible.find(m => m.capabilities.search)         // 2. 搜索模型
         || visible.find(m => m.id.includes('flash'))        // 3. Flash 模型
         || visible[0];                                      // 4. 第一个可见模型

// OpenAI Provider 优先级
candidate = visible.find(m => m.id.includes('gpt-4o'))       // 1. GPT-4o
         || visible[0];                                      // 2. 第一个可见模型

// DeepSeek Provider 优先级
candidate = visible.find(m => m.id.includes('chat'))         // 1. Chat 模型
         || visible[0];                                      // 2. 第一个可见模型
```

---

## 6. AppMode 模型过滤规则

| AppMode | 过滤规则 | 示例模型 |
|---------|---------|---------|
| `video-gen` | 包含 veo, sora, video, luma | Veo 2, Sora |
| `audio-gen` | 包含 tts, audio, speech | Google TTS |
| `image-gen` | 包含 image, dall, wanx, flux, midjourney 或 vision | Imagen 3, DALL-E |
| `image-edit` | vision 能力且非 veo | Gemini 2.0 Flash |
| `image-outpainting` | vision 能力且非 veo | Gemini 2.0 Flash |
| `virtual-try-on` | vision 能力且非 veo | Gemini 2.0 Flash |
| `deep-research` | search 或 reasoning 能力 | Gemini 2.5 Pro, Gemini Flash |
| `pdf-extract` | 排除 veo, tts, wanx, imagen | Gemini Flash |
| `chat` | 排除 veo, tts, wanx | Gemini 2.0 Flash |

**补充说明**：
- `virtual-try-on`（虚拟试衣）：需要视觉理解能力来处理服装图像
- `deep-research`（深度研究）：需要搜索能力获取信息或推理能力进行分析
- 这两个模式在早期版本文档中遗漏，现已补充完整

---

## 7. 模型自动选择逻辑（App.tsx）

当用户切换 AppMode 时，`App.tsx` 会自动选择最适合的模型：

```typescript
// App.tsx:579-611 - handleModeSwitch 函数
const handleModeSwitch = useCallback((mode: AppMode) => {
    setAppMode(mode);

    if (mode === 'image-gen') {
        // 优先级：imagen > gemini-2.5-flash-image > 其他 image 模型 > vision 模型
        let imageModel = visibleModels.find(m => m.id.includes('imagen'));
        if (!imageModel) {
            imageModel = visibleModels.find(m => m.id === 'gemini-2.5-flash-image')
                      || visibleModels.find(m => m.id.includes('image'))
                      || visibleModels.find(m => m.capabilities.vision);
        }
        if (imageModel) setCurrentModelId(imageModel.id);
    } else if (mode === 'image-edit' || mode === 'image-outpainting') {
        // 需要视觉能力但排除图像生成专用模型
        const imageModel = visibleModels.find(m => m.capabilities.vision && !m.id.includes('imagen'));
        if (imageModel) setCurrentModelId(imageModel.id);
    } else if (mode === 'video-gen') {
        // 优先选择 veo 模型
        const videoModel = visibleModels.find(m => m.id.includes('veo'));
        if (videoModel) setCurrentModelId(videoModel.id);
    } else if (mode === 'audio-gen') {
        // 优先选择 tts 模型
        const audioModel = visibleModels.find(m => m.id.includes('tts'));
        if (audioModel) setCurrentModelId(audioModel.id);
    } else if (mode === 'deep-research') {
        // 优先选择具有搜索或推理能力的模型
        const researchModel = visibleModels.find(m => m.capabilities.search || m.capabilities.reasoning);
        if (researchModel) setCurrentModelId(researchModel.id);
    }
    // chat 和 pdf-extract 模式保持当前模型（如果兼容）
}, [visibleModels, setCurrentModelId]);
```

**关键特性**：
- **主动选择**：不同于 Header 组件的被动过滤，App.tsx 会主动切换模型
- **智能回退**：如果首选模型不可用，会按优先级依次尝试
- **保留兼容**：对于 chat/pdf-extract 模式，如果当前模型兼容则保持不变

---

## 8. API 端点构建逻辑

### supportedGenerationMethods 完整列表

Google API 返回的模型支持以下生成方法：

```typescript
// models.ts:79-82 - 方法检查
const canGen = supportedMethods.includes('generateContent') ||   // 标准文本/多模态生成
               supportedMethods.includes('generateVideos') ||    // 视频生成
               supportedMethods.includes('predict');            // 预测/推理任务
```

**三种方法说明**：
1. **generateContent**：适用于大多数 Gemini 模型（文本、多模态）
2. **generateVideos**：专用于视频生成模型（如 Veo）
3. **predict**：通用预测接口（兼容性 API）

### 官方 Google API

```
https://generativelanguage.googleapis.com/v1beta/models?key={apiKey}
```

### 代理 API

```
情况 1: baseUrl 以 /v1beta 或 /v1 结尾
    → {baseUrl}/models?key={apiKey}

情况 2: baseUrl 不包含版本路径
    → 尝试 {baseUrl}/v1beta/models?key={apiKey}
    → 失败则尝试 {baseUrl}/models?key={apiKey}
```

---

## 8. 模型排序权重

```typescript
const score = (id: string) => {
    if (id.includes('gemini-3-pro')) return 100;      // 最高优先级
    if (id.includes('gemini-2.5-pro')) return 90;
    if (id.includes('2.5-flash-image')) return 11;
    if (id.includes('2.5-flash')) return 10;
    if (id.includes('thinking')) return 9;
    if (id.includes('imagen')) return 8;
    if (id.includes('veo')) return 1;                 // 最低优先级
    return 0;
};
```

---

## 9. 关键流程图

```
┌─────────────────────────────────────────────────────────────┐
│  阶段 0：Profile 验证（建立数据库缓存）                       │
│  用户在设置页面点击"Verify Connection"                       │
│  └─ EditorTab.handleVerify()                               │
│      └─ Provider.getAvailableModels(apiKey, baseUrl)       │
│          └─ 获取模型列表 ModelConfig[]                      │
│              └─ setFormData({ savedModels: models })       │
│                  └─ 用户点击"Save"                          │
│                      └─ db.saveProfile(profileToSave)      │
│                          └─ Profile.savedModels 存入数据库  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 1：用户激活 Profile                                    │
│  └─ onActivateProfile(profileId)                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  llmService.setConfig(apiKey, baseUrl, protocol, providerId)│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 2：useModels Hook 触发                                 │
│  └─ useEffect 监听配置变化                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  检查数据库缓存 (cachedModels = activeProfile?.savedModels) │
│  ├─ 有数据库缓存 → 直接使用，跳过 API 调用                   │
│  │   └─ setAvailableModels(cachedModels)                   │
│  │       └─ 自动选择最佳模型                                │
│  │           └─ 完成加载                                    │
│  │                                                          │
│  └─ 无数据库缓存 → 继续检查内存缓存                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  llmService.getAvailableModels(useCache=true)               │
│  └─ 检查内存缓存 (5分钟 TTL)                                │
│      ├─ 有内存缓存 → 返回缓存数据                           │
│      └─ 无内存缓存 → 调用 Provider                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  LLMFactory.getProvider(protocol, providerId)               │
│  └─ 返回对应 Provider 实例                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Provider.getAvailableModels(apiKey, baseUrl)               │
│  └─ 以 GoogleProvider 为例                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  getGoogleModels(apiKey, baseUrl)                           │
│  ├─ 构建 API 端点                                           │
│  ├─ 发送 HTTP GET 请求                                      │
│  ├─ 解析响应数据                                            │
│  ├─ 过滤和转换模型                                          │
│  ├─ 应用能力覆盖                                            │
│  ├─ 排序模型列表                                            │
│  └─ 存入内存缓存 (5分钟有效期)                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  返回 ModelConfig[] 数组                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  useModels Hook 处理                                         │
│  ├─ setAvailableModels(models)                             │
│  ├─ 计算 visibleModels (过滤隐藏)                           │
│  ├─ 自动选择最佳模型                                         │
│  └─ 计算 activeModelConfig                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Header 组件接收 props                                       │
│  ├─ visibleModels                                           │
│  ├─ currentModelId                                          │
│  ├─ activeModelConfig                                       │
│  └─ appMode                                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  根据 appMode 过滤模型 (filteredModels)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  渲染模型选择器 UI                                           │
│  ├─ 显示当前模型                                            │
│  ├─ 显示能力标签                                            │
│  └─ 下拉菜单展示所有可用模型                                 │
└─────────────────────────────────────────────────────────────┘
```


---

## 10. 代码示例

### useModels Hook 核心逻辑

```typescript
export const useModels = (
    configReady: boolean, 
    hiddenModelIds: string[], 
    providerId: string,
    cachedModels?: ModelConfig[],
    apiKey?: string
) => {
  const [availableModels, setAvailableModels] = useState<ModelConfig[]>([]);
  const [currentModelId, setCurrentModelId] = useState<string>("");
  
  useEffect(() => {
    if (!configReady) return;

    const internalFetchModels = async (useCache: boolean) => {
      setIsLoadingModels(true);
      try {
        const models = await llmService.getAvailableModels(useCache);
        if (models && models.length > 0) {
          setAvailableModels(models);
          internalSelectBestModel(models, !useCache);
        }
      } catch (e) {
        console.error("Failed to fetch models", e);
      } finally {
        setIsLoadingModels(false);
      }
    };

    if (cachedModels && cachedModels.length > 0) {
        setAvailableModels(cachedModels);
        internalSelectBestModel(cachedModels, false);
    } else {
      internalFetchModels(true);
    }
  }, [configReady, providerId, apiKey, cachedModels, hiddenModelIds]);

  const visibleModels = useMemo(() => {
    return availableModels.filter(m => !hiddenModelIds.includes(m.id));
  }, [availableModels, hiddenModelIds]);

  return {
    availableModels,
    visibleModels,
    currentModelId,
    activeModelConfig,
    isLoadingModels
  };
};
```

### Header 组件模型过滤

```typescript
const filteredModels = useMemo(() => {
    return visibleModels.filter(m => {
        const id = m.id.toLowerCase();
        const caps = m.capabilities;

        switch (appMode) {
            case 'video-gen':
                return id.includes('veo') || id.includes('sora') || 
                       id.includes('video') || id.includes('luma');
            case 'audio-gen':
                return id.includes('tts') || id.includes('audio') || 
                       id.includes('speech');
            case 'image-gen':
                return id.includes('image') || id.includes('dall') || 
                       id.includes('wanx') || id.includes('flux') || 
                       id.includes('midjourney') || 
                       (caps.vision && !id.includes('veo'));
            case 'image-edit':
            case 'image-outpainting':
                return caps.vision && !id.includes('veo');
            case 'pdf-extract':
                return !id.includes('veo') && !id.includes('tts') && 
                       !id.includes('wanx') && !id.includes('imagen');
            case 'chat':
            default:
                return !id.includes('veo') && !id.includes('tts') && 
                       !id.includes('wanx');
        }
    });
}, [visibleModels, appMode]);
```

---

## 11. 总结

### 数据来源

`Header.tsx` 中的模型列表来源于以下完整链路：

1. **配置层**：用户选择的 Profile (包含 apiKey, baseUrl, protocol, providerId)
2. **数据库缓存层**：Profile 验证后保存的 `savedModels` 字段（优先级最高）
3. **服务层**：`llmService` 根据配置调用对应的 Provider
4. **内存缓存层**：`llmService.modelCache` 提供 5 分钟 TTL 缓存
5. **Provider 层**：各 Provider 实现 `getAvailableModels` 方法，从 API 获取模型列表
6. **Hook 层**：`useModels` Hook 管理模型状态、缓存、过滤和自动选择
7. **组件层**：`Header` 组件根据 `appMode` 进一步过滤并展示模型

### 关键特性

- **三层缓存策略**：数据库缓存（永久） → 内存缓存（5分钟） → API 调用（实时）
- **多 Provider 支持**：通过 `LLMFactory` 统一管理不同 Provider
- **智能缓存**：优先使用数据库缓存，降级策略保证可用性
- **自动选择**：根据 Provider 类型智能选择最佳模型
- **模式过滤**：根据 `appMode` 动态过滤适用模型
- **能力标签**：清晰展示模型的 vision、search、reasoning 能力
- **离线可用**：验证过的 Profile 可在无网络环境下使用

### 扩展性

要添加新的 Provider，只需：
1. 在 `services/providers/` 下创建新 Provider 类
2. 实现 `ILLMProvider` 接口
3. 在 `LLMFactory` 中注册
4. 在 `models.ts` 中实现模型获取逻辑

### 性能优化

1. **数据库缓存**：避免重复 API 调用，支持离线使用
2. **内存缓存**：减少 API 调用频率（5分钟 TTL）
3. **useMemo**：避免不必要的重新计算
4. **降级策略**：API 失败时使用过期缓存
5. **按需加载**：只在配置就绪时加载模型
6. **稳定引用**：使用 `useMemo` 避免触发不必要的 `useEffect`

---

## 12. 常见问题

### Q1: 为什么模型列表为空？

**可能原因：**
1. API Key 无效或过期
2. Base URL 配置错误
3. 网络连接问题
4. Provider 不支持该 API 端点
5. Profile 未验证（没有 `savedModels` 缓存）

**排查步骤：**
1. 检查浏览器控制台错误信息
2. 验证 API Key 是否有效
3. 确认 Base URL 格式正确
4. 在设置页面点击"Verify Connection"重新验证
5. 尝试刷新模型列表

### Q2: 为什么某些模型不显示？

**可能原因：**
1. 模型被添加到 `hiddenModelIds` 列表
2. 当前 `appMode` 过滤掉了该模型
3. 模型不支持 `generateContent` 方法

**解决方案：**
1. 检查 Profile 配置中的隐藏模型列表
2. 切换到合适的 `appMode`
3. 查看模型的 `supportedGenerationMethods`

### Q3: 如何添加自定义模型？

**步骤：**
1. 在对应 Provider 的 `models.ts` 中添加模型配置
2. 设置正确的 `capabilities` 标签
3. 如需特殊处理，添加到 `CAPABILITY_OVERRIDES`
4. 调整排序权重（可选）

### Q4: 为什么有时不需要调用 API？

**原因：**

系统采用三层缓存策略，优先级从高到低：

1. **数据库缓存（Profile.savedModels）**：
   - 用户在设置页面验证连接后，模型列表会保存到 Profile 的 `savedModels` 字段
   - 下次启动时直接从数据库加载，无需调用 API
   - 这是最常见的情况，也是为什么大多数时候不需要调用 API

2. **内存缓存（LLMService.modelCache）**：
   - 如果数据库缓存不存在，首次 API 调用后会存入内存缓存
   - 5 分钟内的后续请求直接使用内存缓存
   - 超过 5 分钟后重新调用 API

3. **API 调用（实时获取）**：
   - 只有在数据库缓存和内存缓存都不存在时才会调用
   - 或者用户手动点击刷新按钮时强制调用

**验证方法：**
- 打开浏览器开发者工具 → Network 标签
- 切换 Profile 或刷新页面
- 如果没有看到模型列表的 API 请求，说明使用了缓存

### Q5: 如何强制刷新模型列表？

**方法：**
1. 在设置页面重新点击"Verify Connection"按钮
2. 或者在代码中调用 `refreshModels()` 函数（绕过所有缓存）

### Q6: 数据库缓存和内存缓存有什么区别？

| 特性 | 数据库缓存 | 内存缓存 |
|------|-----------|---------|
| 存储位置 | 数据库（HybridDB） | 内存（Map） |
| 有效期 | 永久 | 5 分钟 |
| 持久化 | 是 | 否 |
| 刷新页面后 | 保留 | 丢失 |
| 离线可用 | 是 | 否 |
| 触发条件 | Profile 验证后保存 | 首次 API 调用后 |

### Q7: 为什么切换 Profile 后模型列表立即显示？

**原因：**

当你切换到一个已验证过的 Profile 时：
1. `App.tsx` 从 `activeProfile.savedModels` 获取缓存的模型列表
2. 通过 `useMemo` 创建稳定的 `cachedModels` 引用
3. 传递给 `useModels` Hook
4. `useModels` 检测到 `cachedModels` 存在且长度 > 0
5. 直接使用缓存，跳过 API 调用
6. 立即渲染模型选择器

这就是为什么切换 Profile 时模型列表能够瞬间显示，而不需要等待 API 响应。

---

## 13. 相关文件索引

| 文件路径 | 职责 |
|---------|------|
| `frontend/components/layout/Header.tsx` | 模型选择器 UI |
| `frontend/hooks/useModels.ts` | 模型状态管理、缓存优先级处理 |
| `frontend/services/llmService.ts` | LLM 服务层、内存缓存管理 |
| `frontend/services/LLMFactory.ts` | Provider 工厂 |
| `frontend/services/db.ts` | 数据库适配器（HybridDB）、Profile 存储 |
| `frontend/components/modals/settings/EditorTab.tsx` | Profile 验证和保存逻辑 |
| `frontend/App.tsx` | 数据库缓存使用、cachedModels 传递 |
| `frontend/services/providers/google/GoogleProvider.ts` | Google Provider |
| `frontend/services/providers/google/models.ts` | Google 模型获取 |
| `frontend/services/providers/openai/OpenAIProvider.ts` | OpenAI Provider |
| `frontend/services/providers/deepseek/DeepSeekProvider.ts` | DeepSeek Provider |
| `frontend/services/providers/tongyi/DashScopeProvider.ts` | 通义千问 Provider |
| `frontend/types/types.ts` | 类型定义（ModelConfig, ConfigProfile） |

---

**文档版本**: 3.0
**最后更新**: 2025-12-28
**作者**: Kiro AI Assistant
**更新内容**:
- v3.0 (2025-12-28): 补充 virtual-try-on 和 deep-research 模式、模型自动选择逻辑、supportedGenerationMethods 完整列表、优化推理模型判断
- v2.0 (2025-12-28): 补充三层缓存机制（数据库缓存、内存缓存、API 调用）的完整说明
- v1.0 (初版): 初始数据流分析文档
