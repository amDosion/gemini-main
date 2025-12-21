# Virtual Try-On 实现任务清单

## 任务概览

本文档列出实现 Virtual Try-On 功能所需的所有任务，按照数据流依赖关系排序。

> **注意**：Phase 1 类型定义和 UI 入口已在模式重构中完成（`AppMode` 已包含 `'virtual-try-on'`，`ModeSelector` 已添加入口）。
> **重要**：Outpainting（画布扩展）功能已分离为独立的 `image-outpainting` 模式，请参考 `.kiro/specs/image-outpainting/` 目录。

---

## Phase 1: 类型定义（基础设施）✅ 已完成

- [x] 1. 扩展类型定义
  - [x] 1.1 扩展 `AppMode` 类型 ✅
    - 已在 `types.ts` 中添加 `'virtual-try-on'` 到 `AppMode` 联合类型
    - _Requirements: 3.1.1_
  - [x] 1.2 `ChatOptions` 已包含 `virtualTryOnTarget` 字段 ✅
    - _Requirements: 3.1.3_
  - [x] 1.3 `ModeSelector` 已添加 Try-On 模式入口 ✅
    - _Requirements: 3.1.2_

---

## Phase 2: 后端 API ✅ 已完成

- [x] 2. 后端 Vertex AI 代理 ✅
  - [x] 2.1 配置 Vertex AI 认证 ✅
    - 已在 `backend/app/core/config.py` 中添加 `GCP_PROJECT_ID`、`GCP_LOCATION`、`GOOGLE_APPLICATION_CREDENTIALS` 配置
    - 已在 `backend/.env` 中添加环境变量模板
    - _Requirements: 3.6.1, 3.6.2_
  - [x] 2.2 创建 Try-On 服务 ✅
    - 已创建 `backend/app/services/tryon_service.py`
    - 实现 `edit_with_mask_vertex()` 函数，调用 Vertex AI Imagen 3 API
    - 实现 `edit_with_gemini()` 函数作为备用方案
    - 处理图像编码/解码和错误处理
    - _Requirements: 3.2.1, 3.2.2_
  - [x] 2.3 创建 `/api/tryon/edit` 端点 ✅
    - 已创建 `backend/app/routers/tryon.py`
    - 实现 POST `/api/tryon/edit` 接口
    - 实现 POST `/api/tryon/segment` 接口（调试用）
    - 实现 GET `/api/tryon/status` 接口
    - 定义请求/响应模型
    - _Requirements: 3.2.1, 3.2.2_
  - [x] 2.4 注册路由 ✅
    - 已在 `backend/app/main.py` 中注册 tryon 路由
    - _Requirements: 3.4.2_

- [ ] 3. Checkpoint - 后端 API 测试
  - 确保 `/api/tryon/edit` 端点可用
  - 使用 curl 或 Postman 测试 API

---

## Phase 3: 前端服务 ✅ 已完成

- [x] 4. 创建 Virtual Try-On 服务 ✅
  - [x] 4.1 创建服务文件 ✅
    - 已创建 `frontend/services/providers/google/media/virtual-tryon.ts`
    - 定义 `SegmentationResult`, `TryOnOptions` 类型
    - _Requirements: 3.1.1_
  - [x] 4.2 实现分割函数 ✅
    - 实现 `segmentClothing()` 函数
    - 调用 Gemini API 进行服装分割
    - 解析 JSON 响应，提取 `box_2d`, `mask`, `label`
    - _Requirements: 3.1.1, 3.1.2, 3.1.3_
  - [x] 4.3 实现掩码处理函数 ✅
    - 实现 `generateMask()` 和 `generateMaskAsync()` 函数
    - 将归一化坐标转换为绝对像素坐标
    - 合并多个分割结果
    - 生成完整的二值掩码
    - _Requirements: 3.1.2, 3.1.3_
  - [x] 4.4 实现后端调用函数 ✅
    - 实现 `editWithMask()` 函数
    - 调用后端 `/api/tryon/edit` 接口
    - 处理响应和错误
    - _Requirements: 3.2.1, 3.2.2_
  - [x] 4.5 实现主函数 ✅
    - 实现 `virtualTryOn()` 主函数
    - 整合分割 → 掩码生成 → 编辑流程
    - _Requirements: 3.2.1, 3.2.2_
  - [x] 4.6 更新服务导出 ✅
    - 已在 `frontend/services/providers/google/media/index.ts` 中导出 virtualTryOn 相关函数
    - _Requirements: 3.4.2_

