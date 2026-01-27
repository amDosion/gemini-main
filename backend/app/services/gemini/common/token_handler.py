"""
Gemini Token Counting Handler

处理 Token 计数、成本估算和用量统计的专门模块。
支持精确的 Token 计算、成本控制、用量监控等功能。
"""

import hashlib
import asyncio
import time
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
from datetime import datetime, timedelta

from .sdk_initializer import SDKInitializer


@dataclass
class TokenCount:
    """Token 计数结果"""
    total_tokens: int
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached_content_tokens: Optional[int] = None


@dataclass
class ModelPricing:
    """模型定价信息"""
    model_name: str
    input_price_per_1m: float  # 每百万输入token价格
    output_price_per_1m: float  # 每百万输出token价格
    input_price_per_1m_cached: Optional[float] = None  # 缓存内容价格
    currency: str = "USD"


@dataclass
class ModelLimits:
    """模型限制信息"""
    model_name: str
    max_input_tokens: int
    max_output_tokens: int
    context_window: int


class TokenHandler:
    """Gemini Token 计数处理器"""
    
    def __init__(self, sdk_initializer: SDKInitializer):
        """
        初始化 Token 处理器
        
        Args:
            sdk_initializer: SDK 初始化器实例
        """
        self.sdk_initializer = sdk_initializer
        self._token_cache: Dict[str, tuple[TokenCount, float]] = {}  # (result, timestamp)
        self._model_info_cache: Dict[str, tuple[Any, float]] = {}
        self._cache_ttl = 3600  # 缓存1小时
        
        # 模型定价信息（2024年价格，美元）
        self._model_pricing = {
            'gemini-1.5-pro': ModelPricing(
                model_name='gemini-1.5-pro',
                input_price_per_1m=1.25,  # ≤128K tokens
                output_price_per_1m=5.00,
                input_price_per_1m_cached=0.3125  # 缓存内容75%折扣
            ),
            'gemini-1.5-pro-002': ModelPricing(
                model_name='gemini-1.5-pro-002',
                input_price_per_1m=1.25,
                output_price_per_1m=5.00,
                input_price_per_1m_cached=0.3125
            ),
            'gemini-1.5-flash': ModelPricing(
                model_name='gemini-1.5-flash',
                input_price_per_1m=0.075,  # ≤128K tokens
                output_price_per_1m=0.30,
                input_price_per_1m_cached=0.01875
            ),
            'gemini-1.5-flash-8b': ModelPricing(
                model_name='gemini-1.5-flash-8b',
                input_price_per_1m=0.0375,
                output_price_per_1m=0.15,
                input_price_per_1m_cached=0.009375
            ),
            'gemini-1.0-pro': ModelPricing(
                model_name='gemini-1.0-pro',
                input_price_per_1m=0.50,
                output_price_per_1m=1.50
            )
        }
        
        # 模型限制信息
        self._model_limits = {
            'gemini-1.5-pro': ModelLimits(
                model_name='gemini-1.5-pro',
                max_input_tokens=2097152,  # 2M
                max_output_tokens=8192,
                context_window=2097152
            ),
            'gemini-1.5-flash': ModelLimits(
                model_name='gemini-1.5-flash',
                max_input_tokens=1048576,  # 1M
                max_output_tokens=8192,
                context_window=1048576
            ),
            'gemini-1.0-pro': ModelLimits(
                model_name='gemini-1.0-pro',
                max_input_tokens=32768,  # 32K
                max_output_tokens=2048,
                context_window=32768
            )
        }
    
    async def count_tokens(
        self,
        content: Union[str, List[Dict[str, Any]]],
        model: str
    ) -> TokenCount:
        """
        计算内容的 Token 数量
        
        Args:
            content: 文本内容或消息列表
            model: 模型名称
            
        Returns:
            Token 计数结果
        """
        # 检查缓存
        cache_key = self._get_content_hash(content, model)
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        try:
            await self.sdk_initializer.ensure_initialized()
            client = self.sdk_initializer.client
            
            # 准备内容
            if isinstance(content, str):
                # 简单文本
                result = await client.aio.models.count_tokens(
                    model=model,
                    contents=content
                )
            else:
                # 消息列表或复杂内容
                result = await client.aio.models.count_tokens(
                    model=model,
                    contents=content
                )
            
            # 解析结果
            token_count = TokenCount(
                total_tokens=result.total_tokens,
                input_tokens=getattr(result, 'input_tokens', None),
                output_tokens=getattr(result, 'output_tokens', None),
                cached_content_tokens=getattr(result, 'cached_content_tokens', None)
            )
            
            # 缓存结果
            self._cache_result(cache_key, token_count)
            
            return token_count
            
        except Exception as e:
            # 降级到本地估算
            return self._estimate_tokens_locally(content, model)
    
    async def compute_tokens(
        self,
        content: Union[str, List[Dict[str, Any]]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None
    ) -> TokenCount:
        """
        计算复杂内容的 Token 数量（包括工具、系统指令等）
        
        Args:
            content: 内容
            model: 模型名称
            tools: 工具配置
            system_instruction: 系统指令
            
        Returns:
            Token 计数结果
        """
        try:
            await self.sdk_initializer.ensure_initialized()
            client = self.sdk_initializer.client
            
            # 构建完整的请求配置
            request_config = {
                'model': model,
                'contents': content
            }
            
            if tools:
                request_config['tools'] = tools
            
            if system_instruction:
                request_config['system_instruction'] = system_instruction
            
            result = await client.aio.models.compute_tokens(**request_config)
            
            return TokenCount(
                total_tokens=result.total_tokens,
                input_tokens=getattr(result, 'input_tokens', None),
                output_tokens=getattr(result, 'output_tokens', None),
                cached_content_tokens=getattr(result, 'cached_content_tokens', None)
            )
            
        except Exception as e:
            # 降级到基础计数
            return await self.count_tokens(content, model)
    
    async def count_tokens_batch(
        self,
        contents: List[Union[str, List[Dict[str, Any]]]],
        model: str
    ) -> List[TokenCount]:
        """
        批量计算 Token 数量
        
        Args:
            contents: 内容列表
            model: 模型名称
            
        Returns:
            Token 计数结果列表
        """
        tasks = [
            self.count_tokens(content, model)
            for content in contents
        ]
        
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    def estimate_cost(
        self,
        token_count: TokenCount,
        model: str,
        is_input: bool = True
    ) -> float:
        """
        估算成本
        
        Args:
            token_count: Token 计数
            model: 模型名称
            is_input: 是否为输入 Token
            
        Returns:
            估算成本（美元）
        """
        pricing = self.get_model_pricing(model)
        if not pricing:
            return 0.0
        
        total_cost = 0.0
        
        if is_input:
            # 输入 Token 成本
            if token_count.input_tokens:
                total_cost += (token_count.input_tokens / 1_000_000) * pricing.input_price_per_1m
            elif token_count.total_tokens:
                total_cost += (token_count.total_tokens / 1_000_000) * pricing.input_price_per_1m
            
            # 缓存内容成本（如果支持）
            if token_count.cached_content_tokens and pricing.input_price_per_1m_cached:
                cached_cost = (token_count.cached_content_tokens / 1_000_000) * pricing.input_price_per_1m_cached
                # 从总成本中减去缓存部分的原价，加上缓存价格
                original_cached_cost = (token_count.cached_content_tokens / 1_000_000) * pricing.input_price_per_1m
                total_cost = total_cost - original_cached_cost + cached_cost
        else:
            # 输出 Token 成本
            if token_count.output_tokens:
                total_cost += (token_count.output_tokens / 1_000_000) * pricing.output_price_per_1m
            elif token_count.total_tokens:
                total_cost += (token_count.total_tokens / 1_000_000) * pricing.output_price_per_1m
        
        return round(total_cost, 6)  # 保留6位小数
    
    def get_model_pricing(self, model: str) -> Optional[ModelPricing]:
        """
        获取模型定价信息
        
        Args:
            model: 模型名称
            
        Returns:
            定价信息或 None
        """
        return self._model_pricing.get(model)
    
    def get_model_limits(self, model: str) -> Optional[ModelLimits]:
        """
        获取模型限制信息
        
        Args:
            model: 模型名称
            
        Returns:
            限制信息或 None
        """
        return self._model_limits.get(model)
    
    def check_token_limit(self, token_count: TokenCount, model: str) -> Dict[str, Any]:
        """
        检查 Token 限制
        
        Args:
            token_count: Token 计数
            model: 模型名称
            
        Returns:
            检查结果字典
        """
        limits = self.get_model_limits(model)
        if not limits:
            return {
                'valid': True,
                'message': f'未知模型 {model} 的限制信息'
            }
        
        total_tokens = token_count.total_tokens or 0
        
        # 检查输入限制
        if total_tokens > limits.max_input_tokens:
            return {
                'valid': False,
                'message': f'Token 数量 ({total_tokens:,}) 超过模型最大输入限制 ({limits.max_input_tokens:,})',
                'limit_type': 'input',
                'current': total_tokens,
                'limit': limits.max_input_tokens
            }
        
        # 检查上下文窗口
        if total_tokens > limits.context_window:
            return {
                'valid': False,
                'message': f'Token 数量 ({total_tokens:,}) 超过模型上下文窗口 ({limits.context_window:,})',
                'limit_type': 'context',
                'current': total_tokens,
                'limit': limits.context_window
            }
        
        return {
            'valid': True,
            'message': 'Token 数量在限制范围内',
            'usage_percentage': round((total_tokens / limits.max_input_tokens) * 100, 2)
        }
    
    def format_token_usage(self, token_count: TokenCount, model: str) -> str:
        """
        格式化 Token 使用情况
        
        Args:
            token_count: Token 计数
            model: 模型名称
            
        Returns:
            格式化的使用情况字符串
        """
        lines = [f"模型: {model}"]
        
        if token_count.input_tokens and token_count.output_tokens:
            lines.append(f"输入 Tokens: {token_count.input_tokens:,}")
            lines.append(f"输出 Tokens: {token_count.output_tokens:,}")
            lines.append(f"总计 Tokens: {token_count.total_tokens:,}")
        else:
            lines.append(f"总计 Tokens: {token_count.total_tokens:,}")
        
        if token_count.cached_content_tokens:
            lines.append(f"缓存 Tokens: {token_count.cached_content_tokens:,}")
        
        # 添加成本信息
        input_cost = self.estimate_cost(token_count, model, is_input=True)
        if token_count.output_tokens:
            output_cost = self.estimate_cost(token_count, model, is_input=False)
            total_cost = input_cost + output_cost
            lines.append(f"输入成本: ${input_cost:.6f}")
            lines.append(f"输出成本: ${output_cost:.6f}")
            lines.append(f"总成本: ${total_cost:.6f}")
        else:
            lines.append(f"估算成本: ${input_cost:.6f}")
        
        return "\n".join(lines)
    
    def _get_content_hash(self, content: Any, model: str) -> str:
        """
        获取内容哈希值用于缓存
        
        Args:
            content: 内容
            model: 模型名称
            
        Returns:
            哈希值
        """
        content_str = str(content) + model
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def _cache_result(self, key: str, result: TokenCount):
        """
        缓存结果
        
        Args:
            key: 缓存键
            result: Token 计数结果
        """
        self._token_cache[key] = (result, time.time())
        
        # 清理过期缓存
        self._cleanup_cache()
    
    def _get_cached_result(self, key: str) -> Optional[TokenCount]:
        """
        获取缓存结果
        
        Args:
            key: 缓存键
            
        Returns:
            缓存的结果或 None
        """
        if key in self._token_cache:
            result, timestamp = self._token_cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return result
            else:
                del self._token_cache[key]
        
        return None
    
    def _cleanup_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._token_cache.items()
            if current_time - timestamp >= self._cache_ttl
        ]
        
        for key in expired_keys:
            del self._token_cache[key]
    
    def _estimate_tokens_locally(
        self,
        content: Union[str, List[Dict[str, Any]]],
        model: str
    ) -> TokenCount:
        """
        本地估算 Token 数量（降级方案）
        
        Args:
            content: 内容
            model: 模型名称
            
        Returns:
            估算的 Token 计数
        """
        if isinstance(content, str):
            # 简单估算：英文约4字符=1token，中文约1.5字符=1token
            char_count = len(content)
            # 混合语言的粗略估算
            estimated_tokens = int(char_count / 3)
        else:
            # 复杂内容的估算
            total_chars = 0
            for item in content:
                if isinstance(item, dict):
                    total_chars += len(str(item))
                else:
                    total_chars += len(str(item))
            estimated_tokens = int(total_chars / 3)
        
        return TokenCount(total_tokens=estimated_tokens)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计字典
        """
        return {
            'cache_size': len(self._token_cache),
            'cache_ttl': self._cache_ttl,
            'supported_models': list(self._model_pricing.keys())
        }
    
    def clear_cache(self):
        """清空所有缓存"""
        self._token_cache.clear()
        self._model_info_cache.clear()