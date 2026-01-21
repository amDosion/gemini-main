# GEN模式跳转Edit/Expand模式附件显示任务文档

## 一、任务概述

优化 GEN 模式跳转到 Edit/Expand 模式时的附件显示逻辑，解决图片不能及时显示的问题。

**目标**：确保点击 Edit/Expand 按钮后，图片能够立即显示在目标模式的画布上，无需等待后端查询。

---

## 二、任务列表

### 任务 1：优化 tryFetchCloudUrl 逻辑

**任务 ID**：TASK-001  
**优先级**：高  
**预估时间**：0.5 天  
**状态**：待开始

**描述**：
优化 `tryFetchCloudUrl` 函数，避免对 Base64 URL 和 Blob URL 进行不必要的查询。

**文件**：`frontend/hooks/handlers/attachmentUtils.ts`  
**位置**：第 378-411 行

**具体修改**：
1. 在函数开头添加 Base64 URL 和 Blob URL 检查
2. 如果是 Base64 URL 或 Blob URL，直接返回 null，不查询后端
3. 优化查询条件：只对 HTTP URL 且 `uploadStatus === 'pending'` 时查询
4. 处理 `uploadStatus === undefined` 的情况（不触发查询，因为 `undefined === 'pending'` 为 false）

**验收标准**：
- ✅ Base64 URL 不触发 `tryFetchCloudUrl` 查询（🚀 加速显示）
- ✅ Blob URL 不触发 `tryFetchCloudUrl` 查询（🚀 加速显示）
- ✅ 只有 HTTP URL 且 pending 时才查询（🔄 避免多次查询）
- ✅ 所有现有测试通过

**设计意图**：
- 🚀 **加速显示**：Base64 URL 和 Blob URL 直接使用，不查询后端
- 🔄 **避免多次查询**：只有 HTTP URL 且 pending 时才查询，避免不必要的请求

**依赖**：无

---

### 任务 2：优化 useImageHandlers 查询逻辑

**任务 ID**：TASK-002  
**优先级**：高  
**预估时间**：0.5 天  
**状态**：待开始

**描述**：
优化 `handleEditImage` 和 `handleExpandImage` 函数，优先使用传入的 URL，不阻塞初始显示。

**文件**：`frontend/hooks/useImageHandlers.ts`  
**位置**：第 37-86 行（handleEditImage）和第 88-159 行（handleExpandImage）

**具体修改**：
1. **立即显示**：无论 URL 类型（Base64 或 HTTP URL），都应该立即调用 `setInitialAttachments`，使用传入的 URL
2. **异步查询**：将查询改为异步（使用 `.then()` 而不是 `await`），不阻塞 `setInitialAttachments`
3. **查询目的明确**：查询是为了获取永久云存储 URL（如果上传已完成），用于后续 API 调用，而不是为了验证 HTTP URL 是否可用
4. **HTTP URL 处理**：HTTP URL（包括 AI 提供商返回的临时 URL）应该直接使用，可以立即显示，不需要等待查询

**验收标准**：
- ✅ 点击按钮后，图片立即显示（< 100ms）（🚀 加速显示）
- ✅ Base64 URL 直接使用，不触发查询（🚀 加速显示）
- ✅ HTTP URL（包括临时 URL）直接使用，立即显示，不等待查询（🔄 避免多次查询）
- ✅ 查询在后台异步进行，不阻塞 `setInitialAttachments`（🚀 加速显示）
- ✅ 查询目的：获取永久云存储 URL（如果上传已完成），用于后续 API 调用（🏗️ 有意设计）
- ✅ 所有现有测试通过

**设计意图**：
- 🚀 **加速显示**：立即使用传入的 URL，不等待查询后端；查询在后台异步进行，不阻塞初始显示
- 🔄 **避免多次查询**：HTTP URL（包括临时 URL）直接使用，不需要查询验证
- 🏗️ **有意设计**：查询目的明确（获取永久云存储 URL，而不是验证 URL 是否可用）

**依赖**：TASK-001

---

### 任务 3：添加降级策略（可选）

**任务 ID**：TASK-003  
**优先级**：中  
**预估时间**：0.5 天  
**状态**：待开始

**描述**：
如果 HTTP URL 不可用，尝试使用 `tempUrl` 中的 Base64 URL。

**文件**：`frontend/hooks/useImageHandlers.ts`  
**位置**：第 45-68 行

**具体修改**：
1. 优先使用传入的 HTTP URL
2. 如果 HTTP URL 失败（通过 `<img>` 的 `onError` 事件检测），自动切换到 Base64 URL
3. 保存 Base64 URL 到 `tempUrl` 字段，作为备选
4. 在 ImageEditView/ImageExpandView 中添加 `onError` 处理，实现自动降级
5. 添加错误处理，如果都不可用，显示友好提示

