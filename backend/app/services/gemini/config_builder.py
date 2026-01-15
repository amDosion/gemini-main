"""
Config Builder Module

Handles building of generation configurations for Google API.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 使用新版 google-genai SDK
try:
    from google.genai import types as genai_types
    GENAI_TYPES_AVAILABLE = True
except ImportError:
    GENAI_TYPES_AVAILABLE = False


class ConfigBuilder:
    """
    Builds generation configurations for Google API.
    
    Handles:
    - Basic generation parameters (temperature, max_tokens, etc.)
    - Tool configurations (search, code execution, grounding)
    - Thinking mode configuration
    """
    
    @staticmethod
    def build_generate_config(**kwargs) -> Dict[str, Any]:
        """
        Convert kwargs to google-genai SDK's generation config format.
        
        Args:
            **kwargs: Configuration parameters:
                - temperature (float): Sampling temperature (0.0-2.0)
                - max_tokens (int): Maximum tokens to generate
                - top_p (float): Nucleus sampling parameter (0.0-1.0)
                - top_k (int): Top-k sampling parameter (>0)
        
        Returns:
            google-genai SDK format config dict with validated parameters
        
        Note:
            - Invalid parameters are logged and skipped
            - max_tokens is converted to max_output_tokens for the SDK
            - Empty config dict is returned if no valid parameters provided
        """
        config = {}
        
        # Temperature
        if 'temperature' in kwargs:
            temp = kwargs['temperature']
            if isinstance(temp, (int, float)) and 0 <= temp <= 2:
                config['temperature'] = temp
            else:
                logger.warning(f"[Config Builder] Invalid temperature: {temp}, skipping")
        
        # Max tokens
        if 'max_tokens' in kwargs:
            max_tokens = kwargs['max_tokens']
            if isinstance(max_tokens, int) and max_tokens > 0:
                config['max_output_tokens'] = max_tokens
            else:
                logger.warning(f"[Config Builder] Invalid max_tokens: {max_tokens}, skipping")
        
        # Top P
        if 'top_p' in kwargs:
            top_p = kwargs['top_p']
            if isinstance(top_p, (int, float)) and 0 <= top_p <= 1:
                config['top_p'] = top_p
            else:
                logger.warning(f"[Config Builder] Invalid top_p: {top_p}, skipping")
        
        # Top K
        if 'top_k' in kwargs:
            top_k = kwargs['top_k']
            if isinstance(top_k, int) and top_k > 0:
                config['top_k'] = top_k
            else:
                logger.warning(f"[Config Builder] Invalid top_k: {top_k}, skipping")
        
        return config
    
    @staticmethod
    def build_generate_config_with_tools(
        enable_search: bool = False,
        enable_thinking: bool = False,
        enable_code_execution: bool = False,
        enable_grounding: bool = False,
        enable_browser: bool = False,
        **kwargs
    ) -> Any:
        """
        构建包含工具配置的生成配置（统一 SDK 方案）

        Args:
            enable_search: 启用 Google Search
            enable_thinking: 启用 Thinking Mode
            enable_code_execution: 启用 Code Execution
            enable_grounding: 启用 Grounding (URL Context)
            enable_browser: 启用 Browser Tools (web_search, read_webpage, selenium_browse)
            **kwargs: 其他配置参数（temperature, max_tokens 等）

        Returns:
            types.GenerateContentConfig 对象
        """
        if not GENAI_TYPES_AVAILABLE:
            raise RuntimeError("google.genai.types not available")
        
        # 基础配置参数
        config_params = {}
        
        # 温度、top_p、top_k 等参数
        if 'temperature' in kwargs:
            temp = kwargs['temperature']
            if isinstance(temp, (int, float)) and 0 <= temp <= 2:
                config_params['temperature'] = temp
        
        if 'max_tokens' in kwargs:
            max_tokens = kwargs['max_tokens']
            if isinstance(max_tokens, int) and max_tokens > 0:
                config_params['max_output_tokens'] = max_tokens
        
        if 'top_p' in kwargs:
            top_p = kwargs['top_p']
            if isinstance(top_p, (int, float)) and 0 <= top_p <= 1:
                config_params['top_p'] = top_p
        
        if 'top_k' in kwargs:
            top_k = kwargs['top_k']
            if isinstance(top_k, int) and top_k > 0:
                config_params['top_k'] = top_k
        
        # ✅ 构建工具列表
        tools = []
        
        # 1. Google Search
        if enable_search:
            tools.append(genai_types.Tool(
                google_search=genai_types.GoogleSearch()
            ))
            logger.info("[Config Builder] Enabled Google Search tool")
        
        # 2. Code Execution
        if enable_code_execution:
            tools.append(genai_types.Tool(
                code_execution=genai_types.ToolCodeExecution()
            ))
            logger.info("[Config Builder] Enabled Code Execution tool")
        
        # 3. Grounding / URL Context
        if enable_grounding:
            tools.append(genai_types.Tool(
                google_maps=genai_types.GoogleMaps()
            ))
            logger.info("[Config Builder] Enabled Grounding (Google Maps) tool")

        # 4. Browser Tools (Function Calling)
        if enable_browser:
            try:
                from .browser import get_tool_declarations
                browser_declarations = get_tool_declarations()
                # 将浏览工具声明转换为 SDK 格式
                function_declarations = []
                for decl in browser_declarations:
                    function_declarations.append(
                        genai_types.FunctionDeclaration(
                            name=decl["name"],
                            description=decl["description"],
                            parameters=decl.get("parameters")
                        )
                    )
                if function_declarations:
                    tools.append(genai_types.Tool(
                        function_declarations=function_declarations
                    ))
                logger.info(f"[Config Builder] Enabled Browser tools: {[d['name'] for d in browser_declarations]}")
            except ImportError as e:
                logger.warning(f"[Config Builder] Browser tools not available: {e}")

        # 添加工具到配置
        if tools:
            config_params['tools'] = tools
        
        # ✅ Thinking Mode 配置
        if enable_thinking:
            thinking_config = genai_types.ThinkingConfig(
                include_thoughts=True  # 返回思考摘要
            )
            config_params['thinking_config'] = thinking_config
            logger.info("[Config Builder] Enabled Thinking Mode with thought summaries")
        
        # 创建 GenerateContentConfig 对象
        return genai_types.GenerateContentConfig(**config_params)
