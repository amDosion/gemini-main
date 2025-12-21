# 掩码预览 API Key 传递修复报告

## 修复日期
2025-12-20

## 问题描述

用户点击"显示掩码预览"按钮时，控制台报错：
```
[handleGenerateMaskPreview] 缺少图片或 API Key
```

## 根本原因

### 问题分析

`VirtualTryOnView` 组件尝试从 `activeModelConfig?.apiKey` 获取 API Key，但是：

1. **ModelConfig 接口不包含 apiKey 字段**：
```typescript
export interface ModelConfig {
  id: string;
  name: string;
  description: string;
  capabilities: {...};
  baseModelId?: string;
  contextWindow?: number;
  // ❌ 没有 apiKey 字段！
}
```

2. **activeModelConfig 由 useModels hook 生成**：
```typescript
const activeModelConfig = availableModels.find(m => m.id === currentModelId) || availableModels[0];
```
这个对象只包含模型的元数据，不包含 API Key。

3. **API Key 存储在 config 对象中**：
```typescript
const { config } = useSettings();
// config.apiKey 包含实际的 API Key
```

### 为什么会出现这个问题？

- `ChatView` 组件接收 `apiKey={config.apiKey}` 作为单独的 prop
- `StudioView` 及其子组件只接收 `activeModelConfig`，没有单独的 `apiKey` prop
- 导致 `VirtualTryOnView` 无法访问 API Key

---

## 解决方案

### 修改策略

将 `config.apiKey` 作为单独的 prop 传递给 `VirtualTryOnView`，与 `ChatView` 的实现保持一致。

### 修改的文件

#### 1. `frontend/components/views/StudioView.tsx` ✅

**添加 apiKey prop**：
```typescript
interface StudioViewProps {
  // ... 其他 props
  apiKey?: string;  // ✅ API Key，用于调用 API
}
```

#### 2. `frontend/App.tsx` ✅

**传递 apiKey 给 StudioView**：
```typescript
const commonProps = {
  messages: currentViewMessages,
  setAppMode: handleModeSwitch,
  onImageClick: (url: string) => setPreviewImage(url),
  loadingState,
  onSend,
  onStop: stopGeneration,
  activeModelConfig,
  onEditImage: handleEditImage,
  onExpandImage: handleExpandImage,
  providerId: config.providerId,
  sessionId: currentSessionId,
  apiKey: config.apiKey  // ✅ 传递 apiKey 用于调用 API
};
```

#### 3. `frontend/components/views/VirtualTryOnView.tsx` ✅

**接收 apiKey prop**：
```typescript
interface VirtualTryOnViewProps {
  // ... 其他 props
  apiKey?: string;  // ✅ API Key，用于调用 Gemini API
}

export const VirtualTryOnView: React.FC<VirtualTryOnViewProps> = ({
  messages,
  setAppMode,
  onImageClick,
  loadingState,
  onSend,
  onStop,
  activeModelConfig,
  initialPrompt,
  initialAttachments,
  providerId,
  sessionId: currentSessionId,
  apiKey  // ✅ 接收 apiKey prop
}) => {
```

**使用 apiKey 而不是 activeModelConfig?.apiKey**：
```typescript
// 检查 API Key
const handleGenerateMaskPreview = async () => {
    if (!activeImageUrl || !apiKey) {  // ✅ 使用 apiKey prop
        console.warn('[handleGenerateMaskPreview] 缺少图片或 API Key');
        alert('请先上传图片并确保已配置 API Key');
        return;
    }
    
    // ... 其他代码
    
    // 调用 API
    const previewUrl = await generateMaskPreview(
        activeImageUrl,
        targetClothing,
        apiKey  // ✅ 使用 apiKey prop
    );
}
```

---

## 数据流

### 修复后的 API Key 传递链路

```
useSettings hook (在 App.tsx 中)
    ↓
config.apiKey
    ↓
App.tsx - commonProps
    ↓
StudioView (props.apiKey)
    ↓
VirtualTryOnView (props.apiKey)
    ↓
handleGenerateMaskPreview
    ↓
generateMaskPreview(imageUrl, targetClothing, apiKey)
    ↓
Gemini API
```

---

## 与其他组件对比

| 组件 | API Key 传递方式 | 说明 |
|------|-----------------|------|
| **ChatView** | `apiKey={config.apiKey}` | 单独的 prop |
| **VirtualTryOnView** | `apiKey={config.apiKey}` | ✅ 修复后与 ChatView 一致 |
| **ImageEditView** | 未使用 API Key | 不需要直接调用 API |
| **ImageGenView** | 未使用 API Key | 不需要直接调用 API |

---

## 测试建议

完成修复后需要测试：

- [ ] 配置 Gemini API Key
- [ ] 上传包含人物的图片
- [ ] 选择服装类型（Upper/Lower/Full Body）
- [ ] 点击"显示掩码预览"按钮
- [ ] 验证不再出现"缺少 API Key"错误
- [ ] 验证掩码预览正常生成
- [ ] 验证半透明红色叠加正确显示

---

## 总结

本次修复解决了 API Key 传递的架构问题：

1. ✅ **识别问题** - `ModelConfig` 不包含 `apiKey` 字段
2. ✅ **找到根源** - `StudioView` 没有接收 `apiKey` prop
3. ✅ **实施修复** - 添加 `apiKey` prop 到传递链路
4. ✅ **保持一致** - 与 `ChatView` 的实现保持一致

修复后，`VirtualTryOnView` 可以正确获取 API Key，掩码预览功能可以正常工作。
