# 掩码预览模型硬编码修复报告

## 修复日期
2025-12-20

## 问题描述

用户反馈：掩码预览功能使用了硬编码的模型 `gemini-2.0-flash-exp`，而不是用户在界面上选择的模型。

错误日志显示：
```
virtual-tryon.ts:91 [VirtualTryOn] Segmenting clothing: target=upper body clothing, model=gemini-2.0-flash-exp
```

## 根本原因

### 问题分析

1. **`segmentClothing` 函数有默认模型**：
```typescript
export async function segmentClothing(
    ai: GoogleGenAI,
    image: Attachment,
    targetClothing: string,
    modelId?: string  // 可选参数
): Promise<SegmentationResult[]> {
    const model = modelId || 'gemini-2.0-flash-exp';  // ❌ 硬编码默认值
    // ...
}
```

2. **`generateMaskPreview` 没有 `modelId` 参数**：
```typescript
export async function generateMaskPreview(
  imageBase64: string,
  targetClothing: string,
  apiKey: string
  // ❌ 缺少 modelId 参数
): Promise<string> {
    // ...
    const segments = await segmentClothing(ai, attachment, targetClothing);
    // ❌ 没有传递 modelId，使用默认值
}
```

3. **`VirtualTryOnView` 没有传递模型 ID**：
```typescript
const previewUrl = await generateMaskPreview(
    imageBase64,
    targetClothing,
    apiKey
    // ❌ 没有传递 activeModelConfig.id
);
```

### 为什么会出现这个问题？

- `generateMaskPreview` 函数设计时没有考虑模型选择
- 假设总是使用 `gemini-2.0-flash-exp` 模型
- 没有从 UI 层传递用户选择的模型 ID

---

## 解决方案

### 修改策略

1. 在 `generateMaskPreview` 函数中添加 `modelId` 参数
2. 将 `modelId` 传递给 `segmentClothing` 调用
3. 在 `VirtualTryOnView` 中传递当前选择的模型 ID

### 修改的文件

#### 1. `frontend/services/providers/google/media/virtual-tryon.ts` ✅

**修改 `generateMaskPreview` 函数签名**：
```typescript
export async function generateMaskPreview(
  imageBase64: string,
  targetClothing: string,
  apiKey: string,
  modelId?: string  // ✅ 添加 modelId 参数
): Promise<string> {
```

**传递 `modelId` 给 `segmentClothing`**：
```typescript
const segments = await segmentClothing(ai, attachment, targetClothing, modelId);
// ✅ 传递 modelId 参数
```

#### 2. `frontend/components/views/VirtualTryOnView.tsx` ✅

**传递当前选择的模型 ID**：
```typescript
const previewUrl = await generateMaskPreview(
    imageBase64,
    targetClothing,
    apiKey,
    activeModelConfig?.id  // ✅ 传递当前选择的模型 ID
);
```

---

## 数据流

### 修复后的模型选择流程

```
用户在界面选择模型
    ↓
activeModelConfig.id (如 "gemini-2.0-flash-thinking-exp-01-21")
    ↓
VirtualTryOnView.handleGenerateMaskPreview
    ↓
generateMaskPreview(imageBase64, targetClothing, apiKey, activeModelConfig.id)
    ↓
segmentClothing(ai, attachment, targetClothing, modelId)
    ↓
const model = modelId || 'gemini-2.0-flash-exp'
    ↓
使用用户选择的模型 ✅
    ↓
调用 Gemini API 进行服装分割
```

---

## 模型选择逻辑

| 场景 | modelId 参数 | 实际使用的模型 |
|------|-------------|---------------|
| **用户选择了模型** | `activeModelConfig.id` | 用户选择的模型 ✅ |
| **用户未选择模型** | `undefined` | `gemini-2.0-flash-exp`（默认） |
| **activeModelConfig 为空** | `undefined` | `gemini-2.0-flash-exp`（默认） |

---

## 与其他功能对比

| 功能 | 模型来源 | 说明 |
|------|---------|------|
| **Virtual Try-On（主流程）** | `options.modelId` | 从 Handler 传递 |
| **掩码预览（修复前）** | 硬编码 `gemini-2.0-flash-exp` | ❌ 不使用用户选择 |
| **掩码预览（修复后）** | `activeModelConfig.id` | ✅ 使用用户选择 |

---

## 测试建议

完成修复后需要测试：

### 测试场景 1：使用默认模型
- [ ] 不选择特定模型（使用默认模型）
- [ ] 上传图片并点击"显示掩码预览"
- [ ] 验证控制台日志显示 `model=gemini-2.0-flash-exp`

### 测试场景 2：选择 Thinking 模型
- [ ] 选择 `gemini-2.0-flash-thinking-exp-01-21` 模型
- [ ] 上传图片并点击"显示掩码预览"
- [ ] 验证控制台日志显示 `model=gemini-2.0-flash-thinking-exp-01-21`

### 测试场景 3：选择其他模型
- [ ] 选择 `gemini-1.5-pro` 或其他模型
- [ ] 上传图片并点击"显示掩码预览"
- [ ] 验证控制台日志显示正确的模型 ID

### 测试场景 4：模型切换
- [ ] 选择模型 A，生成掩码预览
- [ ] 切换到模型 B，再次生成掩码预览
- [ ] 验证两次使用的模型不同

---

## 控制台日志验证

修复后，控制台应该显示：
```
[VirtualTryOn] Segmenting clothing: target=upper body clothing, model=<用户选择的模型>
```

而不是：
```
[VirtualTryOn] Segmenting clothing: target=upper body clothing, model=gemini-2.0-flash-exp
```

---

## 总结

本次修复解决了掩码预览功能的模型硬编码问题：

1. ✅ **识别问题** - `generateMaskPreview` 没有 `modelId` 参数
2. ✅ **找到根源** - 没有从 UI 层传递用户选择的模型 ID
3. ✅ **实施修复** - 添加 `modelId` 参数并传递给 `segmentClothing`
4. ✅ **保持一致** - 与 `virtualTryOn` 主流程的模型选择逻辑保持一致

修复后，掩码预览功能将使用用户在界面上选择的模型，而不是硬编码的默认模型。
