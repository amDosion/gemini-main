"""
腾讯云 COS 存储提供商
支持上传文件到腾讯云 COS
"""

from qcloud_cos import CosConfig, CosS3Client
from qcloud_cos.cos_exception import CosServiceError, CosClientError
from datetime import datetime
from typing import Dict, Any, Optional
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

    def _build_public_url(self, object_name: str) -> str:
        bucket = self.config.get("bucket")
        region = self.config.get("region")
        custom_domain = self.config.get("domain")
        if custom_domain:
            domain = custom_domain.replace("https://", "").replace("http://", "").rstrip("/")
            return f"https://{domain}/{object_name}"
        return f"https://{bucket}.cos.{region}.myqcloud.com/{object_name}"
    
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
                image_url = self._build_public_url(object_name)
                
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
            
            # 检查响应状态（204 或 200 表示成功）
            status_code = response.get('ResponseMetadata', {}).get('HTTPStatusCode')
            return status_code in [200, 204]
        
        except (CosServiceError, CosClientError):
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
        region = self.config.get("region")
        if not bucket or not region:
            return {"success": False, "supported": False, "message": "腾讯云 COS 配置不完整"}

        try:
            client = self._create_client()

            if is_directory:
                normalized = self._normalize_path(path)
                if not normalized:
                    return {"success": False, "supported": False, "message": "不支持删除根目录"}

                prefix = self._build_object_key(normalized).rstrip("/") + "/"
                marker: Optional[str] = None
                keys: list[str] = []

                while True:
                    list_params: Dict[str, Any] = {
                        "Bucket": bucket,
                        "Prefix": prefix,
                        "MaxKeys": 1000,
                    }
                    if marker:
                        list_params["Marker"] = marker

                    response = client.list_objects(**list_params)
                    for obj in response.get("Contents", []):
                        key = obj.get("Key")
                        if key:
                            keys.append(key)

                    is_truncated_value = response.get("IsTruncated")
                    has_more = is_truncated_value is True or str(is_truncated_value).lower() == "true"
                    if not has_more:
                        break
                    marker = response.get("NextMarker")
                    if not marker and response.get("Contents"):
                        marker = response.get("Contents")[-1].get("Key")
                    if not marker:
                        break

                if not keys:
                    return {"success": True, "supported": True, "message": "目录为空或不存在"}

                for key in keys:
                    client.delete_object(Bucket=bucket, Key=key)

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
        except (CosServiceError, CosClientError) as e:
            return {"success": False, "supported": True, "message": f"COS 删除失败: {str(e)}"}
        except Exception as e:
            return {"success": False, "supported": True, "message": f"COS 删除失败: {str(e)}"}

    async def rename_path(
        self,
        path: str,
        new_name: str,
        is_directory: bool = False
    ) -> Dict[str, Any]:
        bucket = self.config.get("bucket")
        region = self.config.get("region")
        if not bucket or not region:
            return {"success": False, "supported": False, "message": "腾讯云 COS 配置不完整"}

        clean_name = (new_name or "").strip().strip("/")
        if not clean_name:
            return {"success": False, "supported": False, "message": "new_name is required"}
        if "/" in clean_name or "\\" in clean_name:
            return {"success": False, "supported": False, "message": "new_name 不能包含路径分隔符"}

        try:
            source_relative = self._normalize_path(path)
            if not source_relative:
                return {"success": False, "supported": False, "message": "path is required"}

            parts = source_relative.split("/")
            parent_relative = "/".join(parts[:-1]) if len(parts) > 1 else ""
            target_relative = f"{parent_relative}/{clean_name}" if parent_relative else clean_name
            source_key = self._build_object_key(source_relative)
            target_key = self._build_object_key(target_relative)
            if source_key == target_key:
                return {"success": True, "supported": True, "message": None}

            client = self._create_client()

            def _copy_object(src_key: str, dst_key: str) -> None:
                client.copy_object(
                    Bucket=bucket,
                    Key=dst_key,
                    CopySource={
                        "Bucket": bucket,
                        "Key": src_key,
                        "Region": region
                    }
                )

            if is_directory:
                source_prefix = source_key.rstrip("/") + "/"
                target_prefix = target_key.rstrip("/") + "/"

                exist_resp = client.list_objects(Bucket=bucket, Prefix=target_prefix, MaxKeys=1)
                if exist_resp.get("Contents"):
                    return {"success": False, "supported": True, "message": "目标目录已存在"}

                marker: Optional[str] = None
                keys: list[str] = []
                while True:
                    list_params: Dict[str, Any] = {
                        "Bucket": bucket,
                        "Prefix": source_prefix,
                        "MaxKeys": 1000,
                    }
                    if marker:
                        list_params["Marker"] = marker
                    resp = client.list_objects(**list_params)
                    for obj in resp.get("Contents", []):
                        key = obj.get("Key")
                        if key:
                            keys.append(key)

                    is_truncated_value = resp.get("IsTruncated")
                    has_more = is_truncated_value is True or str(is_truncated_value).lower() == "true"
                    if not has_more:
                        break
                    marker = resp.get("NextMarker")
                    if not marker and resp.get("Contents"):
                        marker = resp.get("Contents")[-1].get("Key")
                    if not marker:
                        break

                if not keys:
                    return {"success": False, "supported": True, "message": "源目录不存在"}

                for key in keys:
                    suffix = key[len(source_prefix):]
                    new_key = f"{target_prefix}{suffix}" if suffix else target_prefix
                    _copy_object(key, new_key)
                    client.delete_object(Bucket=bucket, Key=key)
                return {"success": True, "supported": True, "message": None}

            # 文件重命名
            try:
                client.head_object(Bucket=bucket, Key=source_key)
            except CosServiceError as e:
                if e.get_status_code() == 404:
                    return {"success": False, "supported": True, "message": "源文件不存在"}
                raise

            try:
                client.head_object(Bucket=bucket, Key=target_key)
                return {"success": False, "supported": True, "message": "目标文件已存在"}
            except CosServiceError as e:
                if e.get_status_code() != 404:
                    raise

            _copy_object(source_key, target_key)
            client.delete_object(Bucket=bucket, Key=source_key)
            return {"success": True, "supported": True, "message": None}
        except ValueError as e:
            return {"success": False, "supported": False, "message": str(e)}
        except (CosServiceError, CosClientError) as e:
            return {"success": False, "supported": True, "message": f"COS 重命名失败: {str(e)}"}
        except Exception as e:
            return {"success": False, "supported": True, "message": f"COS 重命名失败: {str(e)}"}

    async def browse(
        self,
        path: str = "",
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        secret_id = self.config.get("secret_id")
        secret_key = self.config.get("secret_key")
        bucket = self.config.get("bucket")
        region = self.config.get("region")

        if not all([secret_id, secret_key, bucket, region]):
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": "腾讯云 COS 配置不完整"
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
                request_params["Marker"] = cursor

            response = client.list_objects(**request_params)

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
                if not key or key.endswith("/"):
                    continue
                relative_path = self._to_relative_path(key)
                if not relative_path:
                    continue
                items.append({
                    "name": relative_path.split("/")[-1],
                    "path": relative_path,
                    "entry_type": "file",
                    "size": obj.get("Size"),
                    "updated_at": obj.get("LastModified"),
                    "url": self._build_public_url(key)
                })

            items.sort(key=lambda item: (0 if item["entry_type"] == "directory" else 1, item["name"].lower()))

            is_truncated_value = response.get("IsTruncated")
            has_more = is_truncated_value is True or str(is_truncated_value).lower() == "true"
            next_cursor = response.get("NextMarker")
            if has_more and not next_cursor:
                contents = response.get("Contents", [])
                if contents:
                    next_cursor = contents[-1].get("Key")

            return {
                "supported": True,
                "items": items,
                "path": normalized_path,
                "next_cursor": next_cursor,
                "has_more": has_more
            }
        except ValueError as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": str(e)
            }
        except (CosServiceError, CosClientError) as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": f"COS 浏览失败: {str(e)}"
            }
        except Exception as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": f"COS 浏览失败: {str(e)}"
            }

    async def count_items(self, path: str = "") -> Dict[str, Any]:
        secret_id = self.config.get("secret_id")
        secret_key = self.config.get("secret_key")
        bucket = self.config.get("bucket")
        region = self.config.get("region")

        if not all([secret_id, secret_key, bucket, region]):
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": "腾讯云 COS 配置不完整"
            }

        try:
            prefix = self._build_object_prefix(path)
            normalized_path = self._normalize_path(path)
            client = self._create_client()
            marker = None
            total_count = 0

            while True:
                request_params: Dict[str, Any] = {
                    "Bucket": bucket,
                    "Prefix": prefix,
                    "Delimiter": "/",
                    "MaxKeys": 1000
                }
                if marker:
                    request_params["Marker"] = marker

                response = client.list_objects(**request_params)
                total_count += len(response.get("CommonPrefixes") or [])

                for obj in response.get("Contents", []):
                    key = obj.get("Key")
                    if not key or key.endswith("/"):
                        continue
                    total_count += 1

                is_truncated_value = response.get("IsTruncated")
                has_more = is_truncated_value is True or str(is_truncated_value).lower() == "true"
                if not has_more:
                    break

                next_marker = response.get("NextMarker")
                if not next_marker:
                    contents = response.get("Contents", [])
                    prefixes = response.get("CommonPrefixes", [])
                    if contents:
                        next_marker = contents[-1].get("Key")
                    elif prefixes:
                        last_prefix = prefixes[-1]
                        next_marker = last_prefix.get("Prefix") if isinstance(last_prefix, dict) else str(last_prefix or "")
                if not next_marker or next_marker == marker:
                    break
                marker = next_marker

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
        except (CosServiceError, CosClientError) as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": f"COS 统计失败: {str(e)}"
            }
        except Exception as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": f"COS 统计失败: {str(e)}"
            }
    
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
