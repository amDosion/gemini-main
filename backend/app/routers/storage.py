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


# ==================== 异步上传任务处理 ====================

from ..models.db_models import ChatSession

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
            print(f"[UploadTask] 任务不存在: {task_id}")
            return
        
        # ✅ 详细日志：确认任务数据
        print(f"[UploadTask] 开始处理任务: {task_id}")
        print(f"  - 文件名: {task.filename}")
        print(f"  - session_id: {task.session_id[:8] if task.session_id else 'None'}...")
        print(f"  - message_id: {task.message_id[:8] if task.message_id else 'None'}...")
        print(f"  - attachment_id: {task.attachment_id[:8] if task.attachment_id else 'None'}...")
        
        # 1. 更新状态为 uploading
        task.status = 'uploading'
        db.commit()
        
        # 2. 获取存储配置
        if task.storage_id:
            config = db.query(StorageConfig).filter(StorageConfig.id == task.storage_id).first()
        else:
            active = db.query(ActiveStorage).filter(ActiveStorage.user_id == "default").first()
            if not active or not active.storage_id:
                raise Exception("未设置存储配置")
            config = db.query(StorageConfig).filter(StorageConfig.id == active.storage_id).first()
        
        if not config or not config.enabled:
            raise Exception("存储配置不可用")
        
        # 3. 获取图片内容
        image_content = None
        temp_path = None
        
        if task.source_file_path and os.path.exists(task.source_file_path):
            # 模式 1: 从本地文件读取
            print(f"[UploadTask] 读取本地文件: {task.source_file_path}")
            with open(task.source_file_path, 'rb') as f:
                image_content = f.read()
            temp_path = task.source_file_path
        elif task.source_url:
            # 模式 2: 从 URL 下载
            print(f"[UploadTask] 下载图片: {task.source_url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(task.source_url)
                response.raise_for_status()
                image_content = response.content
            
            # 保存到临时文件
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"upload_{task_id}_{task.filename}")
            with open(temp_path, 'wb') as f:
                f.write(image_content)
            print(f"[UploadTask] 临时文件: {temp_path}")
        else:
            raise Exception("没有可用的图片来源")
        
        # 4. 上传到云存储
        print(f"[UploadTask] 上传到云存储: {config.provider}")
        result = await StorageService.upload_file(
            filename=task.filename,
            content=image_content,
            content_type='image/png',
            provider=config.provider,
            config=config.config
        )
        
        # 5. 删除临时文件
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                print(f"[UploadTask] 临时文件已删除: {temp_path}")
            except Exception as e:
                print(f"[UploadTask] 删除临时文件失败: {e}")
        
        # 6. 更新任务状态
        if result.get('success'):
            task.status = 'completed'
            task.target_url = result.get('url')
            task.completed_at = int(datetime.now().timestamp() * 1000)
            db.commit()  # ✅ 先提交任务状态，确保上传成功被记录
            print(f"[UploadTask] 上传成功: {task.target_url}")
            
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
                    print(f"[UploadTask] ⚠️ 更新会话附件 URL 失败（任务已完成）: {e}")
        else:
            task.status = 'failed'
            task.error_message = result.get('error', '上传失败')
            db.commit()
            print(f"[UploadTask] 上传失败: {task.error_message}")
        
    except Exception as e:
        print(f"[UploadTask] 任务失败: {str(e)}")
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
    更新会话中指定附件的 URL（带重试机制）
    
    注意：SQLAlchemy 的 JSON 字段在原地修改时不会自动检测变化，
    需要使用 flag_modified() 或重新赋值来触发更新
    
    由于前端保存消息和提交上传任务是并行的，可能存在竞争条件，
    所以需要重试机制来等待消息保存完成
    
    参数：
    - max_retries: 最大重试次数（默认10次）
    - retry_delay: 每次重试间隔（默认2秒，总等待时间最长20秒）
    """
    from sqlalchemy.orm.attributes import flag_modified
    import copy
    import asyncio
    
    print(f"[UploadTask] 开始更新附件 URL: session={session_id[:8]}..., msg={message_id[:8]}..., att={attachment_id[:8]}...")
    
    for attempt in range(max_retries):
        try:
            # 刷新数据库连接，获取最新数据
            db.expire_all()
            
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not session:
                print(f"[UploadTask] 会话不存在: {session_id}")
                return
            
            # ✅ 深拷贝消息列表，避免原地修改检测问题
            messages = copy.deepcopy(session.messages or [])
            updated = False
            
            # 调试：打印当前消息数量和 ID
            msg_ids = [m.get('id', '')[:8] for m in messages]
            if attempt == 0:
                print(f"[UploadTask] 当前会话消息数: {len(messages)}, IDs: {msg_ids}")
            
            for msg in messages:
                if msg.get('id') == message_id and msg.get('attachments'):
                    for att in msg['attachments']:
                        if att.get('id') == attachment_id:
                            att['url'] = url
                            att['uploadStatus'] = 'completed'
                            att.pop('tempUrl', None)
                            att.pop('file', None)
                            updated = True
                            print(f"[UploadTask] ✅ 找到附件，更新 URL: {url[:60]}...")
                            break
                if updated:
                    break
            
            if updated:
                # ✅ 重新赋值并标记字段已修改
                session.messages = messages
                flag_modified(session, 'messages')
                db.commit()
                print(f"[UploadTask] ✅ 会话已更新: {session_id[:8]}..., 附件: {attachment_id[:8]}...")
                return  # 成功，退出
            else:
                # 未找到附件，可能是消息还没保存到数据库，等待后重试
                if attempt < max_retries - 1:
                    print(f"[UploadTask] ⏳ 未找到附件，等待重试 ({attempt + 1}/{max_retries}): {attachment_id[:8]}...")
                    await asyncio.sleep(retry_delay)
                else:
                    print(f"[UploadTask] ❌ 重试 {max_retries} 次后仍未找到附件: {attachment_id[:8]}... (消息ID: {message_id[:8]}...)")
                    print(f"[UploadTask] ❌ 请检查前端是否正确保存了消息到数据库")
                
        except Exception as e:
            print(f"[UploadTask] ❌ 更新会话失败: {str(e)}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            # ✅ 不再抛出异常，让调用者决定如何处理


@router.post("/upload-async")
async def upload_file_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    attachment_id: Optional[str] = None,
    storage_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    异步上传文件到云存储（不阻塞前端）
    
    前端提交文件后立即返回，后端在后台处理上传并更新数据库
    
    请求参数（multipart/form-data）：
    - file: 要上传的文件
    - session_id: 会话 ID（用于更新数据库）
    - message_id: 消息 ID
    - attachment_id: 附件 ID
    - storage_id: 云存储配置 ID（可选）
    
    返回：
    {
        "task_id": "task-xxx",
        "status": "pending",
        "message": "上传任务已创建"
    }
    """
    # ✅ 详细日志：记录接收到的所有参数
    print(f"[UploadAsync] 接收到上传请求:")
    print(f"  - 文件名: {file.filename}")
    print(f"  - session_id: {session_id[:8] if session_id else 'None'}...")
    print(f"  - message_id: {message_id[:8] if message_id else 'None'}...")
    print(f"  - attachment_id: {attachment_id[:8] if attachment_id else 'None'}...")
    
    # 保存文件到临时目录
    temp_dir = tempfile.gettempdir()
    task_id = str(uuid.uuid4())
    temp_path = os.path.join(temp_dir, f"upload_{task_id}_{file.filename}")
    
    file_content = await file.read()
    with open(temp_path, 'wb') as f:
        f.write(file_content)
    
    print(f"[UploadAsync] 文件已保存到临时目录: {temp_path}")
    print(f"[UploadAsync] 创建任务 ID: {task_id[:8]}...")
    
    # 创建上传任务
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
    
    # 添加后台任务
    background_tasks.add_task(process_upload_task, task_id, db)
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "上传任务已创建"
    }


@router.post("/upload-from-url")
async def upload_from_url(
    data: dict,
    background_tasks: BackgroundTasks,
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
    # 创建上传任务
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
    
    # 添加后台任务
    background_tasks.add_task(process_upload_task, task_id, db)
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "上传任务已创建"
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    重试失败的上传任务
    
    返回：
    {
        "task_id": "task-xxx",
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
    
    # 添加后台任务
    background_tasks.add_task(process_upload_task, task_id, db)
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "重试任务已创建"
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
