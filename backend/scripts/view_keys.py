#!/usr/bin/env python3
"""
密钥查看工具（管理员专用）

通过 IPC 连接到 Key Service，安全地查看密钥。

使用方式：
    python -m backend.scripts.view_keys
"""

import sys
import socket
import json
import getpass
import hashlib
import platform
from pathlib import Path
import os

# Key Service Admin Socket 路径
if platform.system() == 'Windows':
    _temp_dir = Path(os.environ.get('TEMP', os.environ.get('TMP', '/tmp')))
    ADMIN_SOCKET_PATH = _temp_dir / "gemini_key_service_admin.sock"
    ADMIN_PORT_FILE = _temp_dir / "gemini_key_service_admin.port"
else:
    ADMIN_SOCKET_PATH = Path("/tmp/gemini_key_service_admin.sock")
    ADMIN_PORT_FILE = None

def view_keys():
    """查看密钥（从 Key Service）"""
    # 1. 获取管理员密码
    password = getpass.getpass("请输入管理员密码: ")
    
    # 2. 检查 Key Service 是否运行
    if platform.system() == 'Windows':
        if not ADMIN_PORT_FILE.exists():
            print("❌ 错误: Key Service 未运行")
            print("   请先启动 Key Service: python -m backend.services.key_service.main")
            return
        port = int(ADMIN_PORT_FILE.read_text().strip())
        host = '127.0.0.1'
    else:
        if not ADMIN_SOCKET_PATH.exists():
            print("❌ 错误: Key Service 未运行")
            print("   请先启动 Key Service: python -m backend.services.key_service.main")
            return
        host = None
        port = None
    
    try:
        # 3. 连接到 Key Service
        if platform.system() == 'Windows':
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((host, port))
        else:
            client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_socket.connect(str(ADMIN_SOCKET_PATH))
        
        # 4. 发送身份验证请求
        request = {
            'action': 'authenticate',
            'password': password
        }
        client_socket.send(json.dumps(request).encode())
        
        # 5. 接收响应
        response_data = client_socket.recv(4096).decode('utf-8')
        response = json.loads(response_data)
        
        if 'error' in response:
            print(f"❌ 错误: {response['error']}")
            return
        
        # 6. 显示密钥
        print("\n✅ 身份验证成功\n")
        print("=" * 60)
        print("ENCRYPTION_KEY:")
        print(f"  {response['encryption_key']}")
        print("\nJWT_SECRET_KEY:")
        print(f"  {response['jwt_secret_key']}")
        print("=" * 60)
        print("\n⚠️  警告: 请妥善保管这些密钥，不要泄露！")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
    finally:
        if 'client_socket' in locals():
            client_socket.close()

if __name__ == '__main__':
    view_keys()
