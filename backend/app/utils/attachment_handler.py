"""
附件处理工具库 (Python 后端版本)

与前端 attachmentHandler.ts 搭配使用，提供统一的附件处理能力。

核心功能：
1. Base64 Data URL 解析与转换
2. URL 类型检测（Base64、Blob、HTTP）
3. 附件数据验证与处理
4. 文件保存与读取

使用示例：
```python
from app.utils.attachment_handler import AttachmentHandler

# 1. 解析前端发送的附件
attachments = request_body.get('attachments', [])
for att in attachments:
    handler = AttachmentHandler(att)

    # 检查类型
    if handler.is_base64:
        # 保存 Base64 为文件
        file_path = handler.save_to_file('/tmp/uploads')

    # 获取二进制数据
    binary_data = handler.get_binary_data()
```

依赖：
- Python 3.8+
- 无外部依赖（纯标准库）
"""

import base64
import os
import uuid
import re
import mimetypes
from typing import Optional, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
import tempfile
import hashlib


# ============================================================
# 类型定义
# ============================================================

@dataclass
class Attachment:
    """
    附件数据结构

    字段说明：
    - id: 唯一标识符
    - mime_type: MIME 类型（后端 snake_case）
    - name: 文件名
    - url: 主 URL（Base64 Data URL 或 HTTP URL）
    - temp_url: 临时 URL（可选）
    - size: 文件大小（字节）
    - upload_status: 上传状态（后端 snake_case）

    注意：中间件会自动转换前端的 camelCase 为 snake_case
    """
    id: str
    mime_type: str
    name: str
    url: str
    temp_url: Optional[str] = None
    size: Optional[int] = None
    upload_status: str = 'pending'

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Attachment':
        """从字典创建 Attachment（接收 snake_case）"""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            mime_type=data.get('mime_type', 'application/octet-stream'),
            name=data.get('name', 'unknown'),
            url=data.get('url', ''),
            temp_url=data.get('temp_url'),
            size=data.get('size'),
            upload_status=data.get('upload_status', 'pending')
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（输出 snake_case，中间件会转为 camelCase）"""
        return {
            'id': self.id,
            'mime_type': self.mime_type,
            'name': self.name,
            'url': self.url,
            'temp_url': self.temp_url,
            'size': self.size,
            'upload_status': self.upload_status
        }


@dataclass
class ProcessResult:
    """处理结果"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


# ============================================================
# URL 类型检测
# ============================================================

def is_base64_url(url: Optional[str]) -> bool:
    """
    检查是否为 Base64 Data URL

    Args:
        url: URL 字符串

    Returns:
        是否为 Base64 Data URL

    Example:
        >>> is_base64_url('data:image/png;base64,iVBORw0...')
        True
    """
    if not url:
        return False
    return url.startswith('data:')


def is_blob_url(url: Optional[str]) -> bool:
    """
    检查是否为 Blob URL

    注意：Blob URL 只在浏览器端有效，后端无法直接访问

    Args:
        url: URL 字符串

    Returns:
        是否为 Blob URL

    Example:
        >>> is_blob_url('blob:http://localhost:3000/xxx')
        True
    """
    if not url:
        return False
    return url.startswith('blob:')


def is_http_url(url: Optional[str]) -> bool:
    """
    检查是否为 HTTP/HTTPS URL

    Args:
        url: URL 字符串

    Returns:
        是否为 HTTP URL

    Example:
        >>> is_http_url('https://example.com/image.png')
        True
    """
    if not url:
        return False
    return url.startswith('http://') or url.startswith('https://')


def get_url_type(url: Optional[str]) -> str:
    """
    获取 URL 类型

    Args:
        url: URL 字符串

    Returns:
        URL 类型：'base64', 'blob', 'http', 'empty', 'unknown'
    """
    if not url:
        return 'empty'
    if is_base64_url(url):
        return 'base64'
    if is_blob_url(url):
        return 'blob'
    if is_http_url(url):
        return 'http'
    return 'unknown'


# ============================================================
# Base64 解析与转换
# ============================================================

