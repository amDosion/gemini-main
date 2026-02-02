"""
本地存储提供商
支持将文件保存到本地文件系统
"""

import os
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
from .base import BaseStorageProvider, UploadResult


class LocalProvider(BaseStorageProvider):
    """本地存储提供商"""
    
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
        storage_path = self.config.get("storage_path")
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
        storage_path = self.config.get("storage_path")
        url_prefix = self.config.get("url_prefix")

        # 验证配置
        if not storage_path or not url_prefix:
            return UploadResult(
                success=False,
                error="本地存储配置不完整：缺少必填项（storage_path, url_prefix）",
                provider="local"
            )
        
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
        storage_path = self.config.get("storage_path")
        url_prefix = self.config.get("url_prefix")

        if not storage_path or not url_prefix:
            return False
        
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
    
    async def test(self) -> UploadResult:
        """
        测试配置是否有效
        
        Returns:
            UploadResult: 测试结果
        """
        storage_path = self.config.get("storage_path")
        url_prefix = self.config.get("url_prefix")

        if not storage_path or not url_prefix:
            return UploadResult(
                success=False,
                error="本地存储配置不完整：缺少必填项（storage_path, url_prefix）",
                provider="local"
            )
        
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
