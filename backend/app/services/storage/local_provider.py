"""
本地存储提供商
支持将文件保存到本地文件系统
"""

import os
import shutil
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from ...core.path_utils import get_project_root
from .base import BaseStorageProvider, UploadResult

DEFAULT_LOCAL_URL_PREFIX = "/api/storage/local-files"
DEFAULT_LOCAL_STORAGE_RELATIVE_PATH = "backend/app/temp/local_storage"


def resolve_local_storage_runtime_config(config: Optional[Dict[str, Any]] = None) -> tuple[str, str]:
    runtime_config = dict(config or {})
    storage_path = str(runtime_config.get("storage_path") or "").strip()
    url_prefix = str(runtime_config.get("url_prefix") or "").strip()

    if not storage_path:
        storage_path = os.path.join(get_project_root(), *DEFAULT_LOCAL_STORAGE_RELATIVE_PATH.split("/"))
    elif not os.path.isabs(storage_path):
        storage_path = os.path.realpath(os.path.join(get_project_root(), storage_path))
    else:
        storage_path = os.path.realpath(storage_path)

    if not url_prefix:
        url_prefix = DEFAULT_LOCAL_URL_PREFIX
    url_prefix = "/" + url_prefix.strip().strip("/")

    return storage_path, url_prefix


def resolve_local_public_file_path(file_url: str, config: Optional[Dict[str, Any]] = None) -> Optional[Path]:
    storage_path, url_prefix = resolve_local_storage_runtime_config(config)
    normalized_url = str(file_url or "").strip()
    url_prefix_clean = url_prefix.rstrip("/")
    if not normalized_url.startswith(url_prefix_clean):
        return None

    relative_path = normalized_url[len(url_prefix_clean):].lstrip("/").replace("/", os.sep)
    if not relative_path:
        return None

    root = os.path.realpath(storage_path)
    target = os.path.realpath(os.path.join(root, relative_path))
    if target != root and not target.startswith(root + os.sep):
        return None

    return Path(target)


