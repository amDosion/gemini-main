# Design Document

## Overview

本设计文档描述了上传 Worker 池的按需激活（懒加载）实现方案。核心思想是将 Worker 池从"应用启动时立即激活"改为"首次需要时激活"，同时保留崩溃恢复能力。

## Architecture

### 状态机设计

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐     │
│  IDLE   │───▶│STARTING │───▶│ RUNNING │───▶│ STOPPED │     │
└─────────┘    └─────────┘    └─────────┘    └─────────┘     │
     │              │                             │           │
     │              │                             │           │
     │              ▼                             │           │
     │         ┌─────────┐                        │           │
     └────────▶│  ERROR  │◀───────────────────────┘           │
               └─────────┘                                    │
                    │                                         │
                    └─────────────────────────────────────────┘
                         (retry on next request)
```

### 启动流程

```
应用启动
    │
    ▼
┌─────────────────────────────┐
│ 1. 检查数据库是否有未完成任务 │
└─────────────────────────────┘
    │
    ├─── 有未完成任务 ───▶ 自动启动 Worker 池
    │
    └─── 无未完成任务 ───▶ 保持 IDLE 状态
                              │
                              ▼
                    ┌─────────────────────┐
                    │ 等待首次上传请求     │
                    └─────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │ 启动 Worker 池       │
                    └─────────────────────┘
```

## Components and Interfaces

### 1. UploadWorkerPool 类修改

```python
class PoolStatus(Enum):
    IDLE = "idle"           # 未启动，等待首次请求
    STARTING = "starting"   # 正在启动中
    RUNNING = "running"     # 正常运行
    ERROR = "error"         # 启动失败
    STOPPED = "stopped"     # 已停止

class UploadWorkerPool:
    def __init__(self):
        self._status: PoolStatus = PoolStatus.IDLE
        self._init_lock: asyncio.Lock = asyncio.Lock()
        self._redis_connected: bool = False
        # ... 其他现有属性
    
    async def ensure_started(self) -> bool:
        """确保 Worker 池已启动（懒加载入口）"""
        pass
    
    async def check_pending_tasks(self) -> bool:
        """检查数据库是否有未完成任务"""
        pass
    
    def get_status(self) -> dict:
        """获取 Worker 池状态信息"""
        pass
```

### 2. 健康检查接口扩展

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "worker_pool": {
            "status": worker_pool.get_status()["status"],
            "worker_count": worker_pool.get_status()["worker_count"],
            "message": worker_pool.get_status()["message"]
        },
        # ... 其他健康检查项
    }
```

### 3. 上传任务入队修改

```python
async def enqueue_upload_task(task_id: str, priority: str = "normal"):
    """入队上传任务（触发懒加载）"""
    # 确保 Worker 池已启动
    if not await worker_pool.ensure_started():
        raise RuntimeError("Worker pool failed to start")
    
    # 入队任务
    await redis_queue.enqueue(task_id, priority)
```

## Data Models

### PoolStatus 枚举

| 状态 | 说明 | Redis 连接 | Workers 运行 |
|------|------|-----------|-------------|
| IDLE | 未启动 | 可选 | 否 |
| STARTING | 启动中 | 是 | 部分 |
| RUNNING | 运行中 | 是 | 是 |
| ERROR | 错误 | 可能 | 否 |
| STOPPED | 已停止 | 否 | 否 |

### 状态信息结构

```python
{
    "status": "idle" | "starting" | "running" | "error" | "stopped",
    "worker_count": int,          # 当前活跃 Worker 数量
    "message": str,               # 状态描述信息
    "last_error": str | None,     # 最后一次错误信息
    "started_at": datetime | None # 启动时间
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Lazy Start Timing
*For any* valid upload task, when enqueued to an idle Worker pool, the pool SHALL transition to RUNNING state within 2 seconds.
**Validates: Requirements 1.3**

### Property 2: Auto-Start on Pending Tasks
*For any* application startup with pending or uploading tasks in the database, the Worker pool SHALL automatically start and recover all interrupted tasks.
**Validates: Requirements 2.1, 2.2**

### Property 3: Concurrent Initialization Safety
*For any* number of concurrent upload requests arriving when the pool is IDLE, exactly one initialization SHALL occur, and all requests SHALL receive a valid running pool.
**Validates: Requirements 3.1, 3.2**

### Property 4: Status Enum Validity
*For any* health check query, the returned Worker pool status SHALL be one of: idle, starting, running, error, or stopped.
**Validates: Requirements 4.1**

## Error Handling

### 初始化失败处理

1. **Redis 连接失败**
   - 记录错误日志
   - 设置状态为 ERROR
   - 保存错误信息到 `last_error`
   - 下次请求时重试

2. **Worker 启动失败**
   - 停止已启动的 Workers
   - 断开 Redis 连接
   - 设置状态为 ERROR
   - 允许手动或自动重试

3. **重试策略**
   - 最大重试次数：3 次
   - 重试间隔：指数退避（1s, 2s, 4s）
   - 超过重试次数后需要手动干预

### 错误恢复流程

```
ERROR 状态
    │
    ▼
新上传请求到达
    │
    ▼
┌─────────────────────┐
│ 检查重试次数 < 3    │
└─────────────────────┘
    │
    ├─── 是 ───▶ 尝试重新启动
    │              │
    │              ├─── 成功 ───▶ RUNNING
    │              │
    │              └─── 失败 ───▶ ERROR (重试次数+1)
    │
    └─── 否 ───▶ 返回错误，需要手动重启
```

## Testing Strategy

### 单元测试

1. **状态转换测试**
   - 测试 IDLE → STARTING → RUNNING 正常流程
   - 测试 IDLE → STARTING → ERROR 失败流程
   - 测试 ERROR → STARTING → RUNNING 恢复流程

2. **并发安全测试**
   - 模拟多个并发请求同时触发初始化
   - 验证只有一次初始化发生

3. **崩溃恢复测试**
   - 模拟数据库中有 pending 任务
   - 验证应用启动时自动启动 Worker 池

### 属性测试

使用 `hypothesis` 库进行属性测试：

1. **Property 1 测试**：生成随机任务，验证启动时间 < 2s
2. **Property 2 测试**：生成随机 pending 任务集，验证全部恢复
3. **Property 3 测试**：生成随机并发请求数，验证单次初始化
4. **Property 4 测试**：生成随机状态查询，验证返回值有效

### 集成测试

1. **端到端流程测试**
   - 应用启动（无 pending 任务）→ 验证 IDLE
   - 发送上传请求 → 验证 Worker 池启动
   - 验证任务处理完成

2. **健康检查测试**
   - 各状态下的健康检查响应验证
