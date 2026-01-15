# JWT 和加密密钥管理修复说明

## 📋 修复概述

本次修复解决了两个重要的安全问题：

1. **JWT 密钥轮换时清理 Refresh Token 的问题**
2. **ENCRYPTION_KEY 的安全管理问题**

---

## 🔧 修复 1: JWT 密钥轮换时清理 Refresh Token

### 问题描述

**之前的实现**：
- 轮换 JWT 密钥时，会撤销数据库中的所有 refresh tokens
- 导致所有用户立即被强制退出登录
- 用户体验很差

**问题分析**：
- JWT Token 的签名依赖于 JWT Secret Key
- 当 JWT Secret Key 轮换后，所有用旧密钥签名的 Token 都无法验证（签名验证会失败）
- 所以即使不清理数据库中的 Refresh Token 记录，旧的 Refresh Token 也无法使用
- 清理数据库记录只是"标记为已撤销"，但实际上这些 Token 已经因为签名验证失败而无法使用了

### 修复方案

**新的实现**：
- 默认不清理数据库中的 Refresh Token（`revoke_tokens=False`）
- 旧的 Refresh Token 会因为签名验证失败而自然失效
- 用户下次尝试刷新 token 时会失败，然后需要重新登录
- 这样用户体验更好，不会立即被强制退出

**CLI 工具更新**：
- `rotate`：正常轮换（不清理 Refresh Token，推荐）
- `rotate --force`：强制轮换（清理 Refresh Token，仅在安全事件时使用）

### 使用示例

```bash
# 正常轮换（不立即强制用户退出）
python -m backend.scripts.manage_jwt_secret rotate

# 强制轮换（立即强制所有用户退出，仅在安全事件时使用）
python -m backend.scripts.manage_jwt_secret rotate --force
```

---

## 🔐 修复 2: ENCRYPTION_KEY 的安全管理

### 问题描述

**之前的实现**：
- `ENCRYPTION_KEY` 从环境变量读取，需要在 `.env` 文件中硬编码
- 没有自动生成和管理机制
- 作为"主密钥"，比 JWT Secret Key 更重要，但管理方式不够安全

**问题分析**：
- `ENCRYPTION_KEY` 用于加密 JWT Secret Key 和其他敏感数据（API keys）
- 如果 `ENCRYPTION_KEY` 泄露，攻击者可以解密所有加密数据
- 应该像 JWT Secret Key 一样，使用工具自动生成和管理

### 修复方案

**新的实现**：
- 创建 `EncryptionKeyManager` 类，类似于 `JWTSecretManager`
- 实现混合方案：
  1. 优先从环境变量读取（生产环境推荐）
  2. 如果环境变量不存在，从文件读取（开发环境）
  3. 如果文件不存在，自动生成新密钥（首次运行）
- 文件存储到 `backend/credentials/.encryption_key`（不加密，但用文件权限保护 `0o600`）
- 提供 CLI 工具 `manage_encryption_key.py` 生成和管理

**注意**：
- `ENCRYPTION_KEY` 是"主密钥"，不能再用另一个密钥加密（否则会有无限递归）
- 所以文件存储时不加密，但使用文件权限保护

### 使用示例

```bash
# 查看密钥状态
python -m backend.scripts.manage_encryption_key status

# 生成新密钥
python -m backend.scripts.manage_encryption_key generate

# 查看密钥（部分）
python -m backend.scripts.manage_encryption_key show

# 查看完整密钥（需要确认）
python -m backend.scripts.manage_encryption_key show --full
```

---

## 📁 文件变更

### 新增文件

1. `backend/app/core/encryption_key_manager.py`
   - `EncryptionKeyManager` 类
   - `get_encryption_key()` 全局函数

2. `backend/scripts/manage_encryption_key.py`
   - CLI 工具，用于管理 `ENCRYPTION_KEY`

3. `backend/scripts/README_ENCRYPTION_KEY管理工具.md`
   - 使用说明文档

### 修改文件

1. `backend/app/core/jwt_secret_manager.py`
   - 修改 `rotate_secret()` 方法，默认 `revoke_tokens=False`
   - 更新 `_get_encryption_key_for_jwt()` 使用 `EncryptionKeyManager`

2. `backend/app/core/encryption.py`
   - 更新 `_get_encryption_key()` 使用 `EncryptionKeyManager`

3. `backend/scripts/manage_jwt_secret.py`
   - 更新 `generate_secret()` 和 `rotate_secret()` 函数
   - 添加 `rotate_secret_force()` 函数（强制轮换）
   - 添加 `--force` 参数支持

4. `.gitignore`
   - 添加 `backend/credentials/.encryption_key` 到忽略列表

---

## 🔄 迁移指南

### 对于现有项目

#### 1. JWT 密钥轮换行为变更

**影响**：
- 之前的 `rotate` 命令会清理所有 refresh tokens
- 现在的 `rotate` 命令不会清理 refresh tokens（默认行为）

**如果需要立即强制用户退出**：
- 使用 `rotate --force` 命令

#### 2. ENCRYPTION_KEY 管理

**如果之前使用环境变量**：
- 继续使用环境变量（推荐用于生产环境）
- 系统会自动从环境变量读取

**如果之前没有设置**：
- 运行 `python -m backend.scripts.manage_encryption_key generate` 生成密钥
- 系统会自动保存到文件（开发环境）或提示设置环境变量（生产环境）

---

## ⚠️ 重要提醒

### 1. JWT 密钥轮换

- **正常轮换**（`rotate`）：不会立即强制用户退出，旧的 Token 会自然失效
- **强制轮换**（`rotate --force`）：立即强制所有用户退出，仅在安全事件时使用

### 2. ENCRYPTION_KEY 安全

- **生产环境**：建议使用环境变量或密钥管理服务
- **开发环境**：可以使用文件存储（已添加到 `.gitignore`）
- **密钥泄露**：如果 `ENCRYPTION_KEY` 泄露，必须立即轮换所有密钥

### 3. 密钥轮换影响

- 生成新的 `ENCRYPTION_KEY` 后，所有用旧密钥加密的数据将无法解密
- 包括 JWT Secret Key、API keys 等
- 在轮换前，需要解密所有数据并重新加密（或接受数据丢失，仅适用于开发环境）

---

## 📚 相关文档

- [JWT密钥安全管理方案](./JWT密钥安全管理方案.md)
- [JWT密钥管理工具使用说明](../backend/scripts/README_JWT密钥管理工具.md)
- [ENCRYPTION_KEY管理工具使用说明](../backend/scripts/README_ENCRYPTION_KEY管理工具.md)
- [JWT使用说明](../backend/app/core/JWT使用说明.md)
- [Core 模块文档](../backend/app/core/README.md)

---

## 🔄 更新日志

### 2026-01-15

**修复 1: JWT 密钥轮换时清理 Refresh Token**
- ✅ 修改 `rotate_secret()` 方法，默认 `revoke_tokens=False`
- ✅ 更新 CLI 工具，提供 `rotate` 和 `rotate --force` 两个选项
- ✅ 更新文档，说明密钥轮换的行为

**修复 2: ENCRYPTION_KEY 的安全管理**
- ✅ 创建 `EncryptionKeyManager` 类
- ✅ 实现混合方案（环境变量 + 文件存储）
- ✅ 创建 CLI 工具 `manage_encryption_key.py`
- ✅ 更新 `encryption.py` 和 `jwt_secret_manager.py` 使用新的管理器
- ✅ 更新 `.gitignore` 忽略密钥文件
