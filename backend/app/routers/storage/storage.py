"""
云存储配置和上传路由
支持兰空图床和阿里云 OSS
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, BackgroundTasks, Response, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import uuid
import httpx
import os
from pathlib import Path
import logging

from ...core.database import SessionLocal, get_db
from ...core.config import settings
from ...models.db_models import StorageConfig, ActiveStorage, UploadTask
from ...services.storage.storage_service import StorageService
from ...services.storage.storage_manager import StorageManager
from ...services.common.redis_queue_service import redis_queue
from ...core.dependencies import require_current_user
from ...core.user_scoped_query import UserScopedQuery
from ...core.encryption import decrypt_config

router = APIRouter(prefix="/api/storage", tags=["storage"])
logger = logging.getLogger(__name__)

# 导入路径工具
from ...core.path_utils import get_temp_dir, get_temp_dir_relative, resolve_relative_path, ensure_relative_path

# 项目内临时文件目录（使用统一的路径工具）
TEMP_DIR = get_temp_dir()

# Startup log to verify TEMP_DIR (只记录一次)
if not hasattr(router, '_temp_dir_logged'):
    logger.info(f"[Storage Router] TEMP_DIR initialized: {TEMP_DIR}")
    router._temp_dir_logged = True


def _mask_url(url: str) -> str:
    try:
        if "://" not in url:
            return url
        scheme, rest = url.split("://", 1)
        if "@" not in rest:
            return url
        creds, tail = rest.split("@", 1)
        if ":" not in creds:
            return url
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{tail}"
    except Exception:
        return url


@router.get("/debug")
async def storage_debug():
    """返回后端运行态信息（用于排查是否命中最新代码/路由）。"""
    backend_env = Path(__file__).resolve().parents[2] / ".env"
    return {
        "module_file": __file__,
        "cwd": os.getcwd(),
        "temp_dir": TEMP_DIR,
        "backend_env_exists": backend_env.exists(),
        "database_url": _mask_url(settings.database_url),
        "redis_url": _mask_url(settings.redis_url),
        "features": {
            "upload_logs": True,
            "upload_status": True,
            "upload_async": True,
        },
    }


@router.get("/worker-status")
async def get_worker_status():
    """查看 WorkerPool/Redis 状态（用于定位“排队后不处理，重启才成功”）。"""
    try:
        from ...services.common.upload_worker_pool import worker_pool
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"WorkerPool 不可用: {e}")

    redis_error: str | None = None
    stats = None
    try:
        if redis_queue._redis is None:
            await redis_queue.connect()
        stats = await redis_queue.get_stats()
    except Exception as e:
        redis_error = str(e)

    workers_total = len(worker_pool._workers)
    workers_alive = sum(1 for t in worker_pool._workers if not t.done())

    return {
        "worker_pool": {
            "running": bool(worker_pool._running),
            "workers_total": workers_total,
            "workers_alive": workers_alive,
            "reconcile_interval_s": getattr(worker_pool, "_reconcile_interval_s", None),
            "reconcile_limit": getattr(worker_pool, "_reconcile_limit", None),
        },
        "redis": {
            "connected": redis_queue._redis is not None,
            "error": redis_error,
            "stats": stats,
        },
        "server": {
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "module_file": __file__,
        },
    }


# ==================== 配置管理 ====================

@router.get("/configs")
async def get_storage_configs(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """获取所有存储配置（自动解密）"""
    logger.info(f"[StorageConfigs] 获取用户存储配置: user_id={user_id}")
    
    manager = StorageManager(db, user_id)
    configs = manager.get_all_configs()
    
    logger.info(f"[StorageConfigs] 返回 {len(configs)} 个配置给前端")
    return configs


@router.post("/configs")
async def create_storage_config(
    config_data: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """创建存储配置（自动加密敏感字段）"""
    manager = StorageManager(db, user_id)
    return manager.create_config(config_data)


@router.put("/configs/{config_id}")
async def update_storage_config(
    config_id: str,
    config_data: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """更新存储配置（自动加密敏感字段）"""
    manager = StorageManager(db, user_id)
    return manager.update_config(config_id, config_data)


@router.delete("/configs/{config_id}")
async def delete_storage_config(
    config_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """删除存储配置"""
    manager = StorageManager(db, user_id)
    manager.delete_config(config_id)
    return {"success": True}


@router.get("/active")
async def get_active_storage(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """获取当前激活的存储配置"""
    manager = StorageManager(db, user_id)
    storage_id = manager.get_active_storage_id()

    return {"storage_id": storage_id}


@router.post("/active/{storage_id}")
async def set_active_storage(
    storage_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """设置当前激活的存储配置"""
    manager = StorageManager(db, user_id)
    manager.set_active_storage(storage_id)

    return {"success": True, "storage_id": storage_id}


@router.post("/test")
async def test_storage_config(
    config_data: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    测试存储配置
    
    请求参数：
    {
        "provider": "lsky" | "aliyun-oss" | "tencent-cos" | "google-drive" | "local" | "s3-compatible",
        "config": {
            // Provider-specific configuration
        }
    }
    
    返回：
    {
        "success": true,
        "message": "Configuration test successful",
        "test_url": "https://..."
    }
    """
    manager = StorageManager(db, user_id)
    return await manager.test_config(config_data)


