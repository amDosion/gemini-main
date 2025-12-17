# Celery 自动启动测试指南

## 功能说明

现在当您启动 FastAPI 后端时，Celery Worker 会**自动随后端一起启动**，无需手动运行额外的命令。

## 启动方式

### 方式 1：使用 uvicorn（推荐开发环境）

```bash
cd backend
uvicorn app.main:app --reload
```

### 方式 2：直接运行 Python

```bash
cd backend
python -m app.main
```

## 验证启动成功

启动后端时，您应该看到以下日志输出：

```
============================================================
[ℹ️ INFO] 正在启动 Celery Worker...
============================================================
[ℹ️ INFO] 检测到操作系统: Windows
[ℹ️ INFO] 使用 pool 模式: solo
[✅ SUCCESS] ✅ Celery Worker 已启动 (PID: 12345)
[ℹ️ INFO] 并发数: 3, 队列: upload_queue
============================================================
```

## 测试文件上传任务

1. 启动后端：
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. 使用 Postman 或 curl 测试上传接口：
   ```bash
   curl -X POST http://localhost:8000/api/storage/upload \
     -F "file=@test.jpg" \
     -F "platform=lsky"
   ```

3. 检查日志，应该看到 Celery 任务处理信息：
   ```
   [Celery] 开始处理任务: task-id-xxx
   [Celery] 上传到云存储: lsky
   [Celery] 上传成功: https://...
   ```

## 停止服务

按 `Ctrl+C` 停止后端时，Celery Worker 会自动优雅停止：

```
============================================================
[ℹ️ INFO] 正在停止 Celery Worker...
============================================================
[✅ SUCCESS] ✅ Celery Worker 已优雅停止
============================================================
```

## 故障排查

### 问题 1：Celery Worker 启动失败

**日志**：`❌ Celery Worker 启动失败`

**原因**：
- Redis 未启动或连接失败
- Celery 依赖未安装

**解决**：
```bash
# 检查 Redis 连接
redis-cli -h 192.168.50.175 -p 6379 -a 941378 ping

# 安装依赖
pip install -r requirements.txt
```

### 问题 2：端口已被占用

**日志**：`Address already in use`

**解决**：
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### 问题 3：Celery Worker 未停止

如果 Worker 进程残留，手动清理：

```bash
# Windows
tasklist | findstr celery
taskkill /IM celery.exe /F

# Linux/Mac
ps aux | grep celery
kill -9 <PID>
```

## 与原始启动方式对比

| 启动方式 | 命令数量 | 终端窗口 | 适用场景 |
|---------|---------|---------|---------|
| **自动启动** | 1 条 | 1 个 | 开发环境（推荐）|
| 手动启动 | 2 条 | 2 个 | 生产环境/调试 |

## 生产环境建议

虽然自动启动方便开发，但**生产环境仍建议分离部署**：

1. 使用 **Supervisor/systemd** 独立管理 Celery Worker
2. 使用 **Docker Compose** 容器化部署
3. 使用 **PM2** 进程管理

原因：
- 独立扩展 Worker 数量
- 更好的监控和日志管理
- 故障隔离（一个服务崩溃不影响另一个）

## 日志说明

### FastAPI 日志

- 来自 `app.main` 和 routers
- 显示 API 请求、响应等

### Celery Worker 日志

- 来自 `celery.app.trace`
- 显示任务执行状态、上传进度等

两者日志会混合显示，可以通过日志前缀区分：
- `[ℹ️ INFO]` - FastAPI 日志
- `[Celery]` - Celery 任务日志

## 注意事项

1. **开发环境**：`--reload` 模式下，代码修改会导致 FastAPI 重启，Celery Worker 也会随之重启
2. **性能影响**：单个终端运行两个服务，日志会混合输出，建议开发时使用
3. **Windows 限制**：Windows 上必须使用 `solo` 模式，性能略低于 Linux 的 `prefork` 模式

## 恢复手动启动

如果需要恢复手动启动模式，删除 `main.py:160-255` 的启动事件处理代码即可。