- [ ]* 4.7 编写属性测试：掩码坐标转换正确性
  - **Property 2: 掩码坐标转换正确性**
  - **Validates: Requirements 3.1.3**

---

## Phase 4: Handler 实现 ✅ 已完成

- [x] 5. 创建 Virtual Try-On Handler ✅
  - [x] 5.1 创建 Handler 文件 ✅
    - 已创建 `frontend/hooks/handlers/virtualTryOnHandler.ts`
    - 定义 `VirtualTryOnResult` 接口
    - _Requirements: 3.4.2_
  - [x] 5.2 实现 Handler 逻辑 ✅
    - 实现 `handleVirtualTryOn()` 函数
    - 优先调用后端 `/api/tryon/edit` API
    - 失败时回退到 `llmService.generateImage`（Gemini 智能编辑）
    - 下载结果图创建 Blob URL
    - 构建显示用附件
    - 提交上传任务到 Redis 队列
    - _Requirements: 3.2.1, 3.4.2_
  - [x] 5.3 更新 Handler 导出 ✅
    - 已在 `frontend/hooks/handlers/index.ts` 中导出 `handleVirtualTryOn`
    - _Requirements: 3.4.2_

- [ ]* 5.4 编写属性测试：错误处理完整性
  - **Property 6: 错误处理完整性**
  - **Validates: Requirements 3.7.1, 3.7.2, 3.7.3**

---

## Phase 5: useChat 集成 ✅ 已完成

- [x] 6. 集成到 useChat Hook ✅
  - [x] 6.1 添加 virtual-try-on 模式分支 ✅
    - 已在 `frontend/hooks/useChat.ts` 中添加 `else if (mode === 'virtual-try-on')` 分支
    - 参考 `image-outpainting` 模式的实现模式
    - 构建 HandlerContext
    - 调用 `handleVirtualTryOn()`
    - 更新 UI 显示
    - 处理上传任务
    - _Requirements: 3.4.2_

- [ ] 7. Checkpoint - Handler 集成测试
  - 确保 useChat 能正确分发到 virtual-try-on Handler
  - 验证数据流完整性

---

## Phase 6: UI 组件 ✅ 已完成

- [x] 8. 创建 VirtualTryOnView 组件 ✅
  - [x] 8.1 创建组件文件 ✅
    - 已创建 `frontend/components/views/VirtualTryOnView.tsx`
    - 复用 `ImageEditView` 的布局结构（`GenViewLayout`）
    - 复用 `useImageCanvas` Hook 实现缩放/平移
    - _Requirements: 3.4.2_
  - [x] 8.2 实现图片上传和画布显示 ✅
    - 复用 `InputArea` 组件处理附件上传
    - 显示上传的人物图片预览
    - _Requirements: 3.4.2_
  - [x] 8.3 实现服装类型选择（通过 VirtualTryOnControls）✅
    - 已有 `VirtualTryOnControls` 组件提供上衣/下装/全身选项
    - 通过 `ModeControlsCoordinator` 自动渲染
    - _Requirements: 3.4.3_
  - [x] 8.4 实现结果展示和历史记录 ✅
    - 显示生成的结果图
    - 支持点击放大、下载
    - 侧边栏显示历史记录
    - _Requirements: 3.4.2_

- [x] 9. 集成到 StudioView 和 GenWorkspace ✅
  - [x] 9.1 更新 StudioView ✅
    - 已在 `frontend/components/views/StudioView.tsx` 中添加 `case 'virtual-try-on'`
    - 返回 `<VirtualTryOnView {...props} />`
    - _Requirements: 3.4.2_
  - [x] 9.2 更新 GenWorkspace ✅
    - 已在 `frontend/components/workspaces/GenWorkspace.tsx` 中添加 `virtual-try-on` 支持
    - 复用 `image-edit` 的分屏布局逻辑
    - _Requirements: 3.4.2_

