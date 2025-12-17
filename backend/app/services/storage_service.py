"""
云存储服务
支持兰空图床和阿里云 OSS 的文件上传
"""
import requests
import oss2
from datetime import datetime
from typing import Dict, Any, Tuple
from fastapi import HTTPException


class StorageService:
    """云存储服务基类"""
    
    @staticmethod
    async def upload_to_lsky(
        filename: str,
        content: bytes,
        content_type: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        上传文件到兰空图床
        
        Args:
            filename: 文件名
            content: 文件内容（字节）
            content_type: 文件 MIME 类型
            config: 兰空图床配置
                - domain: 图床域名
                - token: API Token
                - strategyId: 存储策略 ID（可选）
        
        Returns:
            {
                "success": True,
                "url": "https://...",
                "provider": "lsky"
            }
        """
        domain = config.get("domain")
        token = config.get("token")
        strategy_id = config.get("strategyId")
        
        if not domain or not token:
            raise HTTPException(status_code=400, detail="兰空图床配置不完整：缺少 domain 或 token")
        
        # 确保 token 有 Bearer 前缀
        auth_token = token if token.startswith("Bearer ") else f"Bearer {token}"
        
        # 构建上传 URL
        upload_url = f"{domain.rstrip('/')}/api/v1/upload"
        
        # 准备表单数据
        files = {
            "file": (filename, content, content_type)
        }
        
        headers = {
            "Authorization": auth_token,
            "Accept": "application/json"
        }
        
        data = {}
        if strategy_id:
            data["strategy_id"] = strategy_id
        
        try:
            response = requests.post(
                upload_url,
                files=files,
                headers=headers,
                data=data,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            
            # 兰空图床返回格式：
            # {
            #   "status": true,
            #   "message": "上传成功",
            #   "data": {
            #     "links": {
            #       "url": "https://..."
            #     }
            #   }
            # }
            if result.get("status") and result.get("data", {}).get("links", {}).get("url"):
                image_url = result["data"]["links"]["url"]
                return {
                    "success": True,
                    "url": image_url,
                    "provider": "lsky",
                    "fullData": result.get("data")
                }
            else:
                error_msg = result.get("message", "未知错误")
                raise HTTPException(status_code=500, detail=f"兰空图床上传失败: {error_msg}")
        
        except requests.exceptions.Timeout:
            raise HTTPException(status_code=504, detail="兰空图床上传超时")
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"兰空图床上传失败: {str(e)}")
    
    @staticmethod
    async def upload_to_aliyun_oss(
        filename: str,
        content: bytes,
        content_type: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        上传文件到阿里云 OSS

        Args:
            filename: 文件名
            content: 文件内容（字节）
            content_type: 文件 MIME 类型
            config: 阿里云 OSS 配置
                - accessKeyId: Access Key ID
                - accessKeySecret: Access Key Secret
                - bucket: Bucket 名称
                - endpoint: OSS 访问端点（如 oss-cn-hangzhou.aliyuncs.com）
                - customDomain: 自定义 CDN 域名（可选，用于生成公开访问 URL）
                - secure: 是否使用 HTTPS（默认 True）

        Returns:
            {
                "success": True,
                "url": "https://...",
                "provider": "aliyun-oss",
                "objectName": "uploads/..."
            }
        """
        access_key_id = config.get("accessKeyId")
        access_key_secret = config.get("accessKeySecret")
        bucket_name = config.get("bucket")
        endpoint = config.get("endpoint")
        custom_domain = config.get("customDomain")
        secure = config.get("secure", True)

        if not all([access_key_id, access_key_secret, bucket_name, endpoint]):
            raise HTTPException(
                status_code=400,
                detail="阿里云 OSS 配置不完整：缺少必填项（accessKeyId, accessKeySecret, bucket, endpoint）"
            )
        
        try:
            # 清理 endpoint（移除协议前缀）
            oss_endpoint = endpoint.replace("https://", "").replace("http://", "")
            
            # 创建 OSS 认证和 Bucket 对象
            auth = oss2.Auth(access_key_id, access_key_secret)
            bucket = oss2.Bucket(auth, oss_endpoint, bucket_name)
            
            # 生成对象名称（使用时间戳避免冲突）
            timestamp = int(datetime.now().timestamp() * 1000)
            # 保留原始文件扩展名
            file_ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
            object_name = f"uploads/{timestamp}_{filename}"
            
            # 设置 Content-Type
            headers = {
                'Content-Type': content_type
            }
            
            # 上传文件
            result = bucket.put_object(object_name, content, headers=headers)
            
            if result.status == 200:
                # 构建公开访问 URL
                protocol = "https" if secure else "http"
                
                if custom_domain:
                    # 使用自定义 CDN 域名
                    domain = custom_domain.replace("https://", "").replace("http://", "").rstrip('/')
                    image_url = f"{protocol}://{domain}/{object_name}"
                else:
                    # 使用 OSS 默认域名
                    image_url = f"{protocol}://{bucket_name}.{oss_endpoint}/{object_name}"
                
                return {
                    "success": True,
                    "url": image_url,
                    "provider": "aliyun-oss",
                    "objectName": object_name,
                    "bucket": bucket_name,
                    "endpoint": oss_endpoint
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"阿里云 OSS 上传失败: HTTP {result.status}"
                )
        
        except oss2.exceptions.OssError as e:
            raise HTTPException(
                status_code=500,
                detail=f"阿里云 OSS 错误: {e.code} - {e.message}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"阿里云 OSS 上传失败: {str(e)}"
            )
    
    @staticmethod
    async def upload_file(
        filename: str,
        content: bytes,
        content_type: str,
        provider: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        根据提供商类型上传文件
        
        Args:
            filename: 文件名
            content: 文件内容
            content_type: 文件类型
            provider: 提供商类型 (lsky, aliyun-oss)
            config: 配置信息
        
        Returns:
            上传结果
        """
        if provider == "lsky":
            return await StorageService.upload_to_lsky(filename, content, content_type, config)
        elif provider == "aliyun-oss":
            return await StorageService.upload_to_aliyun_oss(filename, content, content_type, config)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的存储类型: {provider}"
            )
