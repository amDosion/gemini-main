# Virtual Try-On 实现任务清单

## 任务概览

本文档列出实现 Virtual Try-On 功能所需的所有任务，按照数据流依赖关系排序。

---

## Phase 1: 类型定义（基础设施）

- [ ] 1. 扩展类型定义
  - [ ] 1.1 扩展 `AppMode` 类型
    - 在 `types.ts` 中添加 `'virtual-try-on'` 到 `AppMode` 联合类型
    - _Requirements: 3.4.1_
  - [ ] 1.2 添加 `VirtualTryOnOptions` 接口
    - 定义 `targetClothing`, `customTarget`, `editMode`, `dilation`, `showMaskPreview` 字段
    - _Requirements: 3.4.3_
  - [ ] 1.3 扩展 `ChatOptions` 接口
    - 添加 `virtualTryOnOptions?: VirtualTryOnOptions` 字段
    - _Requirements: 3.4.3_

---

## Phase 2: 后端 API

- [ ] 2. 后端 Vertex AI 代理
  - [ ] 2.1 配置 Vertex AI 认证
    - 在 `backend/app/core/config.py` 中添加 `GCP_PROJECT_ID` 配置
    - 在 `backend/.env` 中添加环境变量
    - 配置服务账号凭证路径
    - _Requirements: 3.5.1, 3.5.2_
  - [ ] 2.2 创建 Try-On 服务
    - 创建 `backend/app/services/tryon_service.py`
    - 实现 `edit_with_mask()` 函数，调用 Vertex AI Imagen 3 API
    - 处理图像编码/解码
    - _Requirements: 3.2.3, 3.2.4_
  - [ ] 2.3 创建 `/api/tryon/edit` 端点
    - 创建 `backend/app/routers/tryon.py`
    - 实现 POST `/api/tryon/edit` 接口
    - 定义请求/响应模型
    - _Requirements: 3.2.1, 3.2.2_
  - [ ] 2.4 注册路由
    - 在 `backend/app/main.py` 中注册 tryon 路由
    - _Requirements: 3.5.2_

- [ ] 3. Checkpoint - 后端 API 测试
  - 确保 `/api/tryon/edit` 端点可用
  - 使用 curl 或 Postman 测试 API

---

## Phase 3: 前端服务

- [ ] 4. 创建 Virtual Try-On 服务
  - [ ] 4.1 创建服务文件
    - 创建 `frontend/services/providers/google/media/virtual-tryon.ts`
    - 定义 `SegmentationResult`, `TryOnOptions` 类型
    - _Requirements: 3.1.1_
  - [ ] 4.2 实现分割函数
    - 实现 `segmentClothing()` 函数
    - 调用 Gemini API 进行服装分割
    - 解析 JSON 响应，提取 `box_2d`, `mask`, `label`
    - _Requirements: 3.1.1, 3.1.2, 3.1.3_
  - [ ] 4.3 实现掩码处理函数
    - 实现 `generateMask()` 函数
    - 将归一化坐标转换为绝对像素坐标
    - 合并多个分割结果
    - 生成完整的二值掩码
    - _Requirements: 3.1.2, 3.1.3_
  - [ ] 4.4 实现后端调用函数
    - 实现 `editWithMask()` 函数
    - 调用后端 `/api/tryon/edit` 接口
    - 处理响应和错误
    - _Requirements: 3.2.1, 3.2.2_
  - [ ] 4.5 实现主函数
    - 实现 `virtualTryOn()` 主函数
    - 整合分割 → 掩码生成 → 编辑流程
    - _Requirements: 3.2.1, 3.2.2_
  - [ ] 4.6 更新服务导出
    - 在 `frontend/services/providers/google/media/index.ts` 中导出 virtualTryOn 相关函数
    - _Requirements: 3.4.2_

- [ ]* 4.7 编写属性测试：掩码坐标转换正确性
  - **Property 2: 掩码坐标转换正确性**
  - **Validates: Requirements 3.1.3**

---

## Phase 4: Handler 实现

- [ ] 5. 创建 Virtual Try-On Handler
  - [ ] 5.1 创建 Handler 文件
    - 创建 `frontend/hooks/handlers/virtualTryOnHandler.ts`
    - 定义 `VirtualTryOnHandlerResult` 接口
    - _Requirements: 3.4.2_
  - [ ] 5.2 实现 Handler 逻辑
    - 实现 `handleVirtualTryOn()` 函数
    - 获取原图信息
    - 调用 virtualTryOn 服务
    - 下载结果图创建 Blob URL
    - 构建显示用附件
    - 提交上传任务到 Redis 队列
    - _Requirements: 3.2.1, 3.4.2_
  - [ ] 5.3 更新 Handler 导出
    - 在 `frontend/hooks/handlers/index.ts` 中导出 `handleVirtualTryOn`
    - _Requirements: 3.4.2_

- [ ]* 5.4 编写属性测试：错误处理完整性
  - **Property 5: 错误处理完整性**
  - **Validates: Requirements 3.6.1, 3.6.2, 3.6.3**

---

## Phase 5: useChat 集成

