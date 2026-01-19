# 如何添加新的 AI 提供商

## 问题说明

**重要提示**：提供商配置**不是**在前端的 `SettingsModal.tsx` 中配置的，而是从后端 API 动态加载的。

前端通过 `/api/providers/templates` API 获取所有可用的提供商配置，这些配置定义在后端的 `ProviderConfig` 类中。

## 添加新提供商的步骤

### 1. 修改后端配置文件

编辑文件：`backend/app/services/common/provider_config.py`

在 `ProviderConfig.CONFIGS` 字典中添加新的提供商配置：

```python
CONFIGS: Dict[str, Dict[str, Any]] = {
    # ... 现有配置 ...
    
    "your-provider-id": {
        "base_url": "https://api.example.com/v1",  # 提供商的 API 基础 URL
        "default_model": "model-name",              # 默认模型名称
        "client_type": "openai",                    # 客户端类型：openai, google, ollama, dashscope 等
        "supports_streaming": True,                  # 是否支持流式响应
        "supports_function_call": True,              # 是否支持函数调用
        "supports_vision": False,                    # 是否支持视觉功能
        "supports_thinking": False,                  # 是否支持思考模式
        "supports_web_search": False,                # 是否支持网络搜索
        "supports_code_execution": False,            # 是否支持代码执行
        "name": "Your Provider Name",                # 显示名称
        "description": "Provider description",      # 描述信息
        "icon": "provider-icon",                     # 图标名称（用于前端显示）
        "is_custom": False,                          # 是否为自定义提供商
    },
}
```

### 2. 配置字段说明

#### 必需字段
- `base_url`: API 基础 URL
- `default_model`: 默认模型名称
- `client_type`: 客户端类型（决定使用哪个服务类）
  - `"openai"`: 使用 OpenAI 兼容 API
  - `"google"`: 使用 Google Gemini API
  - `"ollama"`: 使用 Ollama API
  - `"dashscope"`: 使用阿里云 DashScope API
  - `"anthropic"`: 使用 Anthropic API
  - `"zhipuai"`: 使用智谱 AI API
  - `"nvidia"`: 使用 NVIDIA API
- `name`: 提供商显示名称
- `description`: 提供商描述
- `icon`: 图标名称

#### 可选字段
- `supports_streaming`: 是否支持流式响应（默认：True）
- `supports_function_call`: 是否支持函数调用（默认：False）
- `supports_vision`: 是否支持视觉功能（默认：False）
- `supports_thinking`: 是否支持思考模式（默认：False）
- `supports_web_search`: 是否支持网络搜索（默认：False）
- `supports_code_execution`: 是否支持代码执行（默认：False）
- `is_custom`: 是否为自定义提供商（默认：False）
- `modes`: 支持的特殊模式列表（如 Google 的图像编辑模式）
- `platform_routing`: 平台路由配置（如 Vertex AI vs Developer API）

### 3. 客户端类型选择

根据提供商的 API 兼容性选择正确的 `client_type`：

- **OpenAI 兼容 API** (`client_type: "openai"`): 
  - 大多数现代 AI 提供商都兼容 OpenAI API 格式
  - 例如：DeepSeek, SiliconFlow, Moonshot, Zhipu, Doubao, Hunyuan, NVIDIA, OpenRouter 等

- **Google Gemini API** (`client_type: "google"`):
  - 仅用于 Google Gemini 官方 API
  - 支持特殊功能：Vision, Search, Thinking, Code Execution

- **Ollama API** (`client_type: "ollama"`):
  - 用于本地 Ollama 服务
  - 支持动态能力检测

- **DashScope API** (`client_type: "dashscope"`):
  - 用于阿里云通义千问
  - 支持原生和 OpenAI 兼容两种模式

### 4. 验证配置

配置添加后，系统会自动验证配置的完整性。如果配置有误，会在后端日志中显示警告。

### 5. 重启后端服务

修改配置后，需要重启后端服务使配置生效：

```bash
# 停止当前服务（Ctrl+C）
# 然后重新启动
npm run dev
# 或
npm run server
```

### 6. 前端自动更新

前端会在以下情况自动加载新的提供商配置：
- 应用启动时（通过 `useInitData` hook）
- 打开设置模态框时（通过 `EditorTab` 组件）
- 调用 `getProviderTemplates()` 时（带缓存）

**无需修改前端代码**，新添加的提供商会自动出现在设置界面的提供商列表中。

## 示例：添加一个新的 OpenAI 兼容提供商

假设要添加一个名为 "Example AI" 的提供商：

```python
"example-ai": {
    "base_url": "https://api.example-ai.com/v1",
    "default_model": "example-model",
    "client_type": "openai",
    "supports_streaming": True,
    "supports_function_call": True,
    "supports_vision": False,
    "supports_thinking": False,
    "supports_web_search": False,
    "supports_code_execution": False,
    "name": "Example AI",
    "description": "Example AI provider with OpenAI-compatible API.",
    "icon": "settings",  # 使用通用设置图标
    "is_custom": False,
},
```

添加后，用户就可以在设置界面中选择 "Example AI" 并配置 API Key 了。

## 故障排除

### 问题：新添加的提供商没有出现在前端

**解决方案**：
1. 确认后端服务已重启
2. 检查浏览器控制台是否有错误
3. 清除前端缓存：在浏览器控制台执行 `localStorage.clear()` 并刷新页面
4. 检查后端日志，确认配置验证通过

### 问题：配置验证失败

**解决方案**：
1. 检查所有必需字段是否都已填写
2. 确认 `client_type` 是有效值之一
3. 查看后端日志中的具体错误信息

### 问题：提供商无法连接

**解决方案**：
1. 确认 `base_url` 正确
2. 确认 API Key 格式正确
3. 检查网络连接
4. 查看后端日志中的详细错误信息

## 相关文件

- 后端配置：`backend/app/services/common/provider_config.py`
- 后端 API：`backend/app/routers/models/providers.py`
- 前端服务：`frontend/services/providers.ts`
- 前端组件：`frontend/components/modals/settings/EditorTab.tsx`
