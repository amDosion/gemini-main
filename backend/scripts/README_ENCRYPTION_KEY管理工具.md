# ENCRYPTION_KEY 管理工具使用说明

## 📋 概述

`ENCRYPTION_KEY` 是应用程序的**主密钥**，用于加密：
- JWT Secret Key
- API keys（用户配置的 Provider API keys）
- 其他敏感数据

**重要性**：`ENCRYPTION_KEY` 比 JWT Secret Key 更重要，因为如果它泄露，攻击者可以解密所有加密数据。

---

## 🔐 密钥管理策略

### 混合方案（推荐）

**优先级**：
1. **环境变量** `ENCRYPTION_KEY`（生产环境推荐）
2. **文件** `backend/credentials/.encryption_key`（开发环境）
3. **自动生成**（首次运行）

### 为什么文件不加密？

`ENCRYPTION_KEY` 是"主密钥"，不能再用另一个密钥加密（否则会有无限递归）。所以：
- 文件存储时不加密
- 使用文件权限保护（`0o600`，仅所有者可读）
- 文件已添加到 `.gitignore`，不会提交到版本控制

---

## 🚀 快速开始

### 1. 查看密钥状态

```bash
python -m backend.scripts.manage_encryption_key status
```

输出示例：
```
📊 ENCRYPTION_KEY 状态:

❌ 环境变量 ENCRYPTION_KEY 未设置

❌ 密钥文件不存在: D:\gemini-main\gemini-main\backend\credentials\.encryption_key

📝 密钥获取优先级：
  1. 环境变量 ENCRYPTION_KEY（生产环境推荐）
  2. 文件 backend/credentials/.encryption_key（开发环境）
  3. 自动生成（首次运行）
```

### 2. 生成新密钥

```bash
python -m backend.scripts.manage_encryption_key generate
```

**行为说明**：
- **首次生成**（密钥不存在）：生成新密钥并保存到文件
- **覆盖生成**（密钥已存在）：提示确认，生成新密钥（会覆盖旧密钥）

⚠️ **警告**：生成新密钥后，所有用旧密钥加密的数据将无法解密！

### 3. 查看密钥

```bash
# 显示部分密钥（前8字符）
python -m backend.scripts.manage_encryption_key show

# 显示完整密钥（需要确认）
python -m backend.scripts.manage_encryption_key show --full
```

---

## 🔧 使用场景

### 场景 1：开发环境（使用文件存储）

```bash
# 1. 生成密钥（自动保存到文件）
python -m backend.scripts.manage_encryption_key generate

# 2. 验证密钥已保存
python -m backend.scripts.manage_encryption_key status
```

**优点**：
- 简单，不需要手动设置环境变量
- 适合开发环境

**缺点**：
- 文件可能被误删或误提交（虽然已添加到 `.gitignore`）
- 不适合生产环境

### 场景 2：生产环境（使用环境变量）

```bash
# 1. 生成密钥（仅显示，不保存）
python -m backend.scripts.manage_encryption_key generate

# 2. 复制生成的密钥，设置环境变量
export ENCRYPTION_KEY=<生成的密钥>

# 3. 或添加到 .env 文件（如果使用 .env）
echo "ENCRYPTION_KEY=<生成的密钥>" >> .env

# 4. 删除文件（如果存在）
rm backend/credentials/.encryption_key
```

**优点**：
- 更安全，密钥不在文件中
- 适合生产环境（使用密钥管理服务）

**缺点**：
- 需要手动管理环境变量

---

## ⚠️ 重要警告

### 1. 密钥泄露风险

如果 `ENCRYPTION_KEY` 泄露：
- 攻击者可以解密所有加密数据
- 包括 JWT Secret Key、API keys 等
- **必须立即轮换所有密钥**

### 2. 密钥轮换影响

生成新的 `ENCRYPTION_KEY` 后：
- 所有用旧密钥加密的数据将无法解密
- 包括：
  - JWT Secret Key（如果已加密）
  - 所有 API keys（如果已加密）
  - 其他敏感数据（如果已加密）

**解决方案**：
1. 在轮换前，解密所有数据并重新加密
2. 或接受数据丢失（仅适用于开发环境）

### 3. 文件安全

- 确保 `backend/credentials/.encryption_key` 文件权限为 `0o600`（仅所有者可读）
- 确保文件已添加到 `.gitignore`
- 不要将密钥提交到版本控制

---

## 🐛 故障排除

### 问题 1: "ENCRYPTION_KEY 未设置"

**症状**：
```
[EncryptionKeyManager] ⚠️ ENCRYPTION_KEY 未设置，自动生成新密钥（首次运行）
```

**解决方案**：
1. 运行 `python -m backend.scripts.manage_encryption_key generate` 生成密钥
2. 或设置环境变量 `ENCRYPTION_KEY`

### 问题 2: "无法解密数据"

**可能原因**：
- `ENCRYPTION_KEY` 被更改
- 数据是用旧密钥加密的

**解决方案**：
1. 检查 `ENCRYPTION_KEY` 是否正确
2. 如果密钥被更改，需要重新加密数据

### 问题 3: "文件权限错误"

**症状**：
```
PermissionError: [Errno 13] Permission denied
```

**解决方案**：
```bash
# 设置文件权限（仅所有者可读）
chmod 600 backend/credentials/.encryption_key
```

---

## 📚 相关文档

- [JWT密钥安全管理方案](../../docs/JWT密钥安全管理方案.md)
- [JWT密钥管理工具使用说明](./README_JWT密钥管理工具.md)
- [Core 模块文档](../app/core/README.md)
- [JWT使用说明](../app/core/JWT使用说明.md)

---

## 🔄 更新日志

### 2026-01-15
- ✅ 实现 ENCRYPTION_KEY 管理器（`encryption_key_manager.py`）
- ✅ 创建 CLI 工具（`manage_encryption_key.py`）
- ✅ 实现混合方案（环境变量 + 文件存储）
- ✅ 更新 `encryption.py` 使用新的管理器
