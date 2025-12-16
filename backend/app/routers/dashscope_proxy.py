"""
DashScope API 代理路由
用于转发前端请求到阿里云 DashScope API，解决 CORS 跨域问题
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, JSONResponse
import httpx
from typing import Optional

router = APIRouter(prefix="/api/dashscope", tags=["dashscope-proxy"])

# DashScope 官方 API 地址
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com"


@router.post("/api/v1/files")
async def upload_file_to_dashscope(request: Request):
    """
    处理文件上传到 DashScope OSS
    实现两步上传流程：1. 获取凭证 2. 上传到 OSS
    """
    try:
        # 获取 API Key 和表单数据
        auth_header = request.headers.get('authorization', '')
        if not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        api_key = auth_header.replace('Bearer ', '').strip()
        form_data = await request.form()
        
        # 获取文件和 purpose
        file = form_data.get('file')
        purpose = form_data.get('purpose', 'image-out-painting')
        
        if not file or not hasattr(file, 'file'):
            raise HTTPException(status_code=400, detail="No file provided")
        
        # 根据 purpose 确定 model
        model_map = {
            'image-out-painting': 'wanx-v1',
            'image-generation': 'wanx-v1',
            'image-edit': 'wanx-v1'
        }
        model_name = model_map.get(purpose, 'wanx-v1')
        
        # 步骤 1: 获取上传凭证
        async with httpx.AsyncClient(timeout=30.0) as client:
            policy_response = await client.get(
                f"{DASHSCOPE_BASE_URL}/api/v1/uploads",
                headers={'Authorization': f'Bearer {api_key}'},
                params={'action': 'getPolicy', 'model': model_name}
            )
            
            if policy_response.status_code != 200:
                raise HTTPException(
                    status_code=policy_response.status_code,
                    detail=f"Failed to get upload policy: {policy_response.text}"
                )
            
            policy_data = policy_response.json()['data']
            
            # 步骤 2: 上传文件到 OSS
            file_name = file.filename
            key = f"{policy_data['upload_dir']}/{file_name}"
            
            # 重置文件指针
            await file.seek(0)
            file_content = await file.read()
            
            # 构建 OSS 上传表单
            oss_files = {
                'key': (None, key),
                'OSSAccessKeyId': (None, policy_data['oss_access_key_id']),
                'Signature': (None, policy_data['signature']),
                'policy': (None, policy_data['policy']),
                'x-oss-object-acl': (None, policy_data['x_oss_object_acl']),
                'x-oss-forbid-overwrite': (None, policy_data['x_oss_forbid_overwrite']),
                'success_action_status': (None, '200'),
                'file': (file_name, file_content, file.content_type)
            }
            
            oss_response = await client.post(
                policy_data['upload_host'],
                files=oss_files
            )
            
            if oss_response.status_code != 200:
                raise HTTPException(
                    status_code=oss_response.status_code,
                    detail=f"Failed to upload to OSS: {oss_response.text}"
                )
            
            # 返回前端期望的格式
            # 注意：根据阿里云文档，OSS URL 格式应该是 oss://key
            # key 已经包含了完整路径，不需要再加 bucket
            oss_url = f"oss://{key}"
            
            return JSONResponse(
                content={
                    'data': {
                        'url': oss_url,
                        'file_id': key
                    },
                    'request_id': policy_data.get('request_id', '')
                },
                status_code=200
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_dashscope(path: str, request: Request):
    """
    代理所有 /api/dashscope/* 请求到 DashScope API
    
    Args:
        path: API 路径（例如：api/v1/files）
        request: FastAPI 请求对象
    
    Returns:
        代理后的响应
    """
    # 构建目标 URL
    target_url = f"{DASHSCOPE_BASE_URL}/{path}"
    
    # 构建转发的请求头
    # 注意：必须保持原始的大小写格式，特别是 X-DashScope-* 头
    headers = {}
    headers_to_skip = ['host', 'content-length', 'connection']
    
    for key, value in request.headers.items():
        if key.lower() not in headers_to_skip:
            headers[key] = value
    
    # 获取查询参数
    query_params = dict(request.query_params)
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # 根据请求方法转发
            if request.method == "GET":
                response = await client.get(
                    target_url,
                    headers=headers,
                    params=query_params
                )
            elif request.method == "POST":
                # 直接转发原始请求体，保持所有头信息（包括 multipart boundary）
                body = await request.body()
                response = await client.post(
                    target_url,
                    headers=headers,
                    params=query_params,
                    content=body
                )
            else:
                # 其他方法
                body = await request.body()
                response = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    params=query_params,
                    content=body
                )
            
            # 过滤响应头（移除可能导致问题的头）
            response_headers = {}
            for key, value in response.headers.items():
                # 跳过这些头，让 FastAPI 自动处理
                if key.lower() not in ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'keep-alive']:
                    response_headers[key] = value
            
            # 确保 content-type 正确设置
            content_type = response.headers.get('content-type', 'application/json')
            if 'content-type' not in response_headers:
                response_headers['content-type'] = content_type
            
            # 特殊处理：文件上传响应格式转换
            # DashScope 返回 {output: {url: ...}} 但前端期望 {data: {url: ...}}
            if path.endswith('/files') and request.method == "POST":
                try:
                    response_data = response.json()
                    # 转换格式：output -> data
                    if 'output' in response_data and response.status_code == 200:
                        response_data['data'] = response_data['output']
                    return JSONResponse(
                        content=response_data,
                        status_code=response.status_code,
                        headers=response_headers
                    )
                except Exception:
                    pass
            
            # 返回响应（使用 Response 而不是 JSONResponse，避免重复设置 content-length）
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=content_type
            )
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="DashScope API 请求超时")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到 DashScope API: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"代理请求失败: {str(e)}")
