# 基于现有接口的队列优化方案

## 1. 现有接口清单

当前后端已有以下上传相关接口（`backend/app/routers/storage.py`）：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/storage/upload` | `POST` | 同步上传 |
| `/api/storage/upload-async` | `POST` | 异步上传（`BackgroundTasks`） |
| `/api/storage/upload-from-url` | `POST` | 从 `URL` 下载后异步上传 |
| `/api/storage/upload-status/{task_id}` | `GET` | 查询任务状态 |
| `/api/storage/retry-upload/{task_id}` | `POST` | 重试失败任务 |

## 2. 现有实现的问题

```
当前流程：
┌─────────────────────────────────────────────────────────────────┐
│  前端调用 /api/storage/upload-async                             │
│       │                                                          │
│       ▼                                                          │
│  BackgroundTasks.add_task(process_upload_task, task_id)         │
│       │                                                          │
│       ▼                                                          │
│  ❌ 立即执行，无并发控制                                         │
│  ❌ 无限流保护                                                   │
│  ❌ 无自动重试                                                   │
│  ❌ 无优先级                                                     │
│  ❌ 服务重启任务丢失                                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 具体问题场景

根据日志 `.kiro/specs/erron/log.md`：

```
3 张图片同时上传：
- 图片 1: 成功
- 图片 2: TimeoutError: signal timed out
- 图片 3: 成功

原因：并发请求过多，后端检测超时
```

## 3. 优化方案：增强现有接口


### 3.1 架构设计

```
优化后流程：
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  前端调用 /api/storage/upload-async                                             │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  API 层（保持不变）                                                      │   │
│  │  - 接收文件                                                              │   │
│  │  - 保存到临时目录                                                        │   │
│  │  - 创建 UploadTask 记录                                                  │   │
│  │  - 返回 task_id                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                          │
│       │ 不再使用 BackgroundTasks.add_task()                                     │
│       │ 改为：任务入队，由 Worker 池处理                                        │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  UploadQueueManager（新增）                                              │   │
│  │                                                                          │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │   │
│  │  │  数据库队列（复用 upload_tasks 表）                               │   │   │
│  │  │  - status = 'pending' 的任务                                      │   │   │
│  │  │  - 按 priority + created_at 排序                                  │   │   │
│  │  └──────────────────────────────────────────────────────────────────┘   │   │
│  │                                                                          │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │   │
│  │  │  Worker 池（asyncio 协程）                                        │   │   │
│  │  │  - max_workers = 5                                                │   │   │
│  │  │  - 轮询数据库获取任务                                             │   │   │
│  │  └──────────────────────────────────────────────────────────────────┘   │   │
│  │                                                                          │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │   │
│  │  │  限流器（令牌桶）                                                 │   │   │
│  │  │  - rate = 10/s                                                    │   │   │
│  │  └──────────────────────────────────────────────────────────────────┘   │   │
│  │                                                                          │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │   │
│  │  │  自动重试（指数退避）                                             │   │   │
│  │  │  - max_retries = 3                                                │   │   │
│  │  │  - delay = 2^n 秒                                                 │   │   │
│  │  └──────────────────────────────────────────────────────────────────┘   │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                          │
│       ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  StorageService（保持不变）                                              │   │
│  │  - upload_to_lsky()                                                      │   │
│  │  - upload_to_aliyun_oss()                                                │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 数据库表修改

在现有 `UploadTask` 模型基础上增加字段：

```python
# backend/app/models/db_models.py 修改

class UploadTask(Base):
    __tablename__ = "upload_tasks"
    
    # 现有字段（保持不变）
    id = Column(String(36), primary_key=True)
    session_id = Column(String(36))
    message_id = Column(String(36))
    attachment_id = Column(String(36))
    source_url = Column(String(500))
    source_file_path = Column(String(500))
    filename = Column(String(255))
    storage_id = Column(String(36))
    status = Column(String(20))  # pending, uploading, completed, failed
    target_url = Column(String(500))
    error_message = Column(Text)
    created_at = Column(BigInteger)
    completed_at = Column(BigInteger)
    
    # ========== 新增字段 ==========
    priority = Column(String(10), default='normal', index=True)  # high, normal, low
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(BigInteger)  # 下次重试时间戳
    started_at = Column(BigInteger)     # 开始处理时间
    file_size = Column(Integer)         # 文件大小（字节）
