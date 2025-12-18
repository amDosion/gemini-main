# 高并发队列上传方案

## 1. 问题分析

### 1.1 当前架构问题

```
当前问题：
┌─────────────────────────────────────────────────────────────────┐
│  前端并发请求                                                    │
│                                                                  │
│  图片1 ──▶ checkBackendAvailable() ──▶ uploadViaBackend()       │
│  图片2 ──▶ checkBackendAvailable() ──▶ uploadViaBackend()       │
│  图片3 ──▶ checkBackendAvailable() ──▶ uploadViaBackend()       │
│       ↑                                                          │
│       └── 并发竞态，重复检测，资源浪费                           │
│                                                                  │
│  后端 BackgroundTasks                                            │
│  - 无并发控制                                                    │
│  - 无优先级管理                                                  │
│  - 无失败重试策略                                                │
│  - 无资源限制                                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 高并发场景需求

- 批量图片生成（一次 3-10 张）
- 多用户同时操作
- 云存储 API 限流（兰空图床、阿里云 OSS）
- 网络波动和超时处理


## 2. 整体架构设计

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              高并发队列上传架构                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                           前端 (Frontend)                                │   │
│  │                                                                          │   │
│  │  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │   │
│  │  │  Handler 层   │───▶│         UploadQueueService (新增)            │   │   │
│  │  └──────────────┘    │  - 本地队列管理                               │   │   │
│  │                       │  - 并发控制 (最大 3 个)                       │   │   │
│  │                       │  - 自动重试 (指数退避)                        │   │   │
│  │                       │  - 状态回调                                   │   │   │
│  │                       └──────────────────────────────────────────────┘   │   │
│  │                                      │                                   │   │
│  │                                      │ HTTP POST (受控并发)              │   │
│  └──────────────────────────────────────│───────────────────────────────────┘   │
│                                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                           后端 (Backend)                                 │   │
│  │                                                                          │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │   │
│  │  │                    UploadTaskQueue (新增)                         │   │   │
│  │  │  - Redis/内存队列                                                 │   │   │
│  │  │  - Worker 池 (可配置并发数)                                       │   │   │
│  │  │  - 优先级队列                                                     │   │   │
│  │  │  - 死信队列 (失败任务)                                            │   │   │
│  │  │  - 限流器 (令牌桶/漏桶)                                           │   │   │
│  │  └──────────────────────────────────────────────────────────────────┘   │   │
│  │                                      │                                   │   │
│  │                                      ▼                                   │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │   │
│  │  │                    StorageService (现有)                          │   │   │
│  │  │  - 兰空图床上传                                                   │   │   │
│  │  │  - 阿里云 OSS 上传                                                │   │   │
│  │  └──────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 3. 前端队列实现

### 3.1 UploadQueueService 设计

```typescript
// frontend/services/storage/UploadQueueService.ts

interface UploadTask {
  id: string;
  file: File;
  filename: string;
  priority: 'high' | 'normal' | 'low';
  retryCount: number;
  maxRetries: number;
  status: 'pending' | 'uploading' | 'completed' | 'failed';
  createdAt: number;
  onProgress?: (progress: number) => void;
  onComplete?: (url: string) => void;
  onError?: (error: Error) => void;
}

interface QueueConfig {
  maxConcurrent: number;      // 最大并发数，默认 3
  maxRetries: number;         // 最大重试次数，默认 3
  retryDelay: number;         // 重试延迟基数（毫秒），默认 1000
  timeout: number;            // 单个任务超时（毫秒），默认 60000
}

class UploadQueueService {
  private queue: UploadTask[] = [];
  private activeCount = 0;
  private config: QueueConfig;
  private isProcessing = false;

  constructor(config?: Partial<QueueConfig>) {
    this.config = {
      maxConcurrent: 3,
      maxRetries: 3,
      retryDelay: 1000,
      timeout: 60000,
      ...config
    };
  }

  /**
   * 添加上传任务到队列
   */
  enqueue(task: Omit<UploadTask, 'id' | 'retryCount' | 'status' | 'createdAt'>): string {
    const id = crypto.randomUUID();
    const newTask: UploadTask = {
      ...task,
      id,
      retryCount: 0,
      maxRetries: task.maxRetries ?? this.config.maxRetries,
      status: 'pending',
      createdAt: Date.now()
    };

    // 按优先级插入队列
    if (task.priority === 'high') {
      // 高优先级插入到队列前面（但在正在处理的任务之后）
      const insertIndex = this.queue.findIndex(t => t.priority !== 'high');
      if (insertIndex === -1) {
        this.queue.push(newTask);
      } else {
        this.queue.splice(insertIndex, 0, newTask);
      }
    } else {
      this.queue.push(newTask);
    }

    console.log(`[UploadQueue] 任务入队: ${id}, 优先级: ${task.priority}, 队列长度: ${this.queue.length}`);
    
    // 触发队列处理
    this.processQueue();
    
    return id;
  }

