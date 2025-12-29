# Implementation Plan: Ollama Model Management

## Overview

本实现计划将 Ollama 模型管理功能分解为可执行的编码任务。采用后端优先策略，先实现 API 端点，再实现前端组件。

## Tasks

- [x] 1. 后端 API 实现
  - [x] 1.1 创建 Ollama 模型管理路由文件
    - 创建 `backend/app/routers/ollama_models.py`
    - 定义路由前缀 `/api/ollama`
    - 添加依赖注入（base_url, api_key 参数）
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 1.2 实现获取模型列表端点
    - 实现 `GET /api/ollama/models` 端点
    - 调用 `OllamaService.get_available_models_detailed()`
    - 返回格式化的模型列表
    - _Requirements: 6.1_

  - [x] 1.3 实现获取模型详情端点
    - 实现 `GET /api/ollama/models/{name}` 端点
    - 调用 `OllamaService.get_model_info()`
    - 返回模型详情和能力信息
    - _Requirements: 6.4_

  - [x] 1.4 实现删除模型端点
    - 实现 `DELETE /api/ollama/models/{name}` 端点
    - 调用 `OllamaService.delete_model()`
    - 返回操作结果
    - _Requirements: 6.3_

  - [x] 1.5 实现模型下载端点（SSE 流式）
    - 实现 `POST /api/ollama/pull` 端点
    - 使用 `StreamingResponse` 返回 SSE 事件
    - 调用 `OllamaService.pull_model()` 并转发进度
    - _Requirements: 6.2_

  - [x] 1.6 注册路由到主应用
    - 在 `backend/app/main.py` 中注册 ollama_models 路由
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 2. Checkpoint - 后端 API 验证
  - 确保所有后端端点可用
  - 使用 curl 或 Postman 测试各端点
  - 确认 SSE 流式响应正常工作

- [x] 3. 前端类型定义和 API 服务
  - [x] 3.1 创建 Ollama 模型类型定义
    - 在 `frontend/types/ollama.ts` 中定义类型
    - 包含 `OllamaModel`, `OllamaModelInfo`, `PullProgress` 接口
    - _Requirements: 1.4, 4.1_

  - [x] 3.2 创建 Ollama API 服务
    - 创建 `frontend/services/providers/ollama/ollamaApi.ts`
    - 实现 `getModels()`, `getModelInfo()`, `deleteModel()` 方法
    - 实现 `pullModel()` 方法（SSE 处理）
    - _Requirements: 2.1, 3.2_

- [x] 4. 前端组件实现
  - [x] 4.1 创建 OllamaModelManager 主组件
    - 创建 `frontend/components/modals/settings/OllamaModelManager.tsx`
    - 实现状态管理（models, isLoading, error, pullProgress）
    - 实现模型列表获取逻辑
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 4.2 实现模型列表展示
    - 在 OllamaModelManager 中实现模型列表 UI
    - 显示模型名称、大小、修改时间
    - 添加删除按钮和详情按钮
    - _Requirements: 1.4, 3.1_

  - [x] 4.3 实现模型下载功能
    - 添加模型名称输入框和下载按钮
    - 实现 SSE 进度监听
    - 显示下载进度条
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 4.4 实现模型删除功能
    - 添加删除确认对话框
    - 实现删除 API 调用
    - 更新模型列表
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 4.5 实现模型详情展示
    - 添加模型详情面板
    - 显示模型家族、参数量、量化级别
    - 显示模型能力标签
    - _Requirements: 4.1, 4.2_

- [x] 5. EditorTab 集成
  - [x] 5.1 在 EditorTab 中集成 OllamaModelManager
    - 修改 `frontend/components/modals/settings/EditorTab.tsx`
    - 当 providerId 为 'ollama' 时显示模型管理区域
    - 传递 baseUrl 和 apiKey 参数
    - _Requirements: 5.1, 5.2_

  - [x] 5.2 实现模型列表自动刷新
    - 添加 `onModelsChanged` 回调到 `OllamaModelManager`
    - 模型下载/删除后自动调用 `handleVerify()` 刷新验证列表
    - 新下载的模型自动显示在 "Check models to include in the dropdown" 区域
    - _Requirements: 5.1, 5.2_

- [ ] 6. Checkpoint - 功能集成验证
  - 确保所有功能正常工作
  - 测试模型列表、下载、删除、详情功能
  - 验证 UI 与现有设计风格一致

- [ ] 7. 测试实现
  - [ ] 7.1 后端单元测试
    - 创建 `backend/app/routers/test_ollama_models.py`
    - 测试各端点的正常和异常情况
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ] 7.2 前端组件测试
    - 创建 `frontend/components/modals/settings/OllamaModelManager.test.tsx`
    - 测试组件渲染和交互
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ] 7.3 Property 1: Provider-based Component Rendering
    - **Property 1: Provider-based Component Rendering**
    - **Validates: Requirements 1.1, 5.1, 5.2**

  - [ ] 7.4 Property 2: Model List Display Completeness
    - **Property 2: Model List Display Completeness**
    - **Validates: Requirements 1.4**

  - [ ] 7.5 Property 7: Backend Model List Endpoint
    - **Property 7: Backend Model List Endpoint**
    - **Validates: Requirements 6.1**

- [ ] 8. Final Checkpoint
  - 确保所有测试通过
  - 确保代码符合项目规范
  - 如有问题，询问用户

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
