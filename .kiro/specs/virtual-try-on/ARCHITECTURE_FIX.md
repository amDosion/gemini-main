# Virtual Try-On 架构修复说明

## 问题分析

### 发现的问题

1. **控件位置错误**
   - `Upscale` 和掩码预览控件在 `VirtualTryOnView.tsx` 的画布右上角
   - 应该在 `VirtualTryOnControls.tsx` 中，与其他模式保持一致

2. **状态管理混乱**
   - `enableUpscale`, `upscaleFactor`, `addWatermark`, `showMaskPreview` 等状态在 `VirtualTryOnView` 内部管理
   - 应该通过 `useControlsState` Hook 管理，然后通过 props 传递

3. **数据流不一致**
   - 其他模式（`ImageEdit`, `ImageOutpaint`）的控件都在 `Controls` 组件中
   - `Virtual Try-On` 的控件分散在 `View` 组件中

### 正确的架构模式

参考 `ImageEditControls` 和 `ImageOutpaintControls`：

```
useControlsState (Hook)
    ↓
ModeControlsCoordinator
    ↓
VirtualTryOnControls (所有控件)
    ↓
ChatOptions
    ↓
useChat
    ↓
Handler
    ↓
后端 API
```

---

## 已完成的修复

### 1. 更新类型定义

**文件**: `frontend/controls/types.ts`

```typescript
// 扩展 VirtualTryOnControlsProps
export interface VirtualTryOnControlsProps {
  tryOnTarget: string;
  setTryOnTarget: (v: string) => void;
  enableUpscale: boolean;
  setEnableUpscale: (v: boolean) => void;
  upscaleFactor: 2 | 4;
  setUpscaleFactor: (v: 2 | 4) => void;
  addWatermark: boolean;
  setAddWatermark: (v: boolean) => void;
  showMaskPreview: boolean;
  setShowMaskPreview: (v: boolean) => void;
}

// 扩展 ControlsState
export interface ControlsState {
  // ... 其他字段 ...
  
  // Virtual Try-On
  tryOnTarget: string;
  setTryOnTarget: (v: string) => void;
  enableUpscale: boolean;
  setEnableUpscale: (v: boolean) => void;
  upscaleFactor: 2 | 4;
  setUpscaleFactor: (v: 2 | 4) => void;
  addWatermark: boolean;
  setAddWatermark: (v: boolean) => void;
  showMaskPreview: boolean;
  setShowMaskPreview: (v: boolean) => void;
}
```

### 2. 更新 useControlsState Hook

**文件**: `frontend/hooks/useControlsState.ts`

```typescript
// 添加 Virtual Try-On 状态
const [tryOnTarget, setTryOnTarget] = useState('upper');
const [enableUpscale, setEnableUpscale] = useState(false);
const [upscaleFactor, setUpscaleFactor] = useState<2 | 4>(2);
const [addWatermark, setAddWatermark] = useState(false);
const [showMaskPreview, setShowMaskPreview] = useState(false);

// 返回这些状态
return {
  // ... 其他状态 ...
  tryOnTarget, setTryOnTarget,
  enableUpscale, setEnableUpscale,
  upscaleFactor, setUpscaleFactor,
  addWatermark, setAddWatermark,
  showMaskPreview, setShowMaskPreview,
};
```

### 3. 重写 VirtualTryOnControls 组件

**文件**: `frontend/controls/modes/VirtualTryOnControls.tsx`

**新增功能**:
- ✅ 服装类型选择（Upper/Lower/Full Body）
- ✅ Upscale 控件（启用开关、2x/4x 选择、水印选项）
- ✅ 掩码预览按钮

**UI 设计**:
- 使用下拉菜单模式，与其他 Controls 保持一致
- Upscale 菜单包含：启用开关、放大倍数选择、水印选项
- 掩码预览按钮：Eye/EyeOff 图标，点击切换

---

## 待完成的工作

### 1. 更新 VirtualTryOnView.tsx

**需要修改**:
- ❌ 移除内部状态管理（`enableUpscale`, `upscaleFactor`, `addWatermark`, `showMaskPreview`）
- ❌ 移除画布右上角的 Upscale 和掩码预览控件
- ❌ 通过 props 接收这些状态
- ❌ 更新 `VirtualTryOnViewProps` 接口

