# 任务文档：万相（Wanx）图像生成模型支持

## 任务概述

本文档将需求和设计分解为可执行的开发任务，按优先级和依赖关系组织。

## 任务分组

### 阶段 1：后端服务集成（P0 - 最高优先级）

这是整个项目的基础，必须首先完成。

- [ ] **1.1 创建通义千问 API 路由模块**
  - 类型：backend
  - 优先级：P0
  - 依赖：无
  - Requirements: 1.1, 1.7
  - 文件：`backend/app/api/routes/qwen.py` (新建)
  - 任务：
    - 创建路由文件
    - 定义 Pydantic 模型（ValidateRequest, ValidateResponse, ModelInfo）
    - 实现 `/api/qwen/validate` 端点（验证连接）
    - 实现 `/api/qwen/models` 端点（获取模型列表）
    - 添加错误处理和日志记录

- [ ] **1.2 注册通义千问路由到主应用**
  - 类型：backend
  - 优先级：P0
  - 依赖：1.1
  - Requirements: 1.7
  - 文件：`backend/app/main.py` 或 `backend/app/api/routes/__init__.py`
  - 任务：
    - 导入 qwen 路由模块
    - 注册路由到 FastAPI 应用
    - 配置路由前缀（`/api/qwen`）
    - 验证路由可访问性

- [ ] **1.3 创建服务工厂或依赖注入**
  - 类型：backend
  - 优先级：P0
  - 依赖：无
  - Requirements: 1.1, 1.7
  - 文件：`backend/app/core/dependencies.py` 或 `backend/app/services/__init__.py`
  - 任务：
    - 创建 `get_qwen_service()` 依赖函数
    - 实现 API 密钥验证逻辑
    - 添加配置参数支持（base_url, timeout）
    - 添加服务实例缓存（可选）

### 阶段 2：模型获取和命名一致性（P0 - 最高优先级）

确保模型列表正确获取，前后端命名一致。

- [ ] **2.1 验证后端模型价格配置**
  - 类型：backend
  - 优先级：P0
  - 依赖：无
  - Requirements: 1.4
  - 文件：`backend/app/services/qwen.py`
  - 任务：
    - 检查 `MODEL_PRICES` 是否包含所有万相模型
    - 检查 `MODEL_CONTEXT_LENGTHS` 是否包含所有万相模型
    - 验证特殊模型（qwen-deep-research, qwq-32b）配置
    - 添加注释说明按次计费的模型

- [ ] **2.2 验证前端模型元数据**
  - 类型：frontend
  - 优先级：P0
  - 依赖：无
  - Requirements: 1.3
  - 文件：`frontend/services/providers/tongyi/models.ts`
  - 任务：
    - 检查所有万相模型使用 `wanx-` 前缀（而非 `wanxiang-`）
    - 验证模型 ID 与后端一致
    - 检查模型类型标注正确（image-generation, image-editing）
    - 验证上下文长度配置

- [ ] **2.3 实现模型命名标准化**
  - 类型：backend
  - 优先级：P0
  - 依赖：2.1, 2.2
  - Requirements: 1.3
  - 文件：`backend/app/api/routes/qwen.py`
  - 任务：
    - 创建 `MODEL_NAME_MAPPING` 字典
    - 实现 `normalize_model_name()` 函数
    - 在路由层应用命名标准化
    - 添加日志记录命名转换

- [ ] **2.4 测试模型列表获取**
  - 类型：backend
  - 优先级：P0
  - 依赖：1.1, 1.2, 1.3, 2.1
  - Requirements: 1.2
  - 文件：`tests/services/test_qwen.py` (新建)
  - 任务：
    - 编写 `test_get_available_models()` 测试
    - 编写 `test_wanx_models_included()` 测试
    - 编写 `test_special_models_included()` 测试
    - 编写 `test_model_naming_consistency()` 测试
    - 使用 mock 避免实际 API 调用

### 阶段 3：前端集成（P1 - 高优先级）

将前端连接到后端 API。

- [ ] **3.1 更新前端配置验证逻辑**
  - 类型：frontend
  - 优先级：P1
  - 依赖：1.1, 1.2
  - Requirements: 1.2
  - 文件：`frontend/components/modals/settings/EditorTab.tsx`
  - 任务：
    - 修改验证连接逻辑，调用后端 `/api/qwen/validate` 端点
    - 处理验证响应，保存模型列表到 Profile.savedModels
    - 添加错误处理和用户提示
    - 更新 UI 显示验证状态

