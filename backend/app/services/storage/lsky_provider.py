"""
兰空图床存储提供商
支持上传文件到兰空图床
"""

import requests
from typing import Dict, Any, Optional
from .base import BaseStorageProvider, UploadResult


class LskyProvider(BaseStorageProvider):
    """兰空图床存储提供商"""

    def _build_headers(self) -> Dict[str, str]:
        token = self.config.get("token")
        if not token:
            return {"Accept": "application/json"}
        auth_token = token if token.startswith("Bearer ") else f"Bearer {token}"
        return {
            "Authorization": auth_token,
            "Accept": "application/json"
        }
    
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
        strategy_id = self.config.get("strategy_id")
        
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
                    metadata={"full_data": result.get("data")}
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

    async def delete_path(
        self,
        path: str,
        is_directory: bool = False,
        file_url: Optional[str] = None
    ) -> Dict[str, Any]:
        if is_directory:
            return {
                "success": False,
                "supported": False,
                "message": "兰空图床不支持目录删除"
            }
        return {
            "success": False,
            "supported": False,
            "message": "兰空图床当前未提供文件删除能力"
        }

    async def rename_path(
        self,
        path: str,
        new_name: str,
        is_directory: bool = False
    ) -> Dict[str, Any]:
        return {
            "success": False,
            "supported": False,
            "message": "兰空图床当前未提供重命名能力"
        }

    async def browse(
        self,
        path: str = "",
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        domain = self.config.get("domain")
        token = self.config.get("token")

        if not domain or not token:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": "兰空图床配置不完整：缺少 domain 或 token"
            }

        normalized_path = (path or "").replace("\\", "/").strip().strip("/")
        if normalized_path:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": "兰空图床不支持目录层级浏览，仅支持根级文件列表"
            }

        page = 1
        if cursor:
            try:
                page = max(int(cursor), 1)
            except ValueError:
                page = 1

        page_size = max(1, min(limit, 200))
        headers = self._build_headers()
        base = domain.rstrip("/")
        candidate_urls = [
            f"{base}/api/v1/images",
            f"{base}/api/v1/manage/images",
        ]

        last_error = None
        for endpoint in candidate_urls:
            try:
                response = requests.get(
                    endpoint,
                    headers=headers,
                    params={"page": page, "per_page": page_size},
                    timeout=20
                )
                response.raise_for_status()
                payload = response.json()

                data_field = payload.get("data")
                records = []
                next_cursor = None
                has_more = False

                if isinstance(data_field, dict):
                    if isinstance(data_field.get("data"), list):
                        records = data_field.get("data") or []
                        current_page = data_field.get("current_page")
                        last_page = data_field.get("last_page")
                        if isinstance(current_page, int) and isinstance(last_page, int) and current_page < last_page:
                            next_cursor = str(current_page + 1)
                            has_more = True
                    elif isinstance(data_field.get("items"), list):
                        records = data_field.get("items") or []
                elif isinstance(data_field, list):
                    records = data_field

                items = []
                for record in records:
                    if not isinstance(record, dict):
                        continue
                    links = record.get("links") if isinstance(record.get("links"), dict) else {}
                    url = (
                        links.get("url")
                        or record.get("url")
                        or record.get("src")
                        or record.get("image_url")
                    )
                    name = (
                        record.get("name")
                        or record.get("origin_name")
                        or record.get("pathname")
                        or record.get("filename")
                        or str(record.get("id", "unknown"))
                    )
                    items.append({
                        "name": name,
                        "path": name,
                        "entry_type": "file",
                        "size": record.get("size"),
                        "updated_at": record.get("updated_at") or record.get("date"),
                        "url": url
                    })

                if not next_cursor and len(records) >= page_size:
                    next_cursor = str(page + 1)
                    has_more = True

                return {
                    "supported": True,
                    "items": items,
                    "path": "",
                    "next_cursor": next_cursor,
                    "has_more": has_more
                }
            except requests.exceptions.RequestException as e:
                last_error = str(e)
            except ValueError as e:
                last_error = str(e)
            except Exception as e:
                last_error = str(e)

        return {
            "supported": False,
            "items": [],
            "next_cursor": None,
            "has_more": False,
            "message": f"兰空图床浏览失败: {last_error or '未知错误'}"
        }

    async def count_items(self, path: str = "") -> Dict[str, Any]:
        domain = self.config.get("domain")
        token = self.config.get("token")

        if not domain or not token:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": "兰空图床配置不完整：缺少 domain 或 token"
            }

        normalized_path = (path or "").replace("\\", "/").strip().strip("/")
        if normalized_path:
            return {
                "supported": False,
                "path": normalized_path,
                "total_count": None,
                "message": "兰空图床不支持目录层级浏览，仅支持根级文件列表"
            }

        headers = self._build_headers()
        base = domain.rstrip("/")
        candidate_urls = [
            f"{base}/api/v1/images",
            f"{base}/api/v1/manage/images",
        ]
        page_size = 200
        last_error = None

        for endpoint in candidate_urls:
            try:
                page = 1
                total_count = 0

                while True:
                    response = requests.get(
                        endpoint,
                        headers=headers,
                        params={"page": page, "per_page": page_size},
                        timeout=20
                    )
                    response.raise_for_status()
                    payload = response.json()

                    data_field = payload.get("data")
                    records = []
                    current_page = None
                    last_page = None
                    total_value = None

                    if isinstance(data_field, dict):
                        if isinstance(data_field.get("data"), list):
                            records = data_field.get("data") or []
                            current_page = data_field.get("current_page")
                            last_page = data_field.get("last_page")
                            total_value = data_field.get("total")
                        elif isinstance(data_field.get("items"), list):
                            records = data_field.get("items") or []
                            total_value = data_field.get("total") or data_field.get("count")
                    elif isinstance(data_field, list):
                        records = data_field

                    if isinstance(total_value, int) and total_value >= 0:
                        return {
                            "supported": True,
                            "path": "",
                            "total_count": total_value
                        }

                    total_count += len([record for record in records if isinstance(record, dict)])

                    if isinstance(current_page, int) and isinstance(last_page, int):
                        if current_page >= last_page:
                            break
                        page = current_page + 1
                        continue

                    if len(records) < page_size:
                        break

                    page += 1

                return {
                    "supported": True,
                    "path": "",
                    "total_count": total_count
                }
            except requests.exceptions.RequestException as e:
                last_error = str(e)
            except ValueError as e:
                last_error = str(e)
            except Exception as e:
                last_error = str(e)

        return {
            "supported": False,
            "path": "",
            "total_count": None,
            "message": f"兰空图床统计失败: {last_error or '未知错误'}"
        }
    
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
