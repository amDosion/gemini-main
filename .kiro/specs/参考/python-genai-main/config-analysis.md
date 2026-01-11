# Gemini API 配置参数分析

## ⚠️ 重要更新 (2025-01-08)

**发现错误**: 之前文档中提到的 `BLOCK_ALL` 和 `ALLOW_MINOR` **不存在于官方 SDK**。

**正确的 person_generation 参数值**:
- `DONT_ALLOW` - 阻止生成所有人物
- `ALLOW_ADULT` - 只生成成人,不生成儿童 (默认)
- `ALLOW_ALL` - 生成成人和儿童

详见: `.kiro/specs/erron/person-generation-truth.md`

---

## 概述

本文档对比 Google GenAI SDK 的 `GenerateContentConfig` Schema 和当前项目 `image_generator.py` 的实现，识别可以添加的新配置参数。

## 当前实现的参数（已支持）

| 参数名 | 类型 | 说明 | 当前实现 |
|--------|------|------|----------|
| `number_of_images` | int | 生成图像数量 (1-4) | ✅ 已实现 |
| `aspect_ratio` | string | 宽高比 | ✅ 已实现 |
| `image_size` | string | 图像尺寸 (1K/2K/4K) | ✅ 已实现 |
| `image_style` | string | 图像风格 | ✅ 已实现 |
| `negative_prompt` | string | 负面提示词 | ✅ 已实现 (Vertex AI) |
| `guidance_scale` | float | 引导强度 (1.0-20.0) | ✅ 已实现 |
| `seed` | int | 随机种子 | ✅ 已实现 (Vertex AI) |
| `person_generation` | string | 人物生成设置 | ✅ 已实现 (DONT_ALLOW/ALLOW_ADULT/ALLOW_ALL) |
| `include_rai_reason` | bool | 包含 RAI 原因 | ✅ 已实现 |
| `include_safety_attributes` | bool | 包含安全属性 | ✅ 已实现 |
| `output_mime_type` | string | 输出格式 | ✅ 已实现 |
| `output_compression_quality` | int | 压缩质量 (1-100) | ✅ 已实现 |
| `enhance_prompt` | bool | 增强提示词 | ✅ 已实现 (Vertex AI) |
| `labels` | dict | 自定义标签 | ✅ 已实现 (Vertex AI) |

## Schema 中可添加的新参数

### 🔥 高优先级（强烈推荐添加）

#### 1. `systemInstruction` - 系统指令
```python
{
    "type": ["Content", "string", "File", "Part", "array", "null"],
    "description": "Instructions for the model to steer it toward better performance."
}
```

**用途**：
- 设置全局的图像风格指导
- 控制模型行为和输出特征
- 提供上下文信息

**示例**：
```python
system_instruction = "Generate photorealistic images with vibrant colors and high detail"
```

#### 2. `safetySettings` - 安全设置（数组）
```python
{
    "type": "array",
    "items": {"$ref": "#/$defs/SafetySetting"}
}
```

**SafetySetting 结构**：
```python
{
    "category": "HARM_CATEGORY_*",  # 安全类别
    "threshold": "BLOCK_*"          # 阻止阈值
}
```

**安全类别**：
- `HARM_CATEGORY_HATE_SPEECH` - 仇恨言论
- `HARM_CATEGORY_DANGEROUS_CONTENT` - 危险内容
- `HARM_CATEGORY_HARASSMENT` - 骚扰
- `HARM_CATEGORY_SEXUALLY_EXPLICIT` - 性暴露内容

**阈值选项**：
- `BLOCK_NONE` - 不阻止
- `BLOCK_LOW_AND_ABOVE` - 阻止低及以上
- `BLOCK_MEDIUM_AND_ABOVE` - 阻止中及以上
- `BLOCK_ONLY_HIGH` - 仅阻止高风险

**优势**：
- 比当前的简单布尔值 `include_safety_attributes` 更灵活
- 可以针对不同类别设置不同阈值
- 更精细的内容控制

**示例**：
```python
safety_settings = [
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_ONLY_HIGH"
    }
]
```

#### 3. `temperature` - 温度参数
```python
{
    "type": "number",
    "description": "Value that controls the degree of randomness in token selection."
}
```

**用途**：
- 控制生成的随机性和多样性
- 较低温度：更确定、一致的输出
- 较高温度：更多样、创意的输出

**范围**：通常 0.0 - 2.0

**示例**：
```python
temperature = 0.7  # 平衡创意和一致性
```

#### 4. `mediaResolution` - 媒体分辨率
```python
{
    "$ref": "#/$defs/MediaResolution",
    "description": "If specified, the media resolution specified will be used."
}
```

**可能的值**：
- `MEDIA_RESOLUTION_LOW` - 低分辨率
- `MEDIA_RESOLUTION_MEDIUM` - 中分辨率
- `MEDIA_RESOLUTION_HIGH` - 高分辨率

**用途**：
- 控制输入媒体的处理分辨率
- 影响处理速度和质量

### ⚡ 中优先级（建议添加）

