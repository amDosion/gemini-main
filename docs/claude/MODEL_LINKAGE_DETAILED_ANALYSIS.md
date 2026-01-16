# 模型联动切换详细分析

**日期：** 2026-01-15  
**重点分析：** 模式切换时模型列表的联动机制和潜在问题

---

## 🎯 核心问题识别

### 当前实现的问题

**问题 1：双重过滤导致的不一致**
```typescript
// useModels.ts - 第 31-33 行
const filteredModelsByMode = useMemo(() => {
  return filterModelsByAppMode(availableModels, appMode);
}, [availableModels, appMode]);

// useModels.ts - 第 213-215 行
const visibleModels = useMemo(() => {
  return filteredModelsByMode.filter(m => !hiddenModelIds.includes(m.id));
}, [filteredModelsByMode, hiddenModelIds]);

// 问题：visibleModels 已经根据 appMode 过滤了
// 但是 Header.tsx 原本也有过滤逻辑（已移除）
// 如果 Header 重新添加过滤，会导致重复过滤
```

**问题 2：模型选择时机不准确**
```typescript
// useModels.ts - 第 99-109 行
useEffect(() => {
  if (!configReady || availableModels.length === 0) return;
  
  if (appModeChanged) {
    prevAppModeRef.current = appMode;
    userSelectedModelRef.current = false;  // ✅ 清除用户选择
    internalSelectBestModel(availableModels, false);  // ✅ 选择新模型
  }
}, [appMode, appModeChanged, availableModels, internalSelectBestModel, configReady]);

// 问题：
// 1. 这个 useEffect 依赖 availableModels
// 2. 如果 availableModels 还没加载完，可能导致选择错误
// 3. 如果 availableModels 是完整列表，需要过滤后再选择
```

**问题 3：useModeSwitch 的重复逻辑**
```typescript
// useModeSwitch.ts - 第 35-74 行
const handleModeSwitch = useCallback((mode: AppMode) => {
  setAppMode(mode);  // ✅ 更新 appMode
  
  // ❌ 手动选择模型（与 useModels 的自动选择冲突）
  if (mode === 'image-gen') {
    let imageModel = visibleModels.find(m => m.id.toLowerCase().includes('imagen'));
    if (imageModel) setCurrentModelId(imageModel.id);
  }
  // ...
}, [visibleModels, setCurrentModelId, currentModelId, setAppMode]);

// 问题：
// 1. useModeSwitch 手动选择模型
// 2. useModels 也会自动选择模型（通过 useEffect）
// 3. 两者可能冲突，导致不一致
```

---

## 🔍 详细流程分析

### 场景 1：用户从 chat 切换到 image-gen

**当前流程（有问题）：**
```
用户点击 "Image Generation" 按钮
    ↓
1. useModeSwitch: handleModeSwitch('image-gen')
    ↓
2. setAppMode('image-gen')  // ✅ 更新 appMode 状态
    ↓
3. useModeSwitch 手动选择模型:
   - 查找 Imagen 模型
   - 如果找到，调用 setCurrentModelId(imagen.id)
   - 设置 userSelectedModelRef.current = true  // ✅ 标记为用户选择
    ↓
4. useModels 检测到 appModeChanged:
   - prevAppModeRef.current !== appMode
   - 触发 useEffect（第 99-109 行）
    ↓
5. useModels 清除用户选择标志:
   - userSelectedModelRef.current = false  // ❌ 清除了步骤 3 的标记
    ↓
6. useModels 调用 internalSelectBestModel:
   - 过滤模型：filterModelsByAppMode(availableModels, 'image-gen')
   - 选择第一个可用模型
   - 可能与步骤 3 选择的模型不同  // ❌ 冲突
    ↓
7. visibleModels 自动更新（useMemo）:
   - 根据新的 appMode 过滤
    ↓
8. Header 重新渲染:
   - 显示新的模型列表
   - 高亮当前选择的模型（可能不是步骤 3 选择的）
```

**问题总结：**
- useModeSwitch 和 useModels 都在尝试选择模型
- useModels 会清除 useModeSwitch 设置的用户选择标志
- 最终选择的模型可能不是用户期望的

---

## ✅ 优化方案

### 方案 A：移除 useModeSwitch 的模型选择逻辑（推荐）