- [ ] **3.2 更新前端模型获取逻辑**
  - 类型：frontend
  - 优先级：P1
  - 依赖：1.1, 1.2, 3.1
  - Requirements: 1.2
  - 文件：`frontend/services/providers/tongyi/models.ts`
  - 任务：
    - 修改 `getTongYiModels()` 函数
    - 优先从 Profile.savedModels 读取
    - 如果缓存不存在，调用后端 `/api/qwen/models` 端点
    - 合并静态模型定义和动态获取的模型
    - 添加错误处理和降级策略

- [ ] **3.3 测试前端集成**
  - 类型：frontend
  - 优先级：P1
  - 依赖：3.1, 3.2
  - Requirements: 1.2
  - 文件：`tests/services/tongyi.test.ts` (新建)
  - 任务：
    - 编写 `test_get_tongyi_models()` 测试
    - 编写 `test_validate_connection()` 测试
    - 编写 `test_model_caching()` 测试
    - 使用 mock 避免实际 API 调用

### 阶段 4：错误处理和降级策略（P2 - 中优先级）

提升系统稳定性和用户体验。

- [ ] **4.1 实现后端错误处理**
  - 类型：backend
  - 优先级：P2
  - 依赖：1.1, 2.1
  - Requirements: 1.6
  - 文件：`backend/app/services/qwen.py`
  - 任务：
    - 在 `get_available_models()` 中添加 try-except
    - 实现降级策略（返回 MODEL_PRICES.keys()）
    - 添加详细的日志记录
    - 区分不同错误类型（网络错误、认证错误、API 错误）

- [ ] **4.2 实现前端错误处理**
  - 类型：frontend
  - 优先级：P2
  - 依赖：3.1, 3.2
  - Requirements: 1.6
  - 文件：`frontend/services/providers/tongyi/models.ts`
  - 任务：
    - 在 `getTongYiModels()` 中添加 try-catch
    - 实现降级策略（返回静态模型列表）
    - 添加用户友好的错误提示
    - 记录错误到控制台

- [ ] **4.3 实现 CORS 自动切换**
  - 类型：frontend
  - 优先级：P2
  - 依赖：无
  - Requirements: 1.6
  - 文件：`frontend/services/providers/tongyi/api.ts`
  - 任务：
    - 在 `resolveDashUrl()` 中检测官方域名
    - 自动切换到代理路径
    - 添加日志记录切换行为
    - 测试代理路径可用性

- [ ] **4.4 添加错误处理测试**
  - 类型：backend + frontend
  - 优先级：P2
  - 依赖：4.1, 4.2, 4.3
  - Requirements: 1.6
  - 文件：`tests/services/test_qwen.py`, `tests/services/tongyi.test.ts`
  - 任务：
    - 编写 API 调用失败测试
    - 编写降级策略测试
    - 编写 CORS 切换测试
    - 验证错误日志记录

### 阶段 5：性能优化（P2 - 中优先级）

提升系统性能和响应速度。

- [ ] **5.1 实现后端模型列表缓存**
  - 类型：backend
  - 优先级：P2
  - 依赖：2.4
  - Requirements: 性能优化
  - 文件：`backend/app/services/qwen.py`
  - 任务：
    - 添加类级别缓存变量（_model_cache, _cache_timestamp）
    - 实现缓存检查逻辑（TTL: 5 分钟）
    - 添加缓存失效机制
    - 添加日志记录缓存命中/未命中

- [ ] **5.2 实现前端模型列表缓存**
  - 类型：frontend
  - 优先级：P2
  - 依赖：3.2
  - Requirements: 性能优化
  - 文件：`frontend/services/llmService.ts`
  - 任务：
    - 使用 Profile.savedModels 作为持久缓存
    - 实现内存缓存（5 分钟 TTL）
    - 添加缓存失效机制
    - 添加日志记录缓存状态

- [ ] **5.3 优化并行请求**
  - 类型：backend
  - 优先级：P2
  - 依赖：5.1
  - Requirements: 性能优化
  - 文件：`backend/app/services/qwen.py`
  - 任务：
    - 使用 `asyncio.gather()` 并行获取多个数据源
    - 处理部分失败情况
    - 添加超时控制
    - 测试并行性能提升

