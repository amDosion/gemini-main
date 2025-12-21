# 掩码预览参数调整功能设计

## 概述

为了让用户能够根据不同图片和服装类型获得最佳的掩码预览效果，我们需要将硬编码的透明度（alpha）和阈值（threshold）参数改为可动态调整的滑块控件。

---

## 当前问题

### 硬编码参数

```typescript
// frontend/services/providers/google/media/virtual-tryon.ts
const alpha = 0.7;  // 硬编码透明度
const brightness = maskData.data[i];
if (brightness > 50) {  // 硬编码阈值
  // 叠加红色
}
```

### 问题分析

1. **缺乏灵活性**：不同图片的掩码质量可能不同，固定参数无法适应所有情况
2. **用户体验差**：用户无法根据实际效果调整预览，可能看不清或看得太明显
3. **调试困难**：开发者需要修改代码并重新编译才能测试不同参数

---

## 设计方案

### 1. UI 设计

#### 控件位置

将滑块控件放在画布右上角的"掩码预览控制面板"中，与"显示掩码预览"按钮一起。

```
┌─────────────────────────────────────────────────────────────┐
│                        画布区域                              │
│                                                              │
│  ┌──────────────────────────────────────────┐  ┌─────────┐ │
│  │                                          │  │ 掩码预览 │ │
│  │                                          │  │ 控制面板 │ │
│  │         图片显示区域                      │  │         │ │
│  │                                          │  │ [显示]  │ │
│  │                                          │  │         │ │
│  │                                          │  │ 透明度  │ │
│  │                                          │  │ ▓▓▓░░░  │ │
│  │                                          │  │ 70%     │ │
│  │                                          │  │         │ │
│  │                                          │  │ 阈值    │ │
│  │                                          │  │ ▓▓░░░░  │ │
│  │                                          │  │ 50      │ │
│  └──────────────────────────────────────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### 控件规格

| 控件 | 类型 | 范围 | 默认值 | 步长 | 说明 |
|------|------|------|--------|------|------|
| 透明度滑块 | Range | 0.3 - 1.0 | 0.7 | 0.05 | 控制红色叠加的不透明度 |
| 阈值滑块 | Range | 10 - 200 | 50 | 5 | 控制掩码覆盖的精准度 |

#### 视觉设计

```tsx
<div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-lg p-3 text-xs space-y-3">
  {/* 标题 */}
  <div className="flex items-center gap-2">
    <Layers size={12} className="text-rose-400" />
    <span className="font-medium text-slate-300">掩码预览</span>
  </div>
  
  {/* 显示/隐藏按钮 */}
  <button
    onClick={handleToggleMaskPreview}
    className="w-full px-3 py-2 rounded bg-slate-700 hover:bg-slate-600 text-slate-300"
  >
    {showMaskPreview ? '隐藏掩码' : '显示掩码'}
  </button>
  
  {/* 参数调整（只在显示掩码时显示）*/}
  {showMaskPreview && (
    <>
      {/* 透明度滑块 */}
      <div className="space-y-1">
        <div className="flex justify-between text-[10px] text-slate-400">
          <span>透明度</span>
          <span className="font-mono">{Math.round(maskAlpha * 100)}%</span>
        </div>
        <input
          type="range"
          min="0.3"
          max="1.0"
          step="0.05"
          value={maskAlpha}
          onChange={(e) => setMaskAlpha(Number(e.target.value))}
          className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer"
        />
      </div>
      
      {/* 阈值滑块 */}
      <div className="space-y-1">
        <div className="flex justify-between text-[10px] text-slate-400">
          <span>阈值</span>
          <span className="font-mono">{maskThreshold}</span>
        </div>
        <input
          type="range"
          min="10"
          max="200"
          step="5"
          value={maskThreshold}
          onChange={(e) => setMaskThreshold(Number(e.target.value))}
          className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer"
        />
      </div>
      
      {/* 提示文本 */}
      <div className="text-[10px] text-slate-500 leading-relaxed">
        <p>• 透明度：控制红色的明显程度</p>
        <p>• 阈值：控制覆盖区域的精准度</p>
      </div>
    </>
  )}
