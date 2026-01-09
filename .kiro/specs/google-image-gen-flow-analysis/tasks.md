# Implementation Plan: Google Provider Image Generation Flow Optimization

## Overview

本实施计划将 Google 提供商图片生成流程优化分为三个阶段：
1. **阶段 1**：后端修改（无破坏性，支持 Vertex AI 配置）
2. **阶段 2**：前端修改（移除 API Key 暴露）
3. **阶段 3**：清理和文档（标注遗留代码）

每个阶段都包含实现任务和测试任务，确保质量和可靠性。

---

## Tasks

### 阶段 1：后端支持 Vertex AI 配置

- [ ] 1. 修改 ProviderFactory 支持用户上下文
  - 修改 `backend/app/services/provider_factory.py`
  - 添加 `user_id` 和 `db` 可选参数到 `get_service()` 方法
  - 传递参数到 GoogleService 构造函数
  - _Requirements: 2.3_

- [ ]* 1.1 编写 ProviderFactory 单元测试
  - 创建 `backend/tests/unit/test_provider_factory.py`
  - 测试参数正确传递
  - 测试向后兼容性（不传参数时仍工作）
  - _Requirements: 2.3, 3.3_

- [ ] 2. 修改 GoogleService 接收用户上下文
  - 修改 `backend/app/services/gemini/google_service.py`
  - 添加 `user_id` 和 `db` 参数到 `__init__()` 方法
  - 传递参数到 ImageGenerator 构造函数
  - 保存 user_id 和 db 为实例变量
  - _Requirements: 2.3_

- [ ]* 2.1 编写 GoogleService 单元测试
  - 创建 `backend/tests/unit/test_google_service.py`
  - 测试初始化时正确传递参数
  - 测试 ImageGenerator 接收到正确的参数
  - _Requirements: 2.3_

- [ ] 3. 修改 Generate Router 传递用户上下文
  - 修改 `backend/app/routers/generate.py`
  - 在 `generate_image()` 端点中传递 user_id 和 db 到 ProviderFactory
  - 移除从请求体获取 apiKey 的逻辑（设为 None）
  - _Requirements: 2.2, 2.3_

- [ ]* 3.1 编写 Generate Router 单元测试
  - 创建 `backend/tests/unit/test_generate_router.py`
  - 测试端点正确传递 user_id 和 db
  - 测试不再接受请求体中的 apiKey
  - _Requirements: 2.2, 2.3_


- [ ] 4. 验证 ImagenCoordinator 配置加载逻辑
  - 检查 `backend/app/services/gemini/imagen_coordinator.py`
  - 确认 `_load_config()` 方法正确处理用户配置
  - 确认回退逻辑正确（数据库 → 环境变量）
  - 添加日志记录配置来源
  - _Requirements: 2.3_

- [ ]* 4.1 编写 ImagenCoordinator 属性测试
  - 创建 `backend/tests/property/test_vertex_ai_config.py`
  - **Property 2: Vertex AI 配置优先级**
  - 测试有 Vertex AI 配置时使用 VertexAIImageGenerator
  - 测试无配置时回退到 GeminiAPIImageGenerator
  - 测试配置不完整时回退
  - 运行 100 次迭代
  - _Requirements: 2.3_
  - **Validates: Requirements 2.3**

- [ ] 5. Checkpoint - 验证后端 Vertex AI 支持
  - 运行所有后端单元测试
  - 运行属性测试
  - 手动测试：创建用户配置，验证使用 Vertex AI
  - 手动测试：无配置用户，验证回退到 Gemini API
  - 确认所有测试通过，询问用户是否有问题

---

### 阶段 2：前端移除 API Key 暴露

- [ ] 6. 修改 UnifiedProviderClient 移除 apiKey 参数
  - 修改 `frontend/services/providers/UnifiedProviderClient.ts`
  - 从 `generateImage()` 方法签名中移除 `apiKey` 参数
  - 从请求体中移除 `apiKey` 字段
  - 确保 `credentials: 'include'` 发送 session cookie
  - _Requirements: 2.1, 3.1_

- [ ]* 6.1 编写 UnifiedProviderClient 单元测试
  - 创建 `frontend/services/providers/UnifiedProviderClient.test.ts`
  - 测试请求体不包含 apiKey
  - 测试 credentials 设置为 'include'
  - 测试网络错误处理
  - _Requirements: 2.1, 3.1_

- [ ]* 6.2 编写 API 安全性属性测试
  - 创建 `frontend/tests/property/test_api_security.test.ts`
  - **Property 3: API 安全性（无前端密钥暴露）**
  - 测试任意请求都不包含 apiKey
  - 运行 100 次迭代
  - _Requirements: 2.1, 3.1_
  - **Validates: Requirements 2.1, 3.1**

- [ ] 7. 更新 LLMFactory 调用点
  - 检查 `frontend/services/LLMFactory.ts`
  - 确认 UnifiedProviderClient 创建时不传递 apiKey
  - 更新相关类型定义
  - _Requirements: 2.1_

