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

    async def browse(
        self,
        path: str = "",
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        浏览存储目录内容（默认实现：不支持）

        Returns:
            Dict[str, Any]: {
                "supported": bool,
                "items": List[Dict[str, Any]],
                "next_cursor": Optional[str],
                "has_more": bool
            }
        """
        return {
            "supported": False,
            "items": [],
            "next_cursor": None,
            "has_more": False,
            "message": "当前存储提供商暂不支持目录浏览"
        }

    async def count_items(self, path: str = "") -> Dict[str, Any]:
        """
        统计指定目录下的顶层条目真实数量（目录 + 文件）。

        Returns:
            Dict[str, Any]: {
                "supported": bool,
                "path": str,
                "total_count": Optional[int]
            }
        """
        return {
            "supported": False,
            "path": path,
            "total_count": None,
            "message": "当前存储提供商暂不支持目录统计"
        }

    async def delete_path(
        self,
        path: str,
        is_directory: bool = False,
        file_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        按路径删除文件/目录（默认：仅当提供 file_url 时回退到 delete）
        """
        if is_directory:
            return {
                "success": False,
                "supported": False,
                "message": "当前存储提供商暂不支持目录删除"
            }

        if file_url:
            ok = await self.delete(file_url)
            return {
                "success": ok,
                "supported": ok,
                "message": None if ok else "删除失败"
            }

        return {
            "success": False,
            "supported": False,
            "message": "当前存储提供商删除需要 file_url"
        }

    async def rename_path(
        self,
        path: str,
        new_name: str,
        is_directory: bool = False
    ) -> Dict[str, Any]:
        """
        按路径重命名文件/目录（默认：不支持）
        """
        return {
            "success": False,
            "supported": False,
            "message": "当前存储提供商暂不支持重命名"
        }