**优点：**
- 单一职责：useModels 负责所有模型选择逻辑
- 无冲突：不会有两个地方同时选择模型
- 简单清晰：模型选择逻辑集中在一处

**实现：**
```typescript
// useModeSwitch.ts - 简化版本
export const useModeSwitch = ({
  setAppMode
}: UseModeSwitchProps): UseModeSwitchReturn => {
  const handleModeSwitch = useCallback((mode: AppMode) => {
    setAppMode(mode);  // ✅ 只更新 appMode，不选择模型
    // ✅ useModels 会自动处理模型选择
  }, [setAppMode]);

  return { handleModeSwitch };
};

// useModels.ts - 增强过滤逻辑
const internalSelectBestModel = useCallback((models: ModelConfig[], forceReset: boolean) => {
  // ...
  
  // ✅ 根据 appMode 优先选择特定模型
  const modeFiltered = filterModelsByAppMode(models, appMode);
  const visible = modeFiltered.filter(m => !hiddenModelIds.includes(m.id));
  
  if (visible.length === 0) {
    setCurrentModelId("");
    return;
  }
  
  // ✅ 根据模式智能选择第一个模型
  let preferredModel = visible[0];
  
  if (appMode === 'image-gen') {
    // 优先选择 Imagen
    preferredModel = visible.find(m => m.id.toLowerCase().includes('imagen')) || visible[0];
  } else if (appMode === 'video-gen') {
    // 优先选择 Veo
    preferredModel = visible.find(m => m.id.includes('veo')) || visible[0];
  } else if (appMode === 'image-chat-edit' || appMode === 'image-mask-edit') {
    // 优先选择 Vision 模型
    preferredModel = visible.find(m => m.capabilities.vision && !m.id.includes('imagen')) || visible[0];
  }
  
  setCurrentModelId(preferredModel.id);
}, [hiddenModelIds, appMode]);
```

### 方案 B：保留 useModeSwitch，但延迟 useModels 的执行

**优点：**
- 保留 useModeSwitch 的灵活性
- 用户可以在切换模式时手动选择模型

**实现：**
```typescript
// useModels.ts - 添加延迟机制
useEffect(() => {
  if (!configReady || availableModels.length === 0) return;
  
  if (appModeChanged) {
    prevAppModeRef.current = appMode;
    
    // ✅ 延迟执行，给 useModeSwitch 时间选择模型
    setTimeout(() => {
      // ✅ 只有在用户没有手动选择时才自动选择
      if (!userSelectedModelRef.current) {
        userSelectedModelRef.current = false;
        internalSelectBestModel(availableModels, false);
      }
    }, 100);  // 延迟 100ms
  }
}, [appMode, appModeChanged, availableModels, internalSelectBestModel, configReady]);
```

**问题：**
- 使用 setTimeout 不可靠
- 可能导致 UI 闪烁

### 方案 C：使用事件总线（最灵活）

**优点：**
- 解耦：useModeSwitch 和 useModels 完全解耦
- 灵活：可以在任何地方触发模型选择

**实现：**
```typescript
// eventBus.ts
export class EventBus {
  private listeners: Map<string, Function[]> = new Map();
  
  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
  }
  
  emit(event: string, data: any) {
    const callbacks = this.listeners.get(event) || [];
    callbacks.forEach(cb => cb(data));
  }
  
  off(event: string, callback: Function) {
    const callbacks = this.listeners.get(event) || [];
    const index = callbacks.indexOf(callback);
    if (index !== -1) {
      callbacks.splice(index, 1);
    }
  }
}

export const eventBus = new EventBus();

// useModeSwitch.ts
const handleModeSwitch = useCallback((mode: AppMode) => {
  setAppMode(mode);
  
  // ✅ 发送事件，请求选择特定模型
  if (mode === 'image-gen') {
    const imageModel = visibleModels.find(m => m.id.toLowerCase().includes('imagen'));
    if (imageModel) {
      eventBus.emit('request-model-select', { modelId: imageModel.id, mode });
    }
  }
}, [visibleModels, setAppMode]);

// useModels.ts
useEffect(() => {
  const handleRequestModelSelect = ({ modelId, mode }: { modelId: string, mode: AppMode }) => {
    if (appMode === mode) {
      setCurrentModelId(modelId);
      userSelectedModelRef.current = true;
    }
  };
  
  eventBus.on('request-model-select', handleRequestModelSelect);
  
  return () => {
    eventBus.off('request-model-select', handleRequestModelSelect);
  };
}, [appMode, setCurrentModelId]);
```

