"""
DashScope 临时文件上传服务

上传文件到 DashScope 的临时存储（48小时有效期）
返回 oss:// 格式的 URL，用于 DashScope API 调用

文档: https://help.aliyun.com/zh/model-studio/get-temporary-file-url

使用方式:
    from app.services.dashscope_file_upload import upload_to_dashscope, upload_bytes_to_dashscope
    
    # 方式1: 从 URL 或 base64 上传
    result = upload_to_dashscope(image_url, api_key)
    
    # 方式2: 从二进制数据上传
    result = upload_bytes_to_dashscope(image_data, "image.png", api_key)
"""
import requests
import base64
import time
from typing import Optional
from dataclasses import dataclass

# DashScope API 配置
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com"


@dataclass
class DashScopeUploadResult:
    """上传结果"""
    success: bool
    oss_url: Optional[str] = None  # oss:// 格式的 URL
    error: Optional[str] = None


def _get_upload_policy(api_key: str, model: str = "wanx-v1") -> tuple[bool, Optional[dict], Optional[str]]:
    """
    获取 DashScope OSS 上传凭证
    
    Args:
        api_key: DashScope API Key
        model: 模型名称
    
    Returns:
        (success, policy_data, error_msg)
    """
    try:
        policy_url = f"{DASHSCOPE_BASE_URL}/api/v1/uploads"
        
        response = requests.get(
            policy_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            params={
                "action": "getPolicy",
                "model": model
            },
            timeout=30
        )
        
        if response.status_code != 200:
            return False, None, f"获取上传凭证失败: {response.text}"
        
        policy_data = response.json().get("data", {})
        if not policy_data:
            return False, None, "上传凭证数据为空"
        
        return True, policy_data, None
        
    except Exception as e:
        return False, None, f"获取上传凭证异常: {str(e)}"