</div>
```

---

### 2. 状态管理

#### 组件状态

```typescript
// VirtualTryOnView.tsx

// 掩码预览状态
const [showMaskPreview, setShowMaskPreview] = useState(false);
const [maskPreviewUrl, setMaskPreviewUrl] = useState<string | null>(null);
const [isGeneratingMask, setIsGeneratingMask] = useState(false);

// 掩码参数状态（新增）
const [maskAlpha, setMaskAlpha] = useState(0.7);        // 透明度，默认 70%
const [maskThreshold, setMaskThreshold] = useState(50);  // 阈值，默认 50
```

#### 参数持久化

```typescript
// 使用 localStorage 保存用户偏好
useEffect(() => {
  const savedAlpha = localStorage.getItem('maskPreviewAlpha');
  const savedThreshold = localStorage.getItem('maskPreviewThreshold');
  
  if (savedAlpha) setMaskAlpha(Number(savedAlpha));
  if (savedThreshold) setMaskThreshold(Number(savedThreshold));
}, []);

useEffect(() => {
  localStorage.setItem('maskPreviewAlpha', maskAlpha.toString());
  localStorage.setItem('maskPreviewThreshold', maskThreshold.toString());
}, [maskAlpha, maskThreshold]);
```

---

### 3. 防抖优化

#### 问题

用户拖动滑块时，每次值变化都会触发掩码重新生成，导致：
1. 频繁调用 Gemini API（可能产生额外费用）
2. UI 卡顿（大量图像处理操作）
3. 用户体验差（预览闪烁）

#### 解决方案：使用防抖（Debounce）

```typescript
import { useCallback, useRef, useEffect } from 'react';

// 防抖 Hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

// 在组件中使用
const debouncedAlpha = useDebounce(maskAlpha, 300);      // 300ms 延迟
const debouncedThreshold = useDebounce(maskThreshold, 300);

// 只在防抖后的值变化时重新生成掩码
useEffect(() => {
  if (showMaskPreview && activeImageUrl && apiKey) {
    handleGenerateMaskPreview();
  }
}, [debouncedAlpha, debouncedThreshold]);
```

#### 防抖时序图

```
用户拖动滑块：
t=0ms    ─┬─ alpha=0.5
t=50ms   ─┼─ alpha=0.55
t=100ms  ─┼─ alpha=0.6
t=150ms  ─┼─ alpha=0.65
t=200ms  ─┼─ alpha=0.7  ← 用户停止拖动
t=500ms  ─┴─ 触发重新生成（300ms 后）

结果：只调用一次 API，而不是 5 次
```

---

### 4. 服务层修改

#### 修改 generateMaskPreview 函数签名

```typescript
// frontend/services/providers/google/media/virtual-tryon.ts

/**
 * 生成掩码预览（用于 UI 显示）
 * 返回半透明红色叠加的预览图
 * 
 * @param imageBase64 Base64 编码的原图
 * @param targetClothing 目标服装类型
 * @param apiKey Gemini API Key
 * @param modelId Gemini 模型 ID（可选）
 * @param alpha 透明度（0.3-1.0，默认 0.7）
 * @param threshold 阈值（10-200，默认 50）
 * @returns Base64 编码的掩码预览图
 */
export async function generateMaskPreview(
  imageBase64: string,
  targetClothing: string,
  apiKey: string,
  modelId?: string,
  alpha: number = 0.7,      // ✅ 新增参数
  threshold: number = 50    // ✅ 新增参数
): Promise<string> {
  try {
    console.log(`[generateMaskPreview] 参数: alpha=${alpha}, threshold=${threshold}`);
    
    // ... 前面的代码保持不变 ...
    
    // 在原图上绘制半透明红色（使用传入的参数）
    const imageData = ctx.getImageData(0, 0, img.width, img.height);
    for (let i = 0; i < maskData.data.length; i += 4) {
      const brightness = maskData.data[i];
      if (brightness > threshold) {  // ✅ 使用传入的阈值
        // ✅ 使用传入的透明度
        imageData.data[i] = imageData.data[i] * (1 - alpha) + 255 * alpha;     // R
        imageData.data[i + 1] = imageData.data[i + 1] * (1 - alpha);           // G
        imageData.data[i + 2] = imageData.data[i + 2] * (1 - alpha);           // B
      }
    }
    
    ctx.putImageData(imageData, 0, 0);
    
    // ... 后面的代码保持不变 ...
  } catch (error) {
    console.error('[generateMaskPreview] 错误:', error);
    throw error;
  }
}
```

---

### 5. 组件层修改

#### 修改 handleGenerateMaskPreview 函数

```typescript
// VirtualTryOnView.tsx

