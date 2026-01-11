"""
存储提供商基类模块
定义所有存储提供商必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class UploadResult:
    """上传结果数据类"""
    success: bool
    url: Optional[str] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseStorageProvider(ABC):
    """存储提供商抽象基类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化存储提供商
        
        Args:
            config: 提供商配置信息
        """
        self.config = config
    
    @abstractmethod
    async def upload(self, filename: str, content: bytes, content_type: str) -> UploadResult:
        """
        上传文件
        
        Args:
            filename: 文件名
            content: 文件内容
            content_type: 文件 MIME 类型
            
        Returns:
            UploadResult: 上传结果
        """
        pass
    
    @abstractmethod
    async def delete(self, file_url: str) -> bool:
        """
        删除文件
        
        Args:
            file_url: 文件 URL
            
        Returns:
            bool: 删除是否成功
        """
        pass
    
    @abstractmethod
    async def test(self) -> UploadResult:
        """
        测试配置是否有效
        
        Returns:
            UploadResult: 测试结果
        """
        pass
