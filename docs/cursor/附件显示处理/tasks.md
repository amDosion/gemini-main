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

**验收标准**：
- ✅ Base64 URL 不触发 `tryFetchCloudUrl` 查询
- ✅ Blob URL 不触发 `tryFetchCloudUrl` 查询
- ✅ 只有 HTTP URL 且 pending 时才查询
- ✅ 所有现有测试通过

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
1. 优化查询条件：只对 HTTP URL 且 pending 时查询
2. 将查询改为异步，不阻塞 `setInitialAttachments` 的调用
3. 优先使用传入的 URL，查询结果作为可选更新

**验收标准**：
- ✅ 点击按钮后，图片立即显示（< 100ms）
- ✅ Base64 URL 不触发查询
- ✅ HTTP URL 直接使用，查询在后台进行
- ✅ 所有现有测试通过

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
1. 检查传入的 URL 是否可用
2. 如果 HTTP URL 不可用，且 `tempUrl` 是 Base64 URL，使用 Base64 URL
3. 添加错误处理，如果都不可用，显示友好提示

**验收标准**：
- ✅ 如果 HTTP URL 不可用，自动降级到 Base64 URL
- ✅ 如果都不可用，显示友好错误提示
- ✅ 所有现有测试通过

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

## 十、更新日志

- **2024-01-18**：创建任务文档，基于需求文档和设计文档制定实施计划