#### 5. `topP` - 核采样
```python
{
    "type": "number",
    "description": "Tokens are selected from most to least probable until sum equals this value."
}
```

**用途**：
- 控制采样的概率分布
- 与 temperature 配合使用

**范围**：0.0 - 1.0

#### 6. `topK` - Top-K 采样
```python
{
    "type": "number",
    "description": "For each token selection step, the top_k tokens with highest probabilities are sampled."
}
```

**用途**：
- 限制采样的候选数量
- 控制输出的多样性

#### 7. `candidateCount` - 候选数量
```python
{
    "type": "integer",
    "description": "Number of response variations to return."
}
```

**用途**：
- 生成多个候选结果
- 用户可以选择最佳结果

#### 8. `responseModalities` - 响应模态
```python
{
    "type": "array",
    "items": {"type": "string"},
    "description": "The requested modalities of the response."
}
```

**用途**：
- 指定期望的输出模态（图像、文本等）
- 支持多模态输出

#### 9. `thinkingConfig` - 思考配置
```python
{
    "$ref": "#/$defs/ThinkingConfig",
    "description": "The thinking features configuration."
}
```

**用途**：
- 启用模型的"思考"过程
- 可能提供更好的推理结果

#### 10. `routingConfig` - 路由配置
```python
{
    "$ref": "#/$defs/GenerationConfigRoutingConfig",
    "description": "Configuration for model router requests."
}
```

**用途**：
- 自动选择最佳模型
- 负载均衡

### 📋 低优先级（暂不需要）

以下参数主要用于文本生成或特定场景，对图像生成用处不大：

- `maxOutputTokens` - 最大输出令牌（文本相关）
- `stopSequences` - 停止序列（文本相关）
- `responseLogprobs` - 返回对数概率（文本相关）
- `logprobs` - 对数概率数量（文本相关）
- `presencePenalty` - 存在惩罚（文本相关）
- `frequencyPenalty` - 频率惩罚（文本相关）
- `responseMimeType` - 响应 MIME 类型（已有 output_mime_type）
- `responseSchema` - 响应模式（结构化输出，不适用）
- `tools` - 工具配置（函数调用，不适用）
- `toolConfig` - 工具配置（不适用）
- `automaticFunctionCalling` - 自动函数调用（不适用）
- `speechConfig` - 语音配置（不适用）
- `audioTimestamp` - 音频时间戳（不适用）
- `cachedContent` - 缓存内容（性能优化，后期考虑）
- `enableEnhancedCivicAnswers` - 增强公民答案（特定场景）

## 实施建议

### 阶段 1：立即实施（高优先级）

1. **添加 `systemInstruction` 支持**
   - 前端添加输入框
   - 后端添加参数验证
   - 传递给 SDK

2. **升级 `safetySettings` 为数组形式**
   - 保留 `include_safety_attributes` 作为简化选项
   - 添加高级安全设置数组
   - 提供预设配置（宽松/标准/严格）

3. **添加 `temperature` 参数**
   - 前端添加滑块控件（0.0-2.0）
   - 默认值：0.7
   - 添加说明文字

4. **添加 `mediaResolution` 参数**
   - 前端添加下拉选择
   - 选项：低/中/高
   - 默认：中

### 阶段 2：后续优化（中优先级）

1. **添加 `topP` 和 `topK`**
   - 高级设置面板
   - 默认值：topP=0.95, topK=40

2. **添加 `candidateCount`**
   - 允许生成多个候选
   - 前端展示所有候选供选择

3. **探索 `thinkingConfig`**
   - 测试是否支持
   - 评估效果

### 阶段 3：性能优化（低优先级）

1. **添加 `cachedContent`**
   - 缓存常用配置
   - 提高响应速度

2. **添加 `routingConfig`**
   - 自动模型选择
   - 负载均衡

## 配置示例

### 基础配置（当前）
```python
config = {
    "number_of_images": 1,
    "aspect_ratio": "1:1",
    "image_size": "2K",
    "guidance_scale": 7.5,
    "output_mime_type": "image/png"
}
```

### 增强配置（添加新参数后）
```python
config = {
    # 基础参数
    "number_of_images": 1,
    "aspect_ratio": "16:9",
    "image_size": "4K",
    
    # 生成控制
    "temperature": 0.8,
    "guidance_scale": 10.0,
    "seed": 42,
    
    # 人物生成 (正确的值)
    "person_generation": "DONT_ALLOW",  # 阻止生成人物
    
    # 系统指令
    "system_instruction": "Generate photorealistic images with cinematic lighting",
    
    # 安全设置
    "safety_settings": [
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_ONLY_HIGH"
        }
    ],
    
    # 媒体设置
    "media_resolution": "MEDIA_RESOLUTION_HIGH",
    
    # 输出设置
    "output_mime_type": "image/png",
    "output_compression_quality": 95
}
```

## 参考资料

- Schema 文件：`123_formatted.json`
- 当前实现：`backend/app/services/gemini/image_generator.py`
- Google GenAI SDK 文档：https://ai.google.dev/api/python/google/generativeai
- PersonGeneration 真相：`.kiro/specs/erron/person-generation-truth.md`
