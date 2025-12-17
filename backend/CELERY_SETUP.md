# Celery 任务队列设置指南

本项目使用 **Celery + Redis** 实现文件上传的任务队列管理，支持：
- ✅ 并发控制（最多 3 个同时上传）
- ✅ 自动失败重试
- ✅ 任务状态追踪
- ✅ 分布式部署支持

## 一、安装依赖

```bash
cd backend
pip install -r requirements.txt
```

新增依赖：
- `celery>=5.3.0` - 分布式任务队列
- `redis>=5.0.0` - Redis 客户端

## 二、Redis 配置

确保 Redis 服务正在运行，配置已在 `.env` 文件中：

```env
REDIS_HOST=192.168.50.175
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=941378
```

测试 Redis 连接：
```bash
redis-cli -h 192.168.50.175 -p 6379 -a 941378 ping
```
应该返回：`PONG`

## 三、启动 Celery Worker

### 方法 1：Windows（开发环境）

在 `backend` 目录下运行：

```bash
celery -A app.core.celery_app worker --loglevel=info --pool=solo
```

**注意**：Windows 需要使用 `--pool=solo` 参数

### 方法 2：Linux/Mac（生产环境）

```bash
celery -A app.core.celery_app worker --loglevel=info --concurrency=3
```

### 方法 3：使用 Supervisor（推荐生产环境）

创建 `/etc/supervisor/conf.d/celery_worker.conf`：

```ini
[program:celery_worker]
command=/path/to/venv/bin/celery -A app.core.celery_app worker --loglevel=info --concurrency=3
directory=/path/to/backend
user=your_user
autostart=true
autorestart=true
stderr_logfile=/var/log/celery/worker.err.log
stdout_logfile=/var/log/celery/worker.out.log
```

启动：
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start celery_worker
```

## 四、验证运行

### 1. 查看 Worker 状态

```bash
celery -A app.core.celery_app inspect active
```

### 2. 查看队列中的任务

```bash
celery -A app.core.celery_app inspect reserved
```

### 3. 查看 Redis 中的任务

```bash
redis-cli -h 192.168.50.175 -p 6379 -a 941378
> KEYS *
> LLEN upload_queue
```

## 五、配置说明

### Celery 配置（`app/core/celery_app.py`）

```python
worker_concurrency=3,              # 最多 3 个并发任务
worker_prefetch_multiplier=1,      # 每次只预取 1 个任务
worker_max_tasks_per_child=50,     # Worker 进程处理 50 个任务后重启
task_time_limit=300,               # 任务最大执行时间 5 分钟
```

### 调整并发数

如果需要增加并发上传数量，修改 `celery_app.py`：

```python
worker_concurrency=5,  # 改为 5 个并发任务
```

重启 Worker 后生效。

## 六、监控和调试

### 1. 启动 Flower（Web 监控界面）

安装 Flower：
```bash
pip install flower
```

启动：
```bash
celery -A app.core.celery_app flower
```

访问：http://localhost:5555

### 2. 查看任务日志

Worker 日志会实时显示：
```
[Celery] 开始处理任务: 27de96e6...
[Celery] 上传到云存储: lsky
[Celery] 上传成功: https://cdn.example.com/xxx.png
[Celery] ✅ 会话已更新
```

### 3. 查看失败任务

```bash
celery -A app.core.celery_app inspect failed
```

## 七、常见问题

### 1. Worker 无法连接到 Redis

**问题**：`redis.exceptions.ConnectionError`

**解决**：
- 检查 Redis 是否运行：`redis-cli ping`
- 检查 `.env` 文件中的 Redis 配置
- 检查防火墙设置

### 2. 任务一直处于 pending 状态

**问题**：任务提交成功，但没有被处理

**解决**：
- 确保 Celery Worker 正在运行
- 检查 Worker 日志是否有错误
- 检查队列名称是否正确：`upload_queue`

### 3. Windows 上 Worker 报错

**问题**：`billiard.exceptions.WorkerLostError`

**解决**：
- 使用 `--pool=solo` 参数
- 或者安装 `eventlet`：`pip install eventlet` 并使用 `--pool=eventlet`

### 4. 任务执行超时

**问题**：上传大文件时任务超时

**解决**：
- 增加 `task_time_limit` 配置
- 检查网络连接和云存储服务

## 八、部署建议

### 开发环境
- 单个 Worker 进程
- 使用 `--loglevel=debug` 查看详细日志
- 手动启动 Worker

### 生产环境
- 使用 Supervisor 或 systemd 管理 Worker
- 根据负载调整 `worker_concurrency`
- 使用 `--loglevel=warning` 减少日志量
- 配置日志轮转
- 考虑启动多个 Worker 实例

## 九、性能优化

### 1. 增加 Worker 数量

启动多个 Worker 实例（每个实例 3 个并发）：

Terminal 1:
```bash
celery -A app.core.celery_app worker -n worker1@%h --concurrency=3
```

Terminal 2:
```bash
celery -A app.core.celery_app worker -n worker2@%h --concurrency=3
```

### 2. 使用 Redis Sentinel（高可用）

配置 Redis 主从复制和 Sentinel，确保队列服务高可用。

### 3. 监控和告警

使用 Flower 或 Prometheus + Grafana 监控：
- 队列长度
- 任务成功/失败率
- Worker CPU/内存使用
- 任务执行时间

## 十、停止 Worker

```bash
# 优雅停止（等待当前任务完成）
celery -A app.core.celery_app control shutdown

# 或直接 Ctrl+C（会等待当前任务）
```

## 十一、完整启动流程

```bash
# 1. 启动 Redis（如果未运行）
redis-server

# 2. 启动 FastAPI 后端
cd backend
uvicorn app.main:app --reload

# 3. 启动 Celery Worker（新终端）
cd backend
celery -A app.core.celery_app worker --loglevel=info --pool=solo

# 4. （可选）启动 Flower 监控（新终端）
cd backend
celery -A app.core.celery_app flower
```

现在你的上传任务队列系统已经准备就绪！🎉
