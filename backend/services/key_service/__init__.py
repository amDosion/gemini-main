"""
Key Service - 独立的密钥管理服务进程

职责：
1. 管理所有密钥（ENCRYPTION_KEY, JWT_SECRET_KEY）
2. 密钥仅存储在 Key Service 进程内存中
3. 通过 IPC 向 Client 进程提供密钥
4. 提供管理员工具访问接口
"""
