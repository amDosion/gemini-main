"""
云存储服务主协调器
支持多种存储提供商的统一接口
"""

from typing import Dict, Any
from fastapi import HTTPException
from .factory import ProviderFactory


class StorageService:
    """存储服务主协调器"""
    
    @staticmethod
    async def upload_file(
        filename: str,
        content: bytes,
        content_type: str,
        provider: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        上传文件（统一接口）
        
        Args:
            filename: 文件名
            content: 文件内容
            content_type: 文件类型
            provider: 提供商类型 (lsky, aliyun-oss, tencent-cos, google-drive, local, s3-compatible)
            config: 配置信息
        
        Returns:
            上传结果
        """
        try:
            # 使用工厂创建提供商
            provider_instance = ProviderFactory.create(provider, config)
            
            # 调用提供商上传
            result = await provider_instance.upload(filename, content, content_type)
            
            if not result.success:
                raise HTTPException(
                    status_code=500,
                    detail=result.error or f"{provider} 上传失败"
                )
            
            return {
                "success": True,
                "url": result.url,
                "provider": result.provider,
                "metadata": result.metadata
            }
        
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

    @staticmethod
    async def browse_files(
        provider: str,
        config: Dict[str, Any],
        path: str = "",
        limit: int = 200,
        cursor: str | None = None
    ) -> Dict[str, Any]:
        """
        浏览存储目录（统一接口）
        """
        try:
            provider_instance = ProviderFactory.create(provider, config)
            return await provider_instance.browse(path=path, limit=limit, cursor=cursor)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"浏览目录失败: {str(e)}")

    @staticmethod
    async def count_files(
        provider: str,
        config: Dict[str, Any],
        path: str = ""
    ) -> Dict[str, Any]:
        """
        统计目录下的真实顶层条目数量（统一接口）
        """
        try:
            provider_instance = ProviderFactory.create(provider, config)
            return await provider_instance.count_items(path=path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"统计目录失败: {str(e)}")

    @staticmethod
    async def delete_item(
        provider: str,
        config: Dict[str, Any],
        path: str,
        is_directory: bool = False,
        file_url: str | None = None
    ) -> Dict[str, Any]:
        """
        删除文件或目录（统一接口）
        """
        try:
            provider_instance = ProviderFactory.create(provider, config)
            return await provider_instance.delete_path(
                path=path,
                is_directory=is_directory,
                file_url=file_url
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

    @staticmethod
    async def rename_item(
        provider: str,
        config: Dict[str, Any],
        path: str,
        new_name: str,
        is_directory: bool = False
    ) -> Dict[str, Any]:
        """
        重命名文件或目录（统一接口）
        """
        try:
            provider_instance = ProviderFactory.create(provider, config)
            return await provider_instance.rename_path(
                path=path,
                new_name=new_name,
                is_directory=is_directory
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"重命名失败: {str(e)}")
    
    # 向后兼容方法（保留现有 API）
    @staticmethod
    async def upload_to_lsky(
        filename: str, 
        content: bytes, 
        content_type: str, 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """向后兼容：上传到兰空图床"""
        return await StorageService.upload_file(filename, content, content_type, "lsky", config)
    
    @staticmethod
    async def upload_to_aliyun_oss(
        filename: str, 
        content: bytes, 
        content_type: str, 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """向后兼容：上传到阿里云 OSS"""
        return await StorageService.upload_file(filename, content, content_type, "aliyun-oss", config)
