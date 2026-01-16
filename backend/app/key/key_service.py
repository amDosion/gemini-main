"""
Key Service - 独立的密钥管理服务进程

职责：
1. 管理所有密钥（ENCRYPTION_KEY, JWT_SECRET_KEY）
2. 密钥仅存储在 Key Service 进程内存中
3. 通过 IPC 向 Client 进程提供密钥
4. 提供管理员工具访问接口

使用方式：
    python -m backend.app.key.key_service
"""

import socket
import json
import hashlib
import hmac
import threading
from pathlib import Path
from typing import Optional
import logging
import os
import sys
import time
import platform

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Unix Socket 路径（Windows 使用命名管道路径）
if platform.system() == 'Windows':
    # Windows 使用临时目录
    _temp_dir = Path(os.environ.get('TEMP', os.environ.get('TMP', '/tmp')))
    CLIENT_SOCKET_PATH = _temp_dir / "gemini_key_service_client.sock"
    ADMIN_SOCKET_PATH = _temp_dir / "gemini_key_service_admin.sock"
else:
    # Unix/Linux 使用 /tmp
    CLIENT_SOCKET_PATH = Path("/tmp/gemini_key_service_client.sock")
    ADMIN_SOCKET_PATH = Path("/tmp/gemini_key_service_admin.sock")

# Key Service 进程内存存储（模块级变量）
_encryption_key: Optional[str] = None
_jwt_secret_key: Optional[str] = None
_keys_initialized = False
_keys_lock = threading.Lock()

def initialize_keys(
    encryption_key: Optional[str] = None,
    jwt_secret_key: Optional[str] = None
) -> None:
    """
    初始化密钥（Key Service 启动时调用）
    
    Args:
        encryption_key: ENCRYPTION_KEY（如果提供，优先使用）
        jwt_secret_key: JWT_SECRET_KEY（如果提供，优先使用）
    """
    global _encryption_key, _jwt_secret_key, _keys_initialized
    
    with _keys_lock:
        if _keys_initialized:
            logger.warning("[KeyService] 密钥已初始化，跳过重复初始化")
            return
        
        # 从环境变量或启动参数加载（从 .env 文件）
        _encryption_key = encryption_key or os.getenv('ENCRYPTION_KEY')
        _jwt_secret_key = jwt_secret_key or os.getenv('JWT_SECRET_KEY')
        
        # 如果 ENCRYPTION_KEY 未设置，自动生成
        if not _encryption_key:
            try:
                from ..core.encryption import EncryptionKeyManager
                _encryption_key = EncryptionKeyManager.get_or_create_key()
                logger.info("[KeyService] 自动生成 ENCRYPTION_KEY")
            except Exception as e:
                logger.error(f"[KeyService] 自动生成 ENCRYPTION_KEY 失败: {e}")
                raise RuntimeError("ENCRYPTION_KEY 无法生成，无法启动 Key Service")
        
        # 如果 JWT_SECRET_KEY 未设置，自动生成
        if not _jwt_secret_key:
            try:
                from ..core.jwt_utils import JWTSecretManager
                _jwt_secret_key = JWTSecretManager.get_or_create_secret()
                logger.info("[KeyService] 自动生成 JWT_SECRET_KEY")
            except Exception as e:
                logger.error(f"[KeyService] 自动生成 JWT_SECRET_KEY 失败: {e}")
                raise RuntimeError("JWT_SECRET_KEY 无法生成，无法启动 Key Service")
        
        if not _encryption_key:
            raise RuntimeError("ENCRYPTION_KEY 未设置，无法启动 Key Service")
        
        if not _jwt_secret_key:
            logger.warning("[KeyService] JWT_SECRET_KEY 未设置，将使用默认值（不安全）")
            _jwt_secret_key = "your-super-secret-key-change-in-production"
        
        _keys_initialized = True
        logger.info("[KeyService] ✅ 密钥已初始化（Key Service 进程内存存储）")

