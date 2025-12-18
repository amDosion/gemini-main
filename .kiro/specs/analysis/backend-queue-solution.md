# 纯后端队列上传方案

## 1. 设计理念

**核心原则**：前端只负责提交任务，后端统一管理队列、并发、重试、限流。

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              纯后端队列架构                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  前端 (简单)                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  1. 提交文件 → POST /api/upload/submit                                   │   │
│  │  2. 查询状态 → GET /api/upload/status/{task_id}  (可选轮询/WebSocket)   │   │
│  │  3. 接收结果 → 回调通知或轮询获取                                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                          │
│                                      ▼                                          │
│  后端 (核心逻辑)                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │   │
│  │  │   API 层     │───▶│  任务队列    │───▶│  Worker 池   │               │   │
│  │  │  (接收任务)   │    │  (优先级)    │    │  (并发控制)   │               │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘               │   │
│  │                                                │                         │   │
│  │                                                ▼                         │   │
│  │                      ┌──────────────────────────────────────────────┐   │   │
│  │                      │  限流器 + 重试机制 + 云存储上传               │   │   │
│  │                      └──────────────────────────────────────────────┘   │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 2. 后端队列服务完整实现


### 2.1 任务模型

```python
# backend/app/models/upload_task.py

from sqlalchemy import Column, String, Integer, Text, LargeBinary, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum
from ..core.database import Base


class TaskPriority(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskStatus(str, Enum):
    PENDING = "pending"        # 等待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"    # 完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消
    DEAD = "dead"              # 死信（超过重试次数）


class UploadTaskModel(Base):
    """上传任务数据库模型"""
    __tablename__ = "upload_tasks"
    
    id = Column(String(36), primary_key=True)
    
    # 文件信息
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), default="image/png")
    file_size = Column(Integer, default=0)
    file_path = Column(String(500))  # 临时文件路径
    
    # 关联信息
    session_id = Column(String(36), index=True)
    message_id = Column(String(36), index=True)
    attachment_id = Column(String(36), index=True)
    storage_id = Column(String(36))
    
    # 队列控制
    priority = Column(SQLEnum(TaskPriority), default=TaskPriority.NORMAL, index=True)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, index=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # 结果
    result_url = Column(String(500))
    error_message = Column(Text)
    
    # 时间戳
    created_at = Column(Integer, index=True)  # 用于排序
    started_at = Column(Integer)
    completed_at = Column(Integer)
    next_retry_at = Column(Integer)  # 下次重试时间
    
    # 元数据
    metadata = Column(JSONB, default={})
    
    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "file_size": self.file_size,
            "session_id": self.session_id,
            "message_id": self.message_id,
            "attachment_id": self.attachment_id,
            "priority": self.priority.value if self.priority else "normal",
            "status": self.status.value if self.status else "pending",
            "retry_count": self.retry_count,
            "result_url": self.result_url,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }
```

### 2.2 队列服务核心实现

