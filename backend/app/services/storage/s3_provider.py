"""
S3 兼容存储提供商
支持 AWS S3 和 S3 兼容服务（如 MinIO、Ceph 等）
"""

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.config import Config
from datetime import datetime
from typing import Dict, Any
from urllib.parse import urlparse
from .base import BaseStorageProvider, UploadResult


class S3Provider(BaseStorageProvider):
    """S3 兼容存储提供商"""
    
    def _create_client(self):
        """创建 S3 客户端"""
        access_key_id = self.config.get("accessKeyId")
        secret_access_key = self.config.get("secretAccessKey")
        region = self.config.get("region", "us-east-1")
        endpoint = self.config.get("endpoint")
        force_path_style = self.config.get("forcePathStyle", False)
        
        # 配置 boto3
        config = Config(
            s3={'addressing_style': 'path' if force_path_style else 'virtual'}
        )
        
        # 创建客户端参数
        client_params = {
            'service_name': 's3',
            'aws_access_key_id': access_key_id,
            'aws_secret_access_key': secret_access_key,
            'region_name': region,
            'config': config
        }
        
        # 如果指定了自定义 endpoint（用于 S3 兼容服务）
        if endpoint:
            client_params['endpoint_url'] = endpoint
        
        return boto3.client(**client_params)
    
    async def upload(self, filename: str, content: bytes, content_type: str) -> UploadResult:
        """
        上传文件到 S3 兼容存储
        
        Args:
            filename: 文件名
            content: 文件内容
            content_type: 文件 MIME 类型
            
        Returns:
            UploadResult: 上传结果
        """
        access_key_id = self.config.get("accessKeyId")
        secret_access_key = self.config.get("secretAccessKey")
        bucket = self.config.get("bucket")
        region = self.config.get("region", "us-east-1")
        endpoint = self.config.get("endpoint")
        custom_domain = self.config.get("customDomain")
        path_prefix = self.config.get("pathPrefix", "")
        force_path_style = self.config.get("forcePathStyle", False)
        
        # 验证配置
        if not all([access_key_id, secret_access_key, bucket]):
            return UploadResult(
                success=False,
                error="S3 兼容存储配置不完整：缺少必填项（accessKeyId, secretAccessKey, bucket）",
                provider="s3-compatible"
            )
        
        try:
            # 创建客户端
            client = self._create_client()
            
            # 生成对象键（使用时间戳避免冲突）
            timestamp = int(datetime.now().timestamp() * 1000)
            
            # 处理路径前缀
            if path_prefix:
                path_prefix = path_prefix.strip("/")
                object_key = f"{path_prefix}/{timestamp}_{filename}"
            else:
                object_key = f"uploads/{timestamp}_{filename}"
            
            # 上传文件
            response = client.put_object(
                Bucket=bucket,
                Key=object_key,
                Body=content,
                ContentType=content_type
            )
            
            # 检查响应
            if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
                # 构建公开访问 URL
                if custom_domain:
                    # 使用自定义域名
                    domain = custom_domain.replace("https://", "").replace("http://", "").rstrip('/')
                    public_url = f"https://{domain}/{object_key}"
                elif endpoint:
                    # 使用自定义 endpoint（S3 兼容服务）
                    endpoint_clean = endpoint.replace("https://", "").replace("http://", "").rstrip('/')
                    if force_path_style:
                        public_url = f"https://{endpoint_clean}/{bucket}/{object_key}"
                    else:
                        public_url = f"https://{bucket}.{endpoint_clean}/{object_key}"
                else:
                    # 使用 AWS S3 默认域名
                    if force_path_style:
                        public_url = f"https://s3.{region}.amazonaws.com/{bucket}/{object_key}"
                    else:
                        public_url = f"https://{bucket}.s3.{region}.amazonaws.com/{object_key}"
                
                return UploadResult(
                    success=True,
                    url=public_url,
                    provider="s3-compatible",
                    metadata={
                        "objectKey": object_key,
                        "bucket": bucket,
                        "region": region,
                        "etag": response.get('ETag', '').strip('"')
                    }
                )
            else:
                return UploadResult(
                    success=False,
                    error=f"S3 上传失败: HTTP {response.get('ResponseMetadata', {}).get('HTTPStatusCode')}",
                    provider="s3-compatible"
                )
        
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            return UploadResult(
                success=False,
                error=f"S3 客户端错误 ({error_code}): {error_message}",
                provider="s3-compatible"
            )
        except EndpointConnectionError as e:
            return UploadResult(
                success=False,
                error=f"S3 连接错误: 无法连接到 endpoint {endpoint or 'AWS S3'}",
                provider="s3-compatible"
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=f"S3 上传失败: {str(e)}",
                provider="s3-compatible"
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
            path = parsed_url.path.lstrip('/')
            
            # 如果使用 path style，需要移除 bucket 前缀
            if path.startswith(f"{bucket}/"):
                object_key = path[len(bucket) + 1:]
            else:
                object_key = path
            
            if not object_key:
                return False
            
            # 创建客户端
            client = self._create_client()
            
            # 删除对象
            response = client.delete_object(
                Bucket=bucket,
                Key=object_key
            )
            
            # 检查响应状态（204 表示成功）
            status_code = response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            return status_code == 204
        
        except ClientError:
            return False
        except Exception:
            return False
    
    async def test(self) -> UploadResult:
        """
        测试配置是否有效
        
        Returns:
            UploadResult: 测试结果
        """
        access_key_id = self.config.get("accessKeyId")
        secret_access_key = self.config.get("secretAccessKey")
        bucket = self.config.get("bucket")
        
        if not all([access_key_id, secret_access_key, bucket]):
            return UploadResult(
                success=False,
                error="S3 兼容存储配置不完整：缺少必填项（accessKeyId, secretAccessKey, bucket）",
                provider="s3-compatible"
            )
        
        try:
            # 创建客户端并测试连接
            client = self._create_client()
            
            # 尝试列出 bucket（限制1个对象，仅测试连接）
            response = client.list_objects_v2(
                Bucket=bucket,
                MaxKeys=1
            )
            
            # 检查响应状态
            if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
                return UploadResult(
                    success=True,
                    provider="s3-compatible",
                    metadata={
                        "bucket": bucket,
                        "objectCount": response.get('KeyCount', 0)
                    }
                )
            else:
                return UploadResult(
                    success=False,
                    error="S3 连接测试失败",
                    provider="s3-compatible"
                )
        
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            return UploadResult(
                success=False,
                error=f"S3 客户端错误 ({error_code}): {error_message}",
                provider="s3-compatible"
            )
        except EndpointConnectionError as e:
            endpoint = self.config.get("endpoint")
            return UploadResult(
                success=False,
                error=f"S3 连接错误: 无法连接到 endpoint {endpoint or 'AWS S3'}",
                provider="s3-compatible"
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=f"S3 测试失败: {str(e)}",
                provider="s3-compatible"
            )