class LocalProvider(BaseStorageProvider):
    """本地存储提供商"""

    def _normalize_relative_path(self, value: str) -> str:
        normalized = (value or "").replace("\\", "/").strip()
        normalized = normalized.strip("/")
        return normalized

    def _resolve_directory(self, storage_path: str, relative_path: str) -> tuple[str, str]:
        """解析并校验目录路径，防止路径越权。"""
        root = os.path.realpath(storage_path)
        relative = self._normalize_relative_path(relative_path)
        target = os.path.realpath(os.path.join(root, relative))

        if target != root and not target.startswith(root + os.sep):
            raise ValueError("非法目录路径")

        if not os.path.exists(target):
            raise FileNotFoundError("目录不存在")

        if not os.path.isdir(target):
            raise NotADirectoryError("目标不是目录")

        resolved_relative = os.path.relpath(target, root).replace(os.sep, "/")
        if resolved_relative == ".":
            resolved_relative = ""

        return target, resolved_relative
    
    def _get_directory_size(self, path: str) -> int:
        """计算目录总大小（字节）"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except (OSError, PermissionError):
            pass
        return total_size
    
    def _check_storage_space(self, content_size: int) -> tuple[bool, str]:
        """检查存储空间是否足够"""
        storage_path, _url_prefix = resolve_local_storage_runtime_config(self.config)
        max_size_mb = self.config.get("max_size_mb")
        
        if not max_size_mb:
            return True, ""
        
        try:
            # 计算当前使用空间
            current_size_bytes = self._get_directory_size(storage_path)
            current_size_mb = current_size_bytes / (1024 * 1024)
            
            # 计算上传后的总大小
            new_size_mb = current_size_mb + (content_size / (1024 * 1024))
            
            if new_size_mb > max_size_mb:
                return False, f"存储空间不足：当前 {current_size_mb:.2f}MB，限制 {max_size_mb}MB"
            
            return True, ""
        except Exception as e:
            return False, f"检查存储空间失败: {str(e)}"
    
    async def upload(self, filename: str, content: bytes, content_type: str) -> UploadResult:
        """
        上传文件到本地存储
        
        Args:
            filename: 文件名
            content: 文件内容
            content_type: 文件 MIME 类型
            
        Returns:
            UploadResult: 上传结果
        """
        storage_path, url_prefix = resolve_local_storage_runtime_config(self.config)
        
        # 检查存储空间
        space_ok, space_error = self._check_storage_space(len(content))
        if not space_ok:
            return UploadResult(
                success=False,
                error=space_error,
                provider="local"
            )
        
        try:
            # 确保存储路径存在
            Path(storage_path).mkdir(parents=True, exist_ok=True)
            
            # 生成日期目录结构 (YYYY/MM/DD)
            now = datetime.now()
            date_path = now.strftime("%Y/%m/%d")
            full_dir = os.path.join(storage_path, date_path)
            
            # 创建日期目录
            Path(full_dir).mkdir(parents=True, exist_ok=True)
            
            # 生成唯一文件名（使用时间戳避免冲突）
            timestamp = int(now.timestamp() * 1000)
            
            # 清理文件名（移除路径遍历字符）
            safe_filename = os.path.basename(filename)
            unique_filename = f"{timestamp}_{safe_filename}"
            
            # 构建完整文件路径
            file_path = os.path.join(full_dir, unique_filename)
            
            # 写入文件
            with open(file_path, 'wb') as f:
                f.write(content)
            
            # 计算相对路径
            relative_path = os.path.join(date_path, unique_filename)
            
            # 构建公开访问 URL（使用正斜杠）
            relative_path_url = relative_path.replace('\\', '/')
            url_prefix_clean = url_prefix.rstrip('/')
            public_url = f"{url_prefix_clean}/{relative_path_url}"
            
            # 获取文件大小
            file_size = os.path.getsize(file_path)
            
            return UploadResult(
                success=True,
                url=public_url,
                provider="local",
                metadata={
                    "file_path": file_path,
                    "relative_path": relative_path,
                    "file_size": file_size,
                    "content_type": content_type
                }
            )
        
        except PermissionError:
            return UploadResult(
                success=False,
                error="本地存储权限不足：无法写入文件",
                provider="local"
            )
        except OSError as e:
            return UploadResult(
                success=False,
                error=f"本地存储文件系统错误: {str(e)}",
                provider="local"
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=f"本地存储上传失败: {str(e)}",
                provider="local"
            )
    
    async def delete(self, file_url: str) -> bool:
        """
        删除文件
        
        Args:
            file_url: 文件 URL
            
        Returns:
            bool: 删除是否成功
        """
        storage_path, url_prefix = resolve_local_storage_runtime_config(self.config)
        
        try:
            # 从 URL 中提取相对路径
            url_prefix_clean = url_prefix.rstrip('/')
            if not file_url.startswith(url_prefix_clean):
                return False
            
            relative_path = file_url[len(url_prefix_clean):].lstrip('/')
            
            # 构建完整文件路径
            file_path = os.path.join(storage_path, relative_path.replace('/', os.sep))
            
            # 安全检查：确保文件在 storagePath 内
            file_path_abs = os.path.abspath(file_path)
            storage_path_abs = os.path.abspath(storage_path)
            
            if not file_path_abs.startswith(storage_path_abs):
                return False
            
            # 删除文件
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            
            return False
        
        except (OSError, PermissionError):
            return False
        except Exception:
            return False

    async def browse(
        self,
        path: str = "",
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        storage_path, url_prefix = resolve_local_storage_runtime_config(self.config)

        try:
            Path(storage_path).mkdir(parents=True, exist_ok=True)
            target_dir, normalized_path = self._resolve_directory(storage_path, path)

            offset = 0
            if cursor:
                try:
                    offset = max(int(cursor), 0)
                except ValueError:
                    offset = 0

            entries: list[dict] = []
            with os.scandir(target_dir) as iterator:
                for entry in iterator:
                    stat = entry.stat(follow_symlinks=False)
                    relative_item = os.path.relpath(entry.path, os.path.realpath(storage_path)).replace(os.sep, "/")
                    item = {
                        "name": entry.name,
                        "path": relative_item,
                        "entry_type": "directory" if entry.is_dir(follow_symlinks=False) else "file",
                        "size": None if entry.is_dir(follow_symlinks=False) else stat.st_size,
                        "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "url": None
                    }
                    if item["entry_type"] == "file" and url_prefix:
                        item["url"] = f"{url_prefix.rstrip('/')}/{relative_item}"
                    entries.append(item)

            entries.sort(key=lambda item: (0 if item["entry_type"] == "directory" else 1, item["name"].lower()))

            page_items = entries[offset:offset + limit]
            has_more = offset + limit < len(entries)
            next_cursor = str(offset + limit) if has_more else None

            return {
                "supported": True,
                "items": page_items,
                "path": normalized_path,
                "next_cursor": next_cursor,
                "has_more": has_more
            }
        except FileNotFoundError:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": "目录不存在"
            }
        except NotADirectoryError:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": "目标不是目录"
            }
        except ValueError as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": str(e)
            }
        except Exception as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": f"浏览目录失败: {str(e)}"
            }

    async def count_items(self, path: str = "") -> Dict[str, Any]:
        storage_path, _url_prefix = resolve_local_storage_runtime_config(self.config)

        try:
            Path(storage_path).mkdir(parents=True, exist_ok=True)
            target_dir, normalized_path = self._resolve_directory(storage_path, path)
            with os.scandir(target_dir) as iterator:
                total_count = sum(1 for _ in iterator)
            return {
                "supported": True,
                "path": normalized_path,
                "total_count": total_count
            }
        except FileNotFoundError:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": "目录不存在"
            }
        except NotADirectoryError:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": "目标不是目录"
            }
        except ValueError as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": str(e)
            }
        except Exception as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": f"统计目录失败: {str(e)}"
            }

    async def delete_path(
        self,
        path: str,
        is_directory: bool = False,
        file_url: Optional[str] = None
    ) -> Dict[str, Any]:
        storage_path, _url_prefix = resolve_local_storage_runtime_config(self.config)

        try:
            root = os.path.realpath(storage_path)
            normalized = self._normalize_relative_path(path)
            if not normalized:
                return {"success": False, "supported": False, "message": "path is required"}
            target = os.path.realpath(os.path.join(root, normalized))
            if target != root and not target.startswith(root + os.sep):
                return {"success": False, "supported": False, "message": "非法目录路径"}

            if not os.path.exists(target):
                return {"success": True, "supported": True, "message": "目标不存在，已视为删除成功"}

            if is_directory:
                if not os.path.isdir(target):
                    return {"success": False, "supported": True, "message": "目标不是目录"}
                shutil.rmtree(target)
            else:
                if os.path.isdir(target):
                    return {"success": False, "supported": True, "message": "目标是目录，请使用目录删除"}
                os.remove(target)

            return {"success": True, "supported": True, "message": None}
        except Exception as e:
            return {"success": False, "supported": True, "message": f"删除失败: {str(e)}"}

    async def rename_path(
        self,
        path: str,
        new_name: str,
        is_directory: bool = False
    ) -> Dict[str, Any]:
        storage_path, _url_prefix = resolve_local_storage_runtime_config(self.config)

        try:
            root = os.path.realpath(storage_path)
            normalized = self._normalize_relative_path(path)
            if not normalized:
                return {"success": False, "supported": False, "message": "path is required"}

            source = os.path.realpath(os.path.join(root, normalized))
            if source != root and not source.startswith(root + os.sep):
                return {"success": False, "supported": False, "message": "非法路径"}
            if not os.path.exists(source):
                return {"success": False, "supported": True, "message": "目标不存在"}

            parent = os.path.dirname(source)
            target = os.path.realpath(os.path.join(parent, new_name))
            if target != root and not target.startswith(root + os.sep):
                return {"success": False, "supported": False, "message": "非法目标路径"}
            if os.path.exists(target):
                return {"success": False, "supported": True, "message": "同名文件已存在"}

            if is_directory and not os.path.isdir(source):
                return {"success": False, "supported": True, "message": "目标不是目录"}
            if not is_directory and os.path.isdir(source):
                return {"success": False, "supported": True, "message": "目标是目录"}

            os.rename(source, target)
            return {"success": True, "supported": True, "message": None}
        except Exception as e:
            return {"success": False, "supported": True, "message": f"重命名失败: {str(e)}"}
    
    async def test(self) -> UploadResult:
        """
        测试配置是否有效
        
        Returns:
            UploadResult: 测试结果
        """
        storage_path, url_prefix = resolve_local_storage_runtime_config(self.config)
        
        try:
            # 检查存储路径是否存在
            if not os.path.exists(storage_path):
                # 尝试创建
                Path(storage_path).mkdir(parents=True, exist_ok=True)
            
            # 检查是否可写
            test_file = os.path.join(storage_path, '.test_write')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except (OSError, PermissionError):
                return UploadResult(
                    success=False,
                    error="本地存储路径不可写",
                    provider="local"
                )
            
            # 计算当前使用空间
            current_size_bytes = self._get_directory_size(storage_path)
            current_size_mb = current_size_bytes / (1024 * 1024)
            max_size_mb = self.config.get("max_size_mb")

            metadata = {
                "storage_path": storage_path,
                "current_size_mb": round(current_size_mb, 2)
            }

            if max_size_mb:
                metadata["max_size_mb"] = max_size_mb
                metadata["available_mb"] = round(max_size_mb - current_size_mb, 2)
            
            return UploadResult(
                success=True,
                provider="local",
                metadata=metadata
            )
        
        except PermissionError:
            return UploadResult(
                success=False,
                error="本地存储权限不足",
                provider="local"
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=f"本地存储测试失败: {str(e)}",
                provider="local"
            )
