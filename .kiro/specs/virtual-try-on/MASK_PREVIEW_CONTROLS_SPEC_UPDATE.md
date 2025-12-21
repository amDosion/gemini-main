# 掩码预览参数调整功能 - Spec 更新总结

**日期**：2025-12-20  
**状态**：✅ Spec 文档已完成，等待实现

---

## 用户反馈

> "对于透明度和阈值，我们是不是应该利用滑块来进行，而不是原编码？这样才对吧？"

**分析**：用户的观察非常准确！硬编码的参数（`alpha = 0.7`, `threshold = 50`）确实缺乏灵活性，应该改为可动态调整的滑块控件。

---

## Spec 更新内容

### 1. Requirements.md ✅

**新增需求 3.7：掩码预览参数调整**

| 验收标准 | 说明 |
|---------|------|
| AC-3.7.1 | 提供透明度滑块控件（范围 0.3-1.0） |
| AC-3.7.2 | 提供阈值滑块控件（范围 10-200） |
| AC-3.7.3 | 调整透明度时实时更新预览 |
| AC-3.7.4 | 调整阈值时实时更新预览 |
| AC-3.7.5 | 显示当前参数值 |
| AC-3.7.6 | 使用防抖机制避免频繁调用 API |
| AC-3.7.7 | 保存用户的参数偏好设置 |

---

### 2. Design.md ✅

**新增正确性属性**

- **Property 9**：掩码预览参数动态调整
  - *For any* 透明度值 alpha ∈ [0.3, 1.0] 和阈值 threshold ∈ [10, 200]，调整参数后重新生成的掩码预览应反映新的参数设置
  - **Validates**: Requirements 3.7.3, 3.7.4

- **Property 10**：参数防抖优化
  - *For any* 连续的参数调整操作，系统应在用户停止调整后的 300ms 内只触发一次掩码重新生成
  - **Validates**: Requirements 3.7.6

---

### 3. 详细设计文档 ✅

**创建文件**：`MASK_PREVIEW_CONTROLS_DESIGN.md`

**包含内容**：
1. 当前问题分析（硬编码参数的缺陷）
2. UI 设计（控件位置、规格、视觉设计）
3. 状态管理（组件状态、参数持久化）
4. 防抖优化（useDebounce Hook、时序图）
5. 服务层修改（函数签名更新）
6. 组件层修改（handleGenerateMaskPreview 更新）
7. 参数说明与用户指导
8. 测试策略（单元测试、集成测试、手动测试）
9. 实现优先级（P0-P2）
10. 实现时间估算（总计 4.5 小时）

---

### 4. Tasks.md ✅

**新增任务 21：掩码预览参数调整功能**

| 子任务 | 说明 | 优先级 |
|--------|------|--------|
| 21.1 | 修改服务层函数签名 | P0 |
| 21.2 | 实现 UI 状态管理 | P0 |
| 21.3 | 添加滑块控件 | P0 |
| 21.4 | 实现防抖机制 | P1 |
| 21.5 | 更新掩码预览生成逻辑 | P0 |
| 21.6* | 编写属性测试（Property 9）| P2（可选）|
| 21.7* | 编写属性测试（Property 10）| P2（可选）|

---

## 核心改进点

### 1. 灵活性提升

**之前**：
```typescript
const alpha = 0.7;  // 硬编码
if (brightness > 50) {  // 硬编码
  // 叠加红色
}
```

**之后**：
```typescript
// 用户可通过滑块调整
const [maskAlpha, setMaskAlpha] = useState(0.7);
const [maskThreshold, setMaskThreshold] = useState(50);

// 传入动态参数
const previewUrl = await generateMaskPreview(
  imageBase64,
  targetClothing,
  apiKey,
  modelId,
  maskAlpha,      // ✅ 动态参数
  maskThreshold   // ✅ 动态参数
);
```

---

### 2. 用户体验改善

#### 控件设计

```
┌─────────────────────────────────┐
│ 掩码预览控制面板                 │
├─────────────────────────────────┤
│ [显示掩码]                       │
│                                 │
│ 透明度                          │
│ ▓▓▓▓▓▓▓░░░  70%                │
│                                 │
│ 阈值                            │
│ ▓▓▓░░░░░░░  50                 │
│                                 │
│ • 透明度：控制红色的明显程度     │
│ • 阈值：控制覆盖区域的精准度     │
└─────────────────────────────────┘
```

#### 参数范围

| 参数 | 范围 | 默认值 | 步长 | 说明 |
|------|------|--------|------|------|
| 透明度 | 0.3 - 1.0 | 0.7 | 0.05 | 控制红色叠加的不透明度 |
| 阈值 | 10 - 200 | 50 | 5 | 控制掩码覆盖的精准度 |

---