  /**
   * 批量添加任务
   */
  enqueueBatch(tasks: Array<Omit<UploadTask, 'id' | 'retryCount' | 'status' | 'createdAt'>>): string[] {
    return tasks.map(task => this.enqueue(task));
  }

  /**
   * 处理队列
   */
  private async processQueue(): Promise<void> {
    if (this.isProcessing) return;
    this.isProcessing = true;

    while (this.queue.length > 0 && this.activeCount < this.config.maxConcurrent) {
      const task = this.queue.find(t => t.status === 'pending');
      if (!task) break;

      task.status = 'uploading';
      this.activeCount++;

      // 异步处理任务，不阻塞队列
      this.processTask(task).finally(() => {
        this.activeCount--;
        this.processQueue();
      });
    }

    this.isProcessing = false;
  }

  /**
   * 处理单个任务
   */
  private async processTask(task: UploadTask): Promise<void> {
    try {
      console.log(`[UploadQueue] 开始上传: ${task.id}, 文件: ${task.filename}`);
      
      const result = await this.uploadWithTimeout(task);
      
      if (result.success && result.url) {
        task.status = 'completed';
        task.onComplete?.(result.url);
        console.log(`[UploadQueue] 上传成功: ${task.id}, URL: ${result.url}`);
        
        // 从队列移除
        this.removeTask(task.id);
      } else {
        throw new Error(result.error || '上传失败');
      }
    } catch (error) {
      await this.handleTaskError(task, error as Error);
    }
  }

  /**
   * 带超时的上传
   */
  private async uploadWithTimeout(task: UploadTask): Promise<{ success: boolean; url?: string; error?: string }> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.config.timeout);

    try {
      const formData = new FormData();
      formData.append('file', task.file);

      const response = await fetch('/api/storage/upload', {
        method: 'POST',
        body: formData,
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        return { success: false, error: error.detail || `HTTP ${response.status}` };
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if ((error as Error).name === 'AbortError') {
        return { success: false, error: '上传超时' };
      }
      return { success: false, error: (error as Error).message };
    }
  }

  /**
   * 处理任务错误（带重试）
   */
  private async handleTaskError(task: UploadTask, error: Error): Promise<void> {
    task.retryCount++;
    console.warn(`[UploadQueue] 上传失败: ${task.id}, 错误: ${error.message}, 重试: ${task.retryCount}/${task.maxRetries}`);

    if (task.retryCount < task.maxRetries) {
      // 指数退避重试
      const delay = this.config.retryDelay * Math.pow(2, task.retryCount - 1);
      console.log(`[UploadQueue] ${delay}ms 后重试...`);
      
      await new Promise(resolve => setTimeout(resolve, delay));
      
      task.status = 'pending';
      // 重新加入队列处理
    } else {
      task.status = 'failed';
      task.onError?.(error);
      console.error(`[UploadQueue] 任务最终失败: ${task.id}`);
      
      // 从队列移除
      this.removeTask(task.id);
    }
  }

  /**
   * 从队列移除任务
   */
  private removeTask(taskId: string): void {
    const index = this.queue.findIndex(t => t.id === taskId);
    if (index !== -1) {
      this.queue.splice(index, 1);
    }
  }

  /**
   * 获取队列状态
   */
  getStatus(): {
    queueLength: number;
    activeCount: number;
    pendingCount: number;
    completedCount: number;
    failedCount: number;
  } {
    return {
      queueLength: this.queue.length,
      activeCount: this.activeCount,
      pendingCount: this.queue.filter(t => t.status === 'pending').length,
      completedCount: this.queue.filter(t => t.status === 'completed').length,
      failedCount: this.queue.filter(t => t.status === 'failed').length
    };
  }

  /**
   * 取消任务
   */
  cancel(taskId: string): boolean {
    const task = this.queue.find(t => t.id === taskId);
    if (task && task.status === 'pending') {
      this.removeTask(taskId);
      return true;
    }
    return false;
  }

  /**
   * 清空队列
   */
  clear(): void {
    this.queue = this.queue.filter(t => t.status === 'uploading');
  }
}

