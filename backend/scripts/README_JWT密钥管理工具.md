# JWT Secret Key 管理工具使用说明

## 📖 简介

`manage_jwt_secret.py` 是一个命令行工具，用于安全地管理 JWT Secret Key。它提供了生成、查看、轮换密钥的功能，确保密钥不会泄露到代码或配置文件中。

---

## 🚀 快速开始

### 基本用法

```bash
# 从项目根目录执行
python -m backend.scripts.manage_jwt_secret <command> [options]
```

---

## 📋 可用命令

### 1. `show` - 显示 JWT Secret Key

显示当前 JWT Secret Key（默认只显示部分，用于验证）

#### 基本用法

```bash
# 显示部分密钥（推荐，安全）
python -m backend.scripts.manage_jwt_secret show
```

**输出示例：**
```
🔑 JWT Secret Key (部分): abc12345...xyz9
   提示：使用 --full 参数查看完整密钥

✅ 密钥文件: D:\gemini-main\gemini-main\backend\credentials\.jwt_secret.enc (加密)
```

#### 查看完整密钥

```bash
# 显示完整密钥（需要确认）
python -m backend.scripts.manage_jwt_secret show --full
```

**交互提示：**
```
⚠️  警告：完整密钥将显示在终端中，请确保终端安全！
确认显示完整密钥？(yes/no): yes

🔑 JWT Secret Key (完整):
abc12345-xyz67890_ABCDEFGH-IJKL MNOP-QRST-UVWX-YZabcdefghijklmnopqrstuvwxyz1234567890...

✅ 密钥文件: D:\gemini-main\gemini-main\backend\credentials\.jwt_secret.enc (加密)
```

⚠️ **安全提示**：
- 默认只显示部分密钥（前8个字符 + 后4个字符），用于验证
- 使用 `--full` 参数会显示完整密钥，需要手动确认
- 确保终端环境安全，避免密钥泄露

---

### 2. `generate` - 生成新密钥

生成新的 JWT Secret Key 并保存到加密文件

#### 基本用法

```bash
python -m backend.scripts.manage_jwt_secret generate
```

**如果密钥已存在，会提示确认：**
```
⚠️  警告：JWT Secret Key 已存在！
生成新密钥将覆盖现有密钥，所有现有 Token 将失效。
确认生成新密钥？(yes/no): yes

✅ JWT Secret Key 已生成并保存
   文件: D:\gemini-main\gemini-main\backend\credentials\.jwt_secret.enc
   密钥 (前8字符): abc12345...

⚠️  注意：请确保此文件已添加到 .gitignore，不会提交到版本控制！
```

**如果密钥不存在，直接生成：**
```
✅ JWT Secret Key 已生成并保存
   文件: D:\gemini-main\gemini-main\backend\credentials\.jwt_secret.enc
   密钥 (前8字符): xyz98765...

⚠️  注意：请确保此文件已添加到 .gitignore，不会提交到版本控制！
```

⚠️ **重要提示**：
- 生成新密钥会覆盖现有密钥
- 所有现有的 JWT Token 将失效
- 用户需要重新登录

---

### 3. `rotate` - 轮换密钥

轮换 JWT Secret Key（生成新密钥，替换旧密钥）

#### 基本用法

```bash
python -m backend.scripts.manage_jwt_secret rotate
```

**交互提示：**
```
⚠️  警告：轮换 JWT Secret Key 将导致所有现有 Token 失效！
所有用户需要重新登录。
确认轮换密钥？(yes/no): yes

✅ JWT Secret Key 已轮换
   新密钥 (前8字符): new12345...

⚠️  注意：所有现有 Token 已失效，用户需要重新登录
```

⚠️ **使用场景**：
- 定期安全维护（建议每 90 天）
- 密钥可能泄露时
- 安全审计要求

---

### 4. `status` - 查看状态

查看 JWT Secret Key 的当前状态和配置信息

#### 基本用法

```bash
python -m backend.scripts.manage_jwt_secret status
```

