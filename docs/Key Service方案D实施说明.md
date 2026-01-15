# Key Service 方案 D 实施说明

## 📋 概述

本文档说明如何实施和使用 **方案 D：Client 进程 + Key Service** 架构来管理密钥。

**核心原则**：
- **JWT = Token 处理**（生成、验证、提取信息）
- **JWT Secret Key = 仅用于签名/验证 Token**
- **ENCRYPTION_KEY = 加密敏感数据（主密钥，更重要）**

**方案 D 架构**：
- Key Service 独立进程：管理所有密钥（存储在进程内存中）
- Client 进程（应用进程）：通过 IPC 从 Key Service 获取密钥
- 最佳安全隔离：应用进程不存储密钥

---

## 🏗️ 架构说明

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│  Key Service 进程（独立服务）                            │
│  - 密钥存储在进程内存中                                   │
│  - 监听两个 IPC Socket：                                 │
│    1. Client Socket（应用进程访问）                      │
│    2. Admin Socket（管理员工具访问）                     │
└─────────────────────────────────────────────────────────┘
                          │
                          │ IPC (Unix Socket / TCP)
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
        ▼                                   ▼
┌──────────────────────┐        ┌──────────────────────┐
│  Client 进程 1       │        │  Client 进程 2       │
│  (FastAPI 应用)      │        │  (FastAPI 应用)      │
│                      │        │                      │
│  - 通过 IPC 请求密钥  │        │  - 通过 IPC 请求密钥  │
│  - 密钥不存储在内存中 │        │  - 密钥不存储在内存中 │
│  - 仅临时使用（带缓存）│        │  - 仅临时使用（带缓存）│
└──────────────────────┘        └──────────────────────┘
```

### 关键特性

1. **最佳安全隔离**：密钥与应用进程完全隔离
2. **独立管理**：Key Service 可以独立重启、更新
3. **多进程支持**：多个应用进程可以共享同一个 Key Service
4. **最小权限**：应用进程无法直接访问密钥
5. **集中管理**：所有密钥管理逻辑集中在一个服务中

---

## 🚀 快速开始

### ✅ 默认方式：自动启动 Key Service（推荐）

**应用启动时会自动启动 Key Service 子进程**，无需手动管理。

```bash
# 直接启动应用，Key Service 会自动启动
python -m backend.app.main
```

**启动日志**：
```
[KeyService] ✅ 密钥已初始化（Key Service 进程内存存储）
[KeyService] ✅ Key Service 已启动
  - Client Socket: /tmp/gemini_key_service_client.sock
  - Admin Socket: /tmp/gemini_key_service_admin.sock
[main] ✅ Key Service 已自动启动（进程 ID: 12345）
[KeyServiceClient] ✅ Key Service 客户端已初始化（使用 Key Service）
```

**关闭时**：
```
[main] 正在停止 Key Service（进程 ID: 12345）...
[KeyService] 正在关闭...
[main] ✅ Key Service 已停止
```

### 禁用自动启动（使用文件存储）

如果不想使用 Key Service，可以禁用自动启动：

```bash
# Unix/Linux
export AUTO_START_KEY_SERVICE=false
python -m backend.app.main

