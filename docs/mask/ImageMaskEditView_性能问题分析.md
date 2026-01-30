# ImageMaskEditView 性能问题分析报告

日期：2026-01-30

## 范围
- 文件：`frontend/components/views/ImageMaskEditView.tsx`
- 关注：Mask 选择/画笔编辑、mask 生成与预览、侧边历史渲染

## 摘要
当前实现存在多处与图像尺寸线性相关的重计算与高频重绘；在大图（2K/4K）与连续画笔操作下，会出现明显卡顿、主线程占用升高、内存抖动。核心瓶颈集中在“全图像素遍历 + base64 生成 + 高频刷新”三类路径。

## 关键问题一览（按严重度）

| 严重度 | 位置（行号） | 触发条件 | 主要影响 |
|---|---|---|---|
| P0 | 1062–1158 / 1225–1233 | 选区变化、反转切换、画笔结束触发 mask 合成 | 全图像素遍历 + toDataURL，CPU/内存飙升，UI 卡顿 |
| P0 | 851–869 / 1005–1015 | 画笔移动时每次 mousemove | 每次全画布重绘，GPU/CPU 压力大 |
| P0 | 871–885 | 笔画结束时 | 全图扫描 alpha 通道 + toDataURL，耗时随图像大小线性增长 |
| P1 | 380–405 / 824–827 | mousemove 更新光标 | React 高频重渲染，影响交互帧率 |
| P1 | 797 / 1147–1149 | mask 预览 | base64 大字符串入 state，内存与 GC 压力 |
| P2 | 904–909 / 993–1010 / 1164–1167 | 鼠标移动中反复读取布局 | 频繁触发 layout read，可能造成 layout thrash |
| P2 | 1273–1281 | messages 更新 | 长历史 + smooth scroll 频繁触发导致滚动抖动 |

## 详细问题与证据

### 1) 全图像素遍历 + toDataURL（P0）
**位置**：`frontend/components/views/ImageMaskEditView.tsx:1062–1158`、`1225–1233`

**现象**：
- `generateMaskFromSelections` 每次都会 `document.createElement('canvas')` 新建画布，并对整张图 `getImageData` + 遍历像素后 `putImageData`。
- 最后无条件 `toDataURL('image/png')` 写入 state。
- `useEffect` 依赖 `selectionRects`/`maskCanvasUrl`/`isMaskInverted`，当画笔结束后触发 `maskCanvasUrl` 更新时，会再次触发全量合成。

**影响**：
- 复杂度随像素数线性增长，2K/4K 图像会明显卡顿。
- `toDataURL` 生成 base64 字符串极耗时、内存占用大、GC 压力高。

**建议**：
- 复用合成 canvas，避免每次创建新 canvas。
- 合并画笔 mask 时用 `ctx.drawImage` + `globalCompositeOperation` 取代逐像素遍历。
- 仅在“用户结束编辑/点击提交/导出”时生成最终 mask；实时预览使用低分辨率或 throttled 版本。
- `toDataURL` 改 `toBlob` + `URL.createObjectURL`（或直接保留 canvas/`ImageBitmap`）。

### 2) 画笔移动时全画布重绘（P0）
**位置**：`frontend/components/views/ImageMaskEditView.tsx:851–869`、`1005–1015`

**现象**：
- `handleBrushMove` 每个 mousemove 都调用 `updateDisplayCanvas`。
- `updateDisplayCanvas` 会 `clearRect` + `drawImage` 复制整张 mask canvas。

**影响**：
- 高速移动时触发大量全画布重绘，主线程占用高，导致明显掉帧。

**建议**：
- 使用 `requestAnimationFrame` 将多次 mousemove 合并为每帧一次绘制。
- 使用“脏矩形（dirty rect）”仅更新发生变化的区域。
- 可考虑将绘制逻辑移到 `OffscreenCanvas` + worker。

### 3) 笔画结束时全图扫描判断是否有内容（P0）
**位置**：`frontend/components/views/ImageMaskEditView.tsx:871–885`

**现象**：
- `updateMaskCanvasUrl` 会 `getImageData` 全图扫描 alpha 通道判断是否有内容。
- 随后 `toDataURL` 生成大字符串。

**影响**：
- 每次笔画结束都会产生 O(W×H) 扫描，卡顿明显。

**建议**：
- 用 ref 记录“是否画过内容”（例如在画笔开始时标记），避免全图扫描。
- 仅在“需要导出/发送”时生成 URL/Blob。

### 4) mousemove 导致 React 高频重渲染（P1）
**位置**：`frontend/components/views/ImageMaskEditView.tsx:380–405`、`824–827`

**现象**：
- `onMouseMove` 每次更新 `brushCursorPos` state，触发组件树重渲染。

**影响**：
- 绘制 + 渲染叠加，进一步降低帧率。

**建议**：
- 光标位置用 `useRef` + 直接 DOM 更新（`style.transform`）代替 state。
- 将光标层拆成独立组件并 `memo`，只更新光标 DOM。

### 5) base64 URL 存入 state（P1）
**位置**：`frontend/components/views/ImageMaskEditView.tsx:797`、`1147–1149`

**现象**：
- `maskCanvasUrl`、`maskPreviewUrl` 均为 base64 串存入 React state。

**影响**：
- 大字符串内存占用高、diff/渲染成本高、GC 压力大。

**建议**：
- 改用 `Blob` + `URL.createObjectURL`。
- 或仅在需要预览时生成 URL，并在组件卸载时 `revokeObjectURL`。

### 6) 布局读取频繁（P2）
**位置**：`frontend/components/views/ImageMaskEditView.tsx:904–909`、`993–1010`、`1164–1167`

**现象**：
- mousemove 时频繁读取 `getBoundingClientRect`、`clientWidth/Height`。

**影响**：
- 高频 layout read 容易引发 layout thrash。

**建议**：
- 在 `mousedown` 时缓存坐标系和缩放信息，mousemove 复用。
- 仅在缩放/resize 时刷新缓存。

### 7) 长历史 + smooth scroll（P2）
**位置**：`frontend/components/views/ImageMaskEditView.tsx:1273–1281`

**现象**：
- `messages` 更新就执行 `scrollTo({ behavior: 'smooth' })`。

**影响**：
- 长历史情况下频繁动画，滚动抖动。

**建议**：
- 仅当用户在底部附近时自动滚动。
- 或改为 `behavior: 'auto'` 并减少触发频率。

## 优化建议（优先级）

### 立即（1–2 天）
- 对画笔绘制与光标更新使用 `requestAnimationFrame` 节流。
- 去掉 `updateMaskCanvasUrl` 的全图扫描，改为布尔标记。
- `toDataURL` 改为 `toBlob` + object URL，减少触发次数。

### 中期（3–5 天）
- 复用合成 canvas，避免反复创建与释放。
- 合成逻辑改为 `drawImage`/`globalCompositeOperation`，去掉逐像素遍历。
- 实时预览使用低分辨率 mask 或仅更新 dirty rect。

### 长期（> 1 周）
- 使用 `OffscreenCanvas` + worker 进行 mask 合成。
- 引入分块 mask（tile）以支持局部更新。

## 建议验证方法
- 使用 2K/4K 图像连续画笔涂抹 5–10 秒，记录 FPS 与主线程耗时。
- 统计 `generateMaskFromSelections` 执行时长与触发频率。
- 对比优化前后：
  - 单次笔画结束耗时
  - 连续绘制的平均帧率
  - 内存峰值与 GC 次数

---

如需我把上述优化落实到代码，请告知优先级（立即/中期/长期）与希望先改的具体点。
