"""
Celery 上传任务
负责异步处理文件上传到云存储
"""
import os
import httpx
import tempfile
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified
import copy

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.db_models import UploadTask, StorageConfig, ActiveStorage, ChatSession


@celery_app.task(bind=True, name='app.tasks.upload_tasks.process_upload')
def process_upload(self, task_id: str):
    """
    处理文件上传任务（Celery 任务）

    支持两种模式：
    1. 从本地文件上传（source_file_path 存在）
    2. 从 URL 下载后上传（source_url 存在）

    上传完成后自动更新数据库中的会话消息

    参数：
    - task_id: 上传任务 ID
    """
    # 创建独立的数据库会话
    db = SessionLocal()

    try:
        # 1. 获取任务
        task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
        if not task:
            print(f"[Celery] 任务不存在: {task_id}")
            return {'success': False, 'error': '任务不存在'}

        # 详细日志
        print(f"[Celery] 开始处理任务: {task_id[:8]}...")
        print(f"  - 文件名: {task.filename}")
        print(f"  - session_id: {task.session_id[:8] if task.session_id else 'None'}...")
        print(f"  - message_id: {task.message_id[:8] if task.message_id else 'None'}...")
        print(f"  - attachment_id: {task.attachment_id[:8] if task.attachment_id else 'None'}...")

        # 2. 更新状态为 uploading
        task.status = 'uploading'
        db.commit()

        # 更新 Celery 任务状态
        self.update_state(state='PROGRESS', meta={'status': 'uploading'})

        # 3. 获取存储配置
        if task.storage_id:
            config = db.query(StorageConfig).filter(StorageConfig.id == task.storage_id).first()
        else:
            active = db.query(ActiveStorage).filter(ActiveStorage.user_id == "default").first()
            if not active or not active.storage_id:
                raise Exception("未设置存储配置")
            config = db.query(StorageConfig).filter(StorageConfig.id == active.storage_id).first()

        if not config or not config.enabled:
            raise Exception("存储配置不可用")
        
        # ⚠️ 重要：解密配置中的敏感字段（accessKeyId, accessKeySecret 等）
        # 因为前端保存时使用 encrypt_config() 加密，后端使用时必须解密
        try:
            from app.core.encryption import decrypt_config
            decrypted_config_dict = decrypt_config(config.config)
            config.config = decrypted_config_dict
            print(f"[Celery] 已解密存储配置: {config.id} (provider={config.provider})")
        except Exception as e:
            print(f"[Celery] 解密存储配置失败: {e}")
            # 如果解密失败，可能是未加密的历史数据，继续使用原配置
            print(f"[Celery] 使用未解密的配置（可能是历史数据）: {config.id}")

        # 4. 获取图片内容
        image_content = None
        temp_path = None

        if task.source_file_path and os.path.exists(task.source_file_path):
            # 模式 1: 从本地文件读取
            print(f"[Celery] 读取本地文件: {task.source_file_path}")
            with open(task.source_file_path, 'rb') as f:
                image_content = f.read()
            temp_path = task.source_file_path

        elif task.source_url:
            # 模式 2: 从 URL 下载（同步方式）
            print(f"[Celery] 下载图片: {task.source_url[:60]}...")

            # 使用 httpx 同步客户端下载
            import httpx
            with httpx.Client(timeout=30.0) as client:
                response = client.get(task.source_url)
                response.raise_for_status()
                image_content = response.content

            # 保存到临时文件
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"upload_{task_id}_{task.filename}")
            with open(temp_path, 'wb') as f:
                f.write(image_content)
            print(f"[Celery] 临时文件: {temp_path}")

        else:
            raise Exception("没有可用的图片来源")

        # 5. 上传到云存储（使用同步方式）
        print(f"[Celery] 上传到云存储: {config.provider}")

        # 由于 StorageService.upload_file 是异步的，我们需要使用同步版本
        # 直接调用同步上传函数
        from app.routers.storage import upload_to_lsky_sync

        result = upload_to_lsky_sync(
            filename=task.filename,
            content=image_content,
            content_type='image/png',
            config=config.config
        )

        # 6. 删除临时文件
        if temp_path and os.path.exists(temp_path) and task.source_url:
            # 只删除从 URL 下载的临时文件，不删除前端上传的文件
            try:
                os.remove(temp_path)
                print(f"[Celery] 临时文件已删除: {temp_path}")
            except Exception as e:
                print(f"[Celery] 删除临时文件失败: {e}")

        # 7. 更新任务状态
        if result.get('success'):
            task.status = 'completed'
            task.target_url = result.get('url')
            task.completed_at = int(datetime.now().timestamp() * 1000)
            db.commit()
            print(f"[Celery] 上传成功: {task.target_url}")

            # 8. 更新数据库中的会话消息
            if task.session_id and task.message_id and task.attachment_id:
                try:
                    update_session_attachment_url_sync(
                        db,
                        task.session_id,
                        task.message_id,
                        task.attachment_id,
                        task.target_url
                    )
                except Exception as e:
                    print(f"[Celery] ⚠️ 更新会话附件 URL 失败（任务已完成）: {e}")

            return {
                'success': True,
                'url': task.target_url,
                'task_id': task_id
            }
        else:
            task.status = 'failed'
            task.error_message = result.get('error', '上传失败')
            db.commit()
            print(f"[Celery] 上传失败: {task.error_message}")

            return {
                'success': False,
                'error': task.error_message,
                'task_id': task_id
            }

    except Exception as e:
        print(f"[Celery] 任务失败: {str(e)}")
        import traceback
        traceback.print_exc()

        try:
            task = db.query(UploadTask).filter(UploadTask.id == task_id).first()
            if task:
                task.status = 'failed'
                task.error_message = str(e)
                db.commit()
        except:
            pass

        return {
            'success': False,
            'error': str(e),
            'task_id': task_id
        }

    finally:
        db.close()


