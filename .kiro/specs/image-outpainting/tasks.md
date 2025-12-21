# Image Outpainting 实现任务清单

## 任务概览

本文档列出实现 Image Outpainting（画布扩展）功能所需的所有任务，按照数据流依赖关系排序。

> **注意**：`AppMode` 已包含 `'image-outpainting'`，部分基础设施可能已存在。

---

## Phase 1: 类型定义（基础设施）

- [ ] 1. 扩展类型定义
  - [ ] 1.1 检查 `AppMode` 类型
    - 验证 `types.ts` 中是否已包含 `'image-outpainting'`
    - _Requirements: 3.5.1_
  - [ ] 1.2 添加 `ImageOutpaintingOptions` 接口
    - 在 `types.ts` 中定义 `ImageOutpaintingOptions`
    - 包含 direction, expandPixels, expandRatio, prompt, dilation 字段
    - _Requirements: 3.2.1, 3.3.1_
  - [ ] 1.3 扩展 `ChatOptions` 接口
    - 添加 `imageOutpaintingOptions?: ImageOutpaintingOptions` 字段
    - _Requirements: 3.5.5_

---

## Phase 2: 后端 API

- [ ] 2. 后端 Vertex AI 代理
  - [ ] 2.1 检查 Vertex AI 认证配置
    - 验证 `backend/app/core/config.py` 中的 GCP 配置
    - 验证 `backend/.env` 中的环境变量
    - _Requirements: 3.6.1, 3.6.2_
  
  - [ ] 2.2 创建或更新 Image 服务
    - 在 `backend/app/services/image_service.py` 中添加 `outpaint_image()` 函数
    - 实现掩码自动生成逻辑（根据扩展方向）
    - 调用 Imagen 3 outpainting 模式
    - 处理图像编码/解码和错误处理
    - _Requirements: 3.4.1, 3.4.2, 3.4.3_
  
  - [ ] 2.3 创建或更新 `/api/image/outpaint` 端点
    - 在 `backend/app/routers/image.py` 中添加 POST `/api/image/outpaint` 接口
    - 定义 `OutpaintRequest` 和 `OutpaintResponse` 模型
    - 处理方向参数（bottom/top/left/right/all）
    - 返回扩展后的图像和新尺寸
    - _Requirements: 3.2.1, 3.2.2, 3.2.3, 3.2.4, 3.2.5_
  
  - [ ] 2.4 注册路由
    - 确保 `backend/app/main.py` 中注册了 image 路由
    - _Requirements: 3.5.2_

- [ ]* 2.5 编写属性测试：画布尺寸正确性
  - **Property 1: 画布尺寸正确性**
  - **Validates: Requirements 3.3.1**

- [ ] 3. Checkpoint - 后端 API 测试
  - 确保 `/api/image/outpaint` 端点可用
  - 使用 curl 或 Postman 测试 API
  - 验证各个方向的扩展功能

---

## Phase 3: 前端服务

- [ ] 4. 创建或更新 Image Expand 服务
  - [ ] 4.1 创建服务文件
    - 创建或更新 `frontend/services/providers/google/media/image-expand.ts`
    - 定义 `ImageExpandOptions` 类型
    - _Requirements: 3.2.1_
  
  - [ ] 4.2 实现画布尺寸计算函数
    - 实现 `calculateExpandedSize()` 函数
    - 根据方向和像素数计算新尺寸
    - _Requirements: 3.3.1, 3.3.2_
  
  - [ ] 4.3 实现掩码生成函数
    - 实现 `generateExpansionMask()` 函数
    - 根据方向和像素数生成掩码
    - 生成完整的二值掩码
    - _Requirements: 3.4.1_
  
  - [ ] 4.4 实现后端调用函数
    - 实现 `outpaintImage()` 函数
    - 调用后端 `/api/image/outpaint` 接口
    - 处理响应和错误
    - _Requirements: 3.4.2, 3.4.3_
  
  - [ ] 4.5 实现主函数
    - 实现 `imageExpand()` 主函数
    - 整合尺寸计算 → 掩码生成 → 扩展流程
    - _Requirements: 3.4.4, 3.4.5_
  
  - [ ] 4.6 更新服务导出
    - 在 `frontend/services/providers/google/media/index.ts` 中导出 imageExpand 相关函数
    - _Requirements: 3.5.2_

- [ ]* 4.7 编写属性测试：掩码区域正确性
  - **Property 2: 掩码区域正确性**
  - **Validates: Requirements 3.4.1**

