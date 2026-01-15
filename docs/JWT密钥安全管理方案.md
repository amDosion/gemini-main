# JWT Secret Key 安全管理方案

## 🔒 安全原则

1. **不硬编码**：JWT Secret Key 不应硬编码在 `.env` 文件或代码中
2. **自动生成**：系统首次启动时自动生成强随机密钥
3. **加密存储**：密钥以加密形式存储在安全文件中
4. **终端查看**：只能通过项目终端命令查看密钥
5. **版本控制排除**：密钥文件已添加到 `.gitignore`，不会提交到 Git

---

## 📁 文件结构

```
项目根目录/
└── backend/
    ├── credentials/
    │   ├── .jwt_secret.enc          # 加密的 JWT Secret Key（推荐）
    │   └── .jwt_secret              # 未加密的密钥（向后兼容，会自动升级）
    └── app/
        └── core/
            ├── jwt_utils.py              # JWT 工具类（使用 Secret Manager）
            └── jwt_secret_manager.py     # JWT Secret Key 管理器
```

---

## 🚀 使用方法

### 1. 首次运行（自动生成）

系统首次启动时，如果密钥文件不存在，会自动生成并保存：

```python
# 在 jwt_utils.py 中自动调用
JWT_SECRET_KEY = _get_jwt_secret_key()  # 自动生成或读取
```

⚠️ **重要**：自动生成不会影响任何现有的 refresh tokens（因为首次运行还没有 tokens）。

### 2. 查看密钥（终端命令）

#### 查看部分密钥（推荐，用于验证）

```bash
# 从项目根目录执行
python -m backend.scripts.manage_jwt_secret show
```

输出示例：
```
🔑 JWT Secret Key (部分): abc12345...xyz9
   提示：使用 --full 参数查看完整密钥

✅ 密钥文件: D:\gemini-main\gemini-main\backend\credentials\.jwt_secret.enc (加密)
```

#### 查看完整密钥（需要确认）

```bash
python -m backend.scripts.manage_jwt_secret show --full
```

⚠️ **警告**：完整密钥将显示在终端中，请确保终端安全！

### 3. 生成新密钥

```bash
python -m backend.scripts.manage_jwt_secret generate
```

**行为说明**：
- **首次生成**（密钥文件不存在）：生成新密钥，不影响任何 tokens
- **覆盖生成**（密钥文件已存在）：视为安全轮换，会撤销数据库中的所有 refresh tokens，用户需要重新登录

⚠️ **注意**：如果密钥已存在，会提示确认（覆盖后所有现有 Token 将失效）

### 4. 轮换密钥（安全轮换）

```bash
python -m backend.scripts.manage_jwt_secret rotate
```

**行为说明**：
- 生成新密钥
- **自动撤销数据库中的所有 refresh tokens**
- 所有用户需要重新登录

⚠️ **警告**：轮换后所有现有 Token 将失效，用户需要重新登录

### 5. 查看状态

```bash
python -m backend.scripts.manage_jwt_secret status
```

输出示例：
```
📊 JWT Secret Key 状态:

✅ 加密密钥文件存在: D:\gemini-main\gemini-main\backend\credentials\.jwt_secret.enc
   大小: 256 字节
   状态: 已加密存储（推荐）

✅ 未加密密钥文件不存在（正常）

✅ 环境变量 JWT_SECRET_KEY 未设置（正常）

✅ ENCRYPTION_KEY 已设置（用于加密存储）
```

---

## 🔐 安全机制

### 1. 密钥生成

- 使用 `secrets.token_urlsafe(64)` 生成 64 字节的强随机密钥
- 适合 HS256 算法（512 位密钥）
- 使用加密安全的随机数生成器

### 2. 加密存储

- 使用 Fernet 对称加密（AES-128-CBC + HMAC-SHA256）
- 加密密钥来自 `ENCRYPTION_KEY` 环境变量（与 `encryption.py` 使用相同的密钥）
- 密钥文件权限设置为 `0o600`（仅所有者可读）

### 3. 密钥获取优先级

```
1. 加密文件 (.jwt_secret.enc) ← 推荐
   ↓ 不存在
2. 未加密文件 (.jwt_secret) ← 自动升级为加密
   ↓ 不存在
3. 环境变量 (JWT_SECRET_KEY) ← 向后兼容，不推荐
   ↓ 不存在
4. 默认值（仅开发环境，不安全）
```

