"""
腾讯云 COS 存储提供商
支持上传文件到腾讯云 COS
"""

from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosServiceError, CosClientError
from datetime import datetime
from typing import Dict, Any
from urllib.parse import urlparse
from .base import BaseStorageProvider, UploadResult


class TencentProvider(BaseStorageProvider):
    """腾讯云 COS 存储提供商"""
    
    def _create_client(self) -> CosS3Client:
        """创建 COS 客户端"""
        secret_id = self.config.get("secret_id")
        secret_key = self.config.get("secret_key")
        region = self.config.get("region")
        
        config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
        return CosS3Client(config)
    
    async def upload(self, filename: str, content: bytes, content_type: str) -> UploadResult:
        """
        上传文件到腾讯云 COS
        
        Args:
            filename: 文件名
            content: 文件内容
            content_type: 文件 MIME 类型
            
        Returns:
            UploadResult: 上传结果
        """
        secret_id = self.config.get("secret_id")
        secret_key = self.config.get("secret_key")
        bucket = self.config.get("bucket")
        region = self.config.get("region")
        custom_domain = self.config.get("domain")
        path_prefix = self.config.get("path_prefix", "")

        # 验证配置
        if not all([secret_id, secret_key, bucket, region]):
            return UploadResult(
                success=False,
                error="腾讯云 COS 配置不完整：缺少必填项（secret_id, secret_key, bucket, region）",
                provider="tencent-cos"
            )
        
        try:
            # 创建客户端
            client = self._create_client()
            
            # 生成对象名称（使用时间戳避免冲突）
            timestamp = int(datetime.now().timestamp() * 1000)
            
            # 处理路径前缀
            if path_prefix:
                path_prefix = path_prefix.strip("/")
                object_name = f"{path_prefix}/{timestamp}_{filename}"
            else:
                object_name = f"uploads/{timestamp}_{filename}"
            
            # 上传文件
            response = client.put_object(
                Bucket=bucket,
                Key=object_name,
                Body=content,
                ContentType=content_type
            )
            
            # 检查响应状态
            if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
                # 构建公开访问 URL
                if custom_domain:
                    # 使用自定义域名
                    domain = custom_domain.replace("https://", "").replace("http://", "").rstrip('/')
                    image_url = f"https://{domain}/{object_name}"
                else:
                    # 使用 COS 默认域名
                    image_url = f"https://{bucket}.cos.{region}.myqcloud.com/{object_name}"
                
                return UploadResult(
                    success=True,
                    url=image_url,
                    provider="tencent-cos",
                    metadata={
                        "object_name": object_name,
                        "bucket": bucket,
                        "region": region,
                        "etag": response.get('ETag', '').strip('"')
                    }
                )
            else:
                return UploadResult(
                    success=False,
                    error=f"腾讯云 COS 上传失败: HTTP {response.get('ResponseMetadata', {}).get('HTTPStatusCode')}",
                    provider="tencent-cos"
                )
        
        except CosServiceError as e:
            return UploadResult(
                success=False,
                error=f"腾讯云 COS 服务错误: {e.get_error_code()} - {e.get_error_msg()}",
                provider="tencent-cos"
            )
        except CosClientError as e:
            return UploadResult(
                success=False,
                error=f"腾讯云 COS 客户端错误: {str(e)}",
                provider="tencent-cos"
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=f"腾讯云 COS 上传失败: {str(e)}",
                provider="tencent-cos"
            )
    
    async def delete(self, file_url: str) -> bool:
        """
        删除文件
        
        Args:
            file_url: 文件 URL
            
        Returns:
            bool: 删除是否成功
        """
        bucket = self.config.get("bucket")
        
        if not bucket:
            return False
        
        try:
            # 从 URL 中提取对象键
            parsed_url = urlparse(file_url)
            object_key = parsed_url.path.lstrip('/')
            
            if not object_key:
                return False
            
            # 创建客户端
            client = self._create_client()
            
            # 删除对象
            response = client.delete_object(
                Bucket=bucket,
                Key=object_key
            )
            
            # 检查响应状态（204 或 200 表示成功）
            status_code = response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            return status_code in [200, 204]
        
        except (CosServiceError, CosClientError):
            return False
        except Exception:
            return False
    
    async def test(self) -> UploadResult:
        """
        测试配置是否有效
        
        Returns:
            UploadResult: 测试结果
        """
        secret_id = self.config.get("secret_id")
        secret_key = self.config.get("secret_key")
        bucket = self.config.get("bucket")
        region = self.config.get("region")

        if not all([secret_id, secret_key, bucket, region]):
            return UploadResult(
                success=False,
                error="腾讯云 COS 配置不完整：缺少必填项（secret_id, secret_key, bucket, region）",
                provider="tencent-cos"
            )
        
        try:
            # 创建客户端并测试连接
            client = self._create_client()
            
            # 尝试列出 bucket（限制1个对象，仅测试连接）
            response = client.list_objects(
                Bucket=bucket,
                MaxKeys=1
            )
            
            # 检查响应状态
            if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
                return UploadResult(
                    success=True,
                    provider="tencent-cos"
                )
            else:
                return UploadResult(
                    success=False,
                    error="腾讯云 COS 连接测试失败",
                    provider="tencent-cos"
                )
        
        except CosServiceError as e:
            return UploadResult(
                success=False,
                error=f"腾讯云 COS 服务错误: {e.get_error_code()} - {e.get_error_msg()}",
                provider="tencent-cos"
            )
        except CosClientError as e:
            return UploadResult(
                success=False,
                error=f"腾讯云 COS 客户端错误: {str(e)}",
                provider="tencent-cos"
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=f"腾讯云 COS 测试失败: {str(e)}",
                provider="tencent-cos"
            )
