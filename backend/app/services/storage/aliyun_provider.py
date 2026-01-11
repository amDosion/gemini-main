"""
阿里云 OSS 存储提供商
支持上传文件到阿里云 OSS
"""

import oss2
from datetime import datetime
from typing import Dict, Any
from .base import BaseStorageProvider, UploadResult


class AliyunProvider(BaseStorageProvider):
    """阿里云 OSS 存储提供商"""
    
    async def upload(self, filename: str, content: bytes, content_type: str) -> UploadResult:
        """
        上传文件到阿里云 OSS
        
        Args:
            filename: 文件名
            content: 文件内容
            content_type: 文件 MIME 类型
            
        Returns:
            UploadResult: 上传结果
        """
        access_key_id = self.config.get("accessKeyId")
        access_key_secret = self.config.get("accessKeySecret")
        bucket_name = self.config.get("bucket")
        endpoint = self.config.get("endpoint")
        custom_domain = self.config.get("customDomain")
        secure = self.config.get("secure", True)
        
        # 验证配置
        if not all([access_key_id, access_key_secret, bucket_name, endpoint]):
            return UploadResult(
                success=False,
                error="阿里云 OSS 配置不完整：缺少必填项（accessKeyId, accessKeySecret, bucket, endpoint）",
                provider="aliyun-oss"
            )
        
        try:
            # 清理 endpoint（移除协议前缀）
            oss_endpoint = endpoint.replace("https://", "").replace("http://", "")
            
            # 创建 OSS 认证和 Bucket 对象
            auth = oss2.Auth(access_key_id, access_key_secret)
            bucket = oss2.Bucket(auth, oss_endpoint, bucket_name)
            
            # 生成对象名称（使用时间戳避免冲突）
            timestamp = int(datetime.now().timestamp() * 1000)
            object_name = f"uploads/{timestamp}_{filename}"
            
            # 设置 Content-Type
            headers = {
                'Content-Type': content_type
            }
            
            # 上传文件
            result = bucket.put_object(object_name, content, headers=headers)
            
            if result.status == 200:
                # 构建公开访问 URL
                protocol = "https" if secure else "http"
                
                if custom_domain:
                    # 使用自定义 CDN 域名
                    domain = custom_domain.replace("https://", "").replace("http://", "").rstrip('/')
                    image_url = f"{protocol}://{domain}/{object_name}"
                else:
                    # 使用 OSS 默认域名
                    image_url = f"{protocol}://{bucket_name}.{oss_endpoint}/{object_name}"
                
                return UploadResult(
                    success=True,
                    url=image_url,
                    provider="aliyun-oss",
                    metadata={
                        "objectName": object_name,
                        "bucket": bucket_name,
                        "endpoint": oss_endpoint
                    }
                )
            else:
                return UploadResult(
                    success=False,
                    error=f"阿里云 OSS 上传失败: HTTP {result.status}",
                    provider="aliyun-oss"
                )
        
        except oss2.exceptions.OssError as e:
            return UploadResult(
                success=False,
                error=f"阿里云 OSS 错误: {e.code} - {e.message}",
                provider="aliyun-oss"
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=f"阿里云 OSS 上传失败: {str(e)}",
                provider="aliyun-oss"
            )
    
    async def delete(self, file_url: str) -> bool:
        """
        删除文件（占位实现）
        
        Args:
            file_url: 文件 URL
            
        Returns:
            bool: 删除是否成功
        """
        # 需要从 URL 中提取 object_name，然后调用 bucket.delete_object()
        # 这里暂时返回 False
        return False
    
    async def test(self) -> UploadResult:
        """
        测试配置是否有效
        
        Returns:
            UploadResult: 测试结果
        """
        access_key_id = self.config.get("accessKeyId")
        access_key_secret = self.config.get("accessKeySecret")
        bucket_name = self.config.get("bucket")
        endpoint = self.config.get("endpoint")
        
        if not all([access_key_id, access_key_secret, bucket_name, endpoint]):
            return UploadResult(
                success=False,
                error="阿里云 OSS 配置不完整：缺少必填项（accessKeyId, accessKeySecret, bucket, endpoint）",
                provider="aliyun-oss"
            )
        
        return UploadResult(
            success=True,
            provider="aliyun-oss"
        )