# ==================== 文件上传 ====================

def upload_to_active_storage(content: bytes, filename: str, content_type: str, user_id: Optional[str] = None) -> dict:
    """
    同步上传文件到当前激活的存储配置

    供其他模块（如 image_expand）调用

    Args:
        content: 文件内容（字节）
        filename: 文件名
        content_type: MIME 类型

    Returns:
        {"success": True, "url": "https://..."} 或 {"success": False, "error": "..."}
    """
    db = SessionLocal()
    try:
        resolved_user_id = user_id or "default"
        # 获取当前激活的存储配置
        active = db.query(ActiveStorage).filter(ActiveStorage.user_id == resolved_user_id).first()
        if not active or not active.storage_id:
            return {"success": False, "error": "未设置存储配置"}

        config = db.query(StorageConfig).filter(StorageConfig.id == active.storage_id).first()
        if not config:
            return {"success": False, "error": "存储配置不存在"}

        if not config.enabled:
            return {"success": False, "error": "存储配置已禁用"}

        # 根据提供商类型上传
        if config.provider == "lsky":
            return upload_to_lsky_sync(filename, content, content_type, config.config)
        else:
            return {"success": False, "error": f"不支持的存储类型: {config.provider}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def upload_to_active_storage_async(content: bytes, filename: str, content_type: str, user_id: Optional[str] = None) -> dict:
    """
    异步上传文件到当前激活的存储配置

    供其他异步模块（如 chat_handler）调用
    
    使用 StorageManager 统一管理配置，实现配置获取、解密和上传的统一处理。

    Args:
        content: 文件内容（字节）
        filename: 文件名
        content_type: MIME 类型
        user_id: 用户 ID（用于确定存储配置）

    Returns:
        {"success": True, "url": "https://..."} 或 {"success": False, "error": "..."}
    """
    db = SessionLocal()
    try:
        resolved_user_id = user_id or "default"
        logger.info(f"[Storage] Async upload for user: {resolved_user_id}, file: {filename}")

        # ✅ 使用 StorageManager 统一管理配置和上传
        manager = StorageManager(db, resolved_user_id)
        result = await manager.upload_file(
            filename=filename,
            content=content,
            content_type=content_type
        )

        if result.get('success'):
            logger.info(f"[Storage] Upload successful: {result.get('url', '')[:60]}...")
        else:
            logger.error(f"[Storage] Upload failed: {result.get('error', 'Unknown error')}")

        return result
    except HTTPException as e:
        logger.error(f"[Storage] Async upload HTTP error: {e.detail}")
        return {"success": False, "error": e.detail}
    except Exception as e:
        logger.error(f"[Storage] Async upload error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def upload_to_lsky_sync(filename: str, content: bytes, content_type: str, config: dict) -> dict:
    """
    同步上传到兰空图床
    """
    import requests
    
    domain = config.get("domain")
    token = config.get("token")
    strategy_id = config.get("strategyId")
    
    if not domain or not token:
        return {"success": False, "error": "兰空图床配置不完整"}
    
    auth_token = token if token.startswith("Bearer ") else f"Bearer {token}"
    upload_url = f"{domain.rstrip('/')}/api/v1/upload"
    
    files = {"file": (filename, content, content_type)}
    headers = {"Authorization": auth_token, "Accept": "application/json"}
    data = {"strategy_id": strategy_id} if strategy_id else {}
    
    try:
        response = requests.post(upload_url, files=files, headers=headers, data=data, timeout=60)
        result = response.json()
        
        if result.get("status") and result.get("data", {}).get("links", {}).get("url"):
            return {
                "success": True,
                "url": result["data"]["links"]["url"],
                "provider": "lsky"
            }
        else:
            return {"success": False, "error": result.get("message", "上传失败")}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    storage_id: Optional[str] = None,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    上传文件到云存储（使用 StorageManager）
    如果不指定 storage_id，使用当前激活的配置
    """
    
    # 读取文件内容
    file_content = await file.read()
    
    # 使用 StorageManager 上传
    manager = StorageManager(db, user_id)
    return await manager.upload_file(
        filename=file.filename,
        content=file_content,
        content_type=file.content_type,
        storage_id=storage_id
    )


# ==================== 异步上传任务处理 ====================

from ...models.db_models import ChatSession

async def process_upload_task(task_id: str, _db: Session = None):
    """
    后台处理上传任务
    
    支持两种模式：
    1. 从本地文件上传（source_file_path 存在）
    2. 从 URL 下载后上传（source_url 存在）
    
    上传完成后自动更新数据库中的会话消息
    
    注意：此函数创建独立的数据库会话，避免与请求处理器共享会话导致的竞态条件
    """
    # ✅ 创建独立的数据库会话，避免与其他后台任务共享
    db = SessionLocal()
    try:
        task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
        if not task:
            logger.warning(f"[UploadTask] 任务不存在: {task_id}")
            return
        
        # ✅ 详细日志：确认任务数据
        logger.info(f"[UploadTask] 开始处理任务: {task_id}")
        logger.info(f"  - 文件名: {task.filename}")
        logger.info(f"  - session_id: {task.session_id if task.session_id else 'None'}")
        logger.info(f"  - message_id: {task.message_id if task.message_id else 'None'}")
        logger.info(f"  - attachment_id: {task.attachment_id if task.attachment_id else 'None'}")
        
        # 1. 更新状态为 uploading
        task.status = 'uploading'
        db.commit()
        
        # 2. 获取用户ID和存储配置
        # ✅ 使用 StorageManager 统一管理配置
        user_id = "default"
        if task.session_id:
            session = db.query(ChatSession).filter(ChatSession.id == task.session_id).first()
            if session:
                user_id = session.user_id
        
        # ✅ 使用 StorageManager 统一管理配置和上传
        manager = StorageManager(db, user_id)
        
        # 3. 获取图片内容
        image_content = None
        temp_path = None
        
        if task.source_file_path:
            # 模式 1: 从本地文件读取（使用统一的路径解析）
            file_path = resolve_relative_path(task.source_file_path)
            if os.path.exists(file_path):
                logger.info(f"[UploadTask] 读取本地文件: {ensure_relative_path(task.source_file_path)}")
                with open(file_path, 'rb') as f:
                    image_content = f.read()
                temp_path = file_path
            else:
                raise Exception(f"文件不存在: {task.source_file_path}")
        elif task.source_url:
            # 模式 2: 从 URL 下载
            logger.info(f"[UploadTask] 下载图片: {task.source_url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(task.source_url)
                response.raise_for_status()
                image_content = response.content
            
            # 保存到项目内临时目录（使用相对路径存储）
            filename_with_id = f"upload_{task_id}_{task.filename}"
            temp_path_abs = os.path.join(TEMP_DIR, filename_with_id)
            temp_path_rel = f"{get_temp_dir_relative()}/{filename_with_id}"
            
            with open(temp_path_abs, 'wb') as f:
                f.write(image_content)
            logger.info(f"[UploadTask] 临时文件: {temp_path_rel}")
            temp_path = temp_path_abs
        else:
            raise Exception("没有可用的图片来源")
        
        # 4. 上传到云存储
        # ✅ 使用 StorageManager 统一管理上传（自动处理配置获取、解密和上传）
        logger.info(f"[UploadTask] 上传到云存储（使用 StorageManager）")
        result = await manager.upload_file(
            filename=task.filename,
            content=image_content,
            content_type='image/png',
            storage_id=task.storage_id  # 如果指定了 storage_id，使用指定的配置
        )
        
        # 5. 删除临时文件
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.info(f"[UploadTask] 临时文件已删除: {temp_path}")
            except Exception as e:
                logger.warning(f"[UploadTask] 删除临时文件失败: {e}")
        
        # 6. 更新任务状态
        if result.get('success'):
            task.status = 'completed'
            task.target_url = result.get('url')
            task.completed_at = int(datetime.now().timestamp() * 1000)
            db.commit()  # ✅ 先提交任务状态，确保上传成功被记录
            logger.info(f"[UploadTask] 上传成功: {task.target_url}")
            
            # 7. 更新数据库中的会话消息（即使失败也不影响任务状态）
            if task.session_id and task.message_id and task.attachment_id:
                try:
                    await update_session_attachment_url(
                        db, 
                        task.session_id, 
                        task.message_id, 
                        task.attachment_id, 
                        task.target_url
                    )
                except Exception as e:
                    logger.warning(f"[UploadTask] ⚠️ 更新会话附件 URL 失败（任务已完成）: {e}")
        else:
            task.status = 'failed'
            task.error_message = result.get('error', '上传失败')
            db.commit()
            logger.error(f"[UploadTask] 上传失败: {task.error_message}")
        
    except Exception as e:
        logger.error(f"[UploadTask] 任务失败: {str(e)}")
        try:
            task.status = 'failed'
            task.error_message = str(e)
            db.commit()
        except:
            pass
    finally:
        # ✅ 确保关闭独立的数据库会话
        db.close()


async def update_session_attachment_url(
    db: Session, 
    session_id: str, 
    message_id: str, 
    attachment_id: str, 
    url: str,
    max_retries: int = 10,
    retry_delay: float = 2.0
):
    """
    更新会话中指定附件的 URL (v3 架构)
    
    直接更新 message_attachments 表，无需遍历 JSON
    
    参数：
    - max_retries: 最大重试次数（默认10次）
    - retry_delay: 每次重试间隔（默认2秒）
    """
    from ...models.db_models import MessageAttachment
    import asyncio
    
    logger.info(f"[UploadTask] 开始更新附件 URL: session={session_id}, msg={message_id}, att={attachment_id}")
    
    for attempt in range(max_retries):
        try:
            db.expire_all()
            
            attachment = db.query(MessageAttachment).filter(
                MessageAttachment.id == attachment_id
            ).first()
            
            if attachment:
                attachment.url = url
                attachment.upload_status = 'completed'
                attachment.temp_url = None
                db.commit()
                print(f"[UploadTask] ✅ 附件表已更新: {attachment_id}, URL: {url}")
                return
            else:
                if attempt < max_retries - 1:
                    print(f"[UploadTask] ⏳ 附件不存在，等待重试 ({attempt + 1}/{max_retries}): {attachment_id}")
                    await asyncio.sleep(retry_delay)
                else:
                    print(f"[UploadTask] ❌ 重试 {max_retries} 次后仍未找到附件: {attachment_id}")
                
        except Exception as e:
            print(f"[UploadTask] ❌ 更新附件失败: {str(e)}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)


@router.post("/upload-async")
async def upload_file_async(
    file: UploadFile = File(...),
    priority: str = "normal",
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    attachment_id: Optional[str] = None,
    storage_id: Optional[str] = None,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    异步上传文件到云存储（使用 AttachmentService 统一处理）

    使用 AttachmentService.process_user_upload() 统一处理：
    1. 保存文件到临时目录
    2. 创建 MessageAttachment 记录
    3. 创建 UploadTask 记录
    4. 任务 ID 入队 Redis（调度）
    5. 立即返回 task_id（不阻塞）

    请求参数（multipart/form-data）：
    - file: 要上传的文件
    - priority: 优先级 (high/normal/low，默认 normal)
    - session_id: 会话 ID（必需）
    - message_id: 消息 ID（必需）
    - attachment_id: 附件 ID（可选，如果不提供则自动生成）
    - storage_id: 云存储配置 ID（可选）

    返回：
    {
        "task_id": "task-xxx",
        "attachment_id": "att-xxx",
        "status": "pending",
        "priority": "normal",
        "queue_position": 5
    }
    """
    import time
    start_time = time.time()
    
    logger.info(f"[UploadAsync] ========== 开始处理异步上传请求 ==========")
    logger.info(f"[UploadAsync] 📥 请求参数:")
    logger.info(f"[UploadAsync]     - filename: {file.filename}")
    logger.info(f"[UploadAsync]     - content_type: {file.content_type}")
    logger.info(f"[UploadAsync]     - session_id: {session_id if session_id else 'None'}")
    logger.info(f"[UploadAsync]     - message_id: {message_id if message_id else 'None'}")
    logger.info(f"[UploadAsync]     - attachment_id: {attachment_id if attachment_id else 'None'}")
    logger.info(f"[UploadAsync]     - storage_id: {storage_id if storage_id else 'None'}")
    logger.info(f"[UploadAsync]     - priority: {priority}")
    logger.info(f"[UploadAsync]     - user_id: {user_id}")
    
    # ✅ 验证必需参数
    if not session_id or not message_id:
        logger.error(f"[UploadAsync] ❌ 验证失败: session_id 和 message_id 是必需的参数")
        raise HTTPException(
            status_code=400, 
            detail="session_id 和 message_id 是必需的参数"
        )
    logger.info(f"[UploadAsync] ✅ 参数验证通过")
    
    # ✅ 使用 AttachmentService 统一处理用户上传
    from ...services.common.attachment_service import AttachmentService
    
    # ✅ 详细日志：步骤1 - 保存文件到临时目录
    logger.info(f"[UploadAsync] 🔄 [步骤1] 保存文件到临时目录...")
    task_id = str(uuid.uuid4())
    filename_with_id = f"upload_{task_id}_{file.filename}"
    temp_path_abs = os.path.join(TEMP_DIR, filename_with_id)
    temp_path_rel = f"{get_temp_dir_relative()}/{filename_with_id}"
    
    logger.info(f"[UploadAsync]     - 临时文件路径: {temp_path_abs}")
    logger.info(f"[UploadAsync]     - 相对路径: {temp_path_rel}")
    
    file_content = await file.read()
    file_size = len(file_content)
    logger.info(f"[UploadAsync]     - 文件大小: {file_size / 1024:.2f} KB")
    
    with open(temp_path_abs, 'wb') as f:
        f.write(file_content)
    
    step1_time = (time.time() - start_time) * 1000
    logger.info(f"[UploadAsync] ✅ [步骤1] 文件已保存 (耗时: {step1_time:.2f}ms)")
    
    # ✅ 详细日志：步骤2 - 获取存储配置ID
    logger.info(f"[UploadAsync] 🔄 [步骤2] 获取存储配置ID...")
    resolved_storage_id = storage_id
    if not resolved_storage_id:
        logger.info(f"[UploadAsync]     - 未提供 storage_id，查询激活的配置...")
        active = db.query(ActiveStorage).filter(ActiveStorage.user_id == user_id).first()
        if active and active.storage_id:
            resolved_storage_id = active.storage_id
            logger.info(f"[UploadAsync]     - 找到激活的存储配置: {resolved_storage_id}")
        else:
            logger.error(f"[UploadAsync] ❌ 未设置存储配置")
            raise HTTPException(status_code=400, detail="未设置存储配置")
    else:
        logger.info(f"[UploadAsync]     - 使用提供的 storage_id: {resolved_storage_id}")
    
    # ✅ 详细日志：验证存储配置
    logger.info(f"[UploadAsync] 🔄 [步骤2] 验证存储配置...")
    user_query = UserScopedQuery(db, user_id)
    config = user_query.get(StorageConfig, resolved_storage_id)
    if not config:
        logger.error(f"[UploadAsync] ❌ 存储配置不存在或无权访问: {resolved_storage_id}")
        raise HTTPException(status_code=404, detail="存储配置不存在或无权访问")
    if not config.enabled:
        logger.error(f"[UploadAsync] ❌ 存储配置已禁用: {resolved_storage_id}")
        raise HTTPException(status_code=400, detail="存储配置已禁用")
    logger.info(f"[UploadAsync] ✅ [步骤2] 存储配置验证通过: {resolved_storage_id}")
    
    # ✅ 详细日志：步骤3 - 使用 AttachmentService 处理用户上传
    logger.info(f"[UploadAsync] 🔄 [步骤3] 调用 AttachmentService.process_user_upload()...")
    attachment_service = AttachmentService(db)
    result = await attachment_service.process_user_upload(
        file_path=temp_path_rel,  # 相对路径
        filename=file.filename,
        mime_type=file.content_type or 'application/octet-stream',
        session_id=session_id,
        message_id=message_id,
        user_id=user_id,
        storage_id=resolved_storage_id,  # ✅ 传递存储配置ID
        priority=priority  # ✅ 传递优先级
    )
    step3_time = (time.time() - start_time) * 1000
    logger.info(f"[UploadAsync] ✅ [步骤3] AttachmentService 处理完成 (耗时: {step3_time:.2f}ms)")
    logger.info(f"[UploadAsync]     - attachment_id: {result['attachment_id']}")
    logger.info(f"[UploadAsync]     - task_id: {result.get('task_id') if result.get('task_id') else 'None'}")
    logger.info(f"[UploadAsync]     - status: {result['status']}")
    
    # ✅ 详细日志：步骤4 - 如果提供了 attachment_id，更新记录（向后兼容）
    if attachment_id and attachment_id != result['attachment_id']:
        logger.info(f"[UploadAsync] 🔄 [步骤4] 更新 attachment_id (向后兼容)...")
        logger.info(f"[UploadAsync]     - 提供的 attachment_id: {attachment_id}")
        logger.info(f"[UploadAsync]     - 生成的 attachment_id: {result['attachment_id']}")
        from ...models.db_models import MessageAttachment, UploadTask
        
        attachment = db.query(MessageAttachment).filter_by(
            id=result['attachment_id']
        ).first()
        if attachment:
            # 更新 MessageAttachment.id
            attachment.id = attachment_id
            db.commit()
            
            # ✅ 新增：同步更新 UploadTask.attachment_id
            upload_task = db.query(UploadTask).filter_by(
                attachment_id=result['attachment_id']
            ).first()
            if upload_task:
                upload_task.attachment_id = attachment_id
                db.commit()
                logger.info(f"[UploadAsync] ✅ [步骤4] UploadTask.attachment_id 已同步更新")
            else:
                logger.warning(f"[UploadAsync] ⚠️ [步骤4] 未找到 UploadTask 记录，跳过同步更新")
            
            result['attachment_id'] = attachment_id
            logger.info(f"[UploadAsync] ✅ [步骤4] attachment_id 已更新")
        else:
            logger.warning(f"[UploadAsync] ⚠️ [步骤4] 未找到附件记录，跳过更新")
    else:
        logger.info(f"[UploadAsync] ⏭️ [步骤4] 跳过 attachment_id 更新（未提供或已匹配）")
    
    # 注意：AttachmentService._submit_upload_task() 已经入队 Redis
    # 这里不需要再次入队，只需要返回结果
    queue_position = 0  # AttachmentService 已入队，位置由 Worker Pool 管理
    enqueue_error = None
    
    total_time = (time.time() - start_time) * 1000
    logger.info(f"[UploadAsync] ========== 异步上传请求处理完成 (总耗时: {total_time:.2f}ms) ==========")
    logger.info(f"[UploadAsync]     - attachment_id: {result['attachment_id']}")
    logger.info(f"[UploadAsync]     - task_id: {result.get('task_id') if result.get('task_id') else 'None'}")
    logger.info(f"[UploadAsync]     - status: {result['status']}")
    
    return {
        "task_id": result.get('task_id'),
        "attachment_id": result['attachment_id'],
        "status": result['status'],
        "priority": priority,
        "queue_position": queue_position,
        "enqueued": queue_position != -1,
        "enqueue_error": enqueue_error
    }


@router.post("/upload-from-url")
async def upload_from_url(
    data: dict,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    从 URL 下载图片并上传到云存储（异步）
    
    请求参数：
    {
        "url": "https://dashscope.aliyuncs.com/...",  # DashScope 临时 URL
        "filename": "expanded-1234567890.png",         # 文件名
        "session_id": "session-xxx",                   # 会话 ID（用于更新数据库）
        "message_id": "msg-xxx",                       # 消息 ID
        "attachment_id": "att-xxx",                    # 附件 ID
        "storage_id": "storage-xxx"                    # 云存储配置 ID（可选）
    }
    
    返回：
    {
        "task_id": "task-xxx",
        "status": "pending",
        "message": "上传任务已创建"
    }
    """
    user_query = UserScopedQuery(db, user_id)

    storage_id = data.get('storage_id')
    resolved_storage_id = storage_id
    if storage_id:
        config = user_query.get(StorageConfig, storage_id)
    else:
        active = db.query(ActiveStorage).filter(ActiveStorage.user_id == user_id).first()
        if not active or not active.storage_id:
            raise HTTPException(status_code=400, detail="未设置存储配置")
        resolved_storage_id = active.storage_id
        config = user_query.get(StorageConfig, resolved_storage_id)

    if not config:
        raise HTTPException(status_code=404, detail="存储配置不存在或无权访问")

    if not config.enabled:
        raise HTTPException(status_code=400, detail="存储配置已禁用")

    # 创建上传任务
    task_id = str(uuid.uuid4())
    priority = data.get("priority", "normal")

    task = UploadTask(
        id=task_id,
        session_id=data.get('session_id'),
        message_id=data.get('message_id'),
        attachment_id=data.get('attachment_id'),
        source_url=data['url'],
        filename=data['filename'],
        storage_id=resolved_storage_id,
        priority=priority,
        retry_count=0,
        status='pending',
        created_at=int(datetime.now().timestamp() * 1000)
    )

    db.add(task)
    db.commit()

    # 入队任务到 Redis
    enqueue_error: str | None = None
    queue_position: int = -1

    try:
        if redis_queue._redis is None:
            await redis_queue.connect()
        queue_position = await redis_queue.enqueue(task_id, priority)
        await redis_queue.append_task_log(
            task_id,
            level="info",
            message=f"enqueued to redis (position={queue_position})",
            source="api",
        )
    except Exception as e:
        enqueue_error = f"Redis 入队失败: {e}"
        try:
            task.error_message = enqueue_error
            db.commit()
        except Exception:
            db.rollback()
        queue_position = -1

    return {
        "task_id": task_id,
        "status": "pending",
        "priority": priority,
        "queue_position": queue_position,
        "enqueued": queue_position != -1,
        "enqueue_error": enqueue_error
    }


@router.get("/upload-status/{task_id}")
async def get_upload_status(task_id: str, db: Session = Depends(get_db)):
    """
    查询上传任务状态

    返回：
    {
        "id": "task-xxx",
        "status": "completed",
        "targetUrl": "https://cdn.example.com/xxx.png",
        "errorMessage": null,
        "createdAt": 1234567890000,
        "completedAt": 1234567890000
    }
    """
    task = db.query(UploadTask).filter(UploadTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="上传任务不存在")

    return task.to_dict()


@router.get("/worker-pool/health")
async def get_worker_pool_health(db: Session = Depends(get_db)):
    """
    获取 Worker 池健康状态

    返回：
    {
        "available": true,
        "running": true,
        "num_workers": 5,
        "redis_connected": true,
        "pending_tasks_count": 3,
        "redis_queue_length": 3
    }
    """
    try:
        from ...services.common.upload_worker_pool import worker_pool, WORKER_POOL_AVAILABLE
        from ...services.common.redis_queue_service import redis_queue
    except ImportError:
        return {
            "available": False,
            "running": False,
            "num_workers": 0,
            "redis_connected": False,
            "pending_tasks_count": 0,
            "redis_queue_length": 0,
            "error": "Worker pool module not available"
        }

    health = {
        "available": WORKER_POOL_AVAILABLE,
        "running": False,
        "num_workers": 0,
        "redis_connected": False,
        "pending_tasks_count": 0,
        "redis_queue_length": 0
    }

    if WORKER_POOL_AVAILABLE:
        health["running"] = worker_pool._running
        health["num_workers"] = len(worker_pool._workers)

        # 检查 Redis 连接
        try:
            health["redis_connected"] = redis_queue._redis is not None
            if health["redis_connected"]:
                # 获取队列长度
                stats = await redis_queue.get_stats()
                health["redis_queue_length"] = stats.get("total_enqueued", 0) - stats.get("total_dequeued", 0)
        except Exception:
            health["redis_connected"] = False

        # 获取 pending 任务数量
        try:
            health["pending_tasks_count"] = db.query(UploadTask).filter(
                UploadTask.status == 'pending'
            ).count()
        except Exception:
            pass

    return health


@router.get("/upload-task-db/{task_id}")
async def get_upload_task_db(task_id: str, response: Response, db: Session = Depends(get_db)):
    """
    直接从数据库读取 upload_tasks 行（用于排查“看不到更新/必须重启才刷新”）。

    - 不经过 ORM 对象缓存（使用 SQL 读取）
    - 返回 server 信息用于确认命中的是哪个后端进程
    """
    response.headers["Cache-Control"] = "no-store"

    row = (
        db.execute(
            text(
                """
                SELECT
                  id,
                  status,
                  filename,
                  priority,
                  retry_count,
                  source_url,
                  source_file_path,
                  target_url,
                  error_message,
                  created_at,
                  completed_at
                FROM upload_tasks
                WHERE id = :id
                """
            ),
            {"id": task_id},
        )
        .mappings()
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="上传任务不存在")

    return {
        "task": dict(row),
        "server": {
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "module_file": __file__,
        },
    }


@router.get("/upload-logs/{task_id}")
async def get_upload_logs(task_id: str, tail: int = 200):
    """获取上传任务日志（来自 Redis）。"""
    try:
        if redis_queue._redis is None:
            await redis_queue.connect()
        logs = await redis_queue.get_task_logs(task_id, tail=tail)
        return {"task_id": task_id, "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"获取任务日志失败: {e}")


@router.post("/retry-upload/{task_id}")
async def retry_upload(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    重试失败的上传任务（Redis 队列）

    返回：
    {
        "task_id": "task-xxx",
        "status": "pending",
        "queue_position": 5
    }
    """
    task = db.query(UploadTask).filter(UploadTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="上传任务不存在")

    if task.status not in ['failed', 'completed']:
        raise HTTPException(status_code=400, detail="只能重试失败的任务")

    # 重置任务状态
    task.status = 'pending'
    task.error_message = None
    task.target_url = None
    task.completed_at = None
    db.commit()

    # 重新入队 Redis（低优先级）
    queue_position = await redis_queue.enqueue(task_id, 'low')

    return {
        "task_id": task_id,
        "status": "pending",
        "queue_position": queue_position
    }


@router.get("/download")
async def download_image(url: str):
    """
    图片下载代理接口
    
    解决跨域问题，后端下载图片后返回给前端
    
    请求参数：
    - url: 图片 URL（云存储地址）
    
    返回：
    - 图片文件流
    """
    from fastapi.responses import StreamingResponse
    import io
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # 获取 Content-Type
            content_type = response.headers.get('content-type', 'image/png')
            
            # 从 URL 提取文件名
            filename = url.split('/')[-1].split('?')[0] or f'image-{uuid.uuid4().hex[:8]}.png'
            
            return StreamingResponse(
                io.BytesIO(response.content),
                media_type=content_type,
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")
