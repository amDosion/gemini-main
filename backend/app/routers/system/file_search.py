"""
File Search 路由
处理文件上传到 Google File Search Store 的逻辑
"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from typing import Optional, List
import logging
import asyncio
import tempfile
import os
import mimetypes

from ...middleware.case_conversion_middleware import case_conversion_options

router = APIRouter(prefix="/api/file-search", tags=["file-search"])
logger = logging.getLogger(__name__)


def get_mime_type(filename: str, content_type: Optional[str]) -> str:
    """
    获取有效的 MIME type
    
    Args:
        filename: 文件名
        content_type: 上传文件的 content_type
        
    Returns:
        有效的 MIME type 字符串（格式: type/subtype）
    """
    # 如果提供了 content_type 且格式正确，直接使用
    if content_type and '/' in content_type:
        # 移除可能的参数（如 charset）
        mime = content_type.split(';')[0].strip()
        if mime and '/' in mime:
            return mime
    
    # 尝试从文件扩展名推断
    guessed_type, _ = mimetypes.guess_type(filename)
    if guessed_type:
        return guessed_type
    
    # 根据文件扩展名设置常见类型
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        '.txt': 'text/plain',
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.csv': 'text/csv',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.html': 'text/html',
        '.md': 'text/markdown',
    }
    
    return mime_map.get(ext, 'application/octet-stream')


@router.post("/upload")
@case_conversion_options(skip_request_body=True)
async def upload_to_file_search(
    file: UploadFile = File(...),
    store_name: Optional[str] = Form(None),
    authorization: str = Header(None),
):
    """
    上传文件到 Google File Search Store
    
    Args:
        file: 上传的文件
        store_name: File Search Store 名称（可选，不提供则使用默认 store）
        authorization: Bearer token (Google API Key)
        
    Returns:
        {
            "file_search_store_name": "fileSearchStores/xxx",
            "file_name": "files/xxx",
            "status": "active"
        }
    """
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    
    api_key = authorization.split(' ')[1]
    
    try:
        from google import genai
        
        # 初始化 GenAI 客户端
        client = genai.Client(api_key=api_key)
        
        # 1. 获取或创建 File Search Store
        if not store_name:
            # 使用默认 store 名称
            default_store_name = "deep-research-documents"
            
            try:
                # 尝试获取现有 store
                file_search_store = client.file_search_stores.get(
                    name=f"fileSearchStores/{default_store_name}"
                )
                logger.info(f"Using existing store: {file_search_store.name}")
            except Exception:
                # Store 不存在，创建新的
                file_search_store = client.file_search_stores.create(
                    config={'display_name': default_store_name}
                )
                logger.info(f"Created new store: {file_search_store.name}")
        else:
            file_search_store = client.file_search_stores.get(name=store_name)

        # 2. 读取文件内容并保存到临时文件
        file_content = await file.read()

        # 创建临时文件
        suffix = os.path.splitext(file.filename)[1] or '.tmp'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        # 获取正确的 MIME type
        mime_type = get_mime_type(file.filename, file.content_type)
        logger.info(f"文件 {file.filename} 的 MIME type: {mime_type}")

        try:
            # 3. 先上传文件到 Files API
            logger.info(f"上传文件到 Files API: {file.filename}")
            uploaded_file = client.files.upload(path=temp_file_path)
            logger.info(f"文件已上传到 Files API: {uploaded_file.name}")
            
            # 4. 将已上传的文件添加到 File Search Store
            logger.info(f"将文件添加到 File Search Store: {file_search_store.name}")
            operation = client.file_search_stores.upload_to_file_search_store(
                name=file_search_store.name,
                file=uploaded_file
            )

            logger.info(f"Upload operation started: {operation.name}")

            # 4. 等待操作完成（最多 60 秒）
            max_wait = 60
            elapsed = 0
            while not operation.done and elapsed < max_wait:
                await asyncio.sleep(2)
                elapsed += 2
                operation = client.operations.get(operation.name)
                logger.debug(f"Waiting for upload completion... ({elapsed}s)")

            if not operation.done:
                raise HTTPException(
                    status_code=408,
                    detail="File upload timeout - file may still be processing"
                )

            # 5. 获取上传的文件信息
            # operation.response 包含上传结果
            response_data = operation.response

            logger.info(f"File uploaded successfully to store: {file_search_store.name}")

            return {
                "file_search_store_name": file_search_store.name,
                "file_name": file.filename,
                "status": "active",
                "operation": operation.name
            }

        finally:
            # 清理临时文件
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    logger.debug(f"Temporary file deleted: {temp_file_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to delete temporary file: {cleanup_error}")

    except Exception as e:
        logger.error(f"Failed to upload file: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"File upload failed: {str(e)}"
        )


@router.get("/stores")
async def list_file_search_stores(
    authorization: str = Header(None),
):
    """列出所有 File Search Stores"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    
    api_key = authorization.split(' ')[1]
    
    try:
        from google import genai
        
        client = genai.Client(api_key=api_key)
        
        stores = []
        for store in client.file_search_stores.list():
            stores.append({
                "name": store.name,
                "display_name": store.display_name,
                "create_time": store.create_time,
                "update_time": store.update_time
            })
        
        return {"stores": stores}
        
    except Exception as e:
        logger.error(f"Failed to list stores: {e}")
        raise HTTPException(status_code=500, detail=str(e))
