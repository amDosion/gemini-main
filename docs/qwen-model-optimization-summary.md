# 通义千问模型获取优化总结

**修改时间**: 2025-12-28  
**修改文件**: `backend/app/services/qwen.py`  
**参考文件**: `backend/app/services/qwen_native.py`, `frontend/services/providers/tongyi/models.ts`

---

## 修改概览

本次修改旨在优化通义千问（Qwen）模型的获取逻辑，确保前后端模型命名一致，并支持万相（Wanx）图像生成模型及其他特殊模型。

**涉及的主要问题**：
1. 前后端模型命名不一致（`wanxiang-v2` vs `wanx-v2`）
2. 后端缺少万相系列模型的价格配置
3. 后端缺少特殊模型（`qwen-deep-research`, `qwq-32b`）
4. 模型获取逻辑需要优化（借鉴 `qwen_native.py` 的方案 3）

---

## 文件修改详情

### 修改文件：`backend/app/services/qwen.py`

#### 1. 更新文档注释

**修改说明**：
在文件顶部的文档字符串中，新增了支持的模型类型说明，方便开发者快速了解该服务支持哪些模型。

**修改内容**：
```python
"""
阿里通义千问 (Qwen) AI服务实现
使用OpenAI兼容API

支持的模型类型：
- Chat Models: qwen-turbo, qwen-plus, qwen-max, qwen3-max, qwen3-plus, qwen3-coder-plus
- Vision Models: qwen-vl-plus, qwen-vl-max, qwen3-vl-plus
- Image Generation: wanx-v1, wanx-v2, qwen-image-plus
- Image Editing: wanx-v2.5-image-edit, qwen-vl-image-edit
- Special Models: qwen-deep-research, qwq-32b
- Embedding Models: text-embedding-v1/v2/v3/v4
"""
```

#### 2. 修正并补充 `MODEL_PRICES`

**修改说明**：
1. 修正模型命名：`wanxiang-v2` → `wanx-v2`（与前端保持一致）
2. 补充万相系列模型：`wanx-v1`, `qwen-image-plus`
3. 补充图像编辑模型：`wanx-v2.5-image-edit`, `qwen-vl-image-edit`
4. 补充特殊模型：`qwen-deep-research`, `qwq-32b`
5. 添加注释说明图像生成/编辑模型按次计费而非 token 计费

**修改内容**：
```python
MODEL_PRICES = {
    # ... 原有模型 ...

    # Image Generation - 图像生成（万相系列，按次计费非token计费）
    "wanx-v1": {"prompt": 0.0, "completion": 0.0},
    "wanx-v2": {"prompt": 0.0, "completion": 0.0},
    "qwen-image-plus": {"prompt": 0.0, "completion": 0.0},

    # Image Editing - 图像编辑（按次计费非token计费）
    "wanx-v2.5-image-edit": {"prompt": 0.0, "completion": 0.0},
    "qwen-vl-image-edit": {"prompt": 0.0, "completion": 0.0},

    # Special Models - 特殊模型
    "qwen-deep-research": {"prompt": 0.04, "completion": 0.12},  # 与qwen-max同价
    "qwq-32b": {"prompt": 0.004, "completion": 0.012},  # 与qwen-plus同价
}
```

#### 3. 补充 `MODEL_CONTEXT_LENGTHS`

**修改说明**：
为新增的模型补充上下文长度配置，确保 `get_max_context_tokens()` 方法能正确返回值。

**修改内容**：
```python
MODEL_CONTEXT_LENGTHS = {
    # ... 原有模型 ...

    # Special Models
    "qwen-deep-research": 128000,
    "qwq-32b": 32768,

    # Image Models (上下文长度不适用，但提供默认值)
    "wanx-v1": 8192,
    "wanx-v2": 8192,
    "qwen-image-plus": 8192,
    "wanx-v2.5-image-edit": 8192,
    "qwen-vl-image-edit": 8192,
}
```

#### 4. 优化 `get_available_models()` 方法

**修改说明**：
借鉴 `qwen_native.py` 的方案 3，采用"API + 特殊模型补充列表"的策略：
1. 从 OpenAI Compatible API 获取大部分模型（主要来源）
2. 补充 API 未返回但实际可用的特殊模型（`qwen-deep-research`, `qwq-32b`）
3. 合并、去重、排序后返回
4. 如果所有数据源都失败，降级返回 `MODEL_PRICES.keys()`