**问题：**
- 增加复杂度
- 不是 React 的推荐模式

---

## 🎯 推荐实施方案

### 最终方案：方案 A + 优化

**实施步骤：**

1. **简化 useModeSwitch.ts**
   - 移除所有模型选择逻辑
   - 只负责更新 `appMode`

2. **增强 useModels.ts 的智能选择**
   - 在 `internalSelectBestModel` 中根据 `appMode` 优先选择特定模型
   - 保留用户选择的智能逻辑

3. **确保 filterModelsByAppMode 的准确性**
   - 所有模式的过滤规则清晰明确
   - 不会出现空列表的情况

4. **添加调试日志（开发环境）**
   - 记录模型选择的完整流程
   - 便于排查问题

**代码实现：**

```typescript
// Step 1: 简化 useModeSwitch.ts
export const useModeSwitch = ({
  setAppMode
}: UseModeSwitchProps): UseModeSwitchReturn => {
  const handleModeSwitch = useCallback((mode: AppMode) => {
    console.log(`[useModeSwitch] Switching to mode: ${mode}`);
    setAppMode(mode);  // ✅ 只更新 appMode
  }, [setAppMode]);

  return { handleModeSwitch };
};

// Step 2: 增强 useModels.ts
const internalSelectBestModel = useCallback((models: ModelConfig[], forceReset: boolean) => {
  if (!models || models.length === 0) {
    console.warn('[useModels] No models available');
    setCurrentModelId("");
    return;
  }
  
  // ✅ 第一步：根据 appMode 过滤模型
  const modeFiltered = filterModelsByAppMode(models, appMode);
  console.log(`[useModels] Mode filtered models (${appMode}):`, modeFiltered.length);
  
  // ✅ 第二步：排除隐藏模型
  const visible = modeFiltered.filter(m => !hiddenModelIds.includes(m.id));
  console.log(`[useModels] Visible models:`, visible.length);
  
  if (visible.length === 0) {
    console.warn(`[useModels] No visible models for mode: ${appMode}`);
    setCurrentModelId("");
    return;
  }
  
  // ✅ 第三步：智能选择模型
  let preferredModel = visible[0];
  
  switch (appMode) {
    case 'image-gen':
      preferredModel = visible.find(m => m.id.toLowerCase().includes('imagen')) ||
                       visible.find(m => m.id.includes('gemini-2') && m.id.includes('flash-image')) ||
                       visible[0];
      break;
    case 'video-gen':
      preferredModel = visible.find(m => m.id.includes('veo')) || visible[0];
      break;
    case 'audio-gen':
      preferredModel = visible.find(m => m.id.includes('tts')) || visible[0];
      break;
    case 'image-chat-edit':
    case 'image-mask-edit':
    case 'image-inpainting':
    case 'image-background-edit':
    case 'image-recontext':
      preferredModel = visible.find(m => m.capabilities.vision && !m.id.includes('imagen')) ||
                       visible.find(m => m.capabilities.vision) ||
                       visible[0];
      break;
    case 'pdf-extract':
      preferredModel = visible.find(m => m.capabilities.reasoning) ||
                       visible.find(m => m.capabilities.vision) ||
                       visible[0];
      break;
    case 'deep-research':
      preferredModel = visible.find(m => m.capabilities.search || m.capabilities.reasoning) || visible[0];
      break;
    default:
      preferredModel = visible[0];
  }
  
  console.log(`[useModels] Selected model:`, preferredModel.id);
  
  setCurrentModelId(prev => {
    // ✅ 保留用户选择逻辑
    if (!forceReset && !providerChanged && prev && userSelectedModelRef.current) {
      const isPrevModelVisible = visible.find(m => m.id === prev);
      if (isPrevModelVisible) {
        console.log(`[useModels] Keeping user selected model:`, prev);
        return prev;
      }
      userSelectedModelRef.current = false;
    }
    
    if (forceReset || providerChanged) {
      userSelectedModelRef.current = false;
    }
    
    return preferredModel.id;
  });
}, [hiddenModelIds, providerChanged, appMode]);

// Step 3: 确保模式切换时的正确执行
useEffect(() => {
  if (!configReady || availableModels.length === 0) return;
  
  if (appModeChanged) {
    console.log(`[useModels] appMode changed to: ${appMode}`);
    prevAppModeRef.current = appMode;
    userSelectedModelRef.current = false;  // ✅ 清除用户选择标志
    internalSelectBestModel(availableModels, false);
  }
}, [appMode, appModeChanged, availableModels, internalSelectBestModel, configReady]);
```