- [x] 10. 模式入口已完成 ✅
  - [x] 10.1 ModeSelector 已添加 Try-On 入口
  - [x] 10.2 VirtualTryOnControls 已集成到 ModeControlsCoordinator

- [ ] 11. Checkpoint - UI 集成测试
  - 确保 VirtualTryOnView 正确渲染
  - 验证模式切换功能
  - 测试完整的用户交互流程

---

## Phase 7: 错误处理优化 ✅ 已完成

- [x] 12. 完善错误处理 ✅
  - [x] 12.1 前端错误处理 ✅
    - 分割失败提示（在 `virtual-tryon.ts` 中实现）
    - 编辑失败提示（在 `virtualTryOnHandler.ts` 中实现）
    - 网络错误处理（在 `editWithMask()` 中实现）
    - _Requirements: 3.7.1, 3.7.2_
  - [x] 12.2 后端错误处理 ✅
    - Vertex AI 认证错误（在 `tryon_service.py` 中实现）
    - 安全过滤错误（检测 SAFETY 关键字）
    - 配额超限错误（检测 QUOTA/RESOURCE_EXHAUSTED）
    - _Requirements: 3.7.2, 3.7.3_

---

## Phase 8: Upscale（图像超分辨率）实现 ✅ 已完成

- [x] 13. 后端 Upscale API ✅
  - [x] 13.1 实现 Upscale 服务函数 ✅
    - 在 `backend/app/services/tryon_service.py` 中添加 `upscale_image()` 函数
    - 调用 Imagen 4 upscale 模型
    - 实现分辨率检查（17MP 限制）
    - 处理水印参数
    - _Requirements: 3.3.1, 3.3.2, 3.3.3, 3.3.4, 3.3.5_
  
  - [x] 13.2 创建 `/api/tryon/upscale` 端点 ✅
    - 在 `backend/app/routers/tryon.py` 中添加 POST `/api/tryon/upscale` 接口
    - 定义 `UpscaleRequest` 和 `UpscaleResponse` 模型
    - 返回高分辨率图像和分辨率信息
    - _Requirements: 3.3.1, 3.3.6_

- [x] 14. 前端 Upscale 服务 ✅
  - [x] 14.1 实现 Upscale 函数 ✅
    - 在 `frontend/services/providers/google/media/virtual-tryon.ts` 中添加 `upscaleImage()` 函数
    - 调用后端 `/api/tryon/upscale` 接口
    - 实现分辨率检查逻辑
    - _Requirements: 3.3.4_
  
  - [x] 14.2 添加分辨率验证函数 ✅
    - 实现 `checkUpscaleResolution()` 函数
    - 计算输出分辨率并验证是否超过 17MP
    - _Requirements: 3.3.4_

- [x] 15. UI Upscale 控件 ✅
  - [x] 15.1 添加放大倍数选择 ✅
    - 在 `VirtualTryOnView.tsx` 中添加 2x/4x 选择按钮
    - 添加水印选项开关
    - 显示分辨率预览和限制提示
    - _Requirements: 3.3.2, 3.3.3, 3.3.5_
  
  - [x] 15.2 集成到 Handler ✅
    - 在 `virtualTryOnHandler.ts` 中添加 Upscale 调用逻辑
    - 支持完整工作流（试衣 → 超分辨率）
    - _Requirements: 3.3.6_

- [ ]* 15.3 编写属性测试：Upscale 分辨率限制（已推迟）
  - **Property 5: Upscale 分辨率限制**
  - **Validates: Requirements 3.3.4**

- [ ]* 16. Checkpoint - Upscale 功能测试（已推迟）
  - 测试 2x 和 4x 放大
  - 验证分辨率限制检查
  - 测试完整工作流

---

## Phase 9: UI 增强功能 ✅ 已完成