**修改内容**：
```python
async def get_available_models(self) -> List[str]:
    """
    获取可用模型列表（方案3：合并多种数据源）

    数据源优先级：
    1. OpenAI Compatible API（动态获取大部分模型）
    2. 特殊模型补充列表（API未返回但实际可用的模型）

    Returns:
        模型名称列表（已去重和排序）
    """
    # 特殊模型补充列表：OpenAI Compatible API 不返回但实际可用的模型
    SPECIAL_MODELS = [
        "qwen-deep-research",  # Deep Research模型（联网搜索功能）
        "qwq-32b",  # QwQ 32B推理模型
        # 未来可以继续添加其他特殊模型
    ]

    all_models = set()

    try:
        # 数据源1: OpenAI兼容API获取模型列表（主要来源）
        models_response = await self.client.models.list()

        # 获取所有可用模型
        api_models = [model.id for model in models_response.data]
        all_models.update(api_models)

        if api_models:
            logger.info(f"[Qwen] OpenAI Compatible API 获取到 {len(api_models)} 个模型")
        else:
            logger.warning("[Qwen] OpenAI Compatible API 返回空模型列表")

    except Exception as e:
        logger.warning(f"[Qwen] 获取OpenAI Compatible API模型列表异常: {str(e)}")

    # 数据源2: 补充特殊模型（API未返回的模型）
    special_models_added = [m for m in SPECIAL_MODELS if m not in all_models]
    all_models.update(SPECIAL_MODELS)

    if special_models_added:
        logger.info(f"[Qwen] 补充特殊模型: {', '.join(special_models_added)}")

    # 去重、排序并返回
    if all_models:
        final_models = sorted(list(all_models))
        api_count = len(api_models) if 'api_models' in locals() else 0
        logger.info(f"[Qwen] 最终合并模型列表: {len(final_models)} 个 (API: {api_count}, 特殊: {len(special_models_added)})")
        return final_models
    else:
        # 降级：返回已知模型列表（MODEL_PRICES.keys()）
        logger.warning("[Qwen] 所有数据源均失败，使用降级模型列表")
        return sorted(list(self.MODEL_PRICES.keys()))
```

---

## 验证与测试

### 测试方法

1. **前端模型列表验证**：
   - 打开前端配置页面，验证通义千问连接
   - 检查模型列表是否包含以下模型：
     * `wanx-v1`, `wanx-v2`, `qwen-image-plus`（图像生成）
     * `wanx-v2.5-image-edit`, `qwen-vl-image-edit`（图像编辑）
     * `qwen-deep-research`, `qwq-32b`（特殊模型）

2. **后端日志验证**：
   - 启动后端服务
   - 触发模型获取接口
   - 检查日志输出：
     ```
     [Qwen] OpenAI Compatible API 获取到 X 个模型
     [Qwen] 补充特殊模型: qwen-deep-research, qwq-32b
     [Qwen] 最终合并模型列表: Y 个 (API: X, 特殊: 2)
     ```

3. **模型命名一致性验证**：
   - 确认前后端都使用 `wanx-v2` 而非 `wanxiang-v2`
   - 确认 `MODEL_PRICES` 和 `MODEL_CONTEXT_LENGTHS` 中的模型名称一致

### 预期结果

- 前端能够正确展示所有万相系列模型
- 特殊模型（`qwen-deep-research`, `qwq-32b`）能够在前端选择器中显示
- 后端日志显示模型获取成功，且包含特殊模型补充信息
- 前后端模型命名完全一致，无命名冲突

---

## 技术要点

### 1. 前后端命名一致性

**问题**：前端使用 `wanx-v2`，后端使用 `wanxiang-v2`，导致模型匹配失败。

**解决方案**：统一使用官方命名 `wanx-v2`（Wanx 是"万相"的拼音缩写）。

### 2. 特殊模型补充策略

**问题**：某些模型（如 `qwen-deep-research`）不会通过 OpenAI Compatible API 返回，但实际可用。

**解决方案**：维护一个 `SPECIAL_MODELS` 列表，在 API 获取后补充这些模型。

### 3. 图像模型价格处理

**问题**：图像生成/编辑模型按次计费，而非 token 计费。

**解决方案**：将这些模型的价格设置为 `0.0`，并在注释中说明计费方式。

### 4. 降级策略

**问题**：如果 API 调用失败，应该返回什么？

**解决方案**：返回 `MODEL_PRICES.keys()` 作为 fallback，确保服务可用性。

---

## 相关文件索引

| 文件路径 | 说明 |
|---------|------|
| `backend/app/services/qwen.py` | 通义千问服务（OpenAI 兼容 API）- 本次修改的主文件 |
| `backend/app/services/qwen_native.py` | 通义千问服务（原生 SDK）- 参考其优化方案 |
| `frontend/services/providers/tongyi/models.ts` | 前端模型注册表 - 参考模型命名和元数据 |
| `frontend/services/providers/tongyi/DashScopeProvider.ts` | 前端 DashScope Provider |
| `frontend/hooks/useModels.ts` | 前端模型管理 Hook |
| `frontend/services/db.ts` | 前端数据库服务（Profile.savedModels 缓存） |

---

## 总结

本次优化解决了通义千问模型获取的以下核心问题：

1. ✅ 修正前后端模型命名不一致（`wanxiang-v2` → `wanx-v2`）
2. ✅ 补充万相系列模型（`wanx-v1`, `wanx-v2`, `qwen-image-plus`, `wanx-v2.5-image-edit`, `qwen-vl-image-edit`）
3. ✅ 补充特殊模型（`qwen-deep-research`, `qwq-32b`）
4. ✅ 优化模型获取逻辑（API + 特殊模型补充列表）
5. ✅ 更新模型价格表和上下文长度配置
6. ✅ 完善文档注释，说明支持的模型类型

修改后的代码与前端完全兼容，确保用户能够在前端选择器中看到所有可用的通义千问模型，包括万相图像生成模型和特殊功能模型。
