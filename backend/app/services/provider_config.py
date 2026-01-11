"""
Provider 配置管理

职责：
- 集中管理所有 Provider 的配置信息
- 提供配置访问工具方法
- 支持 Provider 列表查询
- 配置验证

设计理念：
- 声明式配置：通过配置字典定义 Provider
- 配置驱动：Factory 根据配置自动注册 Provider
- 易扩展：新增 Provider 只需添加配置项

参考: backend/app/services/参考文件-providers.py
创建时间: 2026-01-02
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class ProviderConfig:
    """Provider 配置管理类"""
    
    # Provider 配置字典
    # 格式: provider_id -> {base_url, default_model, client_type, name, description, icon, is_custom, ...}
    CONFIGS: Dict[str, Dict[str, Any]] = {
        "google": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "default_model": "gemini-2.0-flash-exp",
            "client_type": "google",
            "supports_streaming": True,
            "supports_function_call": True,
            "supports_vision": True,
            "supports_thinking": True,
            "supports_web_search": True,
            "supports_code_execution": True,
            "name": "Google Gemini",
            "description": "Native Google SDK. Supports Vision, Search & Thinking.",
            "icon": "gemini",
            "is_custom": False,
            # Google-specific modes (image editing operations)
            "modes": [
                "image-outpainting",
                "image-inpainting",
                "virtual-try-on",
                "product-background-edit"
            ],
            # Platform routing configuration
            "platform_routing": {
                "vertex": True,           # Supports Vertex AI
                "developer": True,        # Supports Developer API
                "default_platform": "developer"
            },
        },
        "google-custom": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "default_model": "gemini-2.5-flash",
            "client_type": "google",
            "supports_streaming": True,
            "supports_function_call": True,
            "name": "Google Compatible",
            "description": "Custom Google Protocol endpoint (e.g. Vertex Proxy).",
            "icon": "gemini",
            "is_custom": True,
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o",
            "client_type": "openai",
            "supports_streaming": True,
            "supports_function_call": True,
            "supports_vision": True,
            "supports_thinking": False,
            "supports_web_search": False,
            "supports_code_execution": False,
            "name": "OpenAI",
            "description": "Standard OpenAI API.",
            "icon": "openai",
            "is_custom": False,
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
            "client_type": "openai",
            "supports_streaming": True,
            "supports_function_call": True,
            "supports_vision": False,
            "supports_thinking": True,  # DeepSeek R1 supports reasoning
            "supports_web_search": False,
            "supports_code_execution": False,
            "name": "DeepSeek",
            "description": "DeepSeek V3 & R1 (Reasoning).",
            "icon": "deepseek",
            "is_custom": False,
        },
        "tongyi": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "default_model": "qwen-max",
            "client_type": "dashscope",
            "supports_streaming": True,
            "supports_function_call": True,
            "supports_vision": True,
            "supports_thinking": True,
            "supports_web_search": True,
            "supports_code_execution": True,
            "name": "Aliyun TongYi",
            "description": "Qwen models via DashScope.",
            "icon": "qwen",
            "is_custom": False,
            # Dual-client support (OPTIONAL - already implemented in QwenNativeProvider)
            "secondary_client_type": "openai",
            "secondary_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        },
        "siliconflow": {
            "base_url": "https://api.siliconflow.cn/v1",
            "default_model": "Qwen/Qwen2.5-7B-Instruct",
            "client_type": "openai",
            "supports_streaming": True,
            "supports_function_call": True,
            "supports_vision": False,
            "supports_thinking": False,
            "supports_web_search": False,
            "supports_code_execution": False,
            "name": "SiliconFlow",
            "description": "High-performance inference (Qwen, DeepSeek, etc).",
            "icon": "silicon",
            "is_custom": False,
        },
        "moonshot": {
            "base_url": "https://api.moonshot.cn/v1",
            "default_model": "moonshot-v1-8k",
            "client_type": "openai",
            "supports_streaming": True,
            "supports_function_call": True,
            "supports_vision": False,
            "supports_thinking": False,
            "supports_web_search": False,
            "supports_code_execution": False,
            "name": "Moonshot",
            "description": "Kimi AI models.",
            "icon": "moonshot",
            "is_custom": False,
        },
        "zhipu": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "default_model": "glm-4-plus",
            "client_type": "openai",
            "supports_streaming": True,
            "supports_function_call": True,
            "supports_vision": False,
            "supports_thinking": False,
            "supports_web_search": False,
            "supports_code_execution": False,
            "name": "ZhiPu AI",
            "description": "ChatGLM models.",
            "icon": "glm",
            "is_custom": False,
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3",
            "client_type": "ollama",  # Changed from "openai" to "ollama" for dedicated service
            "supports_streaming": True,
            "supports_function_call": False,  # Dynamic detection via /api/show
            "supports_vision": False,         # Dynamic detection via /api/show
            "supports_thinking": False,       # Dynamic detection via /api/show
            "name": "Ollama",
            "description": "Local models. Ensure CORS is enabled.",
            "icon": "ollama",
            "is_custom": False,
            # Dual-API support (OPTIONAL - already implemented in OllamaService)
            # Primary: OpenAI-compatible API (/v1/*) for chat
            # Secondary: Native Ollama API (/api/*) for model management, embedding, capabilities
            "secondary_base_url": "http://localhost:11434",  # Native API endpoint
        },
        "custom": {
            "base_url": "",
            "default_model": "",
            "client_type": "openai",
            "supports_streaming": True,
            "supports_function_call": True,
            "supports_vision": False,
            "supports_thinking": False,
            "supports_web_search": False,
            "supports_code_execution": False,
            "name": "Custom OpenAI",
            "description": "Connect to any OpenAI compatible endpoint.",
            "icon": "settings",
            "is_custom": True,
        },
    }
    
    @classmethod
    def get_config(cls, provider: str) -> Dict[str, Any]:
        """获取 Provider 配置
        
        Args:
            provider: Provider 标识
        
        Returns:
            配置字典，如果不存在返回空字典
        """
        return cls.CONFIGS.get(provider, {})
    
    @classmethod
    def get_base_url(cls, provider: str) -> Optional[str]:
        """获取 Base URL
        
        Args:
            provider: Provider 标识
        
        Returns:
            Base URL，如果不存在返回 None
        """
        return cls.CONFIGS.get(provider, {}).get("base_url")
    
    @classmethod
    def get_default_model(cls, provider: str) -> Optional[str]:
        """获取默认模型
        
        Args:
            provider: Provider 标识
        
        Returns:
            默认模型，如果不存在返回 None
        """
        return cls.CONFIGS.get(provider, {}).get("default_model")
    
    @classmethod
    def get_client_type(cls, provider: str) -> Optional[str]:
        """获取客户端类型
        
        Args:
            provider: Provider 标识
        
        Returns:
            客户端类型（openai, google, ollama 等），如果不存在返回 None
        """
        return cls.CONFIGS.get(provider, {}).get("client_type")
    
    @classmethod
    def supports_streaming(cls, provider: str) -> bool:
        """是否支持流式响应
        
        Args:
            provider: Provider 标识
        
        Returns:
            是否支持流式响应
        """
        return cls.CONFIGS.get(provider, {}).get("supports_streaming", False)
    
    @classmethod
    def supports_function_call(cls, provider: str) -> bool:
        """是否支持函数调用
        
        Args:
            provider: Provider 标识
        
        Returns:
            是否支持函数调用
        """
        return cls.CONFIGS.get(provider, {}).get("supports_function_call", False)
    
    @classmethod
    def supports_vision(cls, provider: str) -> bool:
        """是否支持视觉输入
        
        Args:
            provider: Provider 标识
        
        Returns:
            是否支持视觉输入
        """
        return cls.CONFIGS.get(provider, {}).get("supports_vision", False)
    
    @classmethod
    def supports_thinking(cls, provider: str) -> bool:
        """是否支持思考模式
        
        Args:
            provider: Provider 标识
        
        Returns:
            是否支持思考模式
        """
        return cls.CONFIGS.get(provider, {}).get("supports_thinking", False)
    
    @classmethod
    def supports_web_search(cls, provider: str) -> bool:
        """是否支持网页搜索
        
        Args:
            provider: Provider 标识
        
        Returns:
            是否支持网页搜索
        """
        return cls.CONFIGS.get(provider, {}).get("supports_web_search", False)
    
    @classmethod
    def supports_code_execution(cls, provider: str) -> bool:
        """是否支持代码执行
        
        Args:
            provider: Provider 标识
        
        Returns:
            是否支持代码执行
        """
        return cls.CONFIGS.get(provider, {}).get("supports_code_execution", False)
    
    @classmethod
    def get_secondary_client_type(cls, provider: str) -> Optional[str]:
        """获取次要客户端类型（双客户端支持）
        
        Args:
            provider: Provider 标识
        
        Returns:
            次要客户端类型，如果不存在返回 None
        """
        return cls.CONFIGS.get(provider, {}).get("secondary_client_type")
    
    @classmethod
    def get_secondary_base_url(cls, provider: str) -> Optional[str]:
        """获取次要客户端 Base URL（双客户端支持）
        
        Args:
            provider: Provider 标识
        
        Returns:
            次要客户端 Base URL，如果不存在返回 None
        """
        return cls.CONFIGS.get(provider, {}).get("secondary_base_url")
    
    @classmethod
    def has_dual_client_support(cls, provider: str) -> bool:
        """检查是否支持双客户端模式
        
        Args:
            provider: Provider 标识
        
        Returns:
            是否支持双客户端
        """
        config = cls.CONFIGS.get(provider, {})
        return "secondary_client_type" in config or "secondary_base_url" in config
    
    @classmethod
    def get_modes(cls, provider: str) -> List[str]:
        """获取 Provider 支持的模式列表（如 Google 图像编辑模式）
        
        Args:
            provider: Provider 标识
        
        Returns:
            模式列表，如果不存在返回空列表
        """
        return cls.CONFIGS.get(provider, {}).get("modes", [])
    
    @classmethod
    def get_platform_routing(cls, provider: str) -> Optional[Dict[str, Any]]:
        """获取平台路由配置（如 Google Vertex AI vs Developer API）
        
        Args:
            provider: Provider 标识
        
        Returns:
            平台路由配置，如果不存在返回 None
        """
        return cls.CONFIGS.get(provider, {}).get("platform_routing")
    
    @classmethod
    def list_all_providers(cls) -> List[Dict[str, Any]]:
        """列出所有可用的 Provider
        
        返回格式（统一使用 camelCase）：
        {
            "value": "openai",                # Provider 标识
            "label": "OpenAI (ChatGPT)",      # 友好的中文名称
            "defaultUrl": "https://...",      # 默认API地址
            "defaultModel": "gpt-4o",         # 默认模型
            "clientType": "openai",           # SDK类型
            "supportsStreaming": true,        # 是否支持流式
            "supportsFunctionCall": true      # 是否支持函数调用
        }
        
        Returns:
            Provider 信息列表
        """
        # Provider 友好名称映射（中文 + 英文）
        provider_labels = {
            "openai": "OpenAI (ChatGPT)",
            "google": "Google Gemini",
            "ollama": "Ollama（本地部署）",
            "deepseek": "DeepSeek",
            "moonshot": "月之暗面 (Kimi)",
            "siliconflow": "硅基流动 (SiliconFlow)",
            "zhipu": "智谱AI (GLM)",
            "tongyi": "阿里通义千问 (Qwen)",
        }
        
        providers = []
        for provider_id, config in cls.CONFIGS.items():
            providers.append({
                # 统一使用 camelCase 命名（前端标准）
                "value": provider_id,
                "label": provider_labels.get(provider_id, provider_id),
                "defaultUrl": config.get("base_url"),
                "defaultModel": config.get("default_model"),
                "clientType": config.get("client_type"),
                "supportsStreaming": config.get("supports_streaming"),
                "supportsFunctionCall": config.get("supports_function_call"),
            })
        
        return providers
    
    @classmethod
    def validate_config(cls, provider: str) -> bool:
        """验证配置完整性
        
        Args:
            provider: Provider 标识
        
        Returns:
            配置是否有效
        """
        config = cls.get_config(provider)
        if not config:
            logger.warning(f"[ProviderConfig] Provider '{provider}' not found in CONFIGS")
            return False
        
        # 必需字段
        required_fields = ["client_type", "default_model", "name", "description", "icon"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            logger.warning(
                f"[ProviderConfig] Provider '{provider}' missing required fields: "
                f"{', '.join(missing_fields)}"
            )
            return False
        
        # 验证 client_type 有效性
        valid_client_types = ["openai", "google", "ollama", "anthropic", "zhipuai", "dashscope"]
        client_type = config.get("client_type")
        if client_type not in valid_client_types:
            logger.warning(
                f"[ProviderConfig] Provider '{provider}' has invalid client_type: "
                f"'{client_type}'. Valid types: {', '.join(valid_client_types)}"
            )
            return False
        
        # 验证双客户端配置一致性
        has_secondary_type = "secondary_client_type" in config
        has_secondary_url = "secondary_base_url" in config
        if has_secondary_type != has_secondary_url:
            logger.warning(
                f"[ProviderConfig] Provider '{provider}' has incomplete dual-client config: "
                f"secondary_client_type={has_secondary_type}, secondary_base_url={has_secondary_url}"
            )
            return False
        
        return True
    
    @classmethod
    def validate_all_configs(cls) -> Dict[str, bool]:
        """验证所有配置
        
        Returns:
            字典，key 为 provider_id，value 为验证结果
        """
        results = {}
        for provider_id in cls.CONFIGS.keys():
            results[provider_id] = cls.validate_config(provider_id)
        
        # 记录验证结果
        valid_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        logger.info(
            f"[ProviderConfig] Validated {total_count} providers: "
            f"{valid_count} valid, {total_count - valid_count} invalid"
        )
        
        # 记录双客户端支持的 Provider
        dual_client_providers = [
            provider_id for provider_id in cls.CONFIGS.keys()
            if cls.has_dual_client_support(provider_id)
        ]
        if dual_client_providers:
            logger.info(
                f"[ProviderConfig] Providers with dual-client support: "
                f"{', '.join(dual_client_providers)}"
            )
        
        return results
    
    @classmethod
    def _map_client_type_to_protocol(cls, client_type: str) -> str:
        """将 client_type 映射到前端的 protocol
        
        Args:
            client_type: 后端的 client_type (openai, google, dashscope 等)
        
        Returns:
            前端的 protocol (openai, google)
        """
        if client_type == "google":
            return "google"
        # 大部分 OpenAI 兼容的 Provider 使用 openai protocol
        return "openai"
    
    @classmethod
    def get_provider_templates(cls) -> List[Dict[str, Any]]:
        """获取所有 Provider Templates（前端格式）
        
        返回格式（统一使用 camelCase）：
        {
            "id": "google",
            "name": "Google Gemini",
            "protocol": "google",
            "baseUrl": "https://...",
            "defaultModel": "gemini-2.0-flash-exp",
            "description": "Native Google SDK...",
            "isCustom": false,
            "icon": "gemini",
            "capabilities": {
                "streaming": true,
                "functionCall": true,
                "vision": true,
                "thinking": true,
                "webSearch": true,
                "codeExecution": true
            },
            "dualClient": {
                "supported": true,
                "secondaryType": "openai",
                "secondaryBaseUrl": "https://..."
            },
            "modes": ["image-outpainting", ...],
            "platformRouting": {...}
        }
        
        Returns:
            Provider Templates 列表
        """
        templates = []
        for provider_id, config in cls.CONFIGS.items():
            template = {
                "id": provider_id,
                "name": config.get("name", provider_id),
                "protocol": cls._map_client_type_to_protocol(config.get("client_type", "openai")),
                "baseUrl": config.get("base_url", ""),
                "defaultModel": config.get("default_model"),
                "description": config.get("description", ""),
                "isCustom": config.get("is_custom", False),
                "icon": config.get("icon"),
                "capabilities": {
                    "streaming": config.get("supports_streaming", False),
                    "functionCall": config.get("supports_function_call", False),
                    "vision": config.get("supports_vision", False),
                    "thinking": config.get("supports_thinking", False),
                    "webSearch": config.get("supports_web_search", False),
                    "codeExecution": config.get("supports_code_execution", False),
                }
            }
            
            # 添加双客户端配置（如果存在）
            if cls.has_dual_client_support(provider_id):
                template["dualClient"] = {
                    "supported": True,
                    "secondaryType": config.get("secondary_client_type"),
                    "secondaryBaseUrl": config.get("secondary_base_url"),
                }
            
            # 添加模式列表（如果存在）
            modes = config.get("modes")
            if modes:
                template["modes"] = modes
            
            # 添加平台路由配置（如果存在）
            platform_routing = config.get("platform_routing")
            if platform_routing:
                template["platformRouting"] = platform_routing
            
            templates.append(template)
        
        logger.info(f"[ProviderConfig] Generated {len(templates)} provider templates")
        return templates