```python
# backend/app/services/backend_upload_queue.py

import asyncio
import os
import tempfile
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging

from ..core.database import SessionLocal
from ..models.upload_task import UploadTaskModel, TaskStatus, TaskPriority
from .storage_service import StorageService
from ..models.db_models import StorageConfig, ActiveStorage, ChatSession

logger = logging.getLogger(__name__)


class BackendUploadQueue:
    """
    纯后端上传队列服务
    
    特性：
    - 数据库持久化（重启不丢失）
    - 优先级队列
    - 可配置 Worker 数量
    - 自动重试（指数退避）
    - 限流保护
    - 死信队列
    """
    
    def __init__(
        self,
        max_workers: int = 5,
        max_retries: int = 3,
        base_retry_delay: float = 2.0,
        rate_limit_per_second: float = 10.0,
        poll_interval: float = 1.0
    ):
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self.rate_limit_per_second = rate_limit_per_second
        self.poll_interval = poll_interval
        
        self._running = False
        self._workers: List[asyncio.Task] = []
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        # 限流控制
        self._rate_tokens = rate_limit_per_second
        self._last_refill = datetime.now().timestamp()
        self._rate_lock = asyncio.Lock()
        
        # 统计
        self._stats = {
            "total_processed": 0,
            "total_success": 0,
            "total_failed": 0,
            "total_retried": 0
        }
    
    async def start(self):
        """启动队列服务"""
        if self._running:
            logger.warning("[UploadQueue] 队列服务已在运行")
            return
        
        self._running = True
        self._semaphore = asyncio.Semaphore(self.max_workers)
        
        # 恢复中断的任务（将 PROCESSING 状态重置为 PENDING）
        await self._recover_interrupted_tasks()
        
        # 启动 Worker
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        
        logger.info(f"[UploadQueue] 队列服务已启动，Worker 数量: {self.max_workers}")
    
    async def stop(self):
        """停止队列服务"""
        self._running = False
        
        for worker in self._workers:
            worker.cancel()
        
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._workers.clear()
        logger.info("[UploadQueue] 队列服务已停止")
    
    async def _recover_interrupted_tasks(self):
        """恢复中断的任务"""
        db = SessionLocal()
        try:
            # 将 PROCESSING 状态的任务重置为 PENDING
            interrupted = db.query(UploadTaskModel).filter(
                UploadTaskModel.status == TaskStatus.PROCESSING
            ).all()
            
            for task in interrupted:
                task.status = TaskStatus.PENDING
                task.started_at = None
                logger.info(f"[UploadQueue] 恢复中断任务: {task.id}")
            
            db.commit()
            
            if interrupted:
                logger.info(f"[UploadQueue] 共恢复 {len(interrupted)} 个中断任务")
                
        finally:
            db.close()
    
    async def submit_task(
        self,
        file_content: bytes,
        filename: str,
        content_type: str = "image/png",
        priority: TaskPriority = TaskPriority.NORMAL,
        session_id: Optional[str] = None,
        message_id: Optional[str] = None,
        attachment_id: Optional[str] = None,
        storage_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        提交上传任务
        
        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())
        
        # 保存文件到临时目录
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"upload_{task_id}_{filename}")
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # 创建任务记录
        db = SessionLocal()
        try:
            task = UploadTaskModel(
                id=task_id,
                filename=filename,
                content_type=content_type,
                file_size=len(file_content),
                file_path=file_path,
                session_id=session_id,
                message_id=message_id,
                attachment_id=attachment_id,
                storage_id=storage_id,
                priority=priority,
                status=TaskStatus.PENDING,
                created_at=int(datetime.now().timestamp() * 1000),
                metadata=metadata or {}
            )
            
            db.add(task)
            db.commit()
            
            logger.info(
                f"[UploadQueue] 任务已提交: {task_id}, "
                f"文件: {filename}, 优先级: {priority.value}"
            )
            
            return task_id
            
        finally:
            db.close()
    
    async def submit_batch(
        self,
        files: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        base_priority: TaskPriority = TaskPriority.NORMAL
    ) -> List[str]:
        """
        批量提交任务
        
        Args:
            files: [{"content": bytes, "filename": str, "content_type": str}, ...]
            session_id: 会话 ID
            base_priority: 基础优先级（第一个文件会提升为 HIGH）
        
        Returns:
            任务 ID 列表
        """
        task_ids = []
        
        for i, file_info in enumerate(files):
            # 第一个文件高优先级
            priority = TaskPriority.HIGH if i == 0 and base_priority == TaskPriority.NORMAL else base_priority
            
            task_id = await self.submit_task(
                file_content=file_info["content"],
                filename=file_info["filename"],
                content_type=file_info.get("content_type", "image/png"),
                priority=priority,
                session_id=session_id,
                message_id=file_info.get("message_id"),
                attachment_id=file_info.get("attachment_id"),
                storage_id=file_info.get("storage_id")
            )
            task_ids.append(task_id)
        
        logger.info(f"[UploadQueue] 批量提交 {len(task_ids)} 个任务")
        return task_ids
    
    async def _worker_loop(self, worker_id: int):
        """Worker 主循环"""
        logger.info(f"[UploadQueue] Worker-{worker_id} 已启动")
        
        while self._running:
            try:
                # 获取下一个任务
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
        
        logger.info(f"[UploadQueue] Worker-{worker_id} 已停止")
    
    async def _fetch_next_task(self) -> Optional[UploadTaskModel]:
        """
        获取下一个待处理任务
        
        优先级顺序：HIGH > NORMAL > LOW
        同优先级按创建时间排序
        """
        db = SessionLocal()
        try:
            now = int(datetime.now().timestamp() * 1000)
            
            # 查询待处理任务（包括需要重试的）
            task = db.query(UploadTaskModel).filter(
                and_(
                    UploadTaskModel.status == TaskStatus.PENDING,
                    or_(
                        UploadTaskModel.next_retry_at.is_(None),
                        UploadTaskModel.next_retry_at <= now
                    )
                )
            ).order_by(
                # 优先级排序：HIGH=0, NORMAL=1, LOW=2
                UploadTaskModel.priority,
                UploadTaskModel.created_at
            ).first()
            
            if task:
                # 标记为处理中
                task.status = TaskStatus.PROCESSING
                task.started_at = now
                db.commit()
                db.refresh(task)
                return task
            
            return None
            
        finally:
            db.close()
    
    async def _process_task(self, task: UploadTaskModel, worker_id: int):
        """处理单个任务"""
        logger.info(
            f"[UploadQueue] Worker-{worker_id} 处理任务: {task.id}, "
            f"文件: {task.filename}, 重试: {task.retry_count}"
        )
        
        self._stats["total_processed"] += 1
        
        db = SessionLocal()
        try:
            # 读取文件内容
            if not task.file_path or not os.path.exists(task.file_path):
                raise Exception(f"文件不存在: {task.file_path}")
            
            with open(task.file_path, 'rb') as f:
                file_content = f.read()
            
            # 获取存储配置
            config = await self._get_storage_config(db, task.storage_id)
            if not config:
                raise Exception("存储配置不可用")
            
            # 执行上传
            result = await StorageService.upload_file(
                filename=task.filename,
                content=file_content,
                content_type=task.content_type,
                provider=config.provider,
                config=config.config
            )
            
            if result.get("success"):
                # 上传成功
                await self._handle_success(db, task, result.get("url"), worker_id)
            else:
                raise Exception(result.get("error", "上传失败"))
                
        except Exception as e:
            await self._handle_failure(db, task, str(e), worker_id)
        finally:
            db.close()
    
    async def _handle_success(
        self,
        db: Session,
        task: UploadTaskModel,
        result_url: str,
        worker_id: int
    ):
        """处理成功"""
        now = int(datetime.now().timestamp() * 1000)
        
        # 更新任务状态
        task.status = TaskStatus.COMPLETED
        task.result_url = result_url
        task.completed_at = now
        db.commit()
        
        # 删除临时文件
        if task.file_path and os.path.exists(task.file_path):
            try:
                os.remove(task.file_path)
            except Exception as e:
                logger.warning(f"[UploadQueue] 删除临时文件失败: {e}")
        
        # 更新会话附件 URL
        if task.session_id and task.message_id and task.attachment_id:
            await self._update_session_attachment(
                db, task.session_id, task.message_id, 
                task.attachment_id, result_url
            )
        
        self._stats["total_success"] += 1
        logger.info(
            f"[UploadQueue] Worker-{worker_id} 任务完成: {task.id}, "
            f"URL: {result_url}"
        )
    
    async def _handle_failure(
        self,
        db: Session,
        task: UploadTaskModel,
        error: str,
        worker_id: int
    ):
        """处理失败"""
        task.retry_count += 1
        task.error_message = error
        
        logger.warning(
            f"[UploadQueue] Worker-{worker_id} 任务失败: {task.id}, "
            f"错误: {error}, 重试: {task.retry_count}/{task.max_retries}"
        )
        
        if task.retry_count < task.max_retries:
            # 计算下次重试时间（指数退避）
            delay_seconds = self.base_retry_delay * (2 ** (task.retry_count - 1))
            next_retry = int((datetime.now().timestamp() + delay_seconds) * 1000)
            
            task.status = TaskStatus.PENDING
            task.next_retry_at = next_retry
            task.started_at = None
            
            self._stats["total_retried"] += 1
            logger.info(
                f"[UploadQueue] 任务 {task.id} 将在 {delay_seconds}s 后重试"
            )
        else:
            # 超过重试次数，移入死信
            task.status = TaskStatus.DEAD
            task.completed_at = int(datetime.now().timestamp() * 1000)
            
            self._stats["total_failed"] += 1
            logger.error(f"[UploadQueue] 任务 {task.id} 已移入死信队列")
        
        db.commit()
    
    async def _get_storage_config(
        self,
        db: Session,
        storage_id: Optional[str]
    ) -> Optional[StorageConfig]:
        """获取存储配置"""
        if storage_id:
            config = db.query(StorageConfig).filter(
                StorageConfig.id == storage_id
            ).first()
        else:
            active = db.query(ActiveStorage).filter(
                ActiveStorage.user_id == "default"
            ).first()
            if active and active.storage_id:
                config = db.query(StorageConfig).filter(
                    StorageConfig.id == active.storage_id
                ).first()
            else:
                return None
        
        if config and config.enabled:
            return config
        return None
    
    async def _update_session_attachment(
        self,
        db: Session,
        session_id: str,
        message_id: str,
        attachment_id: str,
        url: str
    ):
        """更新会话附件 URL"""
        from sqlalchemy.orm.attributes import flag_modified
        import copy
        
        try:
            session = db.query(ChatSession).filter(
                ChatSession.id == session_id
            ).first()
            
            if not session:
                return
            
            messages = copy.deepcopy(session.messages or [])
            updated = False
            
            for msg in messages:
                if msg.get("id") == message_id and msg.get("attachments"):
                    for att in msg["attachments"]:
                        if att.get("id") == attachment_id:
                            att["url"] = url
                            att["uploadStatus"] = "completed"
                            updated = True
                            break
                if updated:
                    break
            
            if updated:
                session.messages = messages
                flag_modified(session, "messages")
                db.commit()
                logger.info(f"[UploadQueue] 已更新会话附件: {attachment_id[:8]}...")
                
        except Exception as e:
            logger.error(f"[UploadQueue] 更新会话附件失败: {e}")
    
    async def _acquire_rate_token(self):
        """获取限流令牌"""
        async with self._rate_lock:
            now = datetime.now().timestamp()
            elapsed = now - self._last_refill
            
            # 补充令牌
            self._rate_tokens = min(
                self.rate_limit_per_second,
                self._rate_tokens + elapsed * self.rate_limit_per_second
            )
            self._last_refill = now
            
            if self._rate_tokens < 1:
                wait_time = (1 - self._rate_tokens) / self.rate_limit_per_second
                await asyncio.sleep(wait_time)
                self._rate_tokens = 0
            else:
                self._rate_tokens -= 1
    
    # ==================== 查询接口 ====================
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        db = SessionLocal()
        try:
            task = db.query(UploadTaskModel).filter(
                UploadTaskModel.id == task_id
            ).first()
            return task.to_dict() if task else None
        finally:
            db.close()
    
    def get_queue_stats(self) -> Dict:
        """获取队列统计"""
        db = SessionLocal()
        try:
            # 各状态数量
            pending = db.query(UploadTaskModel).filter(
                UploadTaskModel.status == TaskStatus.PENDING
            ).count()
            
            processing = db.query(UploadTaskModel).filter(
                UploadTaskModel.status == TaskStatus.PROCESSING
            ).count()
            
            completed = db.query(UploadTaskModel).filter(
                UploadTaskModel.status == TaskStatus.COMPLETED
            ).count()
            
            failed = db.query(UploadTaskModel).filter(
                UploadTaskModel.status == TaskStatus.FAILED
            ).count()
            
            dead = db.query(UploadTaskModel).filter(
                UploadTaskModel.status == TaskStatus.DEAD
            ).count()
            
            return {
                "queue_size": pending + processing,
                "pending": pending,
                "processing": processing,
                "completed": completed,
                "failed": failed,
                "dead_letter": dead,
                "workers": self.max_workers,
                "rate_limit": self.rate_limit_per_second,
                **self._stats
            }
        finally:
            db.close()
    
    def get_dead_letter_tasks(self, limit: int = 50) -> List[Dict]:
        """获取死信队列任务"""
        db = SessionLocal()
        try:
            tasks = db.query(UploadTaskModel).filter(
                UploadTaskModel.status == TaskStatus.DEAD
            ).order_by(
                UploadTaskModel.completed_at.desc()
            ).limit(limit).all()
            
            return [t.to_dict() for t in tasks]
        finally:
            db.close()
    
    async def retry_dead_letter(self, task_id: str) -> bool:
        """重试死信任务"""
        db = SessionLocal()
        try:
            task = db.query(UploadTaskModel).filter(
                and_(
                    UploadTaskModel.id == task_id,
                    UploadTaskModel.status == TaskStatus.DEAD
                )
            ).first()
            
            if not task:
                return False
            
            task.status = TaskStatus.PENDING
            task.retry_count = 0
            task.error_message = None
            task.next_retry_at = None
            task.started_at = None
            task.completed_at = None
            
            db.commit()
            logger.info(f"[UploadQueue] 死信任务已重新入队: {task_id}")
            return True
        finally:
            db.close()
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        db = SessionLocal()
        try:
            task = db.query(UploadTaskModel).filter(
                and_(
                    UploadTaskModel.id == task_id,
                    UploadTaskModel.status == TaskStatus.PENDING
                )
            ).first()
            
            if not task:
                return False
            
            task.status = TaskStatus.CANCELLED
            db.commit()
            
            # 删除临时文件
            if task.file_path and os.path.exists(task.file_path):
                try:
                    os.remove(task.file_path)
                except:
                    pass
            
            logger.info(f"[UploadQueue] 任务已取消: {task_id}")
            return True
        finally:
            db.close()


# 全局单例
upload_queue = BackendUploadQueue()
```