def parse_data_url(data_url: str) -> Tuple[str, bytes]:
    """
    解析 Base64 Data URL

    Args:
        data_url: Base64 Data URL (如 'data:image/png;base64,iVBORw0...')

    Returns:
        (mime_type, binary_data) 元组

    Raises:
        ValueError: 如果格式无效

    Example:
        >>> mime_type, data = parse_data_url('data:image/png;base64,iVBORw0KGgo=')
        >>> mime_type
        'image/png'
    """
    if not data_url.startswith('data:'):
        raise ValueError("Invalid data URL: must start with 'data:'")

    # 格式: data:image/png;base64,iVBORw0KGgo...
    try:
        # 分割 header 和 data
        header, base64_str = data_url.split(',', 1)

        # 提取 MIME 类型
        # header 格式: data:image/png;base64
        mime_part = header.split(':')[1]  # image/png;base64
        mime_type = mime_part.split(';')[0]  # image/png

        if not mime_type:
            mime_type = 'application/octet-stream'

        # 解码 Base64
        binary_data = base64.b64decode(base64_str)

        return mime_type, binary_data

    except Exception as e:
        raise ValueError(f"Failed to parse data URL: {e}")


def encode_to_data_url(binary_data: bytes, mime_type: str = 'application/octet-stream') -> str:
    """
    将二进制数据编码为 Base64 Data URL

    Args:
        binary_data: 二进制数据
        mime_type: MIME 类型

    Returns:
        Base64 Data URL

    Example:
        >>> data_url = encode_to_data_url(b'hello', 'text/plain')
        >>> data_url
        'data:text/plain;base64,aGVsbG8='
    """
    base64_str = base64.b64encode(binary_data).decode('utf-8')
    return f"data:{mime_type};base64,{base64_str}"


def base64_to_bytes(base64_str: str) -> bytes:
    """
    将 Base64 字符串解码为二进制数据

    支持两种格式：
    - 纯 Base64 字符串
    - Data URL (data:mime/type;base64,xxx)

    Args:
        base64_str: Base64 字符串或 Data URL

    Returns:
        二进制数据
    """
    if base64_str.startswith('data:'):
        _, binary_data = parse_data_url(base64_str)
        return binary_data
    else:
        return base64.b64decode(base64_str)


def bytes_to_base64(binary_data: bytes) -> str:
    """
    将二进制数据编码为 Base64 字符串

    Args:
        binary_data: 二进制数据

    Returns:
        Base64 字符串（不含 data: 前缀）
    """
    return base64.b64encode(binary_data).decode('utf-8')


# ============================================================
# MIME 类型处理
# ============================================================

def get_extension_from_mime(mime_type: str) -> str:
    """
    根据 MIME 类型获取文件扩展名

    Args:
        mime_type: MIME 类型

    Returns:
        文件扩展名（含点号）
    """
    # 常用类型映射
    mime_to_ext = {
        'image/png': '.png',
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'image/svg+xml': '.svg',
        'application/pdf': '.pdf',
        'text/plain': '.txt',
        'text/html': '.html',
        'text/css': '.css',
        'text/javascript': '.js',
        'application/json': '.json',
        'application/xml': '.xml',
        'video/mp4': '.mp4',
        'video/webm': '.webm',
        'audio/mpeg': '.mp3',
        'audio/wav': '.wav',
    }

    if mime_type in mime_to_ext:
        return mime_to_ext[mime_type]

    # 使用 mimetypes 库
    ext = mimetypes.guess_extension(mime_type)
    return ext or '.bin'