```

### 3.3 队列管理器实现

```python
# backend/app/services/upload_queue_manager.py（新增文件）

import asyncio
import os
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging

from ..core.database import SessionLocal
from ..models.db_models import UploadTask, StorageConfig, ActiveStorage, ChatSession
from .storage_service import StorageService

logger = logging.getLogger(__name__)


class UploadQueueManager:
    """
    上传队列管理器
    
    基于现有 UploadTask 表实现队列功能
    """
    
    def __init__(
        self,
        max_workers: int = 5,
        max_retries: int = 3,
        base_retry_delay: float = 2.0,
        rate_limit: float = 10.0,
        poll_interval: float = 1.0
    ):
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.rate_limit = rate_limit
        self.poll_interval = poll_interval
        
        self._running = False
        self._workers: List[asyncio.Task] = []
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        # 限流
        self._rate_tokens = rate_limit
        self._last_refill = datetime.now().timestamp()
        self._rate_lock = asyncio.Lock()
    
    async def start(self):
        """启动队列管理器"""
        if self._running:
            return
        
        self._running = True
        self._semaphore = asyncio.Semaphore(self.max_workers)
        
        # 恢复中断的任务
        await self._recover_tasks()
        
        # 启动 Worker
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        
        logger.info(f"[UploadQueue] 已启动，Workers: {self.max_workers}, 限流: {self.rate_limit}/s")
    
    async def stop(self):
        """停止队列管理器"""
        self._running = False
        
        for worker in self._workers:
            worker.cancel()
        
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._workers.clear()
        logger.info("[UploadQueue] 已停止")
    
    async def _recover_tasks(self):
        """恢复中断的任务（服务重启后）"""
        db = SessionLocal()
        try:
            # 将 uploading 状态重置为 pending
            tasks = db.query(UploadTask).filter(
                UploadTask.status == 'uploading'
            ).all()
            
            for task in tasks:
                task.status = 'pending'
                task.started_at = None
            
            db.commit()
            
            if tasks:
                logger.info(f"[UploadQueue] 恢复 {len(tasks)} 个中断任务")
        finally:
            db.close()
    
    async def _worker_loop(self, worker_id: int):
        """Worker 主循环"""
        logger.info(f"[UploadQueue] Worker-{worker_id} 启动")
        
        while self._running:
            try:
                task = await self._fetch_next_task()
                
                if task is None:
                    await asyncio.sleep(self.poll_interval)
                    continue
                
                # 限流
                await self._acquire_rate_token()
                
                # 处理任务
                async with self._semaphore:
                    await self._process_task(task, worker_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[UploadQueue] Worker-{worker_id} 异常: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"[UploadQueue] Worker-{worker_id} 停止")
    
    async def _fetch_next_task(self) -> Optional[UploadTask]:
        """获取下一个待处理任务"""
        db = SessionLocal()
        try:
            now = int(datetime.now().timestamp() * 1000)
            
            # 查询待处理任务
            # 优先级：high > normal > low
            # 同优先级按创建时间排序
            task = db.query(UploadTask).filter(
                and_(
                    UploadTask.status == 'pending',
                    or_(
                        UploadTask.next_retry_at.is_(None),
                        UploadTask.next_retry_at <= now
                    )
                )
            ).order_by(
                # priority 排序：high=1, normal=2, low=3
                UploadTask.priority,
                UploadTask.created_at
            ).first()
            
            if task:
                task.status = 'uploading'
                task.started_at = now
                db.commit()
                db.refresh(task)
                return task
            
            return None
        finally:
            db.close()
    
    async def _process_task(self, task: UploadTask, worker_id: int):
        """处理单个任务"""
        logger.info(f"[UploadQueue] Worker-{worker_id} 处理: {task.id[:8]}..., 文件: {task.filename}")
        
        db = SessionLocal()
        try:
            # 读取文件
            if task.source_file_path and os.path.exists(task.source_file_path):
                with open(task.source_file_path, 'rb') as f:
                    content = f.read()
            elif task.source_url:
                import httpx
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(task.source_url)
                    response.raise_for_status()
                    content = response.content
            else:
                raise Exception("无可用的文件来源")
            
            # 获取存储配置
            config = await self._get_storage_config(db, task.storage_id)
            if not config:
                raise Exception("存储配置不可用")
            
            # 上传
            result = await StorageService.upload_file(
                filename=task.filename,
                content=content,
                content_type='image/png',
                provider=config.provider,
                config=config.config
            )
            
            if result.get('success'):
                await self._handle_success(db, task, result.get('url'), worker_id)
            else:
                raise Exception(result.get('error', '上传失败'))
                
        except Exception as e:
            await self._handle_failure(db, task, str(e), worker_id)
        finally:
            db.close()
    
    async def _handle_success(self, db: Session, task: UploadTask, url: str, worker_id: int):
        """处理成功"""
        now = int(datetime.now().timestamp() * 1000)
        
        # 更新任务
        db_task = db.query(UploadTask).filter(UploadTask.id == task.id).first()
        if db_task:
            db_task.status = 'completed'
            db_task.target_url = url
            db_task.completed_at = now
            db.commit()
        
        # 删除临时文件
        if task.source_file_path and os.path.exists(task.source_file_path):
            try:
                os.remove(task.source_file_path)
            except:
                pass
        
        # 更新会话附件
        if task.session_id and task.message_id and task.attachment_id:
            await self._update_session_attachment(
                db, task.session_id, task.message_id, task.attachment_id, url
            )
        
        logger.info(f"[UploadQueue] Worker-{worker_id} 完成: {task.id[:8]}..., URL: {url[:50]}...")
    
    async def _handle_failure(self, db: Session, task: UploadTask, error: str, worker_id: int):
        """处理失败"""
        db_task = db.query(UploadTask).filter(UploadTask.id == task.id).first()
        if not db_task:
            return
        
        db_task.retry_count = (db_task.retry_count or 0) + 1
        db_task.error_message = error
        
        logger.warning(
            f"[UploadQueue] Worker-{worker_id} 失败: {task.id[:8]}..., "
            f"错误: {error}, 重试: {db_task.retry_count}/{self.max_retries}"
        )
        
        if db_task.retry_count < self.max_retries:
            # 指数退避重试
            delay = self.base_retry_delay * (2 ** (db_task.retry_count - 1))
            next_retry = int((datetime.now().timestamp() + delay) * 1000)
            
            db_task.status = 'pending'
            db_task.next_retry_at = next_retry
            db_task.started_at = None
            
            logger.info(f"[UploadQueue] 任务 {task.id[:8]}... 将在 {delay}s 后重试")
        else:
            db_task.status = 'failed'
            db_task.completed_at = int(datetime.now().timestamp() * 1000)
            logger.error(f"[UploadQueue] 任务 {task.id[:8]}... 最终失败")
        
        db.commit()
    
    async def _get_storage_config(self, db: Session, storage_id: Optional[str]):
        """获取存储配置"""
        if storage_id:
            config = db.query(StorageConfig).filter(StorageConfig.id == storage_id).first()
        else:
            active = db.query(ActiveStorage).filter(ActiveStorage.user_id == "default").first()
            if active and active.storage_id:
                config = db.query(StorageConfig).filter(StorageConfig.id == active.storage_id).first()
            else:
                return None
        
        return config if config and config.enabled else None
    
    async def _update_session_attachment(
        self, db: Session, session_id: str, message_id: str, attachment_id: str, url: str
    ):
        """更新会话附件 URL"""
        from sqlalchemy.orm.attributes import flag_modified
        import copy
        
        try:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not session:
                return
            
            messages = copy.deepcopy(session.messages or [])
            updated = False
            
            for msg in messages:
                if msg.get('id') == message_id and msg.get('attachments'):
                    for att in msg['attachments']:
                        if att.get('id') == attachment_id:
                            att['url'] = url
                            att['uploadStatus'] = 'completed'
                            updated = True
                            break
                if updated:
                    break
            
            if updated:
                session.messages = messages
                flag_modified(session, 'messages')
                db.commit()
        except Exception as e:
            logger.error(f"[UploadQueue] 更新会话失败: {e}")
    
    async def _acquire_rate_token(self):
        """获取限流令牌"""
        async with self._rate_lock:
            now = datetime.now().timestamp()
            elapsed = now - self._last_refill
            
            self._rate_tokens = min(
                self.rate_limit,
                self._rate_tokens + elapsed * self.rate_limit
            )
            self._last_refill = now
            
            if self._rate_tokens < 1:
                wait = (1 - self._rate_tokens) / self.rate_limit
                await asyncio.sleep(wait)
                self._rate_tokens = 0
            else:
                self._rate_tokens -= 1
    
    def get_stats(self) -> dict:
        """获取队列统计"""
        db = SessionLocal()
        try:
            pending = db.query(UploadTask).filter(UploadTask.status == 'pending').count()
            uploading = db.query(UploadTask).filter(UploadTask.status == 'uploading').count()
            completed = db.query(UploadTask).filter(UploadTask.status == 'completed').count()
            failed = db.query(UploadTask).filter(UploadTask.status == 'failed').count()
            
            return {
                "queue_size": pending + uploading,
                "pending": pending,
                "uploading": uploading,
                "completed": completed,
                "failed": failed,
                "workers": self.max_workers,
                "rate_limit": self.rate_limit
            }
        finally:
            db.close()