# Windows
$env:AUTO_START_KEY_SERVICE="false"
python -m backend.app.main
```

**启动日志**：
```
[KeyServiceClient] ℹ️ Key Service 未启动，将使用文件存储（这是正常的）
[KeyServiceClient] ✅ Key Service Client initialized (方案 D)
```

### 手动启动 Key Service（高级用法）

如果需要手动控制 Key Service 生命周期：

**终端 1 - 启动 Key Service**：
```bash
python -m backend.services.key_service.main
```

**终端 2 - 启动应用进程（禁用自动启动）**：
```bash
export AUTO_START_KEY_SERVICE=false
python -m backend.app.main
```

### 3. 查看密钥（管理员工具）

```bash
python -m backend.scripts.view_keys
```

需要输入管理员密码（环境变量 `ADMIN_VIEW_KEY_PASSWORD`）。

---

## ⚙️ 配置

### 环境变量

**Key Service 配置**：
- `ENCRYPTION_KEY`：主密钥（必须设置）
- `JWT_SECRET_KEY`：JWT 密钥（可选，如果未设置会从文件加载）
- `KEY_SERVICE_CLIENT_TOKEN`：Client 进程认证令牌（默认：`default_token_change_me`）
- `ADMIN_VIEW_KEY_PASSWORD`：管理员密码（默认：`default_password_change_me`）

**应用进程配置**：
- `AUTO_START_KEY_SERVICE`：是否自动启动 Key Service（默认：`true`）
  - `true`：应用启动时自动启动 Key Service（推荐）
  - `false`：不启动 Key Service，使用文件存储
- `KEY_SERVICE_CLIENT_TOKEN`：必须与 Key Service 配置一致（如果使用 Key Service）

### 配置文件优先级

**Key Service 启动时**：
1. 环境变量 `ENCRYPTION_KEY`
2. 文件 `backend/credentials/.encryption_key`（向后兼容）

**应用进程获取密钥时**：
1. Key Service（如果可用）
2. 文件存储（向后兼容）

---

## 📁 文件结构

```
backend/
├── services/
│   └── key_service/
│       ├── __init__.py
│       └── main.py              # Key Service 主进程
├── app/
│   └── core/
│       ├── key_service_client.py # Key Service 客户端
│       ├── encryption_key_manager.py  # 已更新，优先使用 Key Service
│       └── jwt_secret_manager.py      # 已更新，优先使用 Key Service
├── scripts/
│   ├── start_key_service.sh     # Key Service 启动脚本（Unix/Linux）
│   ├── start_key_service.bat    # Key Service 启动脚本（Windows）
│   └── view_keys.py             # 管理员工具（查看密钥）
└── main.py                      # 已更新，启动时初始化 Key Service Client
```

---

## 🔄 工作流程

### 1. Key Service 启动流程

```
1. 读取环境变量或文件，加载密钥到进程内存
2. 启动 Client IPC Server（应用进程访问）
3. 启动 Admin IPC Server（管理员工具访问）
4. 保持运行，等待请求
```

### 2. 应用进程启动流程

**默认方式（自动启动 Key Service）**：
```
1. 检查 AUTO_START_KEY_SERVICE 环境变量（默认：true）
2. 如果为 true，启动 Key Service 子进程
3. 等待 Key Service 就绪（最多 3 秒）
4. 初始化 Key Service Client
5. 连接到 Key Service
6. 如果连接失败，回退到文件存储（向后兼容）
```

**禁用自动启动**：
```
1. AUTO_START_KEY_SERVICE=false
2. 跳过 Key Service 启动
3. 初始化 Key Service Client
4. 尝试连接到 Key Service（如果手动启动）
5. 如果不可用，回退到文件存储（向后兼容）✅ 这是正常的！
```

**⚠️ 重要说明**：
- Key Service **不是必须的**，应用进程可以独立运行
- 如果 Key Service 未启动，应用进程会**自动回退到文件存储**
- 这是**向后兼容设计**，确保系统在任何情况下都能正常工作
- 警告信息 `⚠️ Key Service 不可用，将使用文件存储` 是**正常的**，不是错误

### 3. 获取密钥流程

```
应用进程需要密钥
    ↓
检查 Key Service 是否可用
    ↓
如果可用：
    - 通过 IPC 从 Key Service 获取
    - 缓存 5 分钟（减少 IPC 调用）
如果不可用：
    - 从文件存储获取（向后兼容）
