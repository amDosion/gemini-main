"""
Gemini Files API Handler

处理文件上传、下载、管理等操作的专门模块。
支持多模态输入，包括文档、图片、音频、视频等文件类型。
"""

import os
import asyncio
import mimetypes
from typing import Callable, Optional, List, Dict, Any, Union
from pathlib import Path

class FileHandler:
    """Gemini Files API 处理器"""

    def __init__(self, client_factory: Callable):
        """
        初始化文件处理器

        Args:
            client_factory: A callable that returns a configured Gemini client
        """
        self._client_factory = client_factory
    
    async def upload_file(
        self, 
        file_path: Union[str, Path], 
        display_name: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        上传文件到 Gemini Files API
        
        Args:
            file_path: 文件路径
            display_name: 显示名称（可选）
            mime_type: MIME 类型（可选，自动检测）
            
        Returns:
            包含文件信息的字典
            
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式不支持
        """
        file_path = Path(file_path)
        
        # 检查文件是否存在
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 自动检测 MIME 类型
        if mime_type is None:
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type is None:
                mime_type = 'application/octet-stream'
        
        # 设置显示名称
        if display_name is None:
            display_name = file_path.name
        
        try:
            # 确保 SDK 已初始化
            client = self._client_factory()
            
            # 上传文件
            file_obj = await client.aio.files.upload(
                file=str(file_path),
                config={
                    'display_name': display_name,
                    'mime_type': mime_type
                }
            )
            
            return {
                'name': file_obj.name,
                'display_name': file_obj.display_name,
                'mime_type': file_obj.mime_type,
                'size_bytes': file_obj.size_bytes,
                'uri': file_obj.uri,
                'create_time': file_obj.create_time,
                'update_time': file_obj.update_time,
                'expiration_time': file_obj.expiration_time,
                'sha256_hash': file_obj.sha256_hash,
                'state': file_obj.state
            }
            
        except Exception as e:
            raise ValueError(f"文件上传失败: {str(e)}")
    
    async def get_file_info(self, file_name: str) -> Dict[str, Any]:
        """
        获取文件信息
        
        Args:
            file_name: 文件名称（格式：files/xxx）
            
        Returns:
            文件信息字典
        """
        try:
            client = self._client_factory()
            
            file_obj = await client.aio.files.get(name=file_name)
            
            return {
                'name': file_obj.name,
                'display_name': file_obj.display_name,
                'mime_type': file_obj.mime_type,
                'size_bytes': file_obj.size_bytes,
                'uri': file_obj.uri,
                'create_time': file_obj.create_time,
                'update_time': file_obj.update_time,
                'expiration_time': file_obj.expiration_time,
                'sha256_hash': file_obj.sha256_hash,
                'state': file_obj.state
            }
            
        except Exception as e:
            raise ValueError(f"获取文件信息失败: {str(e)}")
    
    async def download_file(self, file_name: str, save_path: Optional[str] = None) -> bytes:
        """
        下载文件
        
        Args:
            file_name: 文件名称（格式：files/xxx）
            save_path: 保存路径（可选）
            
        Returns:
            文件字节数据
        """
        try:
            client = self._client_factory()
            
            # 下载文件数据
            file_data = await client.aio.files.download(file=file_name)
            
            # 如果指定了保存路径，则保存到文件
            if save_path:
                save_path = Path(save_path)
                save_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(save_path, 'wb') as f:
                    f.write(file_data)
            
            return file_data
            
        except Exception as e:
            raise ValueError(f"文件下载失败: {str(e)}")
    
    async def delete_file(self, file_name: str) -> bool:
        """
        删除文件
        
        Args:
            file_name: 文件名称（格式：files/xxx）
            
        Returns:
            删除是否成功
        """
        try:
            client = self._client_factory()
            
            await client.aio.files.delete(name=file_name)
            return True
            
        except Exception as e:
            raise ValueError(f"文件删除失败: {str(e)}")
    
    async def list_files(self, page_size: int = 10) -> List[Dict[str, Any]]:
        """
        列出所有文件
        
        Args:
            page_size: 每页文件数量
            
        Returns:
            文件列表
        """
        try:
            client = self._client_factory()
            
            files = []
            async for file_obj in await client.aio.files.list(
                config={'page_size': page_size}
            ):
                files.append({
                    'name': file_obj.name,
                    'display_name': file_obj.display_name,
                    'mime_type': file_obj.mime_type,
                    'size_bytes': file_obj.size_bytes,
                    'uri': file_obj.uri,
                    'create_time': file_obj.create_time,
                    'update_time': file_obj.update_time,
                    'expiration_time': file_obj.expiration_time,
                    'state': file_obj.state
                })
            
            return files
            
        except Exception as e:
            raise ValueError(f"获取文件列表失败: {str(e)}")
    
    def create_file_part(self, file_name: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """
        创建文件部分，用于在对话中引用已上传的文件
        
        Args:
            file_name: 文件名称（格式：files/xxx）
            mime_type: MIME 类型（可选）
            
        Returns:
            文件部分字典，可用于消息内容
        """
        part = {
            'file_data': {
                'file_uri': file_name
            }
        }
        
        if mime_type:
            part['file_data']['mime_type'] = mime_type
        
        return part
    
    def get_supported_mime_types(self) -> Dict[str, List[str]]:
        """
        获取支持的文件类型
        
        Returns:
            按类别分组的 MIME 类型字典
        """
        return {
            'images': [
                'image/jpeg',
                'image/png',
                'image/gif',
                'image/webp',
                'image/bmp',
                'image/tiff'
            ],
            'documents': [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-powerpoint',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'text/plain',
                'text/csv',
                'text/html',
                'text/markdown'
            ],
            'audio': [
                'audio/mpeg',
                'audio/wav',
                'audio/ogg',
                'audio/flac',
                'audio/aac',
                'audio/mp4'
            ],
            'video': [
                'video/mp4',
                'video/mpeg',
                'video/quicktime',
                'video/webm',
                'video/avi',
                'video/x-msvideo'
            ],
            'code': [
                'text/x-python',
                'text/javascript',
                'text/x-java-source',
                'text/x-c',
                'text/x-c++',
                'application/json',
                'application/xml',
                'text/x-sql'
            ]
        }
    
    def validate_file_type(self, file_path: Union[str, Path]) -> bool:
        """
        验证文件类型是否支持
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否支持该文件类型
        """
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            return False
        
        supported_types = self.get_supported_mime_types()
        all_supported = []
        for types_list in supported_types.values():
            all_supported.extend(types_list)
        
        return mime_type in all_supported
    
    def get_file_category(self, file_path: Union[str, Path]) -> Optional[str]:
        """
        获取文件类别
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件类别（images/documents/audio/video/code）或 None
        """
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type is None:
            return None
        
        supported_types = self.get_supported_mime_types()
        for category, types_list in supported_types.items():
            if mime_type in types_list:
                return category
        
        return None