### 2.3 API 路由

```python
# backend/app/routers/upload_queue.py

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import Optional, List
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..services.backend_upload_queue import upload_queue, TaskPriority

router = APIRouter(prefix="/api/upload", tags=["upload-queue"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/submit")
async def submit_upload(
    file: UploadFile = File(...),
    priority: str = "normal",
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    attachment_id: Optional[str] = None,
    storage_id: Optional[str] = None
):
    """
    提交上传任务到队列
    
    前端只需调用此接口，后端自动处理队列、重试、限流
    
    参数：
    - file: 要上传的文件
    - priority: 优先级 (high/normal/low)
    - session_id: 会话 ID（用于上传完成后更新数据库）
    - message_id: 消息 ID
    - attachment_id: 附件 ID
    - storage_id: 存储配置 ID（可选）
    
    返回：
    {
        "task_id": "xxx-xxx-xxx",
        "status": "pending",
        "position": 5
    }
    """
    # 解析优先级
    priority_map = {
        "high": TaskPriority.HIGH,
        "normal": TaskPriority.NORMAL,
        "low": TaskPriority.LOW
    }
    task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
    
    # 读取文件内容
    content = await file.read()
    
    # 提交到队列
    task_id = await upload_queue.submit_task(
        file_content=content,
        filename=file.filename,
        content_type=file.content_type or "image/png",
        priority=task_priority,
        session_id=session_id,
        message_id=message_id,
        attachment_id=attachment_id,
        storage_id=storage_id
    )
    
    stats = upload_queue.get_queue_stats()
    
    return {
        "task_id": task_id,
        "status": "pending",
        "position": stats["queue_size"]
    }


@router.post("/submit-batch")
async def submit_batch_upload(
    files: List[UploadFile] = File(...),
    priority: str = "normal",
    session_id: Optional[str] = None
):
    """
    批量提交上传任务
    
    第一个文件自动提升为高优先级
    
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
    base_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
    
    # 准备文件数据
    file_list = []
    for file in files:
        content = await file.read()
        file_list.append({
            "content": content,
            "filename": file.filename,
            "content_type": file.content_type or "image/png"
        })
    
    # 批量提交
    task_ids = await upload_queue.submit_batch(
        files=file_list,
        session_id=session_id,
        base_priority=base_priority
    )
    
    stats = upload_queue.get_queue_stats()
    
    return {
        "task_ids": task_ids,
        "total": len(task_ids),
        "queue_size": stats["queue_size"]
    }


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态
    
    返回：
    {
        "id": "xxx",
        "filename": "image.png",
        "status": "completed",
        "result_url": "https://...",
        "retry_count": 0,
        "error_message": null
    }
    """
    status = upload_queue.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    return status


@router.get("/status-batch")
async def get_batch_status(task_ids: str):
    """
    批量查询任务状态
    
    参数：
    - task_ids: 逗号分隔的任务 ID
    
    返回：
    {
        "tasks": [...]
    }
    """
    ids = task_ids.split(",")
    tasks = []
    
    for task_id in ids:
        status = upload_queue.get_task_status(task_id.strip())
        if status:
            tasks.append(status)
    
    return {"tasks": tasks}


@router.get("/stats")
async def get_queue_stats():
    """
    获取队列统计信息
    
    返回：
    {
        "queue_size": 10,
        "pending": 8,
        "processing": 2,
        "completed": 100,
        "failed": 5,
        "dead_letter": 2,
        "workers": 5,
        "rate_limit": 10
    }
    """
    return upload_queue.get_queue_stats()


@router.post("/cancel/{task_id}")
async def cancel_task(task_id: str):
    """取消待处理的任务"""
    success = await upload_queue.cancel_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="无法取消任务（可能已在处理中或不存在）"
        )
    return {"success": True}


@router.get("/dead-letter")
async def get_dead_letter_tasks(limit: int = 50):
    """获取死信队列任务"""
    tasks = upload_queue.get_dead_letter_tasks(limit)
    return {"tasks": tasks, "total": len(tasks)}


@router.post("/dead-letter/retry/{task_id}")
async def retry_dead_letter_task(task_id: str):
    """重试死信队列中的任务"""
    success = await upload_queue.retry_dead_letter(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="任务不存在或不在死信队列中"
        )
    return {"success": True}


@router.post("/dead-letter/retry-all")
async def retry_all_dead_letter():
    """重试所有死信任务"""
    tasks = upload_queue.get_dead_letter_tasks(limit=1000)
    retried = 0
    
    for task in tasks:
        if await upload_queue.retry_dead_letter(task["id"]):
            retried += 1
    
    return {"retried": retried, "total": len(tasks)}
```