def update_session_attachment_url_sync(
    db,
    session_id: str,
    message_id: str,
    attachment_id: str,
    url: str,
    max_retries: int = 10,
    retry_delay: float = 2.0
):
    """
    更新会话中指定附件的 URL（同步版本，带重试机制）

    由于前端保存消息和提交上传任务是并行的，可能存在竞争条件，
    所以需要重试机制来等待消息保存完成
    """
    import time

    print(f"[Celery] 开始更新附件 URL: session={session_id[:8]}..., msg={message_id[:8]}..., att={attachment_id[:8]}...")

    for attempt in range(max_retries):
        try:
            # 刷新数据库连接，获取最新数据
            db.expire_all()

            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not session:
                print(f"[Celery] 会话不存在: {session_id}")
                return

            # 深拷贝消息列表
            messages = copy.deepcopy(session.messages or [])
            updated = False

            # 调试日志
            msg_ids = [m.get('id', '')[:8] for m in messages]
            if attempt == 0:
                print(f"[Celery] 当前会话消息数: {len(messages)}, IDs: {msg_ids}")

            for msg in messages:
                if msg.get('id') == message_id and msg.get('attachments'):
                    for att in msg['attachments']:
                        if att.get('id') == attachment_id:
                            att['url'] = url
                            att['uploadStatus'] = 'completed'
                            att.pop('tempUrl', None)
                            att.pop('file', None)
                            updated = True
                            print(f"[Celery] ✅ 找到附件，更新 URL: {url[:60]}...")
                            break
                if updated:
                    break

            if updated:
                # 重新赋值并标记字段已修改
                session.messages = messages
                flag_modified(session, 'messages')
                db.commit()
                print(f"[Celery] ✅ 会话已更新: {session_id[:8]}..., 附件: {attachment_id[:8]}...")
                return
            else:
                # 未找到附件，等待后重试
                if attempt < max_retries - 1:
                    print(f"[Celery] ⏳ 未找到附件，等待重试 ({attempt + 1}/{max_retries}): {attachment_id[:8]}...")
                    time.sleep(retry_delay)
                else:
                    print(f"[Celery] ❌ 重试 {max_retries} 次后仍未找到附件: {attachment_id[:8]}...")

        except Exception as e:
            print(f"[Celery] ❌ 更新会话失败: {str(e)}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
