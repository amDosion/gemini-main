"""
云存储配置和上传路由
支持兰空图床和阿里云 OSS
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import uuid
import httpx
import os
import tempfile

from ..core.database import SessionLocal
from ..models.db_models import StorageConfig, ActiveStorage, UploadTask
from ..services.storage_service import StorageService

# 导入 Celery 任务
from app.tasks.upload_tasks import process_upload

router = APIRouter(prefix="/api/storage", tags=["storage"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== 配置管理 ====================

@router.get("/configs")
async def get_storage_configs(db: Session = Depends(get_db)):
    """获取所有存储配置"""
    configs = db.query(StorageConfig).all()
    return [config.to_dict() for config in configs]


@router.post("/configs")
async def create_storage_config(config_data: dict, db: Session = Depends(get_db)):
    """创建存储配置"""
    config = StorageConfig(
        id=config_data["id"],
        name=config_data["name"],
        provider=config_data["provider"],
        enabled=config_data.get("enabled", True),
        config=config_data["config"],
        created_at=config_data.get("createdAt", int(datetime.now().timestamp() * 1000)),
        updated_at=config_data.get("updatedAt", int(datetime.now().timestamp() * 1000))
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config.to_dict()


@router.put("/configs/{config_id}")
async def update_storage_config(config_id: str, config_data: dict, db: Session = Depends(get_db)):
    """更新存储配置"""
    config = db.query(StorageConfig).filter(StorageConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    config.name = config_data.get("name", config.name)
    config.enabled = config_data.get("enabled", config.enabled)
    config.config = config_data.get("config", config.config)
    config.updated_at = int(datetime.now().timestamp() * 1000)
    
    db.commit()
    db.refresh(config)
    return config.to_dict()


@router.delete("/configs/{config_id}")
async def delete_storage_config(config_id: str, db: Session = Depends(get_db)):
    """删除存储配置"""
    config = db.query(StorageConfig).filter(StorageConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    db.delete(config)
    db.commit()
    return {"success": True}


@router.get("/active")
async def get_active_storage(db: Session = Depends(get_db)):
    """获取当前激活的存储配置"""
    active = db.query(ActiveStorage).filter(ActiveStorage.user_id == "default").first()
    if not active or not active.storage_id:
        return {"storageId": None}
    return {"storageId": active.storage_id}


@router.post("/active/{storage_id}")
async def set_active_storage(storage_id: str, db: Session = Depends(get_db)):
    """设置当前激活的存储配置"""
    active = db.query(ActiveStorage).filter(ActiveStorage.user_id == "default").first()
    if not active:
        active = ActiveStorage(user_id="default", storage_id=storage_id)
        db.add(active)
    else:
        active.storage_id = storage_id
    
    db.commit()
    return {"success": True, "storageId": storage_id}


# ==================== 文件上传 ====================

def upload_to_active_storage(content: bytes, filename: str, content_type: str) -> dict:
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
        # 获取当前激活的存储配置
        active = db.query(ActiveStorage).filter(ActiveStorage.user_id == "default").first()
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
    db: Session = Depends(get_db)
):
    """
    上传文件到云存储
    如果不指定 storage_id，使用当前激活的配置
    """
    # 获取存储配置
    if storage_id:
        config = db.query(StorageConfig).filter(StorageConfig.id == storage_id).first()
    else:
        active = db.query(ActiveStorage).filter(ActiveStorage.user_id == "default").first()
        if not active or not active.storage_id:
            raise HTTPException(status_code=400, detail="未设置存储配置")
        config = db.query(StorageConfig).filter(StorageConfig.id == active.storage_id).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="存储配置不存在")
    
    if not config.enabled:
        raise HTTPException(status_code=400, detail="存储配置已禁用")
    
    # 读取文件内容
    file_content = await file.read()
    
    # 使用 StorageService 上传
    return await StorageService.upload_file(
        filename=file.filename,
        content=file_content,
        content_type=file.content_type,
        provider=config.provider,
        config=config.config
    )


# ==================== 异步上传任务处理（已迁移到 Celery）====================
# 所有上传任务处理逻辑已迁移到 app/tasks/upload_tasks.py
# 使用 Celery + Redis 队列管理，支持并发控制和失败重试

from ..models.db_models import ChatSession


@router.post("/upload-async")
async def upload_file_async(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    attachment_id: Optional[str] = None,
    storage_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    异步上传文件到云存储（不阻塞前端）
    使用 Celery + Redis 任务队列

    前端提交文件后立即返回，后端 Celery Worker 在后台处理上传并更新数据库

    请求参数（multipart/form-data）：
    - file: 要上传的文件
    - session_id: 会话 ID（用于更新数据库）
    - message_id: 消息 ID
    - attachment_id: 附件 ID
    - storage_id: 云存储配置 ID（可选）

    返回：
    {
        "task_id": "task-xxx",
        "celery_task_id": "celery-task-xxx",
        "status": "pending",
        "message": "上传任务已创建"
    }
    """
    # 详细日志
    print(f"[UploadAsync] 接收到上传请求:")
    print(f"  - 文件名: {file.filename}")
    print(f"  - 文件大小: {file.size if hasattr(file, 'size') else 'Unknown'}")
    print(f"  - session_id: {session_id[:8] if session_id else 'None'}...")
    print(f"  - message_id: {message_id[:8] if message_id else 'None'}...")
    print(f"  - attachment_id: {attachment_id[:8] if attachment_id else 'None'}...")

    # 保存文件到临时目录
    temp_dir = tempfile.gettempdir()
    task_id = str(uuid.uuid4())
    temp_path = os.path.join(temp_dir, f"upload_{task_id}_{file.filename}")

    try:
        file_content = await file.read()
        print(f"[UploadAsync] 读取文件内容: {len(file_content)} 字节")
        
        with open(temp_path, 'wb') as f:
            f.write(file_content)
        print(f"[UploadAsync] 文件已保存到临时目录: {temp_path}")
        
        # 验证文件是否正确保存
        if os.path.exists(temp_path):
            file_size = os.path.getsize(temp_path)
            print(f"[UploadAsync] 临时文件验证成功，大小: {file_size} 字节")
        else:
            raise Exception("临时文件保存失败")
            
    except Exception as e:
        print(f"[UploadAsync] ❌ 文件保存失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    print(f"[UploadAsync] 创建任务 ID: {task_id[:8]}...")

    # 创建上传任务记录
    try:
        task = UploadTask(
            id=task_id,
            session_id=session_id,
            message_id=message_id,
            attachment_id=attachment_id,
            source_file_path=temp_path,
            filename=file.filename,
            storage_id=storage_id,
            status='pending',
            created_at=int(datetime.now().timestamp() * 1000)
        )

        db.add(task)
        db.commit()
        print(f"[UploadAsync] ✅ 任务记录已保存到数据库: {task_id[:8]}...")
        
    except Exception as e:
        print(f"[UploadAsync] ❌ 数据库保存失败: {e}")
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"数据库保存失败: {str(e)}")

    # ✅ 使用 Celery 提交任务到 Redis 队列
    try:
        print(f"[UploadAsync] 提交任务到 Celery 队列: {task_id[:8]}...")
        print(f"[UploadAsync] 使用任务函数: {process_upload}")
        print(f"[UploadAsync] 任务参数: task_id={task_id}")
        
        # 检查 Celery 应用状态
        from app.core.celery_app import celery_app
        print(f"[UploadAsync] Celery 应用状态: {celery_app}")
        print(f"[UploadAsync] Celery broker: {celery_app.conf.broker_url}")
        print(f"[UploadAsync] Celery backend: {celery_app.conf.result_backend}")
        
        celery_task = process_upload.delay(task_id)
        print(f"[UploadAsync] ✅ Celery 任务已提交，Celery Task ID: {celery_task.id}")
        print(f"[UploadAsync] 任务状态: {celery_task.status}")
        
        # 尝试获取任务信息
        try:
            task_info = celery_task.info
            print(f"[UploadAsync] 任务信息: {task_info}")
        except Exception as info_error:
            print(f"[UploadAsync] ⚠️ 无法获取任务信息: {info_error}")

        return {
            "task_id": task_id,
            "celery_task_id": celery_task.id,
            "status": "pending",
            "message": "上传任务已提交到队列"
        }
        
    except Exception as e:
        print(f"[UploadAsync] ❌ Celery 任务提交失败: {e}")
        import traceback
        print(f"[UploadAsync] 详细错误: {traceback.format_exc()}")
        
        # 清理数据库记录和临时文件
        try:
            db.delete(task)
            db.commit()
        except:
            pass
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        raise HTTPException(status_code=500, detail=f"任务提交失败: {str(e)}")

    return {
        "task_id": task_id,
        "celery_task_id": celery_task.id,
        "status": "pending",
        "message": "上传任务已提交到队列"
    }


