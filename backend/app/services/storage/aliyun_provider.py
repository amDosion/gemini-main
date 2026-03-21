"""
阿里云 OSS 存储提供商
支持上传文件到阿里云 OSS
"""

import oss2
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from .base import BaseStorageProvider, UploadResult


class AliyunProvider(BaseStorageProvider):
    """阿里云 OSS 存储提供商"""

    def _normalize_path(self, value: str) -> str:
        normalized = (value or "").replace("\\", "/").strip().strip("/")
        if ".." in normalized.split("/"):
            raise ValueError("非法目录路径")
        return normalized

    def _clean_endpoint(self, endpoint: str) -> str:
        return endpoint.replace("https://", "").replace("http://", "").rstrip("/")

    def _extract_object_key_from_url(self, file_url: str) -> str:
        bucket_name = self.config.get("bucket")
        parsed = urlparse(file_url or "")
        path = parsed.path.lstrip("/")
        if bucket_name and path.startswith(f"{bucket_name}/"):
            path = path[len(bucket_name) + 1:]
        return path.strip("/")

    def _create_bucket_client(self):
        access_key_id = self.config.get("access_key_id")
        access_key_secret = self.config.get("access_key_secret")
        bucket_name = self.config.get("bucket")
        endpoint = self.config.get("endpoint")

        if not all([access_key_id, access_key_secret, bucket_name, endpoint]):
            raise ValueError("阿里云 OSS 配置不完整：缺少必填项（access_key_id, access_key_secret, bucket, endpoint）")

        oss_endpoint = self._clean_endpoint(endpoint)
        auth = oss2.Auth(access_key_id, access_key_secret)
        return oss2.Bucket(auth, oss_endpoint, bucket_name)

    def _build_public_url(self, object_key: str) -> str:
        bucket_name = self.config.get("bucket")
        endpoint = self.config.get("endpoint")
        custom_domain = self.config.get("custom_domain")
        secure = self.config.get("secure", True)
        protocol = "https" if secure else "http"
        if custom_domain:
            domain = custom_domain.replace("https://", "").replace("http://", "").rstrip("/")
            return f"{protocol}://{domain}/{object_key}"
        return f"{protocol}://{bucket_name}.{self._clean_endpoint(endpoint)}/{object_key}"
    
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
        access_key_id = self.config.get("access_key_id")
        access_key_secret = self.config.get("access_key_secret")
        bucket_name = self.config.get("bucket")
        endpoint = self.config.get("endpoint")
        
        # 验证配置
        if not all([access_key_id, access_key_secret, bucket_name, endpoint]):
            return UploadResult(
                success=False,
                error="阿里云 OSS 配置不完整：缺少必填项（access_key_id, access_key_secret, bucket, endpoint）",
                provider="aliyun-oss"
            )
        
        try:
            # 创建 OSS 认证和 Bucket 对象
            bucket = self._create_bucket_client()
            
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
                image_url = self._build_public_url(object_name)
                
                return UploadResult(
                    success=True,
                    url=image_url,
                    provider="aliyun-oss",
                    metadata={
                        "object_name": object_name,
                        "bucket": bucket_name,
                        "endpoint": self._clean_endpoint(endpoint)
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

    async def browse(
        self,
        path: str = "",
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        access_key_id = self.config.get("access_key_id")
        access_key_secret = self.config.get("access_key_secret")
        bucket_name = self.config.get("bucket")
        endpoint = self.config.get("endpoint")

        if not all([access_key_id, access_key_secret, bucket_name, endpoint]):
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": "阿里云 OSS 配置不完整"
            }

        try:
            normalized_path = self._normalize_path(path)
            prefix = f"{normalized_path}/" if normalized_path else ""
            max_keys = max(1, min(limit, 1000))
            bucket = self._create_bucket_client()

            result = bucket.list_objects(
                prefix=prefix,
                delimiter="/",
                marker=cursor or "",
                max_keys=max_keys
            )

            items: list[dict] = []

            for directory in result.prefix_list or []:
                dir_key = (directory or "").rstrip("/")
                if not dir_key:
                    continue
                name = dir_key.split("/")[-1]
                items.append({
                    "name": name,
                    "path": dir_key,
                    "entry_type": "directory",
                    "size": None,
                    "updated_at": None,
                    "url": None
                })

            for obj in result.object_list or []:
                key = getattr(obj, "key", "")
                if not key or key.endswith("/"):
                    continue
                items.append({
                    "name": key.split("/")[-1],
                    "path": key,
                    "entry_type": "file",
                    "size": getattr(obj, "size", None),
                    "updated_at": datetime.fromtimestamp(getattr(obj, "last_modified", 0)).isoformat() if getattr(obj, "last_modified", None) else None,
                    "url": self._build_public_url(key)
                })

            items.sort(key=lambda item: (0 if item["entry_type"] == "directory" else 1, item["name"].lower()))

            return {
                "supported": True,
                "items": items,
                "path": normalized_path,
                "next_cursor": result.next_marker if result.is_truncated else None,
                "has_more": bool(result.is_truncated)
            }
        except ValueError as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": str(e)
            }
        except oss2.exceptions.OssError as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": f"阿里云 OSS 浏览失败: {e.code} - {e.message}"
            }
        except Exception as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": f"阿里云 OSS 浏览失败: {str(e)}"
            }

    async def count_items(self, path: str = "") -> Dict[str, Any]:
        access_key_id = self.config.get("access_key_id")
        access_key_secret = self.config.get("access_key_secret")
        bucket_name = self.config.get("bucket")
        endpoint = self.config.get("endpoint")

        if not all([access_key_id, access_key_secret, bucket_name, endpoint]):
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": "阿里云 OSS 配置不完整"
            }

        try:
            normalized_path = self._normalize_path(path)
            prefix = f"{normalized_path}/" if normalized_path else ""
            bucket = self._create_bucket_client()
            marker = ""
            total_count = 0

            while True:
                result = bucket.list_objects(
                    prefix=prefix,
                    delimiter="/",
                    marker=marker,
                    max_keys=1000
                )

                total_count += len(result.prefix_list or [])
                for obj in result.object_list or []:
                    key = getattr(obj, "key", "")
                    if not key or key.endswith("/"):
                        continue
                    total_count += 1

                if not result.is_truncated or not result.next_marker:
                    break
                marker = result.next_marker

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
        except oss2.exceptions.OssError as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": f"阿里云 OSS 统计失败: {e.code} - {e.message}"
            }
        except Exception as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": f"阿里云 OSS 统计失败: {str(e)}"
            }
    
    async def delete(self, file_url: str) -> bool:
        """
        删除文件（占位实现）
        
        Args:
            file_url: 文件 URL
            
        Returns:
            bool: 删除是否成功
        """
        try:
            object_key = self._extract_object_key_from_url(file_url)
            if not object_key:
                return False
            bucket = self._create_bucket_client()
            result = bucket.delete_object(object_key)
            return result.status in [200, 204]
        except Exception:
            return False

    async def delete_path(
        self,
        path: str,
        is_directory: bool = False,
        file_url: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            bucket = self._create_bucket_client()
            if is_directory:
                normalized = self._normalize_path(path)
                if not normalized:
                    return {"success": False, "supported": False, "message": "不支持删除根目录"}

                prefix = normalized.rstrip("/") + "/"
                marker = ""
                keys: list[str] = []

                while True:
                    result = bucket.list_objects(prefix=prefix, marker=marker, max_keys=1000)
                    for obj in result.object_list or []:
                        key = getattr(obj, "key", None)
                        if key:
                            keys.append(key)
                    if not result.is_truncated:
                        break
                    marker = result.next_marker or ""
                    if not marker:
                        break

                if not keys:
                    return {"success": True, "supported": True, "message": "目录为空或不存在"}

                for key in keys:
                    bucket.delete_object(key)

                return {"success": True, "supported": True, "message": None}

            object_key = self._normalize_path(path) if path else self._extract_object_key_from_url(file_url or "")
            if not object_key:
                return {"success": False, "supported": False, "message": "path is required"}

            result = bucket.delete_object(object_key)
            ok = result.status in [200, 204]
            return {"success": ok, "supported": True, "message": None if ok else "删除失败"}
        except ValueError as e:
            return {"success": False, "supported": False, "message": str(e)}
        except oss2.exceptions.OssError as e:
            return {"success": False, "supported": True, "message": f"阿里云 OSS 删除失败: {e.code} - {e.message}"}
        except Exception as e:
            return {"success": False, "supported": True, "message": f"阿里云 OSS 删除失败: {str(e)}"}

    async def rename_path(
        self,
        path: str,
        new_name: str,
        is_directory: bool = False
    ) -> Dict[str, Any]:
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

            if source_relative == target_relative:
                return {"success": True, "supported": True, "message": None}

            bucket_name = self.config.get("bucket")
            bucket = self._create_bucket_client()

            if is_directory:
                source_prefix = source_relative.rstrip("/") + "/"
                target_prefix = target_relative.rstrip("/") + "/"

                existing_target = bucket.list_objects(prefix=target_prefix, max_keys=1)
                if existing_target.object_list:
                    return {"success": False, "supported": True, "message": "目标目录已存在"}

                marker = ""
                keys: list[str] = []
                while True:
                    result = bucket.list_objects(prefix=source_prefix, marker=marker, max_keys=1000)
                    for obj in result.object_list or []:
                        key = getattr(obj, "key", None)
                        if key:
                            keys.append(key)
                    if not result.is_truncated:
                        break
                    marker = result.next_marker or ""
                    if not marker:
                        break

                if not keys:
                    return {"success": False, "supported": True, "message": "源目录不存在"}

                for key in keys:
                    suffix = key[len(source_prefix):]
                    new_key = f"{target_prefix}{suffix}" if suffix else target_prefix
                    bucket.copy_object(bucket_name, key, new_key)
                    bucket.delete_object(key)
                return {"success": True, "supported": True, "message": None}

            if not bucket.object_exists(source_relative):
                return {"success": False, "supported": True, "message": "源文件不存在"}
            if bucket.object_exists(target_relative):
                return {"success": False, "supported": True, "message": "目标文件已存在"}

            bucket.copy_object(bucket_name, source_relative, target_relative)
            bucket.delete_object(source_relative)
            return {"success": True, "supported": True, "message": None}
        except ValueError as e:
            return {"success": False, "supported": False, "message": str(e)}
        except oss2.exceptions.OssError as e:
            return {"success": False, "supported": True, "message": f"阿里云 OSS 重命名失败: {e.code} - {e.message}"}
        except Exception as e:
            return {"success": False, "supported": True, "message": f"阿里云 OSS 重命名失败: {str(e)}"}
    
    async def test(self) -> UploadResult:
        """
        测试配置是否有效
        
        Returns:
            UploadResult: 测试结果
        """
        access_key_id = self.config.get("access_key_id")
        access_key_secret = self.config.get("access_key_secret")
        bucket_name = self.config.get("bucket")
        endpoint = self.config.get("endpoint")

        if not all([access_key_id, access_key_secret, bucket_name, endpoint]):
            return UploadResult(
                success=False,
                error="阿里云 OSS 配置不完整：缺少必填项（access_key_id, access_key_secret, bucket, endpoint）",
                provider="aliyun-oss"
            )
        
        return UploadResult(
            success=True,
            provider="aliyun-oss"
        )
