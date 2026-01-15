"""
Key Service Client - 应用进程通过此客户端从 Key Service 获取密钥

应用进程不存储密钥，每次需要时从 Key Service 获取。
可以缓存密钥以减少 IPC 调用（但缓存时间应较短）。

使用方式：
1. 应用启动时调用 initialize_key_service_client(client_token)
2. 使用 get_encryption_key() 和 get_jwt_secret_key() 获取密钥
"""

import socket
import json
from pathlib import Path
from typing import Optional, Dict, Tuple
import logging
import time
import threading
import platform
import os

logger = logging.getLogger(__name__)

# Key Service Socket 路径
if platform.system() == 'Windows':
    _temp_dir = Path(os.environ.get('TEMP', os.environ.get('TMP', '/tmp')))
    KEY_SERVICE_CLIENT_SOCKET = _temp_dir / "gemini_key_service_client.sock"
    KEY_SERVICE_ADMIN_SOCKET = _temp_dir / "gemini_key_service_admin.sock"
else:
    KEY_SERVICE_CLIENT_SOCKET = Path("/tmp/gemini_key_service_client.sock")
    KEY_SERVICE_ADMIN_SOCKET = Path("/tmp/gemini_key_service_admin.sock")

# 客户端缓存（可选，减少 IPC 调用）
_cache: Dict[str, Tuple[str, float]] = {}  # {key_type: (key_value, expire_time)}
_cache_lock = threading.Lock()
_cache_ttl = 300  # 缓存 5 分钟

class KeyServiceClient:
    """Key Service 客户端"""
    
    def __init__(self, client_token: str):
        """
        初始化客户端
        
        Args:
            client_token: Client 认证令牌（必须与 Key Service 配置一致）
        """
        self.client_token = client_token
        self.socket_path = KEY_SERVICE_CLIENT_SOCKET
    
    def _get_key_from_service(self, key_type: str) -> str:
        """从 Key Service 获取密钥"""
        # Windows 使用 TCP Socket（从端口文件读取）
        if platform.system() == 'Windows':
            port_file = self.socket_path.parent / "gemini_key_service_client.port"
            if not port_file.exists():
                raise RuntimeError(
                    f"Key Service 未运行（端口文件不存在: {port_file}）"
                )
            port = int(port_file.read_text().strip())
            host = '127.0.0.1'
        else:
            # Unix/Linux 使用 Unix Socket
            if not self.socket_path.exists():
                raise RuntimeError(
                    f"Key Service 未运行（Socket 不存在: {self.socket_path}）"
                )
            host = None
            port = None
        
        try:
            if platform.system() == 'Windows':
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((host, port))
            else:
                client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                client_socket.connect(str(self.socket_path))
            
            request = {
                'token': self.client_token,
                'key_type': key_type
            }
            client_socket.send(json.dumps(request).encode())
            
            response_data = client_socket.recv(4096).decode('utf-8')
            response = json.loads(response_data)
            
            if 'error' in response:
                raise RuntimeError(f"Key Service 错误: {response['error']}")
            
            return response['key']
            
        except Exception as e:
            logger.error(f"[KeyServiceClient] 获取密钥失败: {e}")
            raise
        finally:
            if 'client_socket' in locals():
                client_socket.close()
    
    def get_encryption_key(self, use_cache: bool = True) -> str:
        """获取 ENCRYPTION_KEY"""
        cache_key = 'encryption_key'
        
        # 检查缓存
        if use_cache:
            with _cache_lock:
                if cache_key in _cache:
                    key_value, expire_time = _cache[cache_key]
                    if time.time() < expire_time:
                        logger.debug("[KeyServiceClient] 使用缓存的 ENCRYPTION_KEY")
                        return key_value
                    else:
                        # 缓存过期，删除
                        del _cache[cache_key]
        
        # 从 Key Service 获取
        key = self._get_key_from_service('encryption_key')
        
        # 更新缓存
        if use_cache:
            with _cache_lock:
                _cache[cache_key] = (key, time.time() + _cache_ttl)
        
        return key
    
    def get_jwt_secret_key(self, use_cache: bool = True) -> str:
        """获取 JWT_SECRET_KEY"""
        cache_key = 'jwt_secret_key'
        
        # 检查缓存
        if use_cache:
            with _cache_lock:
                if cache_key in _cache:
                    key_value, expire_time = _cache[cache_key]
                    if time.time() < expire_time:
                        logger.debug("[KeyServiceClient] 使用缓存的 JWT_SECRET_KEY")
                        return key_value
                    else:
                        # 缓存过期，删除
                        del _cache[cache_key]
        
        # 从 Key Service 获取
        key = self._get_key_from_service('jwt_secret_key')
        
        # 更新缓存
        if use_cache:
            with _cache_lock:
                _cache[cache_key] = (key, time.time() + _cache_ttl)
        
        return key

