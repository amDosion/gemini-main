"""
存储提供商工厂模块
负责根据提供商类型创建对应的存储提供商实例
"""

from typing import Dict, Any
from .base import BaseStorageProvider
from .lsky_provider import LskyProvider
from .aliyun_provider import AliyunProvider
from .tencent_provider import TencentProvider
from .google_provider import GoogleProvider
from .local_provider import LocalProvider
from .s3_provider import S3Provider


class ProviderFactory:
    """存储提供商工厂类"""
    
    _providers: Dict[str, type] = {
        'lsky': LskyProvider,
        'aliyun-oss': AliyunProvider,
        'tencent-cos': TencentProvider,
        'google-drive': GoogleProvider,
        'local': LocalProvider,
        's3-compatible': S3Provider,
    }
    
    @classmethod
    def create(cls, provider: str, config: Dict[str, Any]) -> BaseStorageProvider:
        """
        创建存储提供商实例
        
        Args:
            provider: 提供商类型 (lsky, aliyun-oss, tencent-cos, google-drive, local, s3-compatible)
            config: 提供商配置信息
            
        Returns:
            BaseStorageProvider: 存储提供商实例
            
        Raises:
            ValueError: 当提供商类型不支持时
        """
        provider_class = cls._providers.get(provider)
        if not provider_class:
            raise ValueError(f"不支持的存储提供商: {provider}")
        return provider_class(config)
