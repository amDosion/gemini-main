# 添加新的 AI 模型

为现有提供商添加一个新的 AI 模型配置。

## 执行步骤

### 1. 确定模型能力

首先确定模型支持的功能：
- `chat` - 文本对话
- `vision` - 图像理解
- `image-gen` - 图像生成
- `image-edit` - 图像编辑
- `video-gen` - 视频生成
- `audio-gen` - 音频生成
- `code` - 代码生成
- `search` - 网络搜索
- `thinking` - 思考过程

### 2. 后端：添加模型能力配置

```python
# backend/app/services/common/model_capabilities.py

MODEL_CAPABILITIES = {
    # ... 现有模型

    "[model-id]": {
        "provider": "[provider-id]",
        "capabilities": ["chat", "vision"],  # 模型能力
        "context_window": 128000,  # 上下文窗口
        "max_output_tokens": 8192,  # 最大输出
        "supports_streaming": True,
        "supports_tools": True,
        "supports_system_prompt": True,
        "pricing": {
            "input": 0.0001,   # 每1K tokens价格
            "output": 0.0003
        }
    }
}
```

### 3. 前端：添加模型过滤配置

```typescript
// frontend/utils/modelFilter.ts

export const MODEL_CONFIGS: Record<string, ModelConfig> = {
  // ... 现有模型

  "[model-id]": {
    provider: "[provider-id]",
    capabilities: ["chat", "vision"],
    contextWindow: 128000,
    maxOutputTokens: 8192,
    supportsStreaming: true,
    supportsTools: true,
    // 模式支持
    supportedModes: ["chat", "image-gen"],
    // 是否为默认模型
    isDefault: false,
    // 是否隐藏
    hidden: false
  }
};
```

### 4. 添加模型显示名称（可选）

```typescript
// frontend/utils/modelFilter.ts 或相关配置

export const MODEL_DISPLAY_NAMES: Record<string, string> = {
  // ... 现有
  "[model-id]": "[模型显示名称]"
};
```

### 5. 更新提供商默认模型（如需要）

```python
# backend/app/services/common/provider_config.py

PROVIDER_CONFIGS = {
    "[provider]": ProviderConfig(
        # ...
        default_model="[new-model-id]",  # 更新默认模型
        # ...
    )
}
```

## 模型 ID 命名约定

- 使用提供商官方的模型 ID
- 例如：`gemini-2.0-flash-exp`, `gpt-4o`, `qwen-vl-max`

## 检查清单

- [ ] 后端：model_capabilities.py 添加能力配置
- [ ] 前端：modelFilter.ts 添加过滤配置
- [ ] 前端：添加显示名称（可选）
- [ ] 更新提供商默认模型（如需要）
- [ ] 测试模型在各模式下的可用性

## 使用示例

```
/add-model 添加 Gemini 2.0 Flash 模型，支持聊天、视觉和代码生成
```

```
/add-model 添加 GPT-4o-mini 模型，是一个轻量级的视觉模型
```