**修改示例**:
```typescript
interface VirtualTryOnViewProps {
  // ... 现有 props ...
  
  // 新增 props（从 Controls 传递）
  enableUpscale: boolean;
  upscaleFactor: 2 | 4;
  addWatermark: boolean;
  showMaskPreview: boolean;
  onGenerateMaskPreview: () => void;  // 掩码预览生成函数
}

// 移除内部状态
// const [enableUpscale, setEnableUpscale] = useState(false);  // ❌ 删除
// const [upscaleFactor, setUpscaleFactor] = useState<2 | 4>(2);  // ❌ 删除
// ...

// 移除画布右上角的控件
// <div className="absolute top-4 right-4 z-10">  // ❌ 删除整个区块
```

### 2. 更新 StudioView.tsx

**需要修改**:
- ❌ 将 `useControlsState` 的状态传递给 `VirtualTryOnView`

**修改示例**:
```typescript
case 'virtual-try-on':
  return (
    <VirtualTryOnView 
      {...props}
      enableUpscale={controlsState.enableUpscale}
      upscaleFactor={controlsState.upscaleFactor}
      addWatermark={controlsState.addWatermark}
      showMaskPreview={controlsState.showMaskPreview}
      onGenerateMaskPreview={handleGenerateMaskPreview}
    />
  );
```

### 3. 更新 ModeControlsCoordinator

**需要修改**:
- ❌ 确保 `VirtualTryOnControls` 接收所有必要的 props

**修改示例**:
```typescript
case 'virtual-try-on':
  return (
    <VirtualTryOnControls
      tryOnTarget={tryOnTarget}
      setTryOnTarget={setTryOnTarget}
      enableUpscale={enableUpscale}
      setEnableUpscale={setEnableUpscale}
      upscaleFactor={upscaleFactor}
      setUpscaleFactor={setUpscaleFactor}
      addWatermark={addWatermark}
      setAddWatermark={setAddWatermark}
      showMaskPreview={showMaskPreview}
      setShowMaskPreview={setShowMaskPreview}
    />
  );
```

### 4. 更新掩码预览逻辑

**问题**:
- 掩码预览生成需要 `activeImageUrl` 和 `apiKey`
- 这些数据在 `VirtualTryOnView` 中，但按钮在 `VirtualTryOnControls` 中

**解决方案**:
- 在 `VirtualTryOnView` 中定义 `handleGenerateMaskPreview` 函数
- 通过 props 传递给 `VirtualTryOnControls`
- 或者：将掩码预览按钮保留在 `VirtualTryOnView` 中（作为特殊情况）

---

## 数据流对比

### 修复前（❌ 错误）

```
VirtualTryOnView (内部状态)
    ↓
handleSend
    ↓
ChatOptions
    ↓
Handler
```

**问题**: 状态分散，控件位置不一致

### 修复后（✅ 正确）

```
useControlsState
    ↓
VirtualTryOnControls (所有控件)
    ↓
VirtualTryOnView (通过 props 接收)
    ↓
handleSend
    ↓
ChatOptions
    ↓
Handler
```

**优点**: 
- 状态集中管理
- 控件位置一致
- 数据流清晰
- 与其他模式保持一致

---

## 测试清单

完成修复后需要测试：

- [ ] 服装类型选择是否正常工作
- [ ] Upscale 启用/禁用是否正常
- [ ] 2x/4x 放大倍数选择是否正常
- [ ] 水印选项是否正常
- [ ] 掩码预览按钮是否正常
- [ ] 数据是否正确传递到 Handler
- [ ] Handler 是否正确调用后端 API
- [ ] 完整的试衣流程是否正常

---

## 参考文件

- `frontend/controls/modes/ImageEditControls.tsx` - 参考架构模式
- `frontend/controls/modes/ImageOutpaintControls.tsx` - 参考架构模式
- `frontend/controls/types.ts` - 类型定义
- `frontend/hooks/useControlsState.ts` - 状态管理
- `frontend/components/views/VirtualTryOnView.tsx` - 视图组件
- `frontend/controls/modes/VirtualTryOnControls.tsx` - 控件组件

---

## 总结

用户发现的问题完全正确：

1. ✅ 参数应该在 `VirtualTryOnControls.tsx` 中
2. ✅ 掩码预览等控件应该在 Controls 中，而不是分散在 View 中
3. ✅ 需要遵循与其他模式一致的架构模式

已完成的修复：
- ✅ 更新类型定义
- ✅ 更新 useControlsState Hook
- ✅ 重写 VirtualTryOnControls 组件

待完成的工作：
- ❌ 更新 VirtualTryOnView.tsx（移除内部状态和控件）
- ❌ 更新 StudioView.tsx（传递 props）
- ❌ 更新 ModeControlsCoordinator（传递 props）
- ❌ 处理掩码预览的特殊逻辑

这是一个重要的架构修复，确保代码的一致性和可维护性。
