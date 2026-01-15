# Key Service 使用说明

## 📋 概述

Key Service 是**可选的**独立进程，用于管理密钥（方案 D：Client 进程 + Key Service）。

**重要**：
- ✅ Key Service **不是必须的**，应用进程可以独立运行
- ✅ 如果 Key Service 未启动，应用进程会**自动回退到文件存储**
- ✅ 警告信息 `⚠️ Key Service 不可用，将使用文件存储` 是**正常的**，不是错误

---

## 🎯 使用方式

### 自动启动 Key Service（默认方式，推荐）

**特点**：
- ✅ **应用启动时自动启动 Key Service**（子进程）
- ✅ 密钥存储在 Key Service 进程内存中
- ✅ 应用进程通过 IPC 获取密钥
- ✅ 应用关闭时自动停止 Key Service
- ✅ 最佳安全隔离
- ✅ 适合开发和生产环境

**启动方式**：
```bash
# 直接启动应用进程，Key Service 会自动启动
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

**特点**：
- 不启动 Key Service
- 密钥存储在文件：`backend/credentials/.jwt_secret.enc`
- 应用进程直接读取文件
- 简单，适合特殊场景

**启动方式**：
```bash
# 设置环境变量禁用自动启动
export AUTO_START_KEY_SERVICE=false
python -m backend.app.main
```

**Windows**：
```powershell
$env:AUTO_START_KEY_SERVICE="false"
python -m backend.app.main
```

**启动日志**：
```
[KeyServiceClient] ℹ️ Key Service 未启动，将使用文件存储（这是正常的）
[KeyServiceClient] ✅ Key Service Client initialized (方案 D)
```

### 手动启动 Key Service（高级用法）

**特点**：
- 手动控制 Key Service 生命周期
- 适合需要独立管理 Key Service 的场景

**启动方式**：
```bash
# 1. 先启动 Key Service（独立终端）
python -m backend.services.key_service.main

# 2. 再启动应用进程（另一个终端，禁用自动启动）
export AUTO_START_KEY_SERVICE=false
python -m backend.app.main
```

---

## ⚙️ 配置

### 环境变量

**应用进程配置**（控制 Key Service 自动启动）：
- `AUTO_START_KEY_SERVICE`：是否自动启动 Key Service（默认：`true`）
  - `true`：应用启动时自动启动 Key Service（推荐）
  - `false`：不启动 Key Service，使用文件存储

**Key Service 配置**（Key Service 进程使用）：
- `ENCRYPTION_KEY`：主密钥（必须设置）
- `JWT_SECRET_KEY`：JWT 密钥（可选，如果未设置会从文件加载）
- `KEY_SERVICE_CLIENT_TOKEN`：Client 进程认证令牌（默认：`default_token_change_me`）
- `ADMIN_VIEW_KEY_PASSWORD`：管理员密码（默认：`default_password_change_me`）

**注意**：应用进程和 Key Service 进程共享相同的环境变量配置。

---

## 🔄 密钥获取优先级

### 应用进程获取密钥时的优先级

**如果使用 Key Service（方式 2）**：
```
1. Key Service（通过 IPC）
   ↓ 不可用
2. 文件存储（向后兼容）
```

**如果不使用 Key Service（方式 1）**：
```
1. 文件存储（backend/credentials/.jwt_secret.enc）
   ↓ 不存在
2. 环境变量（向后兼容，不推荐）
   ↓ 不存在
3. 自动生成（首次运行）
```

---

## 📊 对比

| 特性 | 自动启动 Key Service（默认） | 禁用自动启动（文件存储） |
|------|---------------------------|-------------------------|
| **启动复杂度** | ⭐⭐ 简单（只需启动应用） | ⭐⭐ 简单（只需启动应用） |
| **安全性** | ⭐⭐⭐⭐⭐ 进程内存存储 | ⭐⭐⭐ 文件存储（加密） |
| **适用场景** | 开发和生产环境（推荐） | 特殊场景、测试环境 |
| **密钥隔离** | ✅ 完全隔离（IPC） | ⚠️ 应用进程直接访问文件 |
| **进程管理** | ✅ 自动管理（子进程） | ✅ 无需管理 |
| **向后兼容** | ✅ 完全兼容 | ✅ 完全兼容 |

---

## 🚀 快速开始

### 默认方式（推荐：自动启动 Key Service）

```bash
# 直接启动应用，Key Service 会自动启动
python -m backend.app.main
```

**特点**：
- ✅ Key Service 自动启动（子进程）
- ✅ 应用关闭时自动停止 Key Service
- ✅ 无需手动管理
- ✅ 最佳安全隔离

### 禁用自动启动（使用文件存储）

```bash
# 设置环境变量禁用自动启动
export AUTO_START_KEY_SERVICE=false
python -m backend.app.main
```

**Windows**：
```powershell
$env:AUTO_START_KEY_SERVICE="false"
python -m backend.app.main
```

**特点**：
- ✅ 简单，不需要 Key Service
- ✅ 密钥存储在文件
- ⚠️ 安全性较低（文件存储）

---

## 🛠️ 故障排除

### 问题：应用启动时显示 "Key Service 不可用" 警告

**可能原因**：
1. `AUTO_START_KEY_SERVICE=false` 已设置（禁用了自动启动）
2. Key Service 自动启动失败（进程启动失败）

**解决方案**：
- **如果禁用了自动启动**：这是正常的，系统会自动使用文件存储
- **如果自动启动失败**：检查日志，系统会自动回退到文件存储，功能正常
- **如果想使用 Key Service**：确保 `AUTO_START_KEY_SERVICE=true`（默认值）

### 问题：Key Service 启动失败

**可能原因**：
- `ENCRYPTION_KEY` 未设置
- 端口/Socket 文件被占用

**解决方案**：
1. 检查环境变量 `ENCRYPTION_KEY` 是否设置
2. 检查端口/Socket 文件是否被占用
3. 查看 Key Service 日志

---

## 📝 总结

1. **Key Service 默认自动启动**（推荐）
   - 应用启动时自动启动 Key Service 子进程
   - 应用关闭时自动停止 Key Service
   - 无需手动管理

2. **可以禁用自动启动**（使用文件存储）
   - 设置 `AUTO_START_KEY_SERVICE=false`
   - 系统会自动回退到文件存储
   - 功能完全正常

3. **最佳实践**：
   - **开发和生产环境**：使用默认方式（自动启动 Key Service）
   - **特殊场景**：可以禁用自动启动，使用文件存储

---

## 🔗 相关文档

- [Key Service方案D实施说明](./Key Service方案D实施说明.md) - 完整实施说明
- [基于内存的密钥管理方案分析](./基于内存的密钥管理方案分析.md) - 方案分析
- [JWT实际作用与密钥管理分析](./JWT实际作用与密钥管理分析.md) - JWT 作用说明