- [ ] 8. 更新 llmService 调用点
  - 检查 `frontend/services/llmService.ts`
  - 确认 `generateImage()` 调用不传递 apiKey
  - 更新相关类型定义
  - _Requirements: 2.1_

- [ ] 9. 更新 ImageGenHandlerClass 调用点
  - 检查 `frontend/hooks/handlers/ImageGenHandlerClass.ts`
  - 确认调用链正确
  - 更新错误处理（处理 401 认证错误）
  - _Requirements: 1.1, 2.1_

- [ ]* 9.1 编写请求路由属性测试
  - 创建 `backend/tests/property/test_image_generation_flow.py`
  - **Property 1: 请求路由和数据完整性**
  - 测试 prompt 从前端正确传递到后端 SDK
  - 测试请求通过后端 API 路由
  - 运行 100 次迭代
  - _Requirements: 1.1, 2.2_
  - **Validates: Requirements 1.1, 2.2**

- [ ] 10. Checkpoint - 验证前端安全性改进
  - 运行所有前端单元测试
  - 运行前端属性测试
  - 运行后端属性测试
  - 手动测试：确认前端无法访问 API Key
  - 手动测试：确认图片生成功能正常
  - 确认所有测试通过，询问用户是否有问题

---

### 阶段 3：集成测试和清理

- [ ] 11. 编写端到端集成测试
  - 创建 `backend/tests/integration/test_image_generation_e2e.py`
  - 测试完整的 Vertex AI 流程
  - 测试完整的 Gemini API 流程
  - 测试 Vertex AI 失败时的回退
  - _Requirements: 1.1, 2.3, 3.3_

- [ ]* 11.1 编写向后兼容性属性测试
  - 创建 `backend/tests/property/test_backward_compatibility.py`
  - **Property 4: 向后兼容性**
  - 测试响应格式与之前一致
  - 测试现有功能不受影响
  - 运行 100 次迭代
  - _Requirements: 3.3_
  - **Validates: Requirements 3.3**

- [ ] 12. 标注前端遗留代码
  - 修改 `frontend/services/providers/google/media/image-gen.ts`
  - 添加 @deprecated 注释
  - 说明这是遗留代码，主流程使用 UnifiedProviderClient
  - 列出保留原因（Virtual Try-On 等特殊功能）
  - _Requirements: 2.4_

- [ ] 13. 更新相关文档
  - 更新 API 文档，说明不再接受 apiKey 参数
  - 更新架构文档，说明 Vertex AI 配置流程
  - 更新用户文档，说明如何配置 Vertex AI
  - 创建迁移指南（如果有外部调用者）
  - _Requirements: 3.1, 3.2_

- [ ] 14. 添加监控和日志
  - 在 ImagenCoordinator 添加配置来源日志
  - 在 Generate Router 添加请求日志
  - 添加 Vertex AI 使用率监控
  - 添加回退次数监控
  - _Requirements: 3.1_

- [ ] 15. Final Checkpoint - 完整验证
  - 运行完整测试套件（单元 + 属性 + 集成）
  - 验证测试覆盖率达标（后端 > 85%，前端 > 75%）
  - 手动测试所有场景：
    * Vertex AI 用户生成图片
    * Gemini API 用户生成图片
    * 无配置用户（使用环境变量）
    * 错误处理（无效配置、网络错误）
  - 检查日志和监控数据
  - 确认所有功能正常，询问用户是否可以部署

---

## Notes

### 任务标记说明
- `[ ]` - 未开始的任务
- `[ ]*` - 可选任务（测试相关），可以跳过以加快 MVP
- `[x]` - 已完成的任务

### 测试策略
- **单元测试**：验证具体示例和边界条件
- **属性测试**：验证通用属性，每个运行 100 次迭代
- **集成测试**：验证端到端流程

### 实施顺序
1. **阶段 1**（任务 1-5）：后端修改，无破坏性，可以独立部署
2. **阶段 2**（任务 6-10）：前端修改，有破坏性，需要协调部署
3. **阶段 3**（任务 11-15）：集成测试和清理，确保质量

### Checkpoint 说明
- 每个阶段结束都有 Checkpoint
- Checkpoint 时运行所有测试并手动验证
- 询问用户是否有问题或需要调整
- 确认无问题后继续下一阶段

### 回滚计划
如果阶段 2 出现问题：
1. 恢复 UnifiedProviderClient 的 apiKey 参数
2. 恢复前端调用点
3. 后端保持兼容（可选参数不影响）
4. 回滚时间 < 30 分钟

### 依赖关系
- 任务 1-5 必须按顺序完成（后端修改链）
- 任务 6-10 必须在任务 1-5 完成后开始（依赖后端支持）
- 任务 11-15 可以与任务 6-10 并行（测试和文档）

### 预估时间
- **阶段 1**：4-6 小时（后端修改 + 测试）
- **阶段 2**：3-4 小时（前端修改 + 测试）
- **阶段 3**：2-3 小时（集成测试 + 清理）
- **总计**：9-13 小时

