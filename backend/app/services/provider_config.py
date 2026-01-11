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
            "name": "Google Gemini",
            "description": "Native Google SDK. Supports Vision, Search & Thinking.",
            "icon": "gemini",
            "is_custom": False,
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
            "name": "Aliyun TongYi",
            "description": "Qwen models via DashScope.",
            "icon": "qwen",
            "is_custom": False,
        },
        "siliconflow": {
            "base_url": "https://api.siliconflow.cn/v1",
            "default_model": "Qwen/Qwen2.5-7B-Instruct",
            "client_type": "openai",
            "supports_streaming": True,
            "supports_function_call": True,
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
            "name": "ZhiPu AI",
            "description": "ChatGLM models.",
            "icon": "glm",
            "is_custom": False,
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3",
            "client_type": "openai",
            "supports_streaming": True,
            "supports_function_call": False,
            "name": "Ollama",
            "description": "Local models. Ensure CORS is enabled.",
            "icon": "ollama",
            "is_custom": False,
        },
        "custom": {
            "base_url": "",
            "default_model": "",
            "client_type": "openai",
            "supports_streaming": True,
            "supports_function_call": True,
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
        required_fields = ["client_type", "default_model"]
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
            "icon": "gemini"
        }
        
        Returns:
            Provider Templates 列表
        """
        templates = []
        for provider_id, config in cls.CONFIGS.items():
            templates.append({
                "id": provider_id,
                "name": config.get("name", provider_id),
                "protocol": cls._map_client_type_to_protocol(config.get("client_type", "openai")),
                "baseUrl": config.get("base_url", ""),
                "defaultModel": config.get("default_model"),
                "description": config.get("description", ""),
                "isCustom": config.get("is_custom", False),
                "icon": config.get("icon"),
            })
        
        logger.info(f"[ProviderConfig] Generated {len(templates)} provider templates")
        return templates