### 3. 性能优化

#### 防抖机制

```typescript
// 用户拖动滑块时，只在停止后 300ms 触发一次 API 调用
const debouncedAlpha = useDebounce(maskAlpha, 300);
const debouncedThreshold = useDebounce(maskThreshold, 300);

useEffect(() => {
  if (showMaskPreview && activeImageUrl && apiKey) {
    handleGenerateMaskPreview();
  }
}, [debouncedAlpha, debouncedThreshold]);
```

**效果**：
- 用户连续拖动 5 次 → 只调用 1 次 API
- 避免频繁调用 Gemini API（节省费用）
- 减少 UI 卡顿和预览闪烁

---

### 4. 参数持久化

```typescript
// 保存用户偏好到 localStorage
useEffect(() => {
  localStorage.setItem('maskPreviewAlpha', maskAlpha.toString());
  localStorage.setItem('maskPreviewThreshold', maskThreshold.toString());
}, [maskAlpha, maskThreshold]);

// 恢复用户偏好
useEffect(() => {
  const savedAlpha = localStorage.getItem('maskPreviewAlpha');
  const savedThreshold = localStorage.getItem('maskPreviewThreshold');
  
  if (savedAlpha) setMaskAlpha(Number(savedAlpha));
  if (savedThreshold) setMaskThreshold(Number(savedThreshold));
}, []);
```

**效果**：用户下次打开应用时，参数自动恢复到上次的设置。

---

## 实现计划

### 优先级

| 优先级 | 任务 | 预计时间 |
|--------|------|---------|
| P0 | 修改服务层函数签名 | 30 分钟 |
| P0 | 实现 UI 状态管理 | 1 小时 |
| P0 | 添加滑块控件 | 1 小时 |
| P0 | 更新掩码预览生成逻辑 | 30 分钟 |
| P1 | 实现防抖机制 | 30 分钟 |
| P1 | 参数持久化 | 30 分钟 |
| P2 | 测试和调试 | 1 小时 |
| **总计** | | **4.5 小时** |

### 实现顺序

1. ✅ **Phase 1**：修改服务层（`virtual-tryon.ts`）
   - 添加 `alpha` 和 `threshold` 参数
   - 使用传入的参数替换硬编码值

2. ✅ **Phase 2**：实现 UI 状态管理（`VirtualTryOnView.tsx`）
   - 添加 `maskAlpha` 和 `maskThreshold` 状态
   - 实现参数持久化

3. ✅ **Phase 3**：添加滑块控件
   - 创建透明度和阈值滑块
   - 显示当前参数值
   - 添加参数说明

4. ✅ **Phase 4**：实现防抖机制
   - 创建 `useDebounce` Hook
   - 应用防抖到参数变化

5. ✅ **Phase 5**：更新掩码预览生成逻辑
   - 修改 `handleGenerateMaskPreview()` 函数
   - 传入动态参数

6. ✅ **Phase 6**：测试和调试
   - 单元测试
   - 集成测试
   - 手动测试

---

## 预期效果

### 用户体验提升

1. ✅ **灵活性**：用户可以根据不同图片调整参数
2. ✅ **实时反馈**：拖动滑块时立即看到效果
3. ✅ **个性化**：记住用户的参数偏好
4. ✅ **性能优化**：防抖机制避免频繁调用 API

### 开发体验提升

1. ✅ **易于调试**：无需修改代码即可测试不同参数
2. ✅ **可维护性**：参数集中管理，易于扩展
3. ✅ **可测试性**：参数可通过 props 传入，便于测试

---

## 下一步

**Spec 文档已完成**，可以开始实现：

1. 从任务 21.1 开始（修改服务层函数签名）
2. 按照优先级顺序逐步实现
3. 每完成一个子任务，标记为完成
4. 最后进行完整的测试和验证

**预计完成时间**：4.5 小时

---

## 相关文档

- **需求文档**：`.kiro/specs/virtual-try-on/requirements.md`（需求 3.7）
- **设计文档**：`.kiro/specs/virtual-try-on/design.md`（Property 9, 10）
- **详细设计**：`.kiro/specs/virtual-try-on/MASK_PREVIEW_CONTROLS_DESIGN.md`
- **任务清单**：`.kiro/specs/virtual-try-on/tasks.md`（任务 21）

---

## 总结

用户的反馈非常有价值！将硬编码参数改为滑块控件是一个合理且必要的 UX 改进。通过这次 Spec 更新，我们：

1. ✅ 明确了需求（7 个验收标准）
2. ✅ 定义了正确性属性（Property 9, 10）
3. ✅ 完成了详细设计（UI、状态管理、防抖、测试）
4. ✅ 制定了实现计划（5 个子任务，4.5 小时）

现在可以开始实现了！🚀