### 2.4 应用启动集成

```python
# backend/app/main.py 修改

from fastapi import FastAPI
from contextlib import asynccontextmanager

from .services.backend_upload_queue import upload_queue
from .routers import upload_queue as upload_queue_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    await upload_queue.start()
    yield
    # 关闭时
    await upload_queue.stop()


app = FastAPI(lifespan=lifespan)

# 注册路由
app.include_router(upload_queue_router.router)
```

## 3. 前端调用方式

### 3.1 简化的前端服务

```typescript
// frontend/services/storage/uploadService.ts

const API_BASE = '/api/upload';

interface SubmitResult {
  task_id: string;
  status: string;
  position: number;
}

interface TaskStatus {
  id: string;
  filename: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'dead';
  result_url?: string;
  error_message?: string;
  retry_count: number;
}

/**
 * 简化的上传服务
 * 
 * 所有队列逻辑都在后端，前端只需：
 * 1. 提交任务
 * 2. 查询状态（可选）
 */
export const uploadService = {
  /**
   * 提交单个上传任务
   */
  async submit(
    file: File,
    options?: {
      priority?: 'high' | 'normal' | 'low';
      sessionId?: string;
      messageId?: string;
      attachmentId?: string;
    }
  ): Promise<SubmitResult> {
    const formData = new FormData();
    formData.append('file', file);

    const params = new URLSearchParams();
    if (options?.priority) params.append('priority', options.priority);
    if (options?.sessionId) params.append('session_id', options.sessionId);
    if (options?.messageId) params.append('message_id', options.messageId);
    if (options?.attachmentId) params.append('attachment_id', options.attachmentId);

    const response = await fetch(`${API_BASE}/submit?${params}`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(`提交失败: ${response.status}`);
    }

    return response.json();
  },

  /**
   * 批量提交上传任务
   */
  async submitBatch(
    files: File[],
    options?: {
      priority?: 'high' | 'normal' | 'low';
      sessionId?: string;
    }
  ): Promise<{ task_ids: string[]; total: number }> {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    const params = new URLSearchParams();
    if (options?.priority) params.append('priority', options.priority);
    if (options?.sessionId) params.append('session_id', options.sessionId);

    const response = await fetch(`${API_BASE}/submit-batch?${params}`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(`批量提交失败: ${response.status}`);
    }

    return response.json();
  },

  /**
   * 查询任务状态
   */
  async getStatus(taskId: string): Promise<TaskStatus> {
    const response = await fetch(`${API_BASE}/status/${taskId}`);
    if (!response.ok) {
      throw new Error(`查询失败: ${response.status}`);
    }
    return response.json();
  },

  /**
   * 批量查询任务状态
   */
  async getBatchStatus(taskIds: string[]): Promise<{ tasks: TaskStatus[] }> {
    const response = await fetch(`${API_BASE}/status-batch?task_ids=${taskIds.join(',')}`);
    if (!response.ok) {
      throw new Error(`批量查询失败: ${response.status}`);
    }
    return response.json();
  },

  /**
   * 轮询等待任务完成
   */
  async waitForCompletion(
    taskId: string,
    options?: {
      maxWait?: number;      // 最大等待时间（毫秒），默认 120000
      pollInterval?: number; // 轮询间隔（毫秒），默认 2000
      onProgress?: (status: TaskStatus) => void;
    }
  ): Promise<string> {
    const maxWait = options?.maxWait ?? 120000;
    const pollInterval = options?.pollInterval ?? 2000;
    const startTime = Date.now();

    while (Date.now() - startTime < maxWait) {
      const status = await this.getStatus(taskId);
      options?.onProgress?.(status);

      if (status.status === 'completed' && status.result_url) {
        return status.result_url;
      }

      if (status.status === 'failed' || status.status === 'dead') {
        throw new Error(status.error_message || '上传失败');
      }

      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }

    throw new Error('上传超时');
  },

  /**
   * 批量等待任务完成
   */
  async waitForBatchCompletion(
    taskIds: string[],
    options?: {
      maxWait?: number;
      pollInterval?: number;
      onProgress?: (completed: number, total: number) => void;
    }
  ): Promise<Map<string, string>> {
    const maxWait = options?.maxWait ?? 120000;
    const pollInterval = options?.pollInterval ?? 2000;
    const startTime = Date.now();
    const results = new Map<string, string>();
    const pending = new Set(taskIds);

    while (pending.size > 0 && Date.now() - startTime < maxWait) {
      const { tasks } = await this.getBatchStatus(Array.from(pending));

      for (const task of tasks) {
        if (task.status === 'completed' && task.result_url) {
          results.set(task.id, task.result_url);
          pending.delete(task.id);
        } else if (task.status === 'failed' || task.status === 'dead') {
          pending.delete(task.id);
          console.error(`任务 ${task.id} 失败: ${task.error_message}`);
        }
      }

      options?.onProgress?.(results.size, taskIds.length);

      if (pending.size > 0) {
        await new Promise(resolve => setTimeout(resolve, pollInterval));
      }
    }

    return results;
  }
};
```