---

## Phase 4: Handler 实现

- [ ] 5. 创建或更新 Image Expand Handler
  - [ ] 5.1 创建 Handler 文件
    - 创建或更新 `frontend/hooks/handlers/imageExpandHandler.ts`
    - 定义 `ImageExpandHandlerResult` 接口
    - _Requirements: 3.5.2_
  
  - [ ] 5.2 实现 Handler 逻辑
    - 实现 `handleImageExpand()` 函数
    - 调用 `imageExpand()` 服务
    - 下载结果图创建 Blob URL
    - 构建显示用附件
    - 提交上传任务到 Redis 队列
    - _Requirements: 3.5.6, 3.5.7_
  
  - [ ] 5.3 更新 Handler 导出
    - 在 `frontend/hooks/handlers/index.ts` 中导出 `handleImageExpand`
    - _Requirements: 3.5.2_

- [ ]* 5.4 编写属性测试：错误处理完整性
  - **Property 5: 错误处理完整性**
  - **Validates: Requirements 3.7.1, 3.7.2, 3.7.3, 3.7.4**

---

## Phase 5: useChat 集成

- [ ] 6. 集成到 useChat Hook
  - [ ] 6.1 添加 image-outpainting 模式分支
    - 在 `frontend/hooks/useChat.ts` 中添加 `else if (mode === 'image-outpainting')` 分支
    - 构建 HandlerContext
    - 调用 `handleImageExpand()`
    - 更新 UI 显示
    - 处理上传任务
    - _Requirements: 3.5.2_

- [ ] 7. Checkpoint - Handler 集成测试
  - 确保 useChat 能正确分发到 image-outpainting Handler
  - 验证数据流完整性

---

## Phase 6: UI 组件

- [ ] 8. 创建或更新 ImageExpandView 组件
  - [ ] 8.1 创建组件文件
    - 创建或更新 `frontend/components/views/ImageExpandView.tsx`
    - 复用 `GenViewLayout` 布局结构
    - 复用 `useImageCanvas` Hook 实现缩放/平移
    - _Requirements: 3.5.2_
  
  - [ ] 8.2 实现图片上传和画布显示
    - 复用 `InputArea` 组件处理附件上传
    - 显示上传的图片预览
    - _Requirements: 3.1.5_
  
  - [ ] 8.3 实现方向选择控件
    - 添加方向选择按钮（上/下/左/右/全部）
    - 实现方向选择状态管理
    - _Requirements: 3.5.3_
  
  - [ ] 8.4 实现扩展参数控件
    - 添加扩展像素数输入框
    - 添加扩展比例选择（可选）
    - 实现参数验证
    - _Requirements: 3.5.4, 3.3.3_
  
  - [ ] 8.5 实现内容描述输入
    - 添加可选的内容描述输入框
    - _Requirements: 3.5.5_
  
  - [ ] 8.6 实现结果展示和历史记录
    - 显示生成的结果图
    - 支持点击放大、下载
    - 侧边栏显示历史记录
    - _Requirements: 3.5.7, 3.5.8, 3.5.9_

- [ ] 9. 集成到 StudioView 和 GenWorkspace
  - [ ] 9.1 更新 StudioView
    - 在 `frontend/components/views/StudioView.tsx` 中添加 `case 'image-outpainting'`
    - 返回 `<ImageExpandView {...props} />`
    - _Requirements: 3.5.2_
  
  - [ ] 9.2 更新 GenWorkspace
    - 在 `frontend/components/workspaces/GenWorkspace.tsx` 中添加 `image-outpainting` 支持
    - 复用 `image-edit` 的分屏布局逻辑
    - _Requirements: 3.5.2_

- [ ] 10. Checkpoint - UI 集成测试
  - 确保 ImageExpandView 正确渲染
  - 验证模式切换功能
  - 测试完整的用户交互流程

---

## Phase 7: 错误处理优化

- [ ] 11. 完善错误处理
  - [ ] 11.1 前端错误处理
    - 扩展失败提示（在 `image-expand.ts` 中实现）
    - 参数验证错误提示（在 `ImageExpandView.tsx` 中实现）
    - 网络错误处理（在 `outpaintImage()` 中实现）
    - _Requirements: 3.7.1, 3.7.2_
  
  - [ ] 11.2 后端错误处理
    - Vertex AI 认证错误（在 `image_service.py` 中实现）
    - 安全过滤错误（检测 SAFETY 关键字）
    - 配额超限错误（检测 QUOTA/RESOURCE_EXHAUSTED）
    - 掩码生成错误（在 `create_outpainting_mask()` 中实现）
    - _Requirements: 3.7.3, 3.7.4, 3.7.5_

