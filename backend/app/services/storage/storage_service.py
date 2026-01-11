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