- [ ] 6. 集成到 useChat Hook
  - [ ] 6.1 添加 virtual-try-on 模式分支
    - 在 `frontend/hooks/useChat.ts` 中添加 `else if (mode === 'virtual-try-on')` 分支
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

## Phase 6: UI 组件

- [ ] 8. 创建 VirtualTryOnView 组件
  - [ ] 8.1 创建组件文件
    - 创建 `frontend/components/views/VirtualTryOnView.tsx`
    - 定义 Props 接口
    - _Requirements: 3.4.2_
  - [ ] 8.2 实现图片上传区域
    - 支持拖拽上传
    - 支持点击选择文件
    - 显示上传的图片预览
    - _Requirements: 3.4.2_
  - [ ] 8.3 实现服装类型选择
    - 提供上衣/下装/全身/自定义选项
    - 自定义模式支持输入任意服装类型
    - _Requirements: 3.4.3_
  - [ ] 8.4 实现服装描述输入
    - 文本输入框
    - 占位符提示
    - _Requirements: 3.4.5_
  - [ ] 8.5 实现掩码预览功能（可选）
    - 显示分割掩码叠加在原图上的预览
    - 支持开关控制
    - _Requirements: 3.4.4_
  - [ ] 8.6 实现生成按钮和加载状态
    - 调用 onSend 触发生成
    - 显示加载动画
    - _Requirements: 3.4.2_
  - [ ] 8.7 实现结果展示
    - 显示生成的结果图
    - 支持点击放大
    - 支持下载
    - _Requirements: 3.4.2_

- [ ] 9. 集成到 StudioView
  - [ ] 9.1 添加 case 分支
    - 在 `frontend/components/views/StudioView.tsx` 中添加 `case 'virtual-try-on'`
    - 返回 `<VirtualTryOnView {...props} />`
    - _Requirements: 3.4.2_

- [ ] 10. 集成到 App.tsx
  - [ ] 10.1 更新 handleModeSwitch
    - 在 `frontend/App.tsx` 的 `handleModeSwitch` 函数中添加 `virtual-try-on` 分支
    - 自动选择支持 vision 的模型
    - _Requirements: 3.4.2_
  - [ ] 10.2 添加模式切换入口（可选）
    - 在模式选择器中添加 Virtual Try-On 入口
    - _Requirements: 3.4.2_

- [ ] 11. Checkpoint - UI 集成测试
  - 确保 VirtualTryOnView 正确渲染
  - 验证模式切换功能
  - 测试完整的用户交互流程

---

## Phase 7: 错误处理优化

- [ ] 12. 完善错误处理
  - [ ] 12.1 前端错误处理
    - 分割失败提示
    - 编辑失败提示
    - 网络错误处理
    - _Requirements: 3.6.1, 3.6.2_
  - [ ] 12.2 后端错误处理
    - Vertex AI 认证错误
    - 安全过滤错误
    - 配额超限错误
    - _Requirements: 3.6.2, 3.6.3_

---

## Phase 8: 测试

- [ ]* 13. 单元测试
  - [ ]* 13.1 测试掩码处理函数
    - 测试 JSON 解析逻辑
    - 测试坐标转换正确性
    - 测试掩码合并逻辑
  - [ ]* 13.2 测试错误处理分支
    - 测试各种错误场景

- [ ]* 14. 集成测试
  - [ ]* 14.1 测试完整 Try-On 流程
    - 从上传图片到生成结果的完整流程
  - [ ]* 14.2 测试边界情况
    - 无服装图片
    - 多件服装图片
    - 低质量图片

- [ ] 15. Final Checkpoint - 全流程验证
  - 确保所有测试通过
  - 验证完整的用户体验流程

---

## 任务依赖关系图

```
Phase 1: 类型定义
    │
    ├──────────────────────────────────┐
    ▼                                  ▼
Phase 2: 后端 API                 Phase 3: 前端服务
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
            Phase 8: 测试
```

---

## 优先级说明

| 标记 | 含义 |
|------|------|
| `- [ ]` | 必须完成的核心任务 |
| `- [ ]*` | 可选任务（测试、文档等） |

---

## 文件修改清单

| 文件 | 操作 | 任务 |
|------|------|------|
| `types.ts` | 修改 | 1.1, 1.2, 1.3 |
| `backend/app/core/config.py` | 修改 | 2.1 |
| `backend/.env` | 修改 | 2.1 |
| `backend/app/services/tryon_service.py` | 新增 | 2.2 |
| `backend/app/routers/tryon.py` | 新增 | 2.3 |
| `backend/app/main.py` | 修改 | 2.4 |
| `frontend/services/providers/google/media/virtual-tryon.ts` | 新增 | 4.1-4.5 |
| `frontend/services/providers/google/media/index.ts` | 修改 | 4.6 |
| `frontend/hooks/handlers/virtualTryOnHandler.ts` | 新增 | 5.1, 5.2 |
| `frontend/hooks/handlers/index.ts` | 修改 | 5.3 |
| `frontend/hooks/useChat.ts` | 修改 | 6.1 |
| `frontend/components/views/VirtualTryOnView.tsx` | 新增 | 8.1-8.7 |
| `frontend/components/views/StudioView.tsx` | 修改 | 9.1 |
| `frontend/App.tsx` | 修改 | 10.1, 10.2 |