**验收标准**：
- ✅ 如果 HTTP URL 不可用，自动降级到 Base64 URL（🏗️ 有意设计）
- ✅ 如果都不可用，显示友好错误提示
- ✅ 所有现有测试通过

**设计意图**：
- 🏗️ **有意设计**：降级策略提升可靠性，确保图片能够显示
- 🔄 **避免多次查询**：不预先验证 HTTP URL，避免额外的网络请求

**依赖**：TASK-002

---

### 任务 4：测试验证

**任务 ID**：TASK-004  
**优先级**：高  
**预估时间**：0.5 天  
**状态**：待开始

**描述**：
全面测试优化后的功能，确保所有场景正常工作。

**测试场景**：
1. **场景 1：Base64 URL**
   - GEN 模式生成图片（Base64 URL）
   - 立即点击 Edit 按钮
   - 验证：图片立即显示，不触发后端查询

2. **场景 2：HTTP URL（上传未完成）**
   - GEN 模式生成图片（HTTP 临时 URL）
   - 立即点击 Edit 按钮（上传未完成）
   - 验证：图片立即显示，使用 HTTP 临时 URL

3. **场景 3：HTTP URL（上传已完成）**
   - GEN 模式生成图片（HTTP 临时 URL）
   - 等待上传完成
   - 点击 Edit 按钮
   - 验证：图片立即显示，可选查询云 URL

4. **场景 4：查找失败**
   - GEN 模式生成图片
   - 清空 messages 中的 URL
   - 点击 Edit 按钮
   - 验证：使用传入的 URL，能够显示

5. **场景 5：性能测试**
   - 测量点击按钮到图片显示的时间
   - 验证：< 100ms

6. **场景 6：Blob URL**
   - GEN 模式生成图片（转换为 Blob URL，如果存在）
   - 立即点击 Edit 按钮
   - 验证：图片立即显示，不触发后端查询

7. **场景 7：uploadStatus === undefined**
   - GEN 模式生成图片（uploadStatus 未设置）
   - 立即点击 Edit 按钮
   - 验证：图片立即显示，不触发后端查询（因为 `undefined === 'pending'` 为 false）

8. **场景 8：findAttachmentByUrl 两级匹配 - 精确匹配**
   - GEN 模式生成图片（Base64 URL）
   - 清空 messages 中的 URL，保留 tempUrl
   - 点击 Edit 按钮
   - 验证：通过 tempUrl 精确匹配找到附件

9. **场景 9：findAttachmentByUrl 两级匹配 - Blob URL 兜底**
   - GEN 模式生成图片（转换为 Blob URL）
   - 清空 messages 中的 URL 和 tempUrl
   - 点击 Edit 按钮
   - 验证：通过兜底策略找到最近的有效云端图片附件（如果存在）

10. **场景 10：HTTP URL 降级到 Base64 URL**
    - GEN 模式生成图片（HTTP 临时 URL，tempUrl 中有 Base64 URL）
    - HTTP 临时 URL 不可用（模拟过期）
    - 点击 Edit 按钮
    - 验证：优先使用 HTTP URL，如果失败，自动切换到 Base64 URL

**验收标准**：
- ✅ 所有测试场景通过
- ✅ 性能指标达标（< 100ms）
- ✅ 无回归问题

**依赖**：TASK-001, TASK-002, TASK-003

---

## 三、任务依赖关系

```
TASK-001 (优化 tryFetchCloudUrl)
    ↓
TASK-002 (优化 useImageHandlers)
    ↓
TASK-003 (添加降级策略) [可选]
    ↓
TASK-004 (测试验证)
```

---

## 四、实施步骤

### 步骤 1：实施 TASK-001

1. 打开 `frontend/hooks/handlers/attachmentUtils.ts`
2. 定位到 `tryFetchCloudUrl` 函数（第 378 行）
3. 在函数开头添加 Base64/Blob URL 检查
4. 优化查询条件
5. 运行测试，确保通过

### 步骤 2：实施 TASK-002

1. 打开 `frontend/hooks/useImageHandlers.ts`
2. 定位到 `handleEditImage` 函数（第 37 行）
3. 优化查询逻辑，不阻塞初始显示
4. 同样修改 `handleExpandImage` 函数（第 88 行）
5. 运行测试，确保通过

### 步骤 3：实施 TASK-003（可选）

1. 在 `useImageHandlers.ts` 中添加降级策略
2. 处理 HTTP URL 不可用的情况
3. 添加错误处理
4. 运行测试，确保通过

### 步骤 4：实施 TASK-004

1. 执行所有测试场景
2. 测量性能指标
3. 验证无回归问题
4. 更新文档