---

## Phase 8: 图片上传验证

- [ ] 12. 实现图片上传验证
  - [ ] 12.1 前端验证
    - 验证文件格式（JPG/PNG）
    - 验证文件大小（10MB）
    - 显示验证错误提示
    - _Requirements: 3.1.1, 3.1.2, 3.1.3, 3.1.4_
  
  - [ ] 12.2 后端验证
    - 在 `image_service.py` 中添加 `validate_image()` 函数
    - 验证图像格式和大小
    - _Requirements: 3.1.1, 3.1.2_

- [ ] 13. Checkpoint - 验证功能测试
  - 测试各种文件格式
  - 测试文件大小限制
  - 验证错误提示显示

---

## Phase 9: 测试

- [ ]* 14. 单元测试
  - [ ]* 14.1 测试画布尺寸计算
    - 测试 `calculateExpandedSize()` 函数
    - 测试各个方向的尺寸计算
  - [ ]* 14.2 测试掩码生成
    - 测试 `generateExpansionMask()` 函数
    - 测试 `create_outpainting_mask()` 函数
    - 测试各个方向的掩码生成
  - [ ]* 14.3 测试参数验证
    - 测试扩展参数验证逻辑
    - 测试边界条件
  - [ ]* 14.4 测试错误处理分支
    - 测试各种错误场景

- [ ]* 15. 集成测试
  - [ ]* 15.1 测试完整扩展流程
    - 从上传图片到生成结果的完整流程
  - [ ]* 15.2 测试各个方向的扩展
    - 测试上/下/左/右/全部方向
    - 验证扩展内容与原图的一致性
  - [ ]* 15.3 测试边界情况
    - 最小扩展像素数
    - 最大扩展像素数
    - 有/无内容描述

- [ ] 16. Final Checkpoint - 全流程验证
  - 确保所有测试通过
  - 验证完整的用户体验流程
  - 测试所有功能组合

---

## 任务依赖关系图

```
Phase 1: 类型定义
    │
    ├──────────────────────────────────┐
    ▼                                  ▼
Phase 2: 后端 API              Phase 3: 前端服务
    │                                  │
    └──────────────┬───────────────────┘
                   ▼
            Phase 4: Handler
                   │
                   ▼
            Phase 5: useChat 集成
                   │
                   ▼
            Phase 6: UI 组件
                   │
                   ▼
            Phase 7: 错误处理
                   │
                   ▼
            Phase 8: 图片上传验证
                   │
                   ▼
            Phase 9: 测试 (可选)
```

---

## 优先级说明

| 标记 | 含义 |
|------|------|
| `- [ ]` | 必须完成的核心任务 |
| `- [ ]*` | 可选任务（测试、文档等） |

---

## 文件修改清单

| 文件 | 操作 | 任务 | 状态 |
|------|------|------|------|
| `types.ts` | 修改 | 1.1, 1.2, 1.3 | 待实现 |
| `backend/app/core/config.py` | 检查 | 2.1 | 可能已存在 |
| `backend/.env` | 检查 | 2.1 | 可能已存在 |
| `backend/app/services/image_service.py` | 新增/修改 | 2.2, 12.2 | 待实现 |
| `backend/app/routers/image.py` | 新增/修改 | 2.3 | 待实现 |
| `backend/app/main.py` | 检查 | 2.4 | 可能已存在 |
| `frontend/services/providers/google/media/image-expand.ts` | 新增/修改 | 4.1-4.5 | 待实现 |
| `frontend/services/providers/google/media/index.ts` | 修改 | 4.6 | 待实现 |
| `frontend/hooks/handlers/imageExpandHandler.ts` | 新增/修改 | 5.1, 5.2 | 待实现 |
| `frontend/hooks/handlers/index.ts` | 修改 | 5.3 | 待实现 |
| `frontend/hooks/useChat.ts` | 修改 | 6.1 | 待实现 |
| `frontend/components/views/ImageExpandView.tsx` | 新增/修改 | 8.1-8.6, 12.1 | 待实现 |
| `frontend/components/views/StudioView.tsx` | 修改 | 9.1 | 待实现 |
| `frontend/components/workspaces/GenWorkspace.tsx` | 修改 | 9.2 | 待实现 |