# 全局客户端实例（应用进程启动时初始化）
_key_service_client: Optional[KeyServiceClient] = None
_use_key_service = False  # 是否使用 Key Service（默认 False，向后兼容）

def initialize_key_service_client(client_token: str):
    """
    初始化 Key Service 客户端（应用进程启动时调用）
    
    Args:
        client_token: Client 认证令牌（必须与 Key Service 配置一致）
    
    注意：
    - Key Service 是可选的，如果不可用会自动回退到文件存储
    - 警告信息 "Key Service 不可用" 是正常的，不是错误
    """
    global _key_service_client, _use_key_service
    try:
        _key_service_client = KeyServiceClient(client_token)
        # 测试连接
        _key_service_client.get_encryption_key(use_cache=False)
        _use_key_service = True
        logger.info("[KeyServiceClient] ✅ Key Service 客户端已初始化（使用 Key Service）")
    except Exception as e:
        # Key Service 不可用是正常的（向后兼容设计）
        # 系统会自动回退到文件存储，功能完全正常
        logger.info(f"[KeyServiceClient] ℹ️ Key Service 未启动，将使用文件存储（这是正常的）: {e}")
        _use_key_service = False
        _key_service_client = None

def get_encryption_key() -> str:
    """
    获取 ENCRYPTION_KEY（从 Key Service 或文件）
    
    优先级：
    1. Key Service（如果可用）
    2. 文件存储（向后兼容）
    """
    global _use_key_service, _key_service_client
    
    if _use_key_service and _key_service_client:
        try:
            return _key_service_client.get_encryption_key()
        except Exception as e:
            logger.warning(f"[KeyServiceClient] 从 Key Service 获取 ENCRYPTION_KEY 失败，回退到文件存储: {e}")
            _use_key_service = False
    
    # 回退到文件存储
    from .encryption_key_manager import EncryptionKeyManager
    return EncryptionKeyManager.get_or_create_key()

def get_jwt_secret_key() -> str:
    """
    获取 JWT_SECRET_KEY（从 Key Service 或文件）
    
    优先级：
    1. Key Service（如果可用）
    2. 文件存储（向后兼容）
    """
    global _use_key_service, _key_service_client
    
    if _use_key_service and _key_service_client:
        try:
            return _key_service_client.get_jwt_secret_key()
        except Exception as e:
            logger.warning(f"[KeyServiceClient] 从 Key Service 获取 JWT_SECRET_KEY 失败，回退到文件存储: {e}")
            _use_key_service = False
    
    # 回退到文件存储（直接调用 JWTSecretManager，避免循环依赖）
    from .jwt_secret_manager import JWTSecretManager
    # 直接调用 get_or_create_secret，避免调用 get_jwt_secret_key 导致循环
    try:
        secret = JWTSecretManager.get_or_create_secret()
        if secret and secret != "your-super-secret-key-change-in-production":
            return secret
    except Exception as e:
        logger.warning(f"[KeyServiceClient] 从文件获取 JWT_SECRET_KEY 失败: {e}")
    
    # 最后回退：从环境变量读取
    import os
    env_secret = os.getenv("JWT_SECRET_KEY")
    if env_secret and env_secret != "your-super-secret-key-change-in-production":
        return env_secret
    
    # 使用默认值（仅用于开发环境）
    logger.error("[KeyServiceClient] ❌ 无法获取 JWT_SECRET_KEY，使用默认值（不安全）")
    return "your-super-secret-key-change-in-production"

def is_key_service_available() -> bool:
    """检查 Key Service 是否可用"""
    return _use_key_service and _key_service_client is not None