def get_mime_from_extension(filename: str) -> str:
    """
    根据文件名获取 MIME 类型

    Args:
        filename: 文件名

    Returns:
        MIME 类型
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or 'application/octet-stream'


# ============================================================
# 附件处理器类
# ============================================================

class AttachmentHandler:
    """
    附件处理器

    用于处理前端发送的附件数据，支持：
    - Base64 Data URL 解析
    - 文件保存
    - 二进制数据提取

    Example:
        >>> handler = AttachmentHandler({
        ...     'id': 'att-123',
        ...     'url': 'data:image/png;base64,iVBORw0...',
        ...     'mimeType': 'image/png',
        ...     'name': 'image.png'
        ... })
        >>> handler.is_base64
        True
        >>> binary_data = handler.get_binary_data()
        >>> file_path = handler.save_to_file('/tmp/uploads')
    """

    def __init__(self, attachment_data: Union[Dict[str, Any], Attachment]):
        """
        初始化附件处理器

        Args:
            attachment_data: 附件数据（字典或 Attachment 对象）
        """
        if isinstance(attachment_data, Attachment):
            self.attachment = attachment_data
        else:
            self.attachment = Attachment.from_dict(attachment_data)

        self._binary_data: Optional[bytes] = None
        self._parsed_mime: Optional[str] = None

    # ==================== 属性 ====================

    @property
    def id(self) -> str:
        """附件 ID"""
        return self.attachment.id

    @property
    def url(self) -> str:
        """附件 URL"""
        return self.attachment.url

    @property
    def mime_type(self) -> str:
        """MIME 类型"""
        return self._parsed_mime or self.attachment.mime_type

    @property
    def name(self) -> str:
        """文件名"""
        return self.attachment.name

    @property
    def url_type(self) -> str:
        """URL 类型"""
        return get_url_type(self.attachment.url)

    @property
    def is_base64(self) -> bool:
        """是否为 Base64 Data URL"""
        return is_base64_url(self.attachment.url)

    @property
    def is_http(self) -> bool:
        """是否为 HTTP URL"""
        return is_http_url(self.attachment.url)

    @property
    def is_blob(self) -> bool:
        """是否为 Blob URL（后端无法处理）"""
        return is_blob_url(self.attachment.url)

    # ==================== 数据提取 ====================

    def get_binary_data(self) -> Optional[bytes]:
        """
        获取附件的二进制数据

        支持的 URL 类型：
        - Base64 Data URL：解码为二进制
        - HTTP URL：需要单独下载（本方法不处理）

        Returns:
            二进制数据，如果无法处理返回 None
        """
        if self._binary_data is not None:
            return self._binary_data

        url = self.attachment.url

        if is_base64_url(url):
            try:
                self._parsed_mime, self._binary_data = parse_data_url(url)
                return self._binary_data
            except ValueError:
                return None

        # Blob URL 和 HTTP URL 需要其他方式处理
        return None

    def get_base64_string(self) -> Optional[str]:
        """
        获取纯 Base64 字符串（不含 data: 前缀）

        Returns:
            Base64 字符串，如果不是 Base64 URL 返回 None
        """
        if not is_base64_url(self.attachment.url):
            return None

        try:
            # 格式: data:image/png;base64,iVBORw0KGgo...
            _, base64_str = self.attachment.url.split(',', 1)
            return base64_str
        except ValueError:
            return None

    def get_size(self) -> int:
        """
        获取附件大小（字节）

        Returns:
            文件大小
        """
        if self.attachment.size:
            return self.attachment.size

        binary_data = self.get_binary_data()
        if binary_data:
            return len(binary_data)

        return 0

    # ==================== 文件操作 ====================

    def save_to_file(
        self,
        directory: str,
        filename: Optional[str] = None,
        create_dir: bool = True
    ) -> Optional[str]:
        """
        将附件保存为文件

        Args:
            directory: 保存目录
            filename: 文件名（可选，默认使用附件名或生成）
            create_dir: 是否自动创建目录

        Returns:
            保存的文件路径，失败返回 None
        """
        binary_data = self.get_binary_data()
        if not binary_data:
            return None

        # 确保目录存在
        if create_dir:
            os.makedirs(directory, exist_ok=True)

        # 生成文件名
        if not filename:
            filename = self.attachment.name
            if not filename or filename == 'unknown':
                ext = get_extension_from_mime(self.mime_type)
                filename = f"{self.id}{ext}"

        # 保存文件
        file_path = os.path.join(directory, filename)
        with open(file_path, 'wb') as f:
            f.write(binary_data)

        return file_path

    def save_to_temp_file(self, prefix: str = 'attachment_') -> Optional[str]:
        """
        将附件保存为临时文件

        Args:
            prefix: 文件名前缀

        Returns:
            临时文件路径，失败返回 None
        """
        binary_data = self.get_binary_data()
        if not binary_data:
            return None

        ext = get_extension_from_mime(self.mime_type)

        # 创建临时文件
        fd, temp_path = tempfile.mkstemp(suffix=ext, prefix=prefix)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(binary_data)
            return temp_path
        except Exception:
            os.close(fd)
            return None

    # ==================== 验证 ====================

    def validate(
        self,
        max_size: Optional[int] = None,
        allowed_types: Optional[list] = None
    ) -> ProcessResult:
        """
        验证附件

        Args:
            max_size: 最大文件大小（字节）
            allowed_types: 允许的 MIME 类型列表

        Returns:
            验证结果
        """
        # 检查 URL 类型
        if self.is_blob:
            return ProcessResult(
                success=False,
                error="Blob URLs cannot be processed on the server"
            )

        if not self.is_base64 and not self.is_http:
            return ProcessResult(
                success=False,
                error=f"Unsupported URL type: {self.url_type}"
            )

        # 检查大小
        if max_size:
            size = self.get_size()
            if size > max_size:
                return ProcessResult(
                    success=False,
                    error=f"File size ({size} bytes) exceeds limit ({max_size} bytes)"
                )

        # 检查 MIME 类型
        if allowed_types:
            mime = self.mime_type
            # 支持通配符，如 'image/*'
            is_allowed = False
            for allowed in allowed_types:
                if allowed.endswith('/*'):
                    category = allowed.replace('/*', '')
                    if mime.startswith(category):
                        is_allowed = True
                        break
                elif mime == allowed:
                    is_allowed = True
                    break

            if not is_allowed:
                return ProcessResult(
                    success=False,
                    error=f"MIME type '{mime}' not allowed"
                )

        return ProcessResult(success=True, data=self.attachment)

    # ==================== 工具方法 ====================

    def get_hash(self, algorithm: str = 'md5') -> Optional[str]:
        """
        计算附件内容的哈希值

        Args:
            algorithm: 哈希算法 ('md5', 'sha1', 'sha256')

        Returns:
            哈希值（十六进制字符串）
        """
        binary_data = self.get_binary_data()
        if not binary_data:
            return None

        if algorithm == 'md5':
            return hashlib.md5(binary_data).hexdigest()
        elif algorithm == 'sha1':
            return hashlib.sha1(binary_data).hexdigest()
        elif algorithm == 'sha256':
            return hashlib.sha256(binary_data).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.attachment.to_dict()


# ============================================================
# 批量处理函数
# ============================================================

def process_attachments(
    attachments: list,
    save_directory: Optional[str] = None,
    max_size: Optional[int] = None,
    allowed_types: Optional[list] = None
) -> list:
    """
    批量处理附件

    Args:
        attachments: 附件列表（字典列表）
        save_directory: 保存目录（可选）
        max_size: 最大文件大小
        allowed_types: 允许的 MIME 类型

    Returns:
        处理结果列表
    """
    results = []

    for att_data in attachments:
        handler = AttachmentHandler(att_data)

        # 验证
        validation = handler.validate(max_size=max_size, allowed_types=allowed_types)
        if not validation.success:
            results.append({
                'id': handler.id,
                'success': False,
                'error': validation.error
            })
            continue

        result = {
            'id': handler.id,
            'success': True,
            'mime_type': handler.mime_type,
            'size': handler.get_size(),
            'url_type': handler.url_type
        }

        # 保存文件
        if save_directory and handler.is_base64:
            file_path = handler.save_to_file(save_directory)
            if file_path:
                result['file_path'] = file_path
            else:
                result['success'] = False
                result['error'] = 'Failed to save file'

        results.append(result)

    return results


def extract_base64_attachments(attachments: list) -> list:
    """
    从附件列表中提取 Base64 附件的二进制数据

    Args:
        attachments: 附件列表

    Returns:
        包含二进制数据的附件信息列表
    """
    results = []

    for att_data in attachments:
        handler = AttachmentHandler(att_data)

        if handler.is_base64:
            binary_data = handler.get_binary_data()
            if binary_data:
                results.append({
                    'id': handler.id,
                    'name': handler.name,
                    'mime_type': handler.mime_type,
                    'size': len(binary_data),
                    'data': binary_data
                })

    return results


# ============================================================
# UUID 生成
# ============================================================

def generate_uuid() -> str:
    """生成 UUID v4"""
    return str(uuid.uuid4())


def generate_attachment_id() -> str:
    """生成附件 ID"""
    return f"att-{uuid.uuid4()}"


# ============================================================
# 导出
# ============================================================

__all__ = [
    # 类型
    'Attachment',
    'ProcessResult',

    # URL 检测
    'is_base64_url',
    'is_blob_url',
    'is_http_url',
    'get_url_type',

    # Base64 处理
    'parse_data_url',
    'encode_to_data_url',
    'base64_to_bytes',
    'bytes_to_base64',

    # MIME 处理
    'get_extension_from_mime',
    'get_mime_from_extension',

    # 附件处理器
    'AttachmentHandler',

    # 批量处理
    'process_attachments',
    'extract_base64_attachments',

    # 工具
    'generate_uuid',
    'generate_attachment_id',
]