def get_encryption_key() -> str:
    """获取 ENCRYPTION_KEY（从 Key Service 进程内存）"""
    if not _keys_initialized or _encryption_key is None:
        raise RuntimeError("ENCRYPTION_KEY 未初始化")
    return _encryption_key

def get_jwt_secret_key() -> str:
    """获取 JWT_SECRET_KEY（从 Key Service 进程内存）"""
    if not _keys_initialized or _jwt_secret_key is None:
        raise RuntimeError("JWT_SECRET_KEY 未初始化")
    return _jwt_secret_key

class KeyServiceServer:
    """Key Service IPC Server"""
    
    def __init__(self, client_token: str, admin_password_hash: str):
        """
        初始化 Key Service
        
        Args:
            client_token: Client 进程认证令牌（用于验证应用进程身份）
            admin_password_hash: 管理员密码哈希
        """
        self.client_token = client_token
        self.admin_password_hash = admin_password_hash
        self.client_socket_path = CLIENT_SOCKET_PATH
        self.admin_socket_path = ADMIN_SOCKET_PATH
        self.running = False
        self.client_server_socket: Optional[socket.socket] = None
        self.admin_server_socket: Optional[socket.socket] = None
    
    def start(self):
        """启动 Key Service"""
        if self.running:
            return
        
        # 启动 Client IPC Server（应用进程访问）
        client_thread = threading.Thread(
            target=self._run_client_server,
            daemon=True
        )
        client_thread.start()
        
        # 启动 Admin IPC Server（管理员工具访问）
        admin_thread = threading.Thread(
            target=self._run_admin_server,
            daemon=True
        )
        admin_thread.start()
        
        self.running = True
        logger.info("[KeyService] ✅ Key Service 已启动")
        logger.info(f"  - Client Socket: {self.client_socket_path}")
        logger.info(f"  - Admin Socket: {self.admin_socket_path}")
    
    def stop(self):
        """停止 Key Service"""
        self.running = False
        if self.client_server_socket:
            self.client_server_socket.close()
        if self.admin_server_socket:
            self.admin_server_socket.close()
        if self.client_socket_path.exists():
            self.client_socket_path.unlink()
        if self.admin_socket_path.exists():
            self.admin_socket_path.unlink()
        logger.info("[KeyService] Key Service 已停止")
    
    def _run_client_server(self):
        """运行 Client IPC Server（应用进程访问）"""
        # 删除旧的 socket 文件
        if self.client_socket_path.exists():
            self.client_socket_path.unlink()
        
        try:
            if platform.system() == 'Windows':
                # Windows 使用 TCP Socket（命名管道在 Python 中较复杂）
                self.client_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_server_socket.bind(('127.0.0.1', 0))
                port = self.client_server_socket.getsockname()[1]
                # 将端口写入文件，供客户端读取
                port_file = self.client_socket_path.parent / "gemini_key_service_client.port"
                port_file.write_text(str(port))
                logger.info(f"[KeyService] Client IPC Server 使用 TCP: 127.0.0.1:{port}")
            else:
                # Unix/Linux 使用 Unix Socket
                self.client_server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.client_server_socket.bind(str(self.client_socket_path))
                self.client_socket_path.chmod(0o600)
            
            self.client_server_socket.listen(5)
            logger.info(f"[KeyService] Client IPC Server 已启动: {self.client_socket_path}")
            
            while self.running:
                try:
                    conn, _ = self.client_server_socket.accept()
                    threading.Thread(
                        target=self._handle_client_request,
                        args=(conn,),
                        daemon=True
                    ).start()
                except Exception as e:
                    if self.running:
                        logger.error(f"[KeyService] Client 连接失败: {e}")
        except Exception as e:
            logger.error(f"[KeyService] Client IPC Server 启动失败: {e}")
    
    def _run_admin_server(self):
        """运行 Admin IPC Server（管理员工具访问）"""
        # 删除旧的 socket 文件
        if self.admin_socket_path.exists():
            self.admin_socket_path.unlink()
        
        try:
            if platform.system() == 'Windows':
                # Windows 使用 TCP Socket
                self.admin_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.admin_server_socket.bind(('127.0.0.1', 0))
                port = self.admin_server_socket.getsockname()[1]
                # 将端口写入文件，供客户端读取
                port_file = self.admin_socket_path.parent / "gemini_key_service_admin.port"
                port_file.write_text(str(port))
                logger.info(f"[KeyService] Admin IPC Server 使用 TCP: 127.0.0.1:{port}")
            else:
                # Unix/Linux 使用 Unix Socket
                self.admin_server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.admin_server_socket.bind(str(self.admin_socket_path))
                self.admin_socket_path.chmod(0o600)
            
            self.admin_server_socket.listen(1)
            logger.info(f"[KeyService] Admin IPC Server 已启动: {self.admin_socket_path}")
            
            while self.running:
                try:
                    conn, _ = self.admin_server_socket.accept()
                    self._handle_admin_request(conn)
                except Exception as e:
                    if self.running:
                        logger.error(f"[KeyService] Admin 连接失败: {e}")
        except Exception as e:
            logger.error(f"[KeyService] Admin IPC Server 启动失败: {e}")
    
    def _handle_client_request(self, conn: socket.socket):
        """处理 Client 进程请求"""
        try:
            data = conn.recv(4096).decode('utf-8')
            request = json.loads(data)
            
            # 验证 Client 令牌
            if request.get('token') != self.client_token:
                conn.send(json.dumps({'error': '身份验证失败'}).encode())
                return
            
            # 返回请求的密钥
            key_type = request.get('key_type')
            if key_type == 'encryption_key':
                key = get_encryption_key()
            elif key_type == 'jwt_secret_key':
                key = get_jwt_secret_key()
            else:
                conn.send(json.dumps({'error': '无效的密钥类型'}).encode())
                return
            
            response = {'success': True, 'key': key}
            conn.send(json.dumps(response).encode())
            
        except Exception as e:
            logger.error(f"[KeyService] 处理 Client 请求失败: {e}")
            conn.send(json.dumps({'error': str(e)}).encode())
        finally:
            conn.close()
    
    def _handle_admin_request(self, conn: socket.socket):
        """处理管理员工具请求"""
        try:
            data = conn.recv(4096).decode('utf-8')
            request = json.loads(data)
            
            if request.get('action') != 'authenticate':
                conn.send(json.dumps({'error': '需要先进行身份验证'}).encode())
                return
            
            # 验证管理员密码
            password = request.get('password', '')
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            if not hmac.compare_digest(password_hash, self.admin_password_hash):
                conn.send(json.dumps({'error': '身份验证失败'}).encode())
                return
            
            # 返回所有密钥
            response = {
                'success': True,
                'encryption_key': get_encryption_key(),
                'jwt_secret_key': get_jwt_secret_key()
            }
            conn.send(json.dumps(response).encode())
            
        except Exception as e:
            logger.error(f"[KeyService] 处理 Admin 请求失败: {e}")
            conn.send(json.dumps({'error': str(e)}).encode())
        finally:
            conn.close()

def main():
    """Key Service 主函数"""
    try:
        # 初始化密钥
        initialize_keys()
        
        # 启动 Key Service
        client_token = os.getenv('KEY_SERVICE_CLIENT_TOKEN', 'default_token_change_me')
        admin_password = os.getenv('ADMIN_VIEW_KEY_PASSWORD', 'default_password_change_me')
        admin_password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
        
        server = KeyServiceServer(client_token, admin_password_hash)
        server.start()
        
        # 保持运行
        logger.info("[KeyService] Key Service 正在运行，按 Ctrl+C 停止...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("[KeyService] 正在关闭...")
        if 'server' in locals():
            server.stop()
    except Exception as e:
        logger.error(f"[KeyService] 启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