### 3.2 Handler 层调用示例

```typescript
// frontend/hooks/handlers/imageGenHandler.ts 修改

import { uploadService } from '../../services/storage/uploadService';

export const handleImageGen = async (
  text: string,
  attachments: Attachment[],
  context: HandlerContext
): Promise<ImageGenResult> => {
  // 1. 生成图片
  const results = await llmService.generateImage(text, attachments);

  // 2. 处理结果，创建本地预览
  const processedResults = await Promise.all(results.map(async (res, index) => {
    const attachmentId = uuidv4();
    const filename = `generated-${Date.now()}-${index + 1}.png`;

    let displayUrl = res.url;
    let file: File;

    if (res.url.startsWith('http')) {
      const response = await fetch(res.url);
      const blob = await response.blob();
      displayUrl = URL.createObjectURL(blob);
      file = new File([blob], filename, { type: 'image/png' });
    } else {
      // Base64
      const response = await fetch(res.url);
      const blob = await response.blob();
      file = new File([blob], filename, { type: 'image/png' });
    }

    return { id: attachmentId, filename, displayUrl, file, mimeType: res.mimeType };
  }));

  // 3. 构建显示用附件（立即返回给 UI）
  const displayAttachments: Attachment[] = processedResults.map(r => ({
    id: r.id,
    mimeType: r.mimeType,
    name: r.filename,
    url: r.displayUrl,
    uploadStatus: 'pending'
  }));

  // 4. 提交到后端队列（不阻塞）
  const uploadTask = async (): Promise<{ dbAttachments: Attachment[] }> => {
    // 批量提交到后端队列
    const files = processedResults.map(r => r.file);
    const { task_ids } = await uploadService.submitBatch(files, {
      sessionId: context.sessionId,
      priority: 'normal'
    });

    // 等待所有任务完成
    const urlMap = await uploadService.waitForBatchCompletion(task_ids, {
      onProgress: (completed, total) => {
        console.log(`[imageGenHandler] 上传进度: ${completed}/${total}`);
      }
    });

    // 构建数据库用附件
    const dbAttachments: Attachment[] = processedResults.map((r, i) => ({
      id: r.id,
      mimeType: r.mimeType,
      name: r.filename,
      url: urlMap.get(task_ids[i]) || '',
      uploadStatus: urlMap.has(task_ids[i]) ? 'completed' : 'failed'
    }));

    return { dbAttachments };
  };

  return {
    content: `Generated images for: "${text}"`,
    attachments: displayAttachments,
    uploadTask: uploadTask()
  };
};
```