# 全局单例
upload_queue_manager = UploadQueueManager()
```


### 3.4 修改现有路由

```python
# backend/app/routers/storage.py 修改

# ========== 修改 upload-async 接口 ==========

@router.post("/upload-async")
async def upload_file_async(
    file: UploadFile = File(...),
    priority: str = "normal",  # 新增：优先级参数
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    attachment_id: Optional[str] = None,
    storage_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    异步上传文件到云存储（队列模式）
    
    改动：
    - 新增 priority 参数（high/normal/low）
    - 移除 BackgroundTasks，改为入队由 Worker 处理
    - 新增 retry_count、max_retries 字段
    """
    # 保存文件到临时目录
    temp_dir = tempfile.gettempdir()
    task_id = str(uuid.uuid4())
    temp_path = os.path.join(temp_dir, f"upload_{task_id}_{file.filename}")
    
    file_content = await file.read()
    with open(temp_path, 'wb') as f:
        f.write(file_content)
    
    # 创建任务（入队）
    task = UploadTask(
        id=task_id,
        session_id=session_id,
        message_id=message_id,
        attachment_id=attachment_id,
        source_file_path=temp_path,
        filename=file.filename,
        storage_id=storage_id,
        status='pending',
        priority=priority,           # 新增
        retry_count=0,               # 新增
        max_retries=3,               # 新增
        file_size=len(file_content), # 新增
        created_at=int(datetime.now().timestamp() * 1000)
    )
    
    db.add(task)
    db.commit()
    
    # ❌ 移除：background_tasks.add_task(process_upload_task, task_id, db)
    # ✅ 任务已入队，由 UploadQueueManager 的 Worker 自动处理
    
    from ..services.upload_queue_manager import upload_queue_manager
    stats = upload_queue_manager.get_stats()
    
    return {
        "task_id": task_id,
        "status": "pending",
        "priority": priority,
        "queue_position": stats["queue_size"],
        "message": "任务已入队"
    }


# ========== 修改 upload-from-url 接口 ==========

@router.post("/upload-from-url")
async def upload_from_url(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    从 URL 下载图片并上传到云存储（队列模式）
    
    改动：
    - 移除 BackgroundTasks
    - 新增 priority 支持
    """
    task_id = str(uuid.uuid4())
    task = UploadTask(
        id=task_id,
        session_id=data.get('session_id'),
        message_id=data.get('message_id'),
        attachment_id=data.get('attachment_id'),
        source_url=data['url'],
        filename=data['filename'],
        storage_id=data.get('storage_id'),
        status='pending',
        priority=data.get('priority', 'normal'),  # 新增
        retry_count=0,
        max_retries=3,
        created_at=int(datetime.now().timestamp() * 1000)
    )
    
    db.add(task)
    db.commit()
    
    # ❌ 移除：background_tasks.add_task(process_upload_task, task_id, db)
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "任务已入队"
    }