// 导出单例
export const uploadQueue = new UploadQueueService();
```


### 3.2 前端调用示例

```typescript
// frontend/hooks/handlers/imageGenHandler.ts 修改

import { uploadQueue } from '../../services/storage/UploadQueueService';

export const handleImageGen = async (
  text: string,
  attachments: Attachment[],
  _context: HandlerContext
): Promise<ImageGenResult> => {
  // ... 生成图片逻辑 ...

  // 使用队列批量上传
  const uploadPromises = processedResults.map((r, index) => {
    return new Promise<string>((resolve, reject) => {
      uploadQueue.enqueue({
        file: r.uploadSource instanceof File ? r.uploadSource : new File([r.uploadSource], r.filename),
        filename: r.filename,
        priority: index === 0 ? 'high' : 'normal',  // 第一张高优先级
        maxRetries: 3,
        onComplete: (url) => resolve(url),
        onError: (error) => reject(error)
      });
    });
  });

  // 等待所有上传完成
  const cloudUrls = await Promise.allSettled(uploadPromises);
  
  // ... 处理结果 ...
};
```

## 4. 后端队列实现

### 4.1 方案选择

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 内存队列 | 简单、无依赖 | 重启丢失、单机限制 | 小规模、开发环境 |
| Redis 队列 | 持久化、分布式 | 需要 Redis | 生产环境 |
| Celery | 功能完善、生态好 | 复杂、重量级 | 大规模任务 |
| asyncio.Queue | 轻量、原生支持 | 单进程限制 | 中小规模 |

**推荐方案**：`asyncio.Queue` + `Redis`（可选持久化）

### 4.2 后端队列服务实现

```python
# backend/app/services/upload_queue_service.py

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    HIGH = 0
    NORMAL = 1
    LOW = 2


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class UploadTask:
    """上传任务"""
    id: str
    filename: str
    content: bytes
    content_type: str
    storage_id: Optional[str] = None
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    attachment_id: Optional[str] = None
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result_url: Optional[str] = None
    error_message: Optional[str] = None

    def __lt__(self, other):
        """优先级比较，用于优先队列"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.created_at < other.created_at


class UploadQueueService:
    """
    高并发上传队列服务
    
    特性：
    - 优先级队列
    - 可配置并发数
    - 自动重试（指数退避）
    - 限流保护
    - 任务状态追踪
    """
    
    def __init__(
        self,
        max_workers: int = 5,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limit: int = 10,  # 每秒最大请求数
        rate_window: float = 1.0
    ):
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit = rate_limit
        self.rate_window = rate_window
        
        # 优先队列
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        
        # 任务存储（用于状态查询）
        self._tasks: Dict[str, UploadTask] = {}
        
        # Worker 控制
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        # 限流器
        self._rate_tokens = rate_limit
        self._last_refill = datetime.now().timestamp()
        self._rate_lock = asyncio.Lock()
        
        # 回调
        self._on_complete: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
    
    async def start(self):
        """启动队列服务"""
        if self._running:
            return
        
        self._running = True
        self._semaphore = asyncio.Semaphore(self.max_workers)
        
        # 启动 Worker
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        
        logger.info(f"[UploadQueue] 队列服务已启动，Worker 数量: {self.max_workers}")
    
    async def stop(self):
        """停止队列服务"""
        self._running = False
        
        # 取消所有 Worker
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        
        logger.info("[UploadQueue] 队列服务已停止")
    
    async def enqueue(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        storage_id: Optional[str] = None,
        session_id: Optional[str] = None,
        message_id: Optional[str] = None,
        attachment_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> str:
        """
        添加上传任务到队列
        
        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())
        task = UploadTask(
            id=task_id,
            filename=filename,
            content=content,
            content_type=content_type,
            storage_id=storage_id,
            session_id=session_id,
            message_id=message_id,
            attachment_id=attachment_id,
            priority=priority,
            max_retries=self.max_retries
        )
        
        self._tasks[task_id] = task
        await self._queue.put((task.priority.value, task.created_at, task))
        
        logger.info(f"[UploadQueue] 任务入队: {task_id}, 优先级: {priority.name}, 队列大小: {self._queue.qsize()}")
        
        return task_id
    
    async def _worker(self, worker_id: int):
        """Worker 协程"""
        logger.info(f"[UploadQueue] Worker-{worker_id} 已启动")
        
        while self._running:
            try:
                # 从队列获取任务
                _, _, task = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                
                # 限流
                await self._acquire_rate_token()
                
                # 处理任务
                async with self._semaphore:
                    await self._process_task(task, worker_id)
                
                self._queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[UploadQueue] Worker-{worker_id} 异常: {e}")
        
        logger.info(f"[UploadQueue] Worker-{worker_id} 已停止")
    
    async def _process_task(self, task: UploadTask, worker_id: int):
        """处理单个任务"""
        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.now().timestamp()
        
        logger.info(f"[UploadQueue] Worker-{worker_id} 处理任务: {task.id}, 文件: {task.filename}")
        
        try:
            # 调用实际上传逻辑
            from .storage_service import StorageService
            from ..core.database import SessionLocal
            from ..models.db_models import StorageConfig, ActiveStorage
            
            db = SessionLocal()
            try:
                # 获取存储配置
                if task.storage_id:
                    config = db.query(StorageConfig).filter(StorageConfig.id == task.storage_id).first()
                else:
                    active = db.query(ActiveStorage).filter(ActiveStorage.user_id == "default").first()
                    if active and active.storage_id:
                        config = db.query(StorageConfig).filter(StorageConfig.id == active.storage_id).first()
                    else:
                        raise Exception("未设置存储配置")
                
                if not config or not config.enabled:
                    raise Exception("存储配置不可用")
                
                # 执行上传
                result = await StorageService.upload_file(
                    filename=task.filename,
                    content=task.content,
                    content_type=task.content_type,
                    provider=config.provider,
                    config=config.config
                )
                
                if result.get('success'):
                    task.status = TaskStatus.COMPLETED
                    task.result_url = result.get('url')
                    task.completed_at = datetime.now().timestamp()
                    
                    logger.info(f"[UploadQueue] 任务完成: {task.id}, URL: {task.result_url}")
                    
                    # 回调
                    if self._on_complete:
                        await self._on_complete(task)
                else:
                    raise Exception(result.get('error', '上传失败'))
                    
            finally:
                db.close()
                
        except Exception as e:
            await self._handle_task_error(task, e, worker_id)
    
    async def _handle_task_error(self, task: UploadTask, error: Exception, worker_id: int):
        """处理任务错误"""
        task.retry_count += 1
        task.error_message = str(error)
        
        logger.warning(
            f"[UploadQueue] Worker-{worker_id} 任务失败: {task.id}, "
            f"错误: {error}, 重试: {task.retry_count}/{task.max_retries}"
        )
        
        if task.retry_count < task.max_retries:
            # 指数退避重试
            delay = self.retry_delay * (2 ** (task.retry_count - 1))
            logger.info(f"[UploadQueue] {delay}s 后重试任务: {task.id}")
            
            await asyncio.sleep(delay)
            
            task.status = TaskStatus.PENDING
            await self._queue.put((task.priority.value, task.created_at, task))
        else:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now().timestamp()
            
            logger.error(f"[UploadQueue] 任务最终失败: {task.id}")
            
            # 回调
            if self._on_error:
                await self._on_error(task)
    
    async def _acquire_rate_token(self):
        """获取限流令牌（令牌桶算法）"""
        async with self._rate_lock:
            now = datetime.now().timestamp()
            elapsed = now - self._last_refill
            
            # 补充令牌
            self._rate_tokens = min(
                self.rate_limit,
                self._rate_tokens + elapsed * (self.rate_limit / self.rate_window)
            )
            self._last_refill = now
            
            if self._rate_tokens < 1:
                # 等待令牌
                wait_time = (1 - self._rate_tokens) * (self.rate_window / self.rate_limit)
                await asyncio.sleep(wait_time)
                self._rate_tokens = 0
            else:
                self._rate_tokens -= 1
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        return {
            "id": task.id,
            "filename": task.filename,
            "status": task.status.value,
            "priority": task.priority.name,
            "retry_count": task.retry_count,
            "result_url": task.result_url,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at
        }
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        status_counts = {}
        for task in self._tasks.values():
            status = task.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "queue_size": self._queue.qsize(),
            "total_tasks": len(self._tasks),
            "active_workers": self.max_workers - self._semaphore._value if self._semaphore else 0,
            "status_counts": status_counts
        }
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            return True
        return False
    
    def set_callbacks(
        self,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None
    ):
        """设置回调函数"""
        self._on_complete = on_complete
        self._on_error = on_error