## 4. 流程图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           纯后端队列上传流程                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  前端                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  1. 生成图片 → 创建本地预览 URL → 立即显示给用户                         │   │
│  │                                                                          │   │
│  │  2. POST /api/upload/submit-batch                                        │   │
│  │     - 提交所有文件到后端                                                  │   │
│  │     - 获取 task_ids                                                      │   │
│  │     - 不等待上传完成                                                      │   │
│  │                                                                          │   │
│  │  3. (可选) 轮询 GET /api/upload/status-batch                             │   │
│  │     - 获取上传进度                                                        │   │
│  │     - 更新 UI 状态                                                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                      │                                          │
│                                      ▼                                          │
│  后端                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │   │
│  │  │  API 层: /api/upload/submit                                       │   │   │
│  │  │  - 接收文件                                                        │   │   │
│  │  │  - 保存到临时目录                                                  │   │   │
│  │  │  - 创建任务记录 (数据库)                                           │   │   │
│  │  │  - 立即返回 task_id                                                │   │   │
│  │  └──────────────────────────────────────────────────────────────────┘   │   │
│  │                                      │                                   │   │
│  │                                      ▼                                   │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │   │
│  │  │  BackendUploadQueue                                               │   │   │
│  │  │                                                                    │   │   │
│  │  │  数据库队列 (upload_tasks 表)                                      │   │   │
│  │  │  ┌─────────────────────────────────────────────────────────────┐  │   │   │
│  │  │  │  优先级排序: HIGH → NORMAL → LOW                             │  │   │   │
│  │  │  │  同优先级按 created_at 排序                                   │  │   │   │
│  │  │  └─────────────────────────────────────────────────────────────┘  │   │   │
│  │  │                                                                    │   │   │
│  │  │  Worker 池 (5 个协程)                                              │   │   │
│  │  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐                              │   │   │
│  │  │  │ W1 │ │ W2 │ │ W3 │ │ W4 │ │ W5 │                              │   │   │
│  │  │  └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘                              │   │   │
│  │  │     │      │      │      │      │                                  │   │   │
│  │  │     └──────┴──────┼──────┴──────┘                                  │   │   │
│  │  │                   │                                                │   │   │
│  │  │  限流器 (令牌桶, 10/s)                                             │   │   │
│  │  │                   │                                                │   │   │
│  │  └───────────────────│────────────────────────────────────────────────┘   │   │
│  │                      │                                                     │   │
│  │                      ▼                                                     │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐     │   │
│  │  │  StorageService                                                   │     │   │
│  │  │  - upload_to_lsky()                                               │     │   │
│  │  │  - upload_to_aliyun_oss()                                         │     │   │
│  │  └──────────────────────────────────────────────────────────────────┘     │   │
│  │                      │                                                     │   │
│  │                      ▼                                                     │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐     │   │
│  │  │  结果处理                                                         │     │   │
│  │  │                                                                    │     │   │
│  │  │  成功:                                                             │     │   │
│  │  │  - 更新任务状态 → COMPLETED                                        │     │   │
│  │  │  - 保存 result_url                                                 │     │   │
│  │  │  - 更新会话附件 URL                                                │     │   │
│  │  │  - 删除临时文件                                                    │     │   │
│  │  │                                                                    │     │   │
│  │  │  失败:                                                             │     │   │
│  │  │  - retry_count < max_retries → 重新入队 (指数退避)                 │     │   │
│  │  │  - retry_count >= max_retries → 移入死信队列                       │     │   │
│  │  └──────────────────────────────────────────────────────────────────┘     │   │
│  │                                                                            │   │
│  └────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