- [x] 17. 掩码预览功能 ✅
  - [x] 17.1 实现掩码预览生成 ✅
    - 在 `virtual-tryon.ts` 中添加 `generateMaskPreview()` 函数
    - 生成半透明红色叠加预览
    - _Requirements: 3.4.4_
  
  - [x] 17.2 添加掩码预览 UI ✅
    - 在 `VirtualTryOnView.tsx` 中添加掩码预览叠加层
    - 实现半透明红色显示效果
    - 添加"生成掩码预览"按钮
    - _Requirements: 3.4.4_

- [x] 18. 结果对比功能 ✅
  - [x] 18.1 实现对比滑块 ✅
    - 添加左右对比视图组件
    - 实现滑动对比功能
    - _Requirements: 3.4.8_

- [x] 19. 下载功能 ✅
  - [x] 19.1 实现下载按钮 ✅
    - 添加下载原图按钮
    - 添加下载结果图按钮
    - 添加下载掩码按钮
    - _Requirements: 3.4.9_

- [x] 20. 图片上传验证 ✅
  - [x] 20.1 前端验证 ✅
    - 验证文件格式（JPG/PNG）
    - 验证文件大小（10MB）
    - 显示验证错误提示
    - _Requirements: 3.5.1, 3.5.2, 3.5.3, 3.5.4_
  
  - [x] 20.2 后端验证 ✅
    - 在 `tryon_service.py` 中添加 `validate_image()` 函数
    - 验证图像格式和大小
    - _Requirements: 3.5.1, 3.5.2_

- [ ]* 20.3 编写属性测试：掩码预览可见性（已推迟）
  - **Property 7: 掩码预览可见性**
  - **Validates: Requirements 3.4.4**

- [ ] 21. 掩码预览参数调整功能
  - [x] 21.1 修改服务层函数签名
    - 在 `virtual-tryon.ts` 的 `generateMaskPreview()` 函数中添加 `alpha` 和 `threshold` 参数
    - 默认值：`alpha = 0.7`, `threshold = 50`
    - 使用传入的参数替换硬编码值
    - _Requirements: 3.7.1, 3.7.2_
  
  - [x] 21.2 实现 UI 状态管理
    - 在 `VirtualTryOnView.tsx` 中添加 `maskAlpha` 和 `maskThreshold` 状态
    - 实现参数持久化（使用 localStorage）
    - 从 localStorage 恢复用户偏好设置
    - _Requirements: 3.7.7_
  
  - [x] 21.3 添加滑块控件 ✅
    - 在掩码预览控制面板中添加透明度滑块（0.3-1.0，步长 0.05）
    - 添加阈值滑块（10-200，步长 5）
    - 显示当前参数值（如 "70%"、"50"）
    - 添加参数说明提示文本
    - 实现范围验证和 NaN 检查
    - 修正标题按钮的 onClick 逻辑（条件调用 handleGenerateMaskPreview）
    - _Requirements: 3.7.1, 3.7.2, 3.7.5_
  
  - [x] 21.4 实现防抖机制 ✅
    - 创建 `useDebounce` Hook（延迟 300ms）
    - 对 `maskAlpha` 和 `maskThreshold` 应用防抖
    - 只在防抖后的值变化时重新生成掩码预览
    - 使用 useRef 跳过首次渲染
    - 添加条件判断（showMaskPreview && maskPreviewUrl 存在）
    - _Requirements: 3.7.6_
  
  - [x] 21.5 更新掩码预览生成逻辑 ✅
    - 修改 `handleGenerateMaskPreview()` 函数，传入动态参数
    - 在参数变化时自动重新生成预览（通过任务 21.4 的防抖机制）
    - 添加参数日志输出（用于调试）
    - _Requirements: 3.7.3, 3.7.4_

- [ ]* 21.6 编写属性测试：掩码预览参数动态调整
  - **Property 9: 掩码预览参数动态调整**
  - **Validates: Requirements 3.7.3, 3.7.4**

- [ ]* 21.7 编写属性测试：参数防抖优化
  - **Property 10: 参数防抖优化**
  - **Validates: Requirements 3.7.6**

- [ ]* 22. Checkpoint - UI 增强功能测试（已推迟）
  - 测试掩码预览显示
  - 测试对比滑块功能
  - 测试下载功能
  - 测试图片上传验证

---

## Phase 10: 测试（已推迟）