**输出示例：**
```
📊 JWT Secret Key 状态:

✅ 加密密钥文件存在: D:\gemini-main\gemini-main\.jwt_secret.enc
   大小: 256 字节
   状态: 已加密存储（推荐）

✅ 未加密密钥文件不存在（正常）

✅ 环境变量 JWT_SECRET_KEY 未设置（正常）

✅ ENCRYPTION_KEY 已设置（用于加密存储）
```

**可能的状态：**

| 状态 | 说明 | 建议 |
|------|------|------|
| ✅ 加密密钥文件存在 | 密钥已加密存储 | 正常，推荐 |
| ⚠️ 未加密密钥文件存在 | 密钥未加密存储 | 建议升级为加密存储 |
| ❌ 密钥文件不存在 | 密钥未生成 | 运行 `generate` 生成 |
| ⚠️ 环境变量已设置 | 使用环境变量（不推荐） | 建议迁移到文件存储 |

---

## 🔧 使用场景

### 场景 1: 首次部署

**步骤：**

1. **检查状态**：
   ```bash
   python -m backend.scripts.manage_jwt_secret status
   ```

2. **生成密钥**（如果不存在）：
   ```bash
   python -m backend.scripts.manage_jwt_secret generate
   ```

3. **验证密钥**：
   ```bash
   python -m backend.scripts.manage_jwt_secret show
   ```

---

### 场景 2: 验证密钥

**快速验证密钥是否存在：**
```bash
python -m backend.scripts.manage_jwt_secret show
```

**查看完整密钥（用于备份或迁移）：**
```bash
python -m backend.scripts.manage_jwt_secret show --full
```

---

### 场景 3: 密钥轮换

**定期安全维护：**
```bash
# 1. 查看当前状态
python -m backend.scripts.manage_jwt_secret status

# 2. 轮换密钥
python -m backend.scripts.manage_jwt_secret rotate

# 3. 通知用户重新登录（所有现有 Token 已失效）
```

---

### 场景 4: 从环境变量迁移

**如果你之前使用 `.env` 文件中的 `JWT_SECRET_KEY`：**

1. **查看当前环境变量**：
   ```bash
   # 在 .env 文件中查找 JWT_SECRET_KEY
   ```

2. **生成新密钥**（推荐）：
   ```bash
   python -m backend.scripts.manage_jwt_secret generate
   ```

3. **或手动迁移**（保持现有 Token 有效）：
   ```python
   # 在 Python 中执行
   from backend.app.core.jwt_secret_manager import JWTSecretManager
   old_secret = "your-old-secret-from-env"
   JWTSecretManager.save_secret(old_secret, encrypt=True)
   ```

4. **从 .env 文件中移除 `JWT_SECRET_KEY`**（不再需要）

---

## 📁 文件位置

### 密钥文件

- **加密文件**（推荐）：`backend/credentials/.jwt_secret.enc`
- **未加密文件**（向后兼容）：`backend/credentials/.jwt_secret`

### 文件权限

- 自动设置为 `0o600`（仅所有者可读）
- 已添加到 `.gitignore`，不会提交到版本控制

---

## 🔐 安全注意事项

### ✅ 推荐做法

1. **使用加密存储**：密钥以加密形式存储在 `.jwt_secret.enc`
2. **设置 ENCRYPTION_KEY**：确保 `ENCRYPTION_KEY` 环境变量已设置
3. **定期轮换**：建议每 90 天轮换一次密钥
4. **安全备份**：密钥文件应安全备份（加密存储）
5. **多环境分离**：开发、测试、生产环境使用不同的密钥

### ❌ 避免的做法

1. **不要提交到 Git**：确保 `.jwt_secret*` 文件在 `.gitignore` 中
2. **不要硬编码**：不要在代码中硬编码密钥
3. **不要共享密钥**：不同环境使用不同密钥
4. **不要使用默认值**：生产环境必须使用强随机密钥

---

## 🐛 故障排除

### 问题 1: "ENCRYPTION_KEY 未设置"