### 阶段 6：图像生成功能（P1 - 高优先级，可选）

实现后端图像生成 API（可选，前端已有直连实现）。

- [ ] **6.1 实现后端图像生成端点**
  - 类型：backend
  - 优先级：P1（可选）
  - 依赖：1.1, 1.2
  - Requirements: 1.5
  - 文件：`backend/app/api/routes/qwen.py`
  - 任务：
    - 定义 `ImageGenRequest` 和 `ImageGenResponse` 模型
    - 实现 `/api/qwen/image/generate` 端点
    - 调用 DashScope 图像生成 API
    - 处理同步和异步模式
    - 添加错误处理和日志记录

- [ ] **6.2 实现后端图像编辑端点**
  - 类型：backend
  - 优先级：P1（可选）
  - 依赖：6.1
  - Requirements: 1.5
  - 文件：`backend/app/api/routes/qwen.py`
  - 任务：
    - 定义 `ImageEditRequest` 和 `ImageEditResponse` 模型
    - 实现 `/api/qwen/image/edit` 端点
    - 处理参考图像上传
    - 调用 DashScope 图像编辑 API
    - 添加错误处理和日志记录

- [ ] **6.3 实现后端图像扩展端点**
  - 类型：backend
  - 优先级：P1（可选）
  - 依赖：6.1
  - Requirements: 1.5
  - 文件：`backend/app/api/routes/qwen.py`
  - 任务：
    - 定义 `OutPaintRequest` 和 `OutPaintResponse` 模型
    - 实现 `/api/qwen/image/outpaint` 端点
    - 处理参考图像上传
    - 调用 DashScope Out-Painting API
    - 添加错误处理和日志记录

- [ ] **6.4 更新前端图像生成逻辑（可选）**
  - 类型：frontend
  - 优先级：P1（可选）
  - 依赖：6.1, 6.2, 6.3
  - Requirements: 1.5
  - 文件：`frontend/services/providers/tongyi/DashScopeProvider.ts`
  - 任务：
    - 添加配置选项（使用后端 API 或直连）
    - 修改 `generateImage()` 支持后端路径
    - 修改 `editWanxImage()` 支持后端路径
    - 修改 `outPaintWanxImage()` 支持后端路径
    - 保持向后兼容性

### 阶段 7：测试和文档（P2 - 中优先级）

确保代码质量和可维护性。

- [ ] **7.1 编写 API 集成测试**
  - 类型：backend
  - 优先级：P2
  - 依赖：1.1, 1.2, 2.1
  - Requirements: 1.8
  - 文件：`tests/api/test_qwen_routes.py` (新建)
  - 任务：
    - 编写 `test_validate_connection()` 测试
    - 编写 `test_get_models()` 测试
    - 编写 `test_invalid_api_key()` 测试
    - 使用 TestClient 模拟请求

- [ ] **7.2 编写端到端测试**
  - 类型：e2e
  - 优先级：P2
  - 依赖：3.1, 3.2
  - Requirements: 1.8
  - 文件：`e2e/wanx-model-support.spec.ts` (新建)
  - 任务：
    - 编写连接验证流程测试
    - 编写模型列表显示测试
    - 编写图像生成流程测试（可选）
    - 使用 Playwright 或 Cypress

- [ ] **7.3 创建用户文档**
  - 类型：documentation
  - 优先级：P2
  - 依赖：无
  - Requirements: 1.8
  - 文件：`docs/wanx-model-guide.md` (新建)
  - 任务：
    - 编写配置指南
    - 编写使用指南
    - 编写常见问题解答
    - 添加截图和示例

- [ ] **7.4 创建开发者文档**
  - 类型：documentation
  - 优先级：P2
  - 依赖：无
  - Requirements: 1.8
  - 文件：`docs/wanx-model-development.md` (新建)
  - 任务：
    - 编写架构说明
    - 编写 API 设计文档
    - 编写数据流说明
    - 编写测试指南

- [ ] **7.5 更新 API 文档**
  - 类型：documentation
  - 优先级：P2
  - 依赖：1.1
  - Requirements: 1.8
  - 文件：`backend/app/api/routes/qwen.py`
  - 任务：
    - 添加 OpenAPI 文档字符串
    - 添加请求/响应示例
    - 添加错误码说明
    - 验证 Swagger UI 显示正确