## 5. 配置参数

```python
# backend/app/config.py

UPLOAD_QUEUE_CONFIG = {
    # Worker 配置
    "max_workers": 5,              # Worker 数量
    "poll_interval": 1.0,          # 队列轮询间隔（秒）
    
    # 重试配置
    "max_retries": 3,              # 最大重试次数
    "base_retry_delay": 2.0,       # 重试延迟基数（秒）
    # 实际延迟: base_retry_delay * 2^(retry_count-1)
    # 第1次重试: 2s, 第2次: 4s, 第3次: 8s
    
    # 限流配置
    "rate_limit_per_second": 10.0, # 每秒最大请求数
    
    # 兰空图床建议: 5-10/s
    # 阿里云 OSS 建议: 50-100/s
}
```

## 6. 总结

### 6.1 方案特点

| 特性 | 说明 |
|------|------|
| 纯后端队列 | 前端只提交，后端处理所有队列逻辑 |
| 数据库持久化 | 任务存储在数据库，重启不丢失 |
| 优先级队列 | HIGH > NORMAL > LOW |
| 自动重试 | 指数退避，最多 3 次 |
| 限流保护 | 令牌桶算法，保护云存储 API |
| 死信队列 | 失败任务隔离，支持手动重试 |
| 状态查询 | 支持单个/批量查询任务状态 |

### 6.2 前端职责

- 提交文件到 `/api/upload/submit`
- （可选）轮询查询状态
- 显示上传进度

### 6.3 后端职责

- 接收文件，保存到临时目录
- 管理任务队列（优先级、排序）
- 控制并发（Worker 池）
- 限流保护（令牌桶）
- 自动重试（指数退避）
- 死信队列管理
- 上传完成后更新数据库