**错误信息：**
```
[JWTSecretManager] ⚠️ ENCRYPTION_KEY 未设置，使用开发环境回退密钥
```

**解决方案：**

1. **生成 ENCRYPTION_KEY**：
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

2. **添加到 .env 文件**：
   ```bash
   ENCRYPTION_KEY=your-generated-key-here
   ```

3. **重新运行命令**

---

### 问题 2: "无法读取密钥文件"

**错误信息：**
```
[JWTSecretManager] 读取加密文件失败: ...
```

**可能原因：**
- `ENCRYPTION_KEY` 不正确
- 文件权限问题
- 文件损坏

**解决方案：**

1. **检查 ENCRYPTION_KEY**：
   ```bash
   python -m backend.scripts.manage_jwt_secret status
   ```

2. **检查文件权限**：
   ```bash
   # Windows
   icacls backend\credentials\.jwt_secret.enc
   
   # Linux/Mac
   ls -l backend/credentials/.jwt_secret.enc
   ```

3. **重新生成密钥**（如果文件损坏）：
   ```bash
   python -m backend.scripts.manage_jwt_secret generate
   ```

---

### 问题 3: "ModuleNotFoundError"

**错误信息：**
```
ModuleNotFoundError: No module named 'backend'
```

**解决方案：**

1. **确保在项目根目录执行**：
   ```bash
   cd D:\gemini-main\gemini-main
   python -m backend.scripts.manage_jwt_secret status
   ```

2. **或使用绝对路径**：
   ```bash
   python D:\gemini-main\gemini-main\backend\scripts\manage_jwt_secret.py status
   ```

---

### 问题 4: "所有 Token 失效"

**原因：**
- 密钥被轮换或重新生成
- `ENCRYPTION_KEY` 被更改

**解决方案：**
- 这是预期的安全行为
- 用户需要重新登录
- 如果需要保持 Token 有效，不要轮换密钥

---

## 📊 命令参考

### 完整命令列表

```bash
# 显示帮助
python -m backend.scripts.manage_jwt_secret --help

# 显示密钥（部分）
python -m backend.scripts.manage_jwt_secret show

# 显示完整密钥
python -m backend.scripts.manage_jwt_secret show --full

# 生成新密钥
python -m backend.scripts.manage_jwt_secret generate

# 轮换密钥
python -m backend.scripts.manage_jwt_secret rotate

# 查看状态
python -m backend.scripts.manage_jwt_secret status
```

---

## 🔄 工作流程

### 首次部署流程

```
1. 设置 ENCRYPTION_KEY 环境变量
   ↓
2. 运行: python -m backend.scripts.manage_jwt_secret generate
   ↓
3. 验证: python -m backend.scripts.manage_jwt_secret show
   ↓
4. 启动应用（自动读取密钥）
```

### 日常使用流程

```
应用启动
   ↓
自动读取 .jwt_secret.enc
   ↓
使用密钥生成/验证 Token
```

### 密钥轮换流程

```
1. 通知用户（即将轮换密钥）
   ↓
2. 运行: python -m backend.scripts.manage_jwt_secret rotate
   ↓
3. 所有现有 Token 失效
   ↓
4. 用户重新登录（使用新密钥）
```

---

## 💡 最佳实践

### 1. 密钥生成

- ✅ 使用工具自动生成（强随机）
- ❌ 不要手动设置弱密钥

### 2. 密钥存储

- ✅ 使用加密文件存储（`.jwt_secret.enc`）
- ❌ 不要存储在 `.env` 文件中
- ❌ 不要硬编码在代码中

### 3. 密钥查看

- ✅ 使用 `show` 命令查看（部分显示）
- ✅ 仅在安全环境下使用 `--full` 参数
- ❌ 不要将密钥复制到不安全的地方

### 4. 密钥轮换

- ✅ 定期轮换（建议每 90 天）
- ✅ 轮换前通知用户
- ✅ 轮换后验证系统正常工作

### 5. 多环境管理

- ✅ 每个环境使用不同的密钥
- ✅ 开发、测试、生产环境分离
- ✅ 密钥文件不提交到版本控制