# 全局单例
upload_queue_service = UploadQueueService()
```


### 4.3 后端路由集成

```python
# backend/app/routers/storage.py 新增接口

from ..services.upload_queue_service import upload_queue_service, TaskPriority

@router.on_event("startup")
async def startup_event():
    """应用启动时启动队列服务"""
    await upload_queue_service.start()

@router.on_event("shutdown")
async def shutdown_event():
    """应用关闭时停止队列服务"""
    await upload_queue_service.stop()


@router.post("/upload-queue")
async def upload_to_queue(
    file: UploadFile = File(...),
    priority: str = "normal",
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    attachment_id: Optional[str] = None,
    storage_id: Optional[str] = None
):
    """
    将上传任务加入队列
    
    参数：
    - file: 要上传的文件
    - priority: 优先级 (high/normal/low)
    - session_id: 会话 ID
    - message_id: 消息 ID
    - attachment_id: 附件 ID
    - storage_id: 存储配置 ID
    
    返回：
    {
        "task_id": "xxx",
        "status": "pending",
        "queue_position": 5
    }
    """
    # 读取文件内容
    content = await file.read()
    
    # 解析优先级
    priority_map = {
        "high": TaskPriority.HIGH,
        "normal": TaskPriority.NORMAL,
        "low": TaskPriority.LOW
    }
    task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
    
    # 加入队列
    task_id = await upload_queue_service.enqueue(
        filename=file.filename,
        content=content,
        content_type=file.content_type,
        storage_id=storage_id,
        session_id=session_id,
        message_id=message_id,
        attachment_id=attachment_id,
        priority=task_priority
    )
    
    stats = upload_queue_service.get_queue_stats()
    
    return {
        "task_id": task_id,
        "status": "pending",
        "queue_position": stats["queue_size"]
    }