@router.post("/upload-from-url")
async def upload_from_url(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    从 URL 下载图片并上传到云存储（异步）
    使用 Celery + Redis 任务队列

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
        "celery_task_id": "celery-task-xxx",
        "status": "pending",
        "message": "上传任务已创建"
    }
    """
    # 详细日志
    print(f"[UploadFromUrl] 接收到上传请求:")
    print(f"  - URL: {data.get('url', '')[:60]}...")
    print(f"  - filename: {data.get('filename')}")
    print(f"  - session_id: {data.get('session_id', '')[:8] if data.get('session_id') else 'None'}...")
    print(f"  - message_id: {data.get('message_id', '')[:8] if data.get('message_id') else 'None'}...")
    print(f"  - attachment_id: {data.get('attachment_id', '')[:8] if data.get('attachment_id') else 'None'}...")

    # 创建上传任务记录
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
        created_at=int(datetime.now().timestamp() * 1000)
    )

    db.add(task)
    db.commit()

    # ✅ 使用 Celery 提交任务到 Redis 队列
    print(f"[UploadFromUrl] 提交任务到 Celery 队列: {task_id[:8]}...")
    celery_task = process_upload.delay(task_id)
    print(f"[UploadFromUrl] ✅ Celery 任务已提交，Celery Task ID: {celery_task.id}")

    return {
        "task_id": task_id,
        "celery_task_id": celery_task.id,
        "status": "pending",
        "message": "上传任务已提交到队列"
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


@router.post("/retry-upload/{task_id}")
async def retry_upload(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    重试失败的上传任务
    使用 Celery + Redis 任务队列

    返回：
    {
        "task_id": "task-xxx",
        "celery_task_id": "celery-task-xxx",
        "status": "pending",
        "message": "重试任务已创建"
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

    # ✅ 使用 Celery 提交任务到 Redis 队列
    print(f"[RetryUpload] 重新提交任务到 Celery 队列: {task_id[:8]}...")
    celery_task = process_upload.delay(task_id)
    print(f"[RetryUpload] ✅ Celery 任务已提交，Celery Task ID: {celery_task.id}")

    return {
        "task_id": task_id,
        "celery_task_id": celery_task.id,
        "status": "pending",
        "message": "重试任务已提交到队列"
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