def _upload_to_oss(
    image_data: bytes,
    filename: str,
    policy_data: dict
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    上传文件到 OSS
    
    Args:
        image_data: 图片二进制数据
        filename: 文件名
        policy_data: 上传凭证数据
    
    Returns:
        (success, oss_url, error_msg)
    """
    try:
        key = f"{policy_data['upload_dir']}/{filename}"
        
        # 确定 Content-Type
        if filename.lower().endswith(".png"):
            content_type = "image/png"
        elif filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
            content_type = "image/jpeg"
        elif filename.lower().endswith(".webp"):
            content_type = "image/webp"
        else:
            content_type = "image/png"
        
        # 构建 multipart/form-data
        files = {
            "key": (None, key),
            "OSSAccessKeyId": (None, policy_data["oss_access_key_id"]),
            "Signature": (None, policy_data["signature"]),
            "policy": (None, policy_data["policy"]),
            "x-oss-object-acl": (None, policy_data["x_oss_object_acl"]),
            "x-oss-forbid-overwrite": (None, policy_data["x_oss_forbid_overwrite"]),
            "success_action_status": (None, "200"),
            "file": (filename, image_data, content_type)
        }
        
        response = requests.post(
            policy_data["upload_host"],
            files=files,
            timeout=60
        )
        
        if response.status_code != 200:
            return False, None, f"上传失败: {response.text}"
        
        oss_url = f"oss://{key}"
        return True, oss_url, None
        
    except Exception as e:
        return False, None, f"上传异常: {str(e)}"


def upload_bytes_to_dashscope(
    image_data: bytes,
    filename: str,
    api_key: str,
    model: str = "wanx-v1"
) -> DashScopeUploadResult:
    """
    上传二进制图片数据到 DashScope 临时存储
    
    Args:
        image_data: 图片二进制数据
        filename: 文件名（用于确定文件类型）
        api_key: DashScope API Key
        model: 模型名称（必须与后续 API 调用使用的模型匹配）
    
    Returns:
        DashScopeUploadResult: 包含 oss:// URL 的上传结果
    """
    print(f"[DashScope Upload] 开始上传二进制数据: {len(image_data)} bytes")
    
    # 1. 获取上传凭证
    success, policy_data, error = _get_upload_policy(api_key, model)
    if not success:
        print(f"[DashScope Upload] {error}")
        return DashScopeUploadResult(success=False, error=error)
    
    print("[DashScope Upload] ✅ 获取上传凭证成功")
    
    # 2. 上传到 OSS
    success, oss_url, error = _upload_to_oss(image_data, filename, policy_data)
    if not success:
        print(f"[DashScope Upload] {error}")
        return DashScopeUploadResult(success=False, error=error)
    
    print(f"[DashScope Upload] ✅ 上传成功: {oss_url}")
    print("[DashScope Upload] ⏱️  有效期 48 小时")
    
    return DashScopeUploadResult(success=True, oss_url=oss_url)


def upload_to_dashscope(
    image_url: str,
    api_key: str,
    model: str = "wanx-v1"
) -> DashScopeUploadResult:
    """
    上传图片到 DashScope 临时存储
    
    Args:
        image_url: 图片 URL 或 base64 数据 URL
        api_key: DashScope API Key
        model: 模型名称（必须与后续 API 调用使用的模型匹配）
    
    Returns:
        DashScopeUploadResult: 包含 oss:// URL 的上传结果
    """
    try:
        print("[DashScope Upload] 开始上传到临时存储...")
        print(f"[DashScope Upload] 模型: {model}")
        
        # 步骤 1: 获取上传凭证
        print("[DashScope Upload] 步骤 1: 获取上传凭证...")
        policy_url = f"{DASHSCOPE_BASE_URL}/api/v1/uploads"
        
        policy_response = requests.get(
            policy_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            params={
                "action": "getPolicy",
                "model": model
            },
            timeout=30
        )
        
        if policy_response.status_code != 200:
            error_text = policy_response.text
            print(f"[DashScope Upload] 获取凭证失败: {error_text}")
            return DashScopeUploadResult(
                success=False,
                error=f"获取上传凭证失败: {error_text}"
            )
        
        policy_data = policy_response.json().get("data", {})
        if not policy_data:
            return DashScopeUploadResult(
                success=False,
                error="上传凭证数据为空"
            )
        
        print("[DashScope Upload] ✅ 获取上传凭证成功")
        
        # 步骤 2: 转换图片为二进制数据
        print("[DashScope Upload] 步骤 2: 转换图片为二进制数据...")
        
        if image_url.startswith("data:"):
            # Base64 数据 URL
            # 格式: data:image/jpeg;base64,/9j/4AAQ...
            try:
                header, base64_data = image_url.split(",", 1)
                mime_type = header.split(":")[1].split(";")[0] if ":" in header else "image/jpeg"
                image_data = base64.b64decode(base64_data)
                extension = mime_type.split("/")[1] if "/" in mime_type else "jpg"
                file_name = f"expansion-{int(time.time() * 1000)}.{extension}"
            except Exception as e:
                return DashScopeUploadResult(
                    success=False,
                    error=f"解析 base64 数据失败: {str(e)}"
                )
        else:
            # URL - 下载图片
            try:
                image_response = requests.get(image_url, timeout=30)
                if image_response.status_code != 200:
                    return DashScopeUploadResult(
                        success=False,
                        error=f"下载图片失败: HTTP {image_response.status_code}"
                    )
                image_data = image_response.content
                file_name = f"expansion-{int(time.time() * 1000)}.jpg"
            except Exception as e:
                return DashScopeUploadResult(
                    success=False,
                    error=f"下载图片失败: {str(e)}"
                )
        
        print(f"[DashScope Upload] ✅ 图片转换完成: {len(image_data)} bytes")
        
        # 步骤 3: 上传到 OSS
        print("[DashScope Upload] 步骤 3: 上传到 OSS...")
        key = f"{policy_data['upload_dir']}/{file_name}"
        
        # 确定 Content-Type
        if file_name.lower().endswith(".png"):
            content_type = "image/png"
        elif file_name.lower().endswith(".jpg") or file_name.lower().endswith(".jpeg"):
            content_type = "image/jpeg"
        else:
            content_type = "image/png"
        
        # 构建 multipart/form-data
        files = {
            "key": (None, key),
            "OSSAccessKeyId": (None, policy_data["oss_access_key_id"]),
            "Signature": (None, policy_data["signature"]),
            "policy": (None, policy_data["policy"]),
            "x-oss-object-acl": (None, policy_data["x_oss_object_acl"]),
            "x-oss-forbid-overwrite": (None, policy_data["x_oss_forbid_overwrite"]),
            "success_action_status": (None, "200"),
            "file": (file_name, image_data, content_type)
        }
        
        upload_response = requests.post(
            policy_data["upload_host"],
            files=files,
            timeout=60
        )
        
        if upload_response.status_code != 200:
            error_text = upload_response.text
            print(f"[DashScope Upload] 上传失败: {error_text}")
            return DashScopeUploadResult(
                success=False,
                error=f"上传失败: {error_text}"
            )
        
        oss_url = f"oss://{key}"
        print("[DashScope Upload] ✅ 上传成功!")
        print(f"[DashScope Upload] OSS URL: {oss_url}")
        print("[DashScope Upload] ⏱️  有效期 48 小时")
        
        return DashScopeUploadResult(
            success=True,
            oss_url=oss_url
        )
        
    except Exception as e:
        print(f"[DashScope Upload] 错误: {str(e)}")
        return DashScopeUploadResult(
            success=False,
            error=str(e)
        )