const handleGenerateMaskPreview = async () => {
  if (!activeImageUrl || !apiKey) {
    console.warn('[handleGenerateMaskPreview] 缺少图片或 API Key');
    alert('请先上传图片并确保已配置 API Key');
    return;
  }
  
  setIsGeneratingMask(true);
  try {
    // URL 转换逻辑（保持不变）
    let imageBase64: string;
    // ... URL 转换代码 ...
    
    // 调用掩码预览生成（传入参数）
    const { generateMaskPreview } = await import('../../services/providers/google/media/virtual-tryon');
    
    const targetClothingMap: Record<string, string> = {
      'upper': 'upper body clothing',
      'lower': 'lower body clothing',
      'full': 'full body clothing'
    };
    const targetClothing = targetClothingMap[currentTryOnTarget] || 'upper body clothing';
    
    console.log(`[handleGenerateMaskPreview] 生成掩码预览: ${targetClothing}, alpha=${maskAlpha}, threshold=${maskThreshold}`);
    
    // ✅ 传入动态参数
    const previewUrl = await generateMaskPreview(
      imageBase64,
      targetClothing,
      apiKey,
      activeModelConfig?.id,
      maskAlpha,      // ✅ 传入透明度
      maskThreshold   // ✅ 传入阈值
    );
    
    setMaskPreviewUrl(previewUrl);
    setShowMaskPreview(true);
    console.log('[handleGenerateMaskPreview] 掩码预览生成成功');
  } catch (error) {
    console.error('[handleGenerateMaskPreview] 生成失败:', error);
    alert(`掩码预览生成失败：${error instanceof Error ? error.message : '未知错误'}\n请检查图片是否包含目标服装`);
  } finally {
    setIsGeneratingMask(false);
  }
};
```

---

### 6. 参数说明与用户指导

#### 透明度（Alpha）

| 值 | 效果 | 适用场景 |
|----|------|---------|
| 0.3 | 非常淡的红色，几乎看不见 | 图片本身颜色较深，需要保留更多原图细节 |
| 0.5 | 淡红色，半透明 | 一般场景，平衡可见性和原图 |
| 0.7 | 明显的红色（默认） | 大多数场景，清晰标识替换区域 |
| 1.0 | 完全不透明的红色 | 需要非常明确地看到替换区域 |

#### 阈值（Threshold）

| 值 | 效果 | 适用场景 |
|----|------|---------|
| 10 | 覆盖范围最大，包含几乎所有掩码区域 | 掩码质量较差，需要宽松匹配 |
| 50 | 平衡覆盖（默认） | 大多数场景，精准度和覆盖度平衡 |
| 100 | 覆盖范围中等，只包含较亮的掩码区域 | 掩码质量好，需要精确匹配 |
| 200 | 覆盖范围最小，只包含最亮的掩码区域 | 掩码质量非常好，需要严格匹配 |

#### UI 提示文本

```tsx
<div className="text-[10px] text-slate-500 leading-relaxed space-y-1">
  <p className="font-medium text-slate-400">参数说明：</p>
  <p>• <span className="text-rose-400">透明度</span>：控制红色的明显程度</p>
  <p className="ml-3">- 值越大，红色越明显</p>
  <p className="ml-3">- 建议范围：50%-90%</p>
  <p>• <span className="text-rose-400">阈值</span>：控制覆盖区域的精准度</p>
  <p className="ml-3">- 值越小，覆盖范围越大</p>
  <p className="ml-3">- 建议范围：30-100</p>