@router.get("/upload-queue/status/{task_id}")
async def get_queue_task_status(task_id: str):
    """获取队列任务状态"""
    status = upload_queue_service.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    return status


@router.get("/upload-queue/stats")
async def get_queue_stats():
    """获取队列统计信息"""
    return upload_queue_service.get_queue_stats()


@router.post("/upload-queue/cancel/{task_id}")
async def cancel_queue_task(task_id: str):
    """取消队列任务"""
    success = await upload_queue_service.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="无法取消任务（可能已在处理中）")
    return {"success": True}


@router.post("/upload-queue/batch")
async def upload_batch_to_queue(
    files: List[UploadFile] = File(...),
    priority: str = "normal",
    session_id: Optional[str] = None
):
    """
    批量上传到队列
    
    返回：
    {
        "task_ids": ["xxx", "yyy", ...],
        "total": 5,
        "queue_size": 10
    }
    """
    priority_map = {
        "high": TaskPriority.HIGH,
        "normal": TaskPriority.NORMAL,
        "low": TaskPriority.LOW
    }
    task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
    
    task_ids = []
    for i, file in enumerate(files):
        content = await file.read()
        
        # 第一个文件高优先级
        file_priority = TaskPriority.HIGH if i == 0 and priority == "normal" else task_priority
        
        task_id = await upload_queue_service.enqueue(
            filename=file.filename,
            content=content,
            content_type=file.content_type,
            session_id=session_id,
            priority=file_priority
        )
        task_ids.append(task_id)
    
    stats = upload_queue_service.get_queue_stats()
    
    return {
        "task_ids": task_ids,
        "total": len(task_ids),
        "queue_size": stats["queue_size"]
    }
```

## 5. Redis 持久化方案（可选）

### 5.1 Redis 队列实现

```python
# backend/app/services/redis_upload_queue.py

import redis.asyncio as redis
import json
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio

class RedisUploadQueue:
    """
    基于 Redis 的持久化上传队列
    
    特性：
    - 任务持久化，重启不丢失
    - 分布式支持，多实例部署
    - 死信队列，失败任务隔离
    """
    
    QUEUE_KEY = "upload:queue"
    PRIORITY_QUEUES = {
        "high": "upload:queue:high",
        "normal": "upload:queue:normal",
        "low": "upload:queue:low"
    }
    TASK_KEY_PREFIX = "upload:task:"
    DEAD_LETTER_KEY = "upload:dead_letter"
    STATS_KEY = "upload:stats"
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._running = False
        self._workers = []
    
    async def connect(self):
        """连接 Redis"""
        self._redis = await redis.from_url(self.redis_url, decode_responses=True)
    
    async def disconnect(self):
        """断开连接"""
        if self._redis:
            await self._redis.close()
    
    async def enqueue(
        self,
        task_id: str,
        filename: str,
        content_base64: str,  # Redis 存储 Base64 编码
        content_type: str,
        priority: str = "normal",
        **kwargs
    ) -> str:
        """添加任务到队列"""
        task_data = {
            "id": task_id,
            "filename": filename,
            "content_base64": content_base64,
            "content_type": content_type,
            "priority": priority,
            "status": "pending",
            "retry_count": 0,
            "created_at": datetime.now().isoformat(),
            **kwargs
        }
        
        # 存储任务详情
        await self._redis.set(
            f"{self.TASK_KEY_PREFIX}{task_id}",
            json.dumps(task_data),
            ex=86400 * 7  # 7 天过期
        )
        
        # 加入优先级队列
        queue_key = self.PRIORITY_QUEUES.get(priority, self.PRIORITY_QUEUES["normal"])
        await self._redis.lpush(queue_key, task_id)
        
        # 更新统计
        await self._redis.hincrby(self.STATS_KEY, "total_enqueued", 1)
        
        return task_id
    
    async def dequeue(self) -> Optional[Dict[str, Any]]:
        """
        从队列获取任务（按优先级）
        使用 BRPOP 阻塞等待
        """
        # 按优先级顺序尝试获取
        result = await self._redis.brpop(
            [
                self.PRIORITY_QUEUES["high"],
                self.PRIORITY_QUEUES["normal"],
                self.PRIORITY_QUEUES["low"]
            ],
            timeout=1
        )
        
        if not result:
            return None
        
        _, task_id = result
        task_data = await self._redis.get(f"{self.TASK_KEY_PREFIX}{task_id}")
        
        if task_data:
            return json.loads(task_data)
        return None
    
    async def update_task(self, task_id: str, updates: Dict[str, Any]):
        """更新任务状态"""
        task_data = await self._redis.get(f"{self.TASK_KEY_PREFIX}{task_id}")
        if task_data:
            task = json.loads(task_data)
            task.update(updates)
            await self._redis.set(
                f"{self.TASK_KEY_PREFIX}{task_id}",
                json.dumps(task),
                ex=86400 * 7
            )
    
    async def move_to_dead_letter(self, task_id: str):
        """移动到死信队列"""
        await self._redis.lpush(self.DEAD_LETTER_KEY, task_id)
        await self._redis.hincrby(self.STATS_KEY, "dead_letter_count", 1)
    
    async def retry_dead_letter(self, task_id: str) -> bool:
        """重试死信队列中的任务"""
        # 从死信队列移除
        removed = await self._redis.lrem(self.DEAD_LETTER_KEY, 1, task_id)
        if removed:
            # 重置重试计数
            await self.update_task(task_id, {"retry_count": 0, "status": "pending"})
            # 重新入队
            await self._redis.lpush(self.PRIORITY_QUEUES["low"], task_id)
            return True
        return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = await self._redis.hgetall(self.STATS_KEY)
        
        # 获取各队列长度
        queue_lengths = {}
        for name, key in self.PRIORITY_QUEUES.items():
            queue_lengths[name] = await self._redis.llen(key)
        
        dead_letter_count = await self._redis.llen(self.DEAD_LETTER_KEY)
        
        return {
            **stats,
            "queue_lengths": queue_lengths,
            "dead_letter_count": dead_letter_count
        }
```

## 6. 限流策略

### 6.1 令牌桶算法

```python
# backend/app/services/rate_limiter.py

import asyncio
from datetime import datetime
from typing import Optional

