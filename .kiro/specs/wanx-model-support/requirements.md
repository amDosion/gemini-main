# 需求文档：万相（Wanx）图像生成模型支持

## 简介

本需求文档旨在为项目添加完整的万相（Wanx）图像生成模型支持。当前项目虽然在前端定义了万相模型的元数据，但后端并未实际使用 `qwen.py` 或 `qwen_native.py` 服务，导致无法获取和使用万相模型。

## 术语表

- **Wanx（万相）**: 阿里云通义千问提供的图像生成模型系列
- **DashScope**: 阿里云的 AI 模型服务平台
- **OpenAI Compatible API**: 兼容 OpenAI API 格式的接口
- **Native SDK**: 阿里云 DashScope 原生 SDK
- **Profile**: 用户配置文件，包含 API 密钥和已保存的模型列表
- **Model Registry**: 前端模型注册表，定义模型元数据

## 需求

### 需求 1：后端服务集成

**用户故事**: 作为开发者，我希望后端能够正确集成通义千问服务，以便前端可以获取和使用万相模型。

#### 验收标准

1. WHEN 后端启动时，THE System SHALL 正确初始化通义千问服务（QwenService 或 QwenNativeProvider）
2. WHEN 前端请求模型列表时，THE System SHALL 返回包含万相模型的完整列表
3. WHEN 用户验证通义千问连接时，THE System SHALL 能够成功获取模型列表并保存到数据库
4. THE System SHALL 支持通过 OpenAI Compatible API 或 Native SDK 两种方式访问通义千问服务

### 需求 2：万相模型获取

**用户故事**: 作为用户，我希望在配置页面验证通义千问连接时，能够看到所有可用的万相图像生成模型。

#### 验收标准

1. WHEN 用户在配置页面点击"验证连接"时，THE System SHALL 调用后端 API 获取模型列表
2. WHEN 后端获取模型列表时，THE System SHALL 包含以下万相模型：
   - `wanx-v1`（文本生成图像 - 旧版）
   - `wanx-v2`（文本生成图像 - 最新版）
   - `qwen-image-plus`（旗舰图像生成模型）
   - `wanx-v2.5-image-edit`（图像编辑模型）
   - `qwen-vl-image-edit`（视觉语言图像编辑模型）
3. WHEN API 未返回某些特殊模型时，THE System SHALL 自动补充这些模型到列表中
4. WHEN 模型列表获取成功后，THE System SHALL 将模型保存到 Profile.savedModels 中

### 需求 3：前后端模型命名一致性

**用户故事**: 作为系统架构师，我希望前后端使用一致的模型命名，以避免模型匹配失败。

#### 验收标准

1. THE System SHALL 在前端和后端都使用 `wanx-v2` 作为模型名称（而非 `wanxiang-v2`）
2. THE System SHALL 在前端和后端都使用 `wanx-v1` 作为模型名称
3. THE System SHALL 确保所有万相模型的命名在前后端完全一致
4. WHEN 前端发送模型 ID 到后端时，THE System SHALL 能够正确识别和处理

### 需求 4：模型元数据配置

**用户故事**: 作为开发者，我希望后端正确配置万相模型的价格和上下文长度，以便系统能够准确计算成本和管理上下文。

#### 验收标准

1. THE System SHALL 在 `MODEL_PRICES` 中为所有万相模型配置价格信息
2. THE System SHALL 在 `MODEL_CONTEXT_LENGTHS` 中为所有万相模型配置上下文长度
3. WHEN 万相模型按次计费（非 token 计费）时，THE System SHALL 将价格设置为 0.0 并在注释中说明
4. THE System SHALL 为特殊模型（如 `qwen-deep-research`, `qwq-32b`）配置正确的价格和上下文长度

### 需求 5：图像生成功能支持

**用户故事**: 作为用户，我希望能够使用万相模型生成图像，包括文本生成图像、图像编辑和图像扩展功能。

#### 验收标准

1. WHEN 用户选择万相模型并输入文本提示词时，THE System SHALL 调用图像生成 API
2. WHEN 用户上传参考图像并选择编辑模型时，THE System SHALL 调用图像编辑 API
3. WHEN 用户选择图像扩展功能时，THE System SHALL 调用 Out-Painting API
4. THE System SHALL 支持以下图像生成参数：
   - 图像分辨率（imageResolution）
   - 图像数量（numberOfImages）
   - 图像风格（imageStyle）
   - 负面提示词（negativePrompt）
   - LoRA 模型（用于风格融合）
   - 随机种子（seed）

