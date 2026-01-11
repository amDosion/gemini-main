"""
兰空图床存储提供商
支持上传文件到兰空图床
"""

import requests
from typing import Dict, Any
from .base import BaseStorageProvider, UploadResult


class LskyProvider(BaseStorageProvider):
    """兰空图床存储提供商"""
    
    async def upload(self, filename: str, content: bytes, content_type: str) -> UploadResult:
        """
        上传文件到兰空图床
        
        Args:
            filename: 文件名
            content: 文件内容
            content_type: 文件 MIME 类型
            
        Returns:
            UploadResult: 上传结果
        """
        domain = self.config.get("domain")
        token = self.config.get("token")
        strategy_id = self.config.get("strategyId")
        
        # 验证配置
        if not domain or not token:
            return UploadResult(
                success=False,
                error="兰空图床配置不完整：缺少 domain 或 token",
                provider="lsky"
            )
        
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
                return UploadResult(
                    success=True,
                    url=image_url,
                    provider="lsky",
                    metadata={"fullData": result.get("data")}
                )
            else:
                error_msg = result.get("message", "未知错误")
                return UploadResult(
                    success=False,
                    error=f"兰空图床上传失败: {error_msg}",
                    provider="lsky"
                )
        
        except requests.exceptions.Timeout:
            return UploadResult(
                success=False,
                error="兰空图床上传超时",
                provider="lsky"
            )
        except requests.exceptions.RequestException as e:
            return UploadResult(
                success=False,
                error=f"兰空图床上传失败: {str(e)}",
                provider="lsky"
            )
    
    async def delete(self, file_url: str) -> bool:
        """
        删除文件（占位实现）
        
        Args:
            file_url: 文件 URL
            
        Returns:
            bool: 删除是否成功
        """
        # 兰空图床可能不支持通过 API 删除文件
        # 这里暂时返回 False
        return False
    
    async def test(self) -> UploadResult:
        """
        测试配置是否有效
        
        Returns:
            UploadResult: 测试结果
        """
        domain = self.config.get("domain")
        token = self.config.get("token")
        
        if not domain or not token:
            return UploadResult(
                success=False,
                error="兰空图床配置不完整：缺少 domain 或 token",
                provider="lsky"
            )
        
        return UploadResult(
            success=True,
            provider="lsky"
        )