### 阶段 8：部署和监控（P3 - 低优先级）

准备生产环境部署。

- [ ] **8.1 配置环境变量**
  - 类型：devops
  - 优先级：P3
  - 依赖：无
  - Requirements: 部署
  - 文件：`.env.example`, `docker-compose.yml`
  - 任务：
    - 添加 DASHSCOPE_API_KEY 环境变量
    - 添加 DASHSCOPE_BASE_URL 环境变量
    - 添加 QWEN_SERVICE_ENABLED 环境变量
    - 更新 Docker 配置

- [ ] **8.2 配置日志记录**
  - 类型：devops
  - 优先级：P3
  - 依赖：无
  - Requirements: 部署
  - 文件：`backend/app/core/logging.py`
  - 任务：
    - 配置 qwen 服务日志级别
    - 配置日志文件路径
    - 配置日志格式
    - 添加日志轮转

- [ ] **8.3 添加监控指标**
  - 类型：devops
  - 优先级：P3
  - 依赖：1.1
  - Requirements: 部署
  - 文件：`backend/app/api/routes/qwen.py`
  - 任务：
    - 添加 API 调用次数统计
    - 添加 API 响应时间统计
    - 添加错误率统计
    - 集成 Prometheus 或其他监控工具

- [ ] **8.4 创建部署文档**
  - 类型：documentation
  - 优先级：P3
  - 依赖：8.1, 8.2, 8.3
  - Requirements: 部署
  - 文件：`docs/deployment.md`
  - 任务：
    - 编写部署步骤
    - 编写配置说明
    - 编写故障排查指南
    - 添加监控指南

## 任务依赖图

```
阶段 1: 后端服务集成
1.1 → 1.2
1.3 → 1.2

阶段 2: 模型获取和命名一致性
2.1 → 2.3 → 2.4
2.2 → 2.3
1.1, 1.2, 1.3 → 2.4

阶段 3: 前端集成
1.1, 1.2 → 3.1 → 3.2 → 3.3

阶段 4: 错误处理和降级策略
1.1, 2.1 → 4.1
3.1, 3.2 → 4.2
4.1, 4.2, 4.3 → 4.4

阶段 5: 性能优化
2.4 → 5.1 → 5.3
3.2 → 5.2

阶段 6: 图像生成功能（可选）
1.1, 1.2 → 6.1 → 6.2, 6.3
6.1, 6.2, 6.3 → 6.4

阶段 7: 测试和文档
1.1, 1.2, 2.1 → 7.1
3.1, 3.2 → 7.2
1.1 → 7.5

阶段 8: 部署和监控
1.1 → 8.3
8.1, 8.2, 8.3 → 8.4
```

## 任务优先级总结

| 优先级 | 阶段 | 任务数 | 说明 |
|--------|------|--------|------|
| P0 | 阶段 1, 2 | 9 | 必须首先完成，是整个项目的基础 |
| P1 | 阶段 3, 6 | 7 | 核心功能，尽快完成 |
| P2 | 阶段 4, 5, 7 | 13 | 提升质量和性能，逐步完成 |
| P3 | 阶段 8 | 4 | 生产环境准备，最后完成 |

## 预估工作量

| 阶段 | 预估时间 | 说明 |
|------|----------|------|
| 阶段 1 | 4-6 小时 | 后端服务集成 |
| 阶段 2 | 3-4 小时 | 模型获取和命名一致性 |
| 阶段 3 | 3-4 小时 | 前端集成 |
| 阶段 4 | 2-3 小时 | 错误处理和降级策略 |
| 阶段 5 | 2-3 小时 | 性能优化 |
| 阶段 6 | 4-6 小时 | 图像生成功能（可选） |
| 阶段 7 | 4-6 小时 | 测试和文档 |
| 阶段 8 | 2-3 小时 | 部署和监控 |
| **总计** | **24-35 小时** | 不包括阶段 6 约 20-29 小时 |

## 下一步

Spec 文档已完成（requirements.md, design.md, tasks.md），现在可以开始执行任务。

建议执行顺序：
1. 先完成阶段 1（后端服务集成）
2. 再完成阶段 2（模型获取和命名一致性）
3. 然后完成阶段 3（前端集成）
4. 最后根据需要完成其他阶段

每个任务完成后，使用 `taskStatus` 标记任务状态。