### 需求 6：错误处理和降级策略

**用户故事**: 作为系统管理员，我希望当模型获取失败时，系统能够提供合理的降级策略，确保服务可用性。

#### 验收标准

1. WHEN OpenAI Compatible API 调用失败时，THE System SHALL 记录警告日志
2. WHEN 所有数据源都失败时，THE System SHALL 返回预设的模型列表（MODEL_PRICES.keys()）
3. WHEN 特殊模型未被 API 返回时，THE System SHALL 自动补充这些模型
4. THE System SHALL 在日志中清晰记录模型获取的数据源和结果统计

### 需求 7：服务路由配置

**用户故事**: 作为开发者，我希望后端路由能够正确调用通义千问服务，以便前端请求能够被正确处理。

#### 验收标准

1. THE System SHALL 在服务工厂或依赖注入中注册通义千问服务
2. WHEN 前端请求通义千问相关接口时，THE System SHALL 路由到正确的服务实例
3. THE System SHALL 支持通过环境变量或配置文件选择使用 OpenAI Compatible API 或 Native SDK
4. THE System SHALL 在服务初始化时验证 API 密钥的有效性

### 需求 8：文档和日志

**用户故事**: 作为开发者，我希望有清晰的文档和日志，以便理解系统如何获取和使用万相模型。

#### 验收标准

1. THE System SHALL 在代码中提供清晰的注释，说明支持的模型类型
2. THE System SHALL 在模型获取过程中记录详细的日志信息
3. THE System SHALL 提供文档说明如何配置和使用万相模型
4. THE System SHALL 在日志中区分不同的数据源（API、特殊模型补充、降级列表）

## 当前状态分析

### 前端现状

✅ **已完成**：
- 前端已定义万相模型的元数据（`frontend/services/providers/tongyi/models.ts`）
- 前端已实现图像生成、编辑、扩展功能（`DashScopeProvider.ts`）
- 前端已实现模型获取逻辑（`getTongYiModels()`）

### 后端现状

❌ **缺失**：
- 后端虽然有 `qwen.py` 和 `qwen_native.py` 文件，但**未被项目实际使用**
- 后端路由和服务工厂中**未注册通义千问服务**
- 后端 API 接口中**未实现模型列表获取端点**
- 后端**未实现图像生成相关的 API 端点**

### 关键问题

1. **服务未集成**: `qwen.py` 和 `qwen_native.py` 只是代码文件，未被项目导入和使用
2. **路由缺失**: 后端没有通义千问相关的 API 路由
3. **前端直连**: 前端直接调用 DashScope API，绕过了后端服务
4. **数据库缓存未生效**: 由于后端未集成，Profile.savedModels 无法保存万相模型

## 解决方案概述

要让项目完整支持万相模型，需要：

1. **集成后端服务**: 在后端服务工厂中注册 `QwenService`
2. **添加 API 路由**: 创建通义千问相关的 API 端点
3. **实现模型获取**: 后端提供模型列表获取接口
4. **实现图像生成**: 后端提供图像生成、编辑、扩展接口
5. **更新前端调用**: 前端通过后端 API 调用通义千问服务（可选，保持现有直连方式）

## 优先级

| 需求 | 优先级 | 说明 |
|------|--------|------|
| 需求 1 | P0（最高） | 后端服务集成是基础 |
| 需求 2 | P0（最高） | 模型获取是核心功能 |
| 需求 3 | P0（最高） | 命名一致性避免错误 |
| 需求 4 | P1（高） | 元数据配置影响成本计算 |
| 需求 5 | P1（高） | 图像生成是主要功能 |
| 需求 6 | P2（中） | 错误处理提升稳定性 |
| 需求 7 | P0（最高） | 路由配置是服务可用的前提 |
| 需求 8 | P2（中） | 文档和日志辅助开发 |

## 下一步

完成需求文档后，将创建设计文档（`design.md`），详细说明：
- 后端服务架构设计
- API 接口设计
- 数据流设计
- 错误处理设计
- 测试策略