- [ ]* 22. 单元测试（已推迟）
  - [ ]* 22.1 测试掩码处理函数
    - 测试 JSON 解析逻辑
    - 测试坐标转换正确性
    - 测试掩码合并逻辑
  - [ ]* 22.2 测试 Upscale 分辨率检查
    - 测试分辨率计算逻辑
    - 测试 17MP 限制验证
  - [ ]* 22.3 测试错误处理分支
    - 测试各种错误场景

- [ ]* 23. 集成测试（已推迟）
  - [ ]* 23.1 测试完整 Try-On 流程
    - 从上传图片到生成结果的完整流程
  - [ ]* 23.2 测试 Upscale 流程
    - 测试 2x 和 4x 放大
    - 测试完整工作流（试衣 → 超分辨率）
  - [ ]* 23.3 测试边界情况
    - 无服装图片
    - 多件服装图片
    - 低质量图片

- [ ]* 24. Final Checkpoint - 全流程验证（已推迟）
  - 确保所有测试通过
  - 验证完整的用户体验流程
  - 测试所有功能组合

---

## 任务依赖关系图

```
Phase 1: 类型定义 ✅
    │
    ├──────────────────────────────────┐
    ▼                                  ▼
Phase 2: 后端 API ✅            Phase 3: 前端服务 ✅
    │                                  │
    └──────────────┬───────────────────┘
                   ▼
            Phase 4: Handler ✅
                   │
                   ▼
            Phase 5: useChat 集成 ✅
                   │
                   ▼
            Phase 6: UI 组件 ✅
                   │
                   ▼
            Phase 7: 错误处理 ✅
                   │
                   ▼
            Phase 8: Upscale
                   │
                   ▼
            Phase 9: UI 增强
                   │
                   ▼
            Phase 10: 测试 (可选)
```

---

## 优先级说明

| 标记 | 含义 |
|------|------|
| `- [x]` | 已完成的任务 |
| `- [ ]` | 必须完成的核心任务 |
| `- [ ]*` | 可选任务（测试、文档等） |

---

## 文件修改清单

| 文件 | 操作 | 任务 | 状态 |
|------|------|------|------|
| `types.ts` | 修改 | 1.1, 1.2, 1.3 | ✅ |
| `backend/app/core/config.py` | 修改 | 2.1 | ✅ |
| `backend/.env` | 修改 | 2.1 | ✅ |
| `backend/app/services/tryon_service.py` | 修改 | 2.2, 13.1 | ✅ (需补充 Upscale) |
| `backend/app/routers/tryon.py` | 修改 | 2.3, 13.2 | ✅ (需补充 Upscale) |
| `backend/app/main.py` | 修改 | 2.4 | ✅ |
| `frontend/services/providers/google/media/virtual-tryon.ts` | 修改 | 4.1-4.5, 14.1, 14.2, 17.1 | ✅ (需补充 Upscale 和预览) |
| `frontend/services/providers/google/media/index.ts` | 修改 | 4.6 | ✅ |
| `frontend/hooks/handlers/virtualTryOnHandler.ts` | 修改 | 5.1, 5.2, 15.2 | ✅ (需补充 Upscale) |
| `frontend/hooks/handlers/index.ts` | 修改 | 5.3 | ✅ |
| `frontend/hooks/useChat.ts` | 修改 | 6.1 | ✅ |
| `frontend/components/views/VirtualTryOnView.tsx` | 修改 | 8.1-8.4, 15.1, 17.2, 18.1, 19.1, 20.1 | ✅ (需补充 UI 增强) |
| `frontend/components/views/StudioView.tsx` | 修改 | 9.1 | ✅ |
| `frontend/components/workspaces/GenWorkspace.tsx` | 修改 | 9.2 | ✅ |

---

## 注意事项

1. **Outpainting 功能已分离**：画布扩展功能现在是独立的 `image-outpainting` 模式，请参考 `.kiro/specs/image-outpainting/` 目录
2. **Virtual Try-On 专注于**：服装分割、服装替换、图像超分辨率
3. **工作流建议**：用户可以先使用 Virtual Try-On 进行服装替换，然后切换到 Image Outpainting 模式进行画布扩展
