"""
S3 兼容存储提供商
支持 AWS S3 和 S3 兼容服务（如 MinIO、Ceph 等）
"""

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.config import Config
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from .base import BaseStorageProvider, UploadResult


class S3Provider(BaseStorageProvider):
    """S3 兼容存储提供商"""
    
    def _create_client(self):
        """创建 S3 客户端"""
        access_key_id = self.config.get("access_key_id")
        secret_access_key = self.config.get("secret_access_key")
        region = self.config.get("region", "us-east-1")
        endpoint = self.config.get("endpoint")
        force_path_style = self.config.get("force_path_style", False)
        
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

    def _normalize_path(self, value: str) -> str:
        normalized = (value or "").replace("\\", "/").strip().strip("/")
        if ".." in normalized.split("/"):
            raise ValueError("非法目录路径")
        return normalized

    def _get_base_prefix(self) -> str:
        return (self.config.get("path_prefix", "") or "").strip("/")

    def _build_object_prefix(self, path: str) -> str:
        base_prefix = self._get_base_prefix()
        normalized_path = self._normalize_path(path)
        if base_prefix and normalized_path:
            return f"{base_prefix}/{normalized_path}/"
        if base_prefix:
            return f"{base_prefix}/"
        if normalized_path:
            return f"{normalized_path}/"
        return ""

    def _to_relative_path(self, object_key: str) -> str:
        key = object_key.strip("/")
        base_prefix = self._get_base_prefix()
        if base_prefix and key.startswith(f"{base_prefix}/"):
            key = key[len(base_prefix) + 1:]
        return key

    def _build_object_key(self, relative_path: str) -> str:
        normalized = self._normalize_path(relative_path)
        base_prefix = self._get_base_prefix()
        if base_prefix and normalized:
            return f"{base_prefix}/{normalized}"
        if base_prefix:
            return base_prefix
        return normalized

    def _extract_object_key_from_url(self, file_url: str) -> str:
        bucket = self.config.get("bucket")
        parsed_url = urlparse(file_url or "")
        path = parsed_url.path.lstrip("/")
        if bucket and path.startswith(f"{bucket}/"):
            path = path[len(bucket) + 1:]
        return path.strip("/")

    def _build_public_url(self, object_key: str) -> str:
        bucket = self.config.get("bucket")
        region = self.config.get("region", "us-east-1")
        endpoint = self.config.get("endpoint")
        custom_domain = self.config.get("custom_domain")
        force_path_style = self.config.get("force_path_style", False)

        if custom_domain:
            domain = custom_domain.replace("https://", "").replace("http://", "").rstrip("/")
            return f"https://{domain}/{object_key}"
        if endpoint:
            endpoint_clean = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
            if force_path_style:
                return f"https://{endpoint_clean}/{bucket}/{object_key}"
            return f"https://{bucket}.{endpoint_clean}/{object_key}"

        if force_path_style:
            return f"https://s3.{region}.amazonaws.com/{bucket}/{object_key}"
        return f"https://{bucket}.s3.{region}.amazonaws.com/{object_key}"
    
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
        access_key_id = self.config.get("access_key_id")
        secret_access_key = self.config.get("secret_access_key")
        bucket = self.config.get("bucket")
        region = self.config.get("region", "us-east-1")
        endpoint = self.config.get("endpoint")
        path_prefix = self.config.get("path_prefix", "")
        
        # 验证配置
        if not all([access_key_id, secret_access_key, bucket]):
            return UploadResult(
                success=False,
                error="S3 兼容存储配置不完整：缺少必填项（access_key_id, secret_access_key, bucket）",
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
                public_url = self._build_public_url(object_key)
                
                return UploadResult(
                    success=True,
                    url=public_url,
                    provider="s3-compatible",
                    metadata={
                        "object_key": object_key,
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
            object_key = self._extract_object_key_from_url(file_url)
            if not object_key:
                return False
            
            # 创建客户端
            client = self._create_client()
            
            # 删除对象
            response = client.delete_object(
                Bucket=bucket,
                Key=object_key
            )
            
            # 检查响应状态（204/200 表示成功）
            status_code = response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            return status_code in [200, 204]
        
        except ClientError:
            return False
        except Exception:
            return False

    async def delete_path(
        self,
        path: str,
        is_directory: bool = False,
        file_url: Optional[str] = None
    ) -> Dict[str, Any]:
        bucket = self.config.get("bucket")
        if not bucket:
            return {"success": False, "supported": False, "message": "S3 配置不完整"}

        try:
            client = self._create_client()

            if is_directory:
                normalized = self._normalize_path(path)
                if not normalized:
                    return {"success": False, "supported": False, "message": "不支持删除根目录"}

                prefix = self._build_object_key(normalized).rstrip("/") + "/"
                continuation_token: Optional[str] = None
                keys: list[str] = []

                while True:
                    list_params: Dict[str, Any] = {
                        "Bucket": bucket,
                        "Prefix": prefix,
                        "MaxKeys": 1000,
                    }
                    if continuation_token:
                        list_params["ContinuationToken"] = continuation_token
                    resp = client.list_objects_v2(**list_params)
                    for obj in resp.get("Contents", []):
                        key = obj.get("Key")
                        if key:
                            keys.append(key)
                    if not resp.get("IsTruncated"):
                        break
                    continuation_token = resp.get("NextContinuationToken")

                if not keys:
                    return {"success": True, "supported": True, "message": "目录为空或不存在"}

                for index in range(0, len(keys), 1000):
                    chunk = keys[index:index + 1000]
                    client.delete_objects(
                        Bucket=bucket,
                        Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True}
                    )

                return {"success": True, "supported": True, "message": None}

            object_key = self._build_object_key(path) if path else self._extract_object_key_from_url(file_url or "")
            if not object_key:
                return {"success": False, "supported": False, "message": "path is required"}

            response = client.delete_object(Bucket=bucket, Key=object_key)
            status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            ok = status_code in [200, 204]
            return {"success": ok, "supported": True, "message": None if ok else "删除失败"}
        except ValueError as e:
            return {"success": False, "supported": False, "message": str(e)}
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            return {"success": False, "supported": True, "message": f"S3 删除失败 ({error_code}): {error_message}"}
        except Exception as e:
            return {"success": False, "supported": True, "message": f"S3 删除失败: {str(e)}"}

    async def rename_path(
        self,
        path: str,
        new_name: str,
        is_directory: bool = False
    ) -> Dict[str, Any]:
        bucket = self.config.get("bucket")
        if not bucket:
            return {"success": False, "supported": False, "message": "S3 配置不完整"}

        clean_name = (new_name or "").strip().strip("/")
        if not clean_name:
            return {"success": False, "supported": False, "message": "new_name is required"}
        if "/" in clean_name or "\\" in clean_name:
            return {"success": False, "supported": False, "message": "new_name 不能包含路径分隔符"}

        try:
            source_relative = self._normalize_path(path)
            if not source_relative:
                return {"success": False, "supported": False, "message": "path is required"}

            segments = source_relative.split("/")
            parent_relative = "/".join(segments[:-1]) if len(segments) > 1 else ""
            target_relative = f"{parent_relative}/{clean_name}" if parent_relative else clean_name

            source_key = self._build_object_key(source_relative)
            target_key = self._build_object_key(target_relative)
            if source_key == target_key:
                return {"success": True, "supported": True, "message": None}

            client = self._create_client()

            def _is_not_found(err: ClientError) -> bool:
                code = str(err.response.get("Error", {}).get("Code", ""))
                return code in {"404", "NoSuchKey", "NotFound"}

            if is_directory:
                source_prefix = source_key.rstrip("/") + "/"
                target_prefix = target_key.rstrip("/") + "/"

                exists_resp = client.list_objects_v2(Bucket=bucket, Prefix=target_prefix, MaxKeys=1)
                if exists_resp.get("KeyCount", 0) > 0:
                    return {"success": False, "supported": True, "message": "目标目录已存在"}

                continuation_token: Optional[str] = None
                keys: list[str] = []
                while True:
                    list_params: Dict[str, Any] = {
                        "Bucket": bucket,
                        "Prefix": source_prefix,
                        "MaxKeys": 1000,
                    }
                    if continuation_token:
                        list_params["ContinuationToken"] = continuation_token
                    resp = client.list_objects_v2(**list_params)
                    for obj in resp.get("Contents", []):
                        key = obj.get("Key")
                        if key:
                            keys.append(key)
                    if not resp.get("IsTruncated"):
                        break
                    continuation_token = resp.get("NextContinuationToken")

                if not keys:
                    return {"success": False, "supported": True, "message": "源目录不存在"}

                for key in keys:
                    suffix = key[len(source_prefix):]
                    new_key = f"{target_prefix}{suffix}" if suffix else target_prefix
                    client.copy_object(
                        Bucket=bucket,
                        Key=new_key,
                        CopySource={"Bucket": bucket, "Key": key}
                    )
                    client.delete_object(Bucket=bucket, Key=key)
                return {"success": True, "supported": True, "message": None}

            # 文件重命名
            try:
                client.head_object(Bucket=bucket, Key=source_key)
            except ClientError as e:
                if _is_not_found(e):
                    return {"success": False, "supported": True, "message": "源文件不存在"}
                raise

            try:
                client.head_object(Bucket=bucket, Key=target_key)
                return {"success": False, "supported": True, "message": "目标文件已存在"}
            except ClientError as e:
                if not _is_not_found(e):
                    raise

            client.copy_object(
                Bucket=bucket,
                Key=target_key,
                CopySource={"Bucket": bucket, "Key": source_key}
            )
            client.delete_object(Bucket=bucket, Key=source_key)
            return {"success": True, "supported": True, "message": None}
        except ValueError as e:
            return {"success": False, "supported": False, "message": str(e)}
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            return {"success": False, "supported": True, "message": f"S3 重命名失败 ({error_code}): {error_message}"}
        except Exception as e:
            return {"success": False, "supported": True, "message": f"S3 重命名失败: {str(e)}"}

    async def browse(
        self,
        path: str = "",
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        access_key_id = self.config.get("access_key_id")
        secret_access_key = self.config.get("secret_access_key")
        bucket = self.config.get("bucket")

        if not all([access_key_id, secret_access_key, bucket]):
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": "S3 配置不完整"
            }

        try:
            prefix = self._build_object_prefix(path)
            normalized_path = self._normalize_path(path)
            client = self._create_client()

            request_params: Dict[str, Any] = {
                "Bucket": bucket,
                "Prefix": prefix,
                "Delimiter": "/",
                "MaxKeys": max(1, min(limit, 1000))
            }
            if cursor:
                request_params["ContinuationToken"] = cursor

            response = client.list_objects_v2(**request_params)

            items: list[dict] = []

            for directory in response.get("CommonPrefixes", []):
                dir_prefix = (directory.get("Prefix") or "").rstrip("/")
                relative_path = self._to_relative_path(dir_prefix)
                name = relative_path.split("/")[-1] if relative_path else "/"
                items.append({
                    "name": name,
                    "path": relative_path,
                    "entry_type": "directory",
                    "size": None,
                    "updated_at": None,
                    "url": None
                })

            for obj in response.get("Contents", []):
                key = obj.get("Key")
                if not key:
                    continue
                if key.endswith("/"):
                    continue
                relative_path = self._to_relative_path(key)
                if not relative_path:
                    continue
                if "/" in relative_path and prefix and key.rstrip("/") == prefix.rstrip("/"):
                    continue
                items.append({
                    "name": relative_path.split("/")[-1],
                    "path": relative_path,
                    "entry_type": "file",
                    "size": obj.get("Size"),
                    "updated_at": obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
                    "url": self._build_public_url(key)
                })

            items.sort(key=lambda item: (0 if item["entry_type"] == "directory" else 1, item["name"].lower()))

            return {
                "supported": True,
                "items": items,
                "path": normalized_path,
                "next_cursor": response.get("NextContinuationToken"),
                "has_more": bool(response.get("IsTruncated"))
            }
        except ValueError as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": str(e)
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": f"S3 浏览失败 ({error_code}): {error_message}"
            }
        except Exception as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": f"S3 浏览失败: {str(e)}"
            }

    async def count_items(self, path: str = "") -> Dict[str, Any]:
        access_key_id = self.config.get("access_key_id")
        secret_access_key = self.config.get("secret_access_key")
        bucket = self.config.get("bucket")

        if not all([access_key_id, secret_access_key, bucket]):
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": "S3 配置不完整"
            }

        try:
            prefix = self._build_object_prefix(path)
            normalized_path = self._normalize_path(path)
            client = self._create_client()
            continuation_token = None
            total_count = 0

            while True:
                request_params: Dict[str, Any] = {
                    "Bucket": bucket,
                    "Prefix": prefix,
                    "Delimiter": "/",
                    "MaxKeys": 1000
                }
                if continuation_token:
                    request_params["ContinuationToken"] = continuation_token

                response = client.list_objects_v2(**request_params)
                total_count += len(response.get("CommonPrefixes") or [])

                for obj in response.get("Contents", []):
                    key = obj.get("Key")
                    if not key or key.endswith("/"):
                        continue
                    total_count += 1

                if not response.get("IsTruncated"):
                    break

                continuation_token = response.get("NextContinuationToken")
                if not continuation_token:
                    break

            return {
                "supported": True,
                "path": normalized_path,
                "total_count": total_count
            }
        except ValueError as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": str(e)
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": f"S3 统计失败 ({error_code}): {error_message}"
            }
        except Exception as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": f"S3 统计失败: {str(e)}"
            }
    
    async def test(self) -> UploadResult:
        """
        测试配置是否有效
        
        Returns:
            UploadResult: 测试结果
        """
        access_key_id = self.config.get("access_key_id")
        secret_access_key = self.config.get("secret_access_key")
        bucket = self.config.get("bucket")
        
        if not all([access_key_id, secret_access_key, bucket]):
            return UploadResult(
                success=False,
                error="S3 兼容存储配置不完整：缺少必填项（access_key_id, secret_access_key, bucket）",
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
                        "object_count": response.get('KeyCount', 0)
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