```

---

## 🔐 安全性

### 1. 密钥存储

- **Key Service 进程内存**：密钥仅存储在 Key Service 进程内存中
- **应用进程**：不存储密钥，仅临时使用（带缓存）

### 2. 身份验证

- **Client 进程**：使用 `KEY_SERVICE_CLIENT_TOKEN` 验证
- **管理员工具**：使用 `ADMIN_VIEW_KEY_PASSWORD` 验证

### 3. IPC 通信

- **Unix/Linux**：使用 Unix Socket（文件权限 `0o600`）
- **Windows**：使用 TCP Socket（`127.0.0.1`，仅本地访问）

### 4. 向后兼容

- 如果 Key Service 不可用，自动回退到文件存储
- 不影响现有部署（可以逐步迁移）

---

## 🛠️ 故障排除

### 问题 0：应用启动时显示 "Key Service 不可用" 警告

**这是正常的！** ⚠️

**原因**：
- Key Service 是独立进程，需要单独启动
- 如果未启动 Key Service，应用进程会自动回退到文件存储
- 这是向后兼容设计，确保系统在任何情况下都能正常工作

**解决方案**：
- **选项 1（推荐）**：不启动 Key Service，使用文件存储（当前方式）
  - 系统完全正常工作
  - 密钥存储在 `backend/credentials/.jwt_secret.enc`
- **选项 2**：启动 Key Service（生产环境推荐）
  - 先启动 Key Service：`python -m backend.services.key_service.main`
  - 再启动应用进程：`python -m backend.app.main`
  - 应用进程会自动连接到 Key Service

### 问题 1：Key Service 无法启动

**可能原因**：
- `ENCRYPTION_KEY` 未设置
- 端口/Socket 文件被占用

**解决方案**：
1. 检查环境变量 `ENCRYPTION_KEY` 是否设置
2. 检查端口/Socket 文件是否被占用
3. 查看 Key Service 日志

### 问题 2：应用进程无法连接到 Key Service

**可能原因**：
- Key Service 未运行
- `KEY_SERVICE_CLIENT_TOKEN` 不匹配
- Socket 文件不存在（Unix/Linux）

**解决方案**：
1. 确保 Key Service 正在运行
2. 检查 `KEY_SERVICE_CLIENT_TOKEN` 是否匹配
3. 检查 Socket 文件权限（Unix/Linux）

### 问题 3：管理员工具无法查看密钥

**可能原因**：
- Key Service 未运行
- 管理员密码错误
- Socket 文件不存在（Unix/Linux）

**解决方案**：
1. 确保 Key Service 正在运行
2. 检查 `ADMIN_VIEW_KEY_PASSWORD` 是否正确
3. 检查 Socket 文件权限（Unix/Linux）

---

## 📝 迁移指南

### 从文件存储迁移到 Key Service

1. **生成密钥**（如果还没有）：
   ```bash
   python -m backend.scripts.manage_encryption_key generate
   python -m backend.scripts.manage_jwt_secret generate
   ```

2. **设置环境变量**：
   ```bash
   export ENCRYPTION_KEY="your-encryption-key"
   export JWT_SECRET_KEY="your-jwt-secret-key"  # 可选
   export KEY_SERVICE_CLIENT_TOKEN="your-client-token"
   export ADMIN_VIEW_KEY_PASSWORD="your-admin-password"
   ```

3. **启动 Key Service**：
   ```bash
   python -m backend.services.key_service.main
   ```

4. **启动应用进程**：
   ```bash
   python -m backend.app.main
   ```

5. **验证**：
   - 应用进程应该能够正常启动
   - 使用 `view_keys.py` 查看密钥

---

## 📚 相关文档

- [基于内存的密钥管理方案分析](./基于内存的密钥管理方案分析.md) - 完整方案分析
- [JWT实际作用与密钥管理分析](./JWT实际作用与密钥管理分析.md) - JWT 作用说明
- [JWT使用说明](../backend/app/core/JWT使用说明.md) - JWT 完整使用说明

---

## 📝 更新日志

### 2026-01-15
- ✅ 实施方案 D：Client 进程 + Key Service
- ✅ 创建 Key Service 独立进程
- ✅ 创建 Key Service Client
- ✅ 更新 encryption_key_manager.py 和 jwt_secret_manager.py
- ✅ 更新应用启动逻辑
- ✅ 创建启动脚本和管理员工具
- ✅ 支持 Windows 和 Unix/Linux