# ========== 新增：队列统计接口 ==========

@router.get("/queue/stats")
async def get_queue_stats():
    """
    获取上传队列统计信息
    
    返回：
    {
        "queue_size": 10,
        "pending": 8,
        "uploading": 2,
        "completed": 100,
        "failed": 5,
        "workers": 5,
        "rate_limit": 10
    }
    """
    from ..services.upload_queue_manager import upload_queue_manager
    return upload_queue_manager.get_stats()


# ========== 新增：批量提交接口 ==========

@router.post("/upload-async-batch")
async def upload_batch_async(
    files: List[UploadFile] = File(...),
    priority: str = "normal",
    session_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    批量异步上传（第一个文件自动高优先级）
    
    返回：
    {
        "task_ids": ["xxx", "yyy", ...],
        "total": 5,
        "queue_size": 10
    }
    """
    task_ids = []
    
    for i, file in enumerate(files):
        temp_dir = tempfile.gettempdir()
        task_id = str(uuid.uuid4())
        temp_path = os.path.join(temp_dir, f"upload_{task_id}_{file.filename}")
        
        file_content = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(file_content)
        
        # 第一个文件高优先级
        file_priority = 'high' if i == 0 and priority == 'normal' else priority
        
        task = UploadTask(
            id=task_id,
            session_id=session_id,
            source_file_path=temp_path,
            filename=file.filename,
            status='pending',
            priority=file_priority,
            retry_count=0,
            max_retries=3,
            file_size=len(file_content),
            created_at=int(datetime.now().timestamp() * 1000)
        )
        
        db.add(task)
        task_ids.append(task_id)
    
    db.commit()
    
    from ..services.upload_queue_manager import upload_queue_manager
    stats = upload_queue_manager.get_stats()
    
    return {
        "task_ids": task_ids,
        "total": len(task_ids),
        "queue_size": stats["queue_size"]
    }


# ========== 新增：批量查询状态 ==========

@router.get("/upload-status-batch")
async def get_batch_status(task_ids: str, db: Session = Depends(get_db)):
    """
    批量查询任务状态
    
    参数：task_ids=xxx,yyy,zzz
    """
    ids = [id.strip() for id in task_ids.split(',')]
    tasks = db.query(UploadTask).filter(UploadTask.id.in_(ids)).all()
    
    return {
        "tasks": [task.to_dict() for task in tasks]
    }
```

### 3.5 应用启动集成

```python
# backend/app/main.py 修改

from contextlib import asynccontextmanager
from fastapi import FastAPI

from .services.upload_queue_manager import upload_queue_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时
    await upload_queue_manager.start()
    yield
    # 关闭时
    await upload_queue_manager.stop()


app = FastAPI(lifespan=lifespan)
```

## 4. 接口对照表

| 现有接口 | 改动 | 说明 |
|----------|------|------|
| `POST /api/storage/upload` | 无改动 | 同步上传，保持不变 |
| `POST /api/storage/upload-async` | 修改 | 移除 `BackgroundTasks`，改为入队 |
| `POST /api/storage/upload-from-url` | 修改 | 移除 `BackgroundTasks`，改为入队 |
| `GET /api/storage/upload-status/{task_id}` | 无改动 | 查询状态，保持不变 |
| `POST /api/storage/retry-upload/{task_id}` | 无改动 | 重试任务，保持不变 |
| `GET /api/storage/queue/stats` | **新增** | 队列统计 |
| `POST /api/storage/upload-async-batch` | **新增** | 批量上传 |
| `GET /api/storage/upload-status-batch` | **新增** | 批量查询状态 |

## 5. 前端调用方式（无需修改）

前端现有调用方式完全兼容：

```typescript
// 现有调用方式保持不变
const result = await storageUpload.uploadFileAsync(file, {
  sessionId,
  messageId,
  attachmentId
});

// 可选：使用新的优先级参数
const formData = new FormData();
formData.append('file', file);

const response = await fetch('/api/storage/upload-async?priority=high&session_id=xxx', {
  method: 'POST',
  body: formData
});
```

## 6. 配置参数

```python
# backend/app/config.py

UPLOAD_QUEUE_CONFIG = {
    "max_workers": 5,           # Worker 数量
    "max_retries": 3,           # 最大重试次数
    "base_retry_delay": 2.0,    # 重试延迟基数（秒）
    "rate_limit": 10.0,         # 每秒最大请求数
    "poll_interval": 1.0        # 队列轮询间隔（秒）
}
```

## 7. 数据库迁移

```python
# backend/app/migrations/add_queue_fields.py

"""
添加队列相关字段到 upload_tasks 表
"""

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('upload_tasks', sa.Column('priority', sa.String(10), default='normal'))
    op.add_column('upload_tasks', sa.Column('retry_count', sa.Integer, default=0))
    op.add_column('upload_tasks', sa.Column('max_retries', sa.Integer, default=3))
    op.add_column('upload_tasks', sa.Column('next_retry_at', sa.BigInteger))
    op.add_column('upload_tasks', sa.Column('started_at', sa.BigInteger))
    op.add_column('upload_tasks', sa.Column('file_size', sa.Integer))
    
    # 创建索引
    op.create_index('ix_upload_tasks_priority', 'upload_tasks', ['priority'])
    op.create_index('ix_upload_tasks_status_priority', 'upload_tasks', ['status', 'priority'])


def downgrade():
    op.drop_index('ix_upload_tasks_status_priority')
    op.drop_index('ix_upload_tasks_priority')
    op.drop_column('upload_tasks', 'file_size')
    op.drop_column('upload_tasks', 'started_at')
    op.drop_column('upload_tasks', 'next_retry_at')
    op.drop_column('upload_tasks', 'max_retries')
    op.drop_column('upload_tasks', 'retry_count')
    op.drop_column('upload_tasks', 'priority')
```

## 8. 总结

### 8.1 改动范围

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/app/models/db_models.py` | 修改 | 添加队列字段 |
| `backend/app/services/upload_queue_manager.py` | **新增** | 队列管理器 |
| `backend/app/routers/storage.py` | 修改 | 移除 `BackgroundTasks`，新增接口 |
| `backend/app/main.py` | 修改 | 启动/停止队列管理器 |

### 8.2 兼容性

- ✅ 现有 `API` 接口路径不变
- ✅ 现有请求参数兼容
- ✅ 现有返回格式兼容
- ✅ 前端无需修改

### 8.3 新增能力

- ✅ 并发控制（5 个 `Worker`）
- ✅ 限流保护（10/s）
- ✅ 自动重试（指数退避，最多 3 次）
- ✅ 优先级队列（`high` > `normal` > `low`）
- ✅ 服务重启恢复（数据库持久化）
- ✅ 批量上传支持
- ✅ 队列统计接口