---

## 五、代码修改清单

### 5.1 需要修改的文件

1. **frontend/hooks/handlers/attachmentUtils.ts**
   - 函数：`tryFetchCloudUrl`（第 378-411 行）
   - 修改类型：逻辑优化

2. **frontend/hooks/useImageHandlers.ts**
   - 函数：`handleEditImage`（第 37-86 行）
   - 函数：`handleExpandImage`（第 88-159 行）
   - 修改类型：逻辑优化

### 5.2 不需要修改的文件

- `frontend/components/views/ImageGenView.tsx` - 无需修改
- `frontend/components/views/ImageEditView.tsx` - 无需修改
- `frontend/components/views/ImageExpandView.tsx` - 无需修改
- 后端文件 - 无需修改

---

## 六、测试计划

### 6.1 单元测试

- ✅ `tryFetchCloudUrl` 函数测试
  - Base64 URL 不触发查询
  - Blob URL 不触发查询
  - HTTP URL 且 pending 时触发查询
  - uploadStatus === undefined 时不触发查询

- ✅ `useImageHandlers` 函数测试
  - Base64 URL 直接使用
  - HTTP URL 直接使用
  - 查询不阻塞初始显示

### 6.2 集成测试

- ✅ 完整流程测试：GEN → Edit/Expand
- ✅ 各种 URL 类型测试
- ✅ 各种上传状态测试

### 6.3 性能测试

- ✅ 响应时间测试：< 100ms
- ✅ 网络请求数量测试：减少 50% 以上

---

## 七、验收标准

### 7.1 功能验收

- ✅ Base64 URL 直接使用，不查询后端
- ✅ HTTP URL 直接使用，查询在后台进行
- ✅ 图片在点击按钮后立即显示（< 100ms）
- ✅ 所有现有功能正常工作

### 7.2 性能验收

- ✅ 响应时间 < 100ms
- ✅ 网络请求减少 50% 以上

### 7.3 可靠性验收

- ✅ 各种 URL 类型都能正常显示
- ✅ 各种上传状态都能正常显示
- ✅ 无回归问题

---

## 八、风险与缓解

### 8.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 修改影响其他功能 | 中 | 低 | 充分测试，确保向后兼容 |
| HTTP URL 过期问题 | 高 | 中 | 添加降级策略，使用 Base64 URL |

### 8.2 业务风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 用户体验下降 | 中 | 低 | 优化后用户体验应该提升 |

---

## 九、相关文档

- `requirements.md` - 需求文档
- `design.md` - 设计文档
- `IMAGE_GEN_TO_EDIT_EXPAND_FLOW.md` - 完整流程文档

---

## 十、设计意图分类说明

### 10.1 设计意图分类

本文档中的所有任务都明确标注了设计意图：

- 🚀 **加速显示**：为了提升用户体验，减少延迟，立即显示图片
- 🏗️ **有意设计**：架构设计决策，确保系统稳定性和可靠性
- 🔄 **避免多次查询**：避免不必要的后端查询，减少网络请求

### 10.2 关键设计决策

#### 决策 1：立即显示，不等待查询（🚀 加速显示）

**任务**：TASK-001, TASK-002

**原因**：提升用户体验，减少延迟

**实现**：
- Base64 URL 和 HTTP URL 都立即使用，不等待查询
- 查询在后台异步进行，不阻塞初始显示

#### 决策 2：后端上传后不更新前端会话（🏗️ 有意设计，🔄 避免多次查询）

**说明**：此决策已在架构层面实现，不在当前任务范围内

**原因**：
- 避免前端重新渲染，提升性能
- 保持原始 URL，避免查询后端获取云存储 URL
- 重载后自动使用永久云存储 URL

#### 决策 3：重载后使用永久云存储 URL（🏗️ 有意设计，🔄 避免多次查询）

**说明**：此决策已在架构层面实现，不在当前任务范围内

**原因**：
- 临时 URL（Base64、Blob URL）在重载后会失效
- 永久云存储 URL 可以持久化，重载后仍然可用

---

## 十一、更新日志

- **2024-01-18**：创建任务文档，基于需求文档和设计文档制定实施计划
- **2024-01-21**：更新文档，补充 Blob URL 测试场景、uploadStatus 边界情况测试、findAttachmentByUrl 两级匹配测试、HTTP URL 降级测试，明确降级策略实现方式
- **2024-01-21**：明确查询后端的真正目的（获取永久云存储 URL，而不是验证 URL 是否可用），强调 HTTP URL 应该立即显示，查询应该异步进行，不阻塞 `setInitialAttachments`
- **2024-01-21**：补充设计意图分类说明，明确区分加速显示、有意设计、避免多次查询的设计决策