---

## 📝 示例

### 示例 1: 首次设置

```bash
# 1. 检查状态
$ python -m backend.scripts.manage_jwt_secret status

📊 JWT Secret Key 状态:

❌ 加密密钥文件不存在: D:\gemini-main\gemini-main\.jwt_secret.enc
✅ 未加密密钥文件不存在（正常）
✅ 环境变量 JWT_SECRET_KEY 未设置（正常）
✅ ENCRYPTION_KEY 已设置（用于加密存储）

# 2. 生成密钥
$ python -m backend.scripts.manage_jwt_secret generate

✅ JWT Secret Key 已生成并保存
   文件: D:\gemini-main\gemini-main\backend\credentials\.jwt_secret.enc
   密钥 (前8字符): xK9mP2qR...

# 3. 验证
$ python -m backend.scripts.manage_jwt_secret show

🔑 JWT Secret Key (部分): xK9mP2qR...zY8w
✅ 密钥文件: D:\gemini-main\gemini-main\backend\credentials\.jwt_secret.enc (加密)
```

### 示例 2: 定期检查

```bash
# 检查密钥状态
$ python -m backend.scripts.manage_jwt_secret status

📊 JWT Secret Key 状态:

✅ 加密密钥文件存在: D:\gemini-main\gemini-main\.jwt_secret.enc
   大小: 256 字节
   状态: 已加密存储（推荐）

✅ 未加密密钥文件不存在（正常）
✅ 环境变量 JWT_SECRET_KEY 未设置（正常）
✅ ENCRYPTION_KEY 已设置（用于加密存储）
```

### 示例 3: 密钥轮换

```bash
# 轮换密钥
$ python -m backend.scripts.manage_jwt_secret rotate

⚠️  警告：轮换 JWT Secret Key 将导致所有现有 Token 失效！
所有用户需要重新登录。
确认轮换密钥？(yes/no): yes

✅ JWT Secret Key 已轮换
   新密钥 (前8字符): aB3cD5eF...

⚠️  注意：所有现有 Token 已失效，用户需要重新登录
```

---

## 🔗 相关文档

- [JWT密钥安全管理方案](../../docs/JWT密钥安全管理方案.md) - 完整的安全方案说明
- [encryption.py](../app/core/encryption.py) - 加密工具（使用相同的 ENCRYPTION_KEY）
- [jwt_utils.py](../app/core/jwt_utils.py) - JWT 工具类（使用 Secret Manager）

---

## ❓ 常见问题

### Q1: 密钥文件在哪里？

**A:** 密钥文件存储在 `backend/credentials/` 目录：
- 加密文件：`backend/credentials/.jwt_secret.enc`
- 未加密文件：`backend/credentials/.jwt_secret`（向后兼容，会自动升级）

### Q2: 如何备份密钥？

**A:** 
1. 使用 `show --full` 查看完整密钥
2. 将密钥安全存储（加密存储，例如密码管理器）
3. 或直接备份 `backend/credentials/.jwt_secret.enc` 文件（需要同时备份 `ENCRYPTION_KEY`）

### Q3: 密钥轮换后用户需要做什么？

**A:** 用户需要重新登录。所有现有的 JWT Token 将失效。

### Q4: 可以在生产环境使用吗？

**A:** 可以，但必须：
1. 设置 `ENCRYPTION_KEY` 环境变量
2. 确保密钥文件权限安全（`0o600`）
3. 确保密钥文件不在版本控制中
4. 定期轮换密钥

### Q5: 如何迁移到新服务器？

**A:**
1. 备份 `backend/credentials/.jwt_secret.enc` 文件
2. 备份 `ENCRYPTION_KEY` 环境变量
3. 在新服务器上恢复这两个文件（确保 `backend/credentials/` 目录存在）
4. 验证密钥正常工作

---

## 📞 支持

如果遇到问题，请：
1. 查看 [故障排除](#-故障排除) 部分
2. 检查日志文件
3. 运行 `status` 命令查看详细状态