class TokenBucketRateLimiter:
    """
    令牌桶限流器
    
    特性：
    - 平滑限流
    - 支持突发流量
    - 异步友好
    """
    
    def __init__(
        self,
        rate: float,           # 每秒生成令牌数
        capacity: int,         # 桶容量
        initial_tokens: Optional[int] = None
    ):
        self.rate = rate
        self.capacity = capacity
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.last_refill = datetime.now().timestamp()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        获取令牌
        
        Returns:
            是否成功获取
        """
        async with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    async def wait_and_acquire(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """
        等待并获取令牌
        
        Args:
            tokens: 需要的令牌数
            timeout: 最大等待时间（秒）
        
        Returns:
            是否成功获取
        """
        start_time = datetime.now().timestamp()
        
        while True:
            if await self.acquire(tokens):
                return True
            
            elapsed = datetime.now().timestamp() - start_time
            if elapsed >= timeout:
                return False
            
            # 计算需要等待的时间
            async with self._lock:
                self._refill()
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate
            
            await asyncio.sleep(min(wait_time, timeout - elapsed))
    
    def _refill(self):
        """补充令牌"""
        now = datetime.now().timestamp()
        elapsed = now - self.last_refill
        
        new_tokens = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now
    
    @property
    def available_tokens(self) -> float:
        """当前可用令牌数"""
        self._refill()
        return self.tokens


class SlidingWindowRateLimiter:
    """
    滑动窗口限流器
    
    特性：
    - 精确限流
    - 防止边界突发
    """
    
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """尝试获取许可"""
        async with self._lock:
            now = datetime.now().timestamp()
            
            # 清理过期请求
            self.requests = [t for t in self.requests if now - t < self.window_seconds]
            
            if len(self.requests) < self.limit:
                self.requests.append(now)
                return True
            return False
    
    async def wait_and_acquire(self, timeout: float = 30.0) -> bool:
        """等待并获取许可"""
        start_time = datetime.now().timestamp()
        
        while True:
            if await self.acquire():
                return True
            
            elapsed = datetime.now().timestamp() - start_time
            if elapsed >= timeout:
                return False
            
            # 等待最早的请求过期
            async with self._lock:
                if self.requests:
                    wait_time = self.requests[0] + self.window_seconds - datetime.now().timestamp()
                    if wait_time > 0:
                        await asyncio.sleep(min(wait_time, timeout - elapsed))
                else:
                    await asyncio.sleep(0.1)
```


## 7. 完整流程图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           高并发队列上传完整流程                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  用户操作                                                                       │
│     │                                                                           │
│     ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  1. 前端 Handler 层                                                      │   │
│  │     - 生成图片/处理附件                                                  │   │
│  │     - 构建上传任务                                                       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│     │                                                                           │
│     ▼                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  2. 前端 UploadQueueService                                              │   │
│  │     ┌─────────────────────────────────────────────────────────────┐     │   │
│  │     │  优先级队列                                                  │     │   │
│  │     │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                   │     │   │
│  │     │  │ H1  │ │ H2  │ │ N1  │ │ N2  │ │ L1  │  ...              │     │   │
│  │     │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘                   │     │   │
│  │     │  高优先级 ◀────────────────────────────▶ 低优先级           │     │   │
│  │     └─────────────────────────────────────────────────────────────┘     │   │
│  │                                                                          │   │
│  │     并发控制: maxConcurrent = 3                                          │   │
│  │     ┌─────────┐ ┌─────────┐ ┌─────────┐                                 │   │
│  │     │ Worker1 │ │ Worker2 │ │ Worker3 │  ← 同时最多 3 个请求            │   │
│  │     └────┬────┘ └────┬────┘ └────┬────┘                                 │   │
│  └──────────│───────────│───────────│──────────────────────────────────────┘   │
│             │           │           │                                           │
│             └───────────┼───────────┘                                           │
│                         │ HTTP POST /api/storage/upload-queue                   │
│                         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  3. 后端 API 层                                                          │   │
│  │     - 接收文件                                                           │   │
│  │     - 验证参数                                                           │   │
│  │     - 加入后端队列                                                       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                         │                                                       │
│                         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  4. 后端 UploadQueueService                                              │   │
│  │     ┌─────────────────────────────────────────────────────────────┐     │   │
│  │     │  asyncio.PriorityQueue (或 Redis)                           │     │   │
│  │     │                                                              │     │   │
│  │     │  ┌──────────────────────────────────────────────────────┐   │     │   │
│  │     │  │  限流器 (TokenBucket)                                 │   │     │   │
│  │     │  │  rate = 10/s, capacity = 20                          │   │     │   │
│  │     │  └──────────────────────────────────────────────────────┘   │     │   │
│  │     │                                                              │     │   │
│  │     │  Worker 池: maxWorkers = 5                                  │     │   │
│  │     │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐                        │     │   │
│  │     │  │ W1 │ │ W2 │ │ W3 │ │ W4 │ │ W5 │                        │     │   │
│  │     │  └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘                        │     │   │
│  │     └─────│──────│──────│──────│──────│───────────────────────────┘     │   │
│  └───────────│──────│──────│──────│──────│─────────────────────────────────┘   │
│              │      │      │      │      │                                      │
│              └──────┴──────┼──────┴──────┘                                      │
│                            │                                                    │
│                            ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  5. StorageService                                                       │   │
│  │     - upload_to_lsky()                                                   │   │
│  │     - upload_to_aliyun_oss()                                             │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                            │                                                    │
│                            ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  6. 云存储                                                               │   │
│  │     - 兰空图床 API                                                       │   │
│  │     - 阿里云 OSS SDK                                                     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                            │                                                    │
│                            ▼                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  7. 结果处理                                                             │   │
│  │     ┌─────────────────┐    ┌─────────────────┐                          │   │
│  │     │  成功            │    │  失败            │                          │   │
│  │     │  - 更新任务状态  │    │  - 重试 (指数退避)│                          │   │
│  │     │  - 回调通知      │    │  - 超过重试次数   │                          │   │
│  │     │  - 更新数据库    │    │    → 死信队列    │                          │   │
│  │     └─────────────────┘    └─────────────────┘                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 8. 配置参数建议

### 8.1 前端配置

```typescript
// 推荐配置
const uploadQueueConfig = {
  maxConcurrent: 3,      // 最大并发数（避免浏览器连接数限制）
  maxRetries: 3,         // 最大重试次数
  retryDelay: 1000,      // 重试延迟基数（毫秒）
  timeout: 60000         // 单个任务超时（毫秒）
};
```

### 8.2 后端配置

```python
# 推荐配置
UPLOAD_QUEUE_CONFIG = {
    "max_workers": 5,        # Worker 数量（根据 CPU 核心数调整）
    "max_retries": 3,        # 最大重试次数
    "retry_delay": 1.0,      # 重试延迟基数（秒）
    "rate_limit": 10,        # 每秒最大请求数（根据云存储 API 限制调整）
    "rate_window": 1.0       # 限流窗口（秒）
}

# 兰空图床限流建议
LSKY_RATE_LIMIT = 5  # 每秒 5 个请求（保守估计）

# 阿里云 OSS 限流建议
ALIYUN_OSS_RATE_LIMIT = 100  # 每秒 100 个请求（根据账户配额调整）
```

## 9. 监控与告警

### 9.1 监控指标

```python
# backend/app/services/upload_metrics.py

from prometheus_client import Counter, Gauge, Histogram

# 计数器
upload_total = Counter(
    'upload_total',
    '上传任务总数',
    ['status', 'provider']
)

# 仪表盘
queue_size = Gauge(
    'upload_queue_size',
    '队列大小',
    ['priority']
)

active_workers = Gauge(
    'upload_active_workers',
    '活跃 Worker 数'
)

# 直方图
upload_duration = Histogram(
    'upload_duration_seconds',
    '上传耗时',
    ['provider'],
    buckets=[0.5, 1, 2, 5, 10, 30, 60]
)
```

### 9.2 告警规则

```yaml
# prometheus/alerts.yml

groups:
  - name: upload_queue
    rules:
      - alert: UploadQueueBacklog
        expr: upload_queue_size > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "上传队列积压"
          description: "队列大小超过 100，当前: {{ $value }}"
      
      - alert: UploadFailureRate
        expr: rate(upload_total{status="failed"}[5m]) / rate(upload_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "上传失败率过高"
          description: "失败率超过 10%，当前: {{ $value | humanizePercentage }}"
      
      - alert: DeadLetterQueueGrowing
        expr: upload_dead_letter_count > 50
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "死信队列增长"
          description: "死信队列任务数: {{ $value }}"
```

## 10. 实施步骤

### 10.1 第一阶段：前端队列优化

1. 创建 `UploadQueueService.ts`
2. 修改 `imageGenHandler.ts` 等 Handler 使用队列
3. 添加上传状态 UI 反馈
4. 测试并发上传场景

### 10.2 第二阶段：后端队列实现

1. 创建 `upload_queue_service.py`
2. 添加新的 API 接口
3. 集成限流器
4. 添加任务状态查询接口

### 10.3 第三阶段：持久化与监控

1. （可选）集成 Redis 持久化
2. 添加 Prometheus 监控指标
3. 配置告警规则
4. 添加管理后台界面

## 11. 总结

### 11.1 方案优势

| 特性 | 说明 |
|------|------|
| 并发控制 | 前端 3 并发 + 后端 5 Worker，避免资源耗尽 |
| 优先级队列 | 支持高/中/低优先级，重要任务优先处理 |
| 自动重试 | 指数退避策略，避免雪崩 |
| 限流保护 | 令牌桶算法，保护云存储 API |
| 状态追踪 | 完整的任务生命周期管理 |
| 可扩展性 | 支持 Redis 持久化，可水平扩展 |

### 11.2 性能预估

```
场景：批量生成 10 张图片

当前方案（无队列）：
- 10 个并发请求同时发起
- 后端检测竞态，部分超时
- 预计成功率：70%
- 总耗时：不确定（可能失败）

新方案（队列）：
- 前端队列：3 并发，分批发送
- 后端队列：5 Worker，限流 10/s
- 预计成功率：99%+
- 总耗时：约 10-15 秒（稳定可控）
```