</div>
```

---

### 7. 测试策略

#### 单元测试

```typescript
describe('generateMaskPreview', () => {
  it('应该使用传入的透明度参数', async () => {
    const result = await generateMaskPreview(
      testImage,
      'upper body clothing',
      apiKey,
      undefined,
      0.5,  // alpha
      50    // threshold
    );
    
    // 验证生成的预览图使用了正确的透明度
    expect(result).toBeDefined();
  });
  
  it('应该使用传入的阈值参数', async () => {
    const result = await generateMaskPreview(
      testImage,
      'upper body clothing',
      apiKey,
      undefined,
      0.7,
      100  // 更高的阈值
    );
    
    // 验证生成的预览图使用了正确的阈值
    expect(result).toBeDefined();
  });
});
```

#### 集成测试

```typescript
describe('VirtualTryOnView - 掩码预览参数调整', () => {
  it('应该在滑块变化时更新参数', () => {
    const { getByRole } = render(<VirtualTryOnView {...props} />);
    
    const alphaSlider = getByRole('slider', { name: /透明度/ });
    fireEvent.change(alphaSlider, { target: { value: '0.8' } });
    
    expect(alphaSlider).toHaveValue('0.8');
  });
  
  it('应该在参数变化后重新生成掩码预览', async () => {
    const { getByRole } = render(<VirtualTryOnView {...props} />);
    
    const alphaSlider = getByRole('slider', { name: /透明度/ });
    fireEvent.change(alphaSlider, { target: { value: '0.9' } });
    
    // 等待防抖延迟
    await waitFor(() => {
      expect(generateMaskPreview).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(String),
        expect.any(String),
        expect.any(String),
        0.9,  // 新的透明度
        expect.any(Number)
      );
    }, { timeout: 500 });
  });
});
```

#### 手动测试清单

- [ ] 拖动透明度滑块，观察红色叠加的明显程度变化
- [ ] 拖动阈值滑块，观察覆盖区域的大小变化
- [ ] 快速连续拖动滑块，验证防抖机制（应该只触发一次重新生成）
- [ ] 关闭掩码预览后重新打开，验证参数是否保存
- [ ] 刷新页面，验证参数是否从 localStorage 恢复
- [ ] 测试极端值（alpha=0.3, threshold=10 和 alpha=1.0, threshold=200）

---

### 8. 实现优先级

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P0 | 修改 `generateMaskPreview` 函数签名 | 添加 alpha 和 threshold 参数 |
| P0 | 在 `VirtualTryOnView` 中添加状态管理 | maskAlpha, maskThreshold |
| P0 | 添加滑块控件 | 透明度和阈值滑块 |
| P1 | 实现防抖机制 | 避免频繁调用 API |
| P1 | 参数持久化 | 使用 localStorage 保存用户偏好 |
| P2 | 添加参数说明 | 帮助用户理解参数含义 |
| P2 | 编写测试 | 单元测试和集成测试 |

---

### 9. 实现时间估算

| 任务 | 预计时间 |
|------|---------|
| 修改服务层函数 | 30 分钟 |
| 修改组件层逻辑 | 1 小时 |
| 实现 UI 控件 | 1 小时 |
| 实现防抖机制 | 30 分钟 |
| 参数持久化 | 30 分钟 |
| 测试和调试 | 1 小时 |
| **总计** | **4.5 小时** |

---

## 总结

通过将硬编码的透明度和阈值参数改为可动态调整的滑块控件，我们可以：

1. ✅ **提高灵活性**：用户可以根据不同图片调整参数
2. ✅ **改善用户体验**：实时预览参数变化效果
3. ✅ **简化调试**：开发者无需修改代码即可测试不同参数
4. ✅ **保存用户偏好**：记住用户的参数设置
5. ✅ **优化性能**：使用防抖机制避免频繁调用 API

这是一个合理且必要的 UX 改进，应该优先实现。