---

## 🔍 测试场景

### 测试 1：从 chat 切换到 image-gen
```
前置条件：
- 当前模式：chat
- 当前模型：gemini-2.5-flash
- 可用模型：gemini-2.5-flash, gemini-2.5-pro, imagen-3.0

操作：
1. 用户点击 "Image Generation" 按钮

预期结果：
- appMode 更新为 'image-gen'
- 模型列表过滤为：imagen-3.0（专用图像生成模型）
- 自动选择 imagen-3.0
- Header 显示 imagen-3.0
- 无 API 调用
- 延迟 < 1ms
```

### 测试 2：从 image-gen 切换到 video-gen
```
前置条件：
- 当前模式：image-gen
- 当前模型：imagen-3.0
- 可用模型：imagen-3.0, veo-2.0

操作：
1. 用户点击 "Video Generation" 按钮

预期结果：
- appMode 更新为 'video-gen'
- 模型列表过滤为：veo-2.0
- 自动选择 veo-2.0
- Header 显示 veo-2.0
- 无 API 调用
- 延迟 < 1ms
```

### 测试 3：用户手动选择模型后切换模式
```
前置条件：
- 当前模式：chat
- 用户手动选择：gemini-2.5-pro
- 可用模型：gemini-2.5-flash, gemini-2.5-pro, imagen-3.0

操作：
1. 用户切换到 image-gen 模式

预期结果：
- appMode 更新为 'image-gen'
- 检查 gemini-2.5-pro 是否在 image-gen 模式下可用
- 如果可用，保留 gemini-2.5-pro
- 如果不可用，自动选择 imagen-3.0
- 用户选择标志清除
```

### 测试 4：Provider 切换
```
前置条件：
- 当前 Provider：Google
- 当前模式：chat
- 当前模型：gemini-2.5-flash

操作：
1. 用户切换 Provider 到 OpenAI

预期结果：
- 调用 /api/models/openai（API 调用）
- 获取 OpenAI 模型列表
- 缓存到 IndexedDB
- 根据 chat 模式过滤
- 自动选择第一个模型（gpt-4o）
- Header 显示 gpt-4o
```

---

## 📊 性能监控

### 关键指标

1. **模式切换延迟**
   - 目标：< 1ms
   - 测量：`performance.now()` 在 setAppMode 前后

2. **模型过滤时间**
   - 目标：< 0.5ms
   - 测量：`filterModelsByAppMode` 执行时间

3. **API 调用次数**
   - 目标：只在 Provider 切换时调用
   - 测量：Network 面板监控

4. **内存占用**
   - 目标：< 50MB（模型列表缓存）
   - 测量：Chrome DevTools Memory Profiler

### 监控代码

```typescript
// 添加性能监控（开发环境）
if (process.env.NODE_ENV === 'development') {
  const startTime = performance.now();
  
  const filteredModels = filterModelsByAppMode(availableModels, appMode);
  
  const endTime = performance.now();
  console.log(`[Performance] Model filtering took ${(endTime - startTime).toFixed(2)}ms`);
  
  if (endTime - startTime > 1) {
    console.warn(`[Performance] Model filtering is slow: ${(endTime - startTime).toFixed(2)}ms`);
  }
}
```

---

## 🎯 总结

### 核心优化
1. ✅ 移除 useModeSwitch 的模型选择逻辑
2. ✅ 增强 useModels 的智能选择
3. ✅ 确保单一职责（useModels 负责所有模型选择）
4. ✅ 添加详细的调试日志

### 性能提升
- 模式切换延迟：< 1ms
- 无冲突：单一选择逻辑
- 可预测：明确的选择规则

### 可维护性
- 代码集中：所有模型选择逻辑在 useModels
- 易于测试：明确的输入输出
- 易于调试：详细的日志记录

---

**分析完成时间：** 2026-01-15  
**推荐实施：** 方案 A + 优化