### 4. 自动升级

- 如果检测到未加密的密钥文件，会自动：
  1. 读取未加密密钥
  2. 加密保存到 `.jwt_secret.enc`
  3. 删除未加密文件

---

## ⚙️ 配置要求

### 必需的环境变量

```bash
# ENCRYPTION_KEY（用于加密 JWT Secret Key）
# 生成方式：
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 添加到 .env 文件：
ENCRYPTION_KEY=your-generated-encryption-key-here
```

### 可选的环境变量

```bash
# JWT Token 过期时间（可选，有默认值）
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## 🔄 迁移指南

### 从旧版本迁移

如果你之前使用 `.env` 文件中的 `JWT_SECRET_KEY`：

1. **备份现有密钥**（如果重要）：
   ```bash
   # 从 .env 文件中复制 JWT_SECRET_KEY 的值
   ```

2. **生成新的安全密钥**：
   ```bash
   python -m backend.scripts.manage_jwt_secret generate
   ```

3. **（可选）从旧密钥迁移**：
   - 如果需要在迁移期间保持现有 Token 有效，可以手动创建密钥文件：
   ```python
   from backend.app.core.jwt_secret_manager import JWTSecretManager
   JWTSecretManager.save_secret("your-old-secret-key", encrypt=True)
   ```

4. **从 .env 文件中移除 JWT_SECRET_KEY**（不再需要）

---

## 🛡️ 安全最佳实践

### ✅ 推荐做法

1. **使用加密存储**：密钥以加密形式存储在 `.jwt_secret.enc`
2. **设置 ENCRYPTION_KEY**：确保 `ENCRYPTION_KEY` 环境变量已设置
3. **文件权限**：密钥文件权限自动设置为 `0o600`（仅所有者可读）
4. **版本控制排除**：密钥文件已添加到 `.gitignore`
5. **定期轮换**：建议定期轮换密钥（例如每 90 天）

### ❌ 避免的做法

1. **不要硬编码**：不要在代码中硬编码密钥
2. **不要提交到 Git**：确保 `.jwt_secret*` 文件在 `.gitignore` 中
3. **不要共享密钥**：每个环境（开发/生产）应使用不同的密钥
4. **不要使用默认值**：生产环境必须使用强随机密钥

---

## 🔧 故障排除

### 问题 1: "ENCRYPTION_KEY 未设置"

**错误信息：**
```
[JWTSecretManager] ⚠️ ENCRYPTION_KEY 未设置，使用开发环境回退密钥
```

**解决方案：**
1. 生成 ENCRYPTION_KEY：
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
2. 添加到 `.env` 文件：
   ```bash
   ENCRYPTION_KEY=your-generated-key-here
   ```

### 问题 2: "无法读取密钥文件"

**错误信息：**
```
[JWTSecretManager] 读取加密文件失败: ...
```

**解决方案：**
1. 检查文件权限：`ls -l .jwt_secret.enc`
2. 检查 ENCRYPTION_KEY 是否正确
3. 如果文件损坏，重新生成：
   ```bash
   python -m backend.scripts.manage_jwt_secret generate
   ```

### 问题 3: "所有 Token 失效"

**原因：**
- 密钥被轮换或重新生成
- ENCRYPTION_KEY 被更改

**解决方案：**
- 这是预期的安全行为
- 用户需要重新登录
- 如果需要保持 Token 有效，不要轮换密钥

---

## 📊 密钥格式

### 密钥特征

- **长度**：约 86 个字符（64 字节的 URL-safe base64 编码）
- **格式**：URL-safe base64（使用 `-` 和 `_` 而不是 `+` 和 `/`）
- **示例**：`abc12345-xyz67890_ABCDEFGH...`（实际密钥更长）

### 存储格式

**加密文件 (.jwt_secret.enc)：**
```json
{
  "secret": "gAAAAABh...encrypted_base64...",
  "encrypted": true,
  "created_at": "1234567890.123"
}
```

---

## 🔍 验证密钥

### 检查密钥是否正常工作

1. **查看密钥状态**：
   ```bash
   python -m backend.scripts.manage_jwt_secret status
   ```

2. **测试 Token 生成**：
   ```python
   from backend.app.core.jwt_utils import create_access_token, decode_token
   token = create_access_token("test-user-id")
   payload = decode_token(token)
   print(f"Token 生成成功: {payload.sub}")
   ```

---

## 📝 总结

### 优势

✅ **安全性**：密钥加密存储，不会泄露到代码或配置文件中  
✅ **自动化**：首次运行自动生成，无需手动配置  
✅ **管理工具**：提供 CLI 命令方便管理  
✅ **向后兼容**：支持从环境变量迁移  
✅ **版本控制安全**：密钥文件已排除在 Git 之外  

### 使用流程

1. **首次部署**：
   - 设置 `ENCRYPTION_KEY` 环境变量
   - 启动应用，自动生成密钥
   - 使用 CLI 命令查看密钥（如需要）

2. **日常使用**：
   - 应用自动读取密钥
   - 无需手动干预

3. **密钥轮换**：
   - 使用 CLI 命令轮换
   - 通知用户重新登录

---

## 🚨 重要提醒

1. **生产环境**：必须设置 `ENCRYPTION_KEY` 环境变量
2. **密钥备份**：建议安全备份密钥文件（加密存储）
3. **多环境**：开发、测试、生产环境应使用不同的密钥
4. **密钥轮换**：定期轮换密钥（建议每 90 天）

---

## 🔄 密钥更换逻辑说明

### 自动生成 vs 手动轮换

系统区分两种密钥更换场景：

#### 1. **自动生成**（首次运行）
- **触发**：系统首次启动，密钥文件不存在
- **行为**：生成新密钥，**不影响任何 refresh tokens**
- **原因**：首次运行还没有任何 tokens，无需清理

#### 2. **手动轮换**（安全轮换）
- **触发**：使用 CLI 命令 `generate`（覆盖）或 `rotate`
- **行为**：
  - 生成新密钥
  - **自动撤销数据库中的所有 refresh tokens**
  - 所有用户需要重新登录
- **原因**：旧密钥已失效，使用旧密钥签发的 tokens 无法验证，必须清理

### 为什么需要清理 refresh tokens？

当 JWT 密钥更换后：
- 使用旧密钥签发的 tokens 无法通过新密钥验证
- 数据库中的 refresh tokens 记录仍然存在
- 如果不清理，可能导致：
  - 用户尝试刷新 token 时失败
  - 数据库中存在大量无效的 refresh token 记录
  - 安全风险（旧 tokens 理论上仍可被使用，如果密钥泄露）

### 清理机制

手动轮换时，系统会：
1. 撤销所有未过期的 refresh tokens（设置 `revoked_at`）
2. 保留已过期的记录（等待定期清理任务删除）
3. 记录日志，显示被撤销的 token 数量

---

## 💡 关于 .env 文件的安全性

### 当前方案（加密文件）vs .env 文件

| 特性 | 加密文件方案 | .env 文件方案 |
|------|-------------|---------------|
| **存储方式** | 加密存储（Fernet） | 明文存储 |
| **安全性** | 高（需要 ENCRYPTION_KEY 才能解密） | 中（文件权限保护） |
| **可见性** | 即使文件泄露，也无法直接读取 | 文件泄露即可直接读取 |
| **管理** | CLI 工具管理 | 手动编辑 |
| **版本控制** | 已排除在 Git 外 | 需要手动排除 |

### 推荐方案

✅ **推荐使用加密文件方案**（当前方案）：
- 密钥以加密形式存储，即使文件泄露也需要 `ENCRYPTION_KEY` 才能解密
- 提供 CLI 工具，便于管理和轮换
- 自动处理 refresh tokens 清理
- 更符合安全最佳实践

⚠️ **.env 文件方案**（不推荐）：
- 虽然一般看不到，但仍然是明文存储
- 如果 `.env` 文件泄露，密钥直接暴露
- 需要手动管理密钥轮换和 refresh tokens 清理
- 不符合安全最佳实践

### 如果必须使用 .env

如果由于特殊原因必须使用 `.env` 文件：
1. 确保 `.env` 文件在 `.gitignore` 中
2. 设置严格的文件权限（`0o600`）
3. 定期轮换密钥
4. 手动清理 refresh tokens（使用数据库管理工具）
