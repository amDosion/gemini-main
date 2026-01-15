# Key Service 自动启动说明

## 📋 概述

应用启动时会**自动启动 Key Service 子进程**，无需手动管理。这是默认行为，推荐用于开发和生产环境。

---

## 🚀 使用方式

### 默认方式（自动启动 Key Service）

**直接启动应用**：
```bash
python -m backend.app.main
```

**系统会自动**：
1. ✅ 启动 Key Service 子进程
2. ✅ 等待 Key Service 就绪（最多 3 秒）
3. ✅ 连接到 Key Service
4. ✅ 应用关闭时自动停止 Key Service

**启动日志示例**：
```
[KeyService] ✅ 密钥已初始化（Key Service 进程内存存储）
[KeyService] ✅ Key Service 已启动
  - Client Socket: /tmp/gemini_key_service_client.sock
  - Admin Socket: /tmp/gemini_key_service_admin.sock
[main] ✅ Key Service 已自动启动（进程 ID: 12345）
[KeyServiceClient] ✅ Key Service 客户端已初始化（使用 Key Service）
```

### 禁用自动启动（使用文件存储）

如果不想使用 Key Service，可以禁用自动启动：

**Unix/Linux**：
```bash
export AUTO_START_KEY_SERVICE=false
python -m backend.app.main
```

**Windows**：
```powershell
$env:AUTO_START_KEY_SERVICE="false"
python -m backend.app.main
```

**启动日志示例**：
```
[KeyServiceClient] ℹ️ Key Service 未启动，将使用文件存储（这是正常的）
[KeyServiceClient] ✅ Key Service Client initialized (方案 D)
```

---

## ⚙️ 配置

### 环境变量

**`AUTO_START_KEY_SERVICE`**：
- **默认值**：`true`（自动启动 Key Service）
- **可选值**：`false`（禁用自动启动，使用文件存储）

---

## 🔄 工作流程

### 自动启动流程

```
应用启动
    ↓
检查 AUTO_START_KEY_SERVICE（默认：true）
    ↓
如果为 true：
    1. 启动 Key Service 子进程
    2. 等待 Key Service 就绪（最多 3 秒）
    3. 检查 Socket/端口文件
    4. 初始化 Key Service Client
    5. 连接到 Key Service
    ↓
如果为 false 或启动失败：
    1. 跳过 Key Service 启动
    2. 初始化 Key Service Client
    3. 回退到文件存储（向后兼容）
```

### 关闭流程

```
应用关闭
    ↓
停止 Key Service 子进程（如果已启动）
    ↓
发送 SIGTERM（Unix）或 terminate（Windows）
    ↓
等待进程结束（最多 5 秒）
    ↓
如果超时，强制终止（kill）
```

---

## 🛠️ 故障排除

### 问题 1：Key Service 自动启动失败

**可能原因**：
- Python 解释器路径错误
- Key Service 模块导入失败
- 端口/Socket 文件被占用

**解决方案**：
- 系统会自动回退到文件存储，功能正常
- 检查日志了解具体错误
- 可以手动启动 Key Service 进行调试

### 问题 2：Key Service 启动超时

**可能原因**：
- Key Service 启动较慢
- 系统资源不足

**解决方案**：
- 系统会继续等待，Key Service 启动后会自动连接
- 如果 3 秒后仍未就绪，系统会继续运行，稍后自动连接

### 问题 3：应用关闭时 Key Service 未停止

**可能原因**：
- 进程终止信号未正确处理
- 进程被其他进程占用

**解决方案**：
- 系统会在 5 秒后强制终止
- 可以手动检查并终止进程

---

## 📝 最佳实践

### ✅ 推荐做法

1. **使用默认方式**（自动启动 Key Service）
   - 简单，无需手动管理
   - 最佳安全隔离
   - 适合开发和生产环境

2. **生产环境配置**
   - 确保 `ENCRYPTION_KEY` 环境变量已设置
   - 确保 `KEY_SERVICE_CLIENT_TOKEN` 已配置（如果使用自定义令牌）

### ⚠️ 注意事项

1. **进程管理**
   - Key Service 是应用进程的子进程
   - 应用进程关闭时，Key Service 会自动停止
   - 不要手动终止 Key Service 进程（除非应用已关闭）

2. **资源占用**
   - Key Service 是轻量级进程，资源占用很小
   - 如果不需要，可以禁用自动启动

---

## 🔗 相关文档

- [Key Service使用说明](./Key Service使用说明.md) - 完整使用说明
- [Key Service方案D实施说明](./Key Service方案D实施说明.md) - 实施说明
- [基于内存的密钥管理方案分析](./基于内存的密钥管理方案分析.md) - 方案分析
