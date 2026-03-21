"""
Google Drive 存储提供商
支持上传文件到 Google Drive
"""

from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from googleapiclient.errors import HttpError
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from .base import BaseStorageProvider, UploadResult


class GoogleProvider(BaseStorageProvider):
    """Google Drive 存储提供商"""

    FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
    
    def _create_credentials(self) -> Credentials:
        """创建 OAuth2 凭证"""
        client_id = self.config.get("client_id")
        client_secret = self.config.get("client_secret")
        refresh_token = self.config.get("refresh_token")
        
        return Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )
    
    def _create_service(self):
        """创建 Drive 服务"""
        creds = self._create_credentials()
        return build('drive', 'v3', credentials=creds)

    def _normalize_path(self, value: str) -> str:
        normalized = (value or "").replace("\\", "/").strip().strip("/")
        if ".." in normalized.split("/"):
            raise ValueError("非法目录路径")
        return normalized

    @staticmethod
    def _escape_query_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _resolve_target_folder(self, service, path: str) -> tuple[str, str]:
        """将相对路径解析为 Google Drive folder_id。"""
        normalized_path = self._normalize_path(path)
        root_folder_id = self.config.get("folder_id") or "root"
        current_folder_id = root_folder_id

        if not normalized_path:
            return current_folder_id, ""

        for segment in normalized_path.split("/"):
            safe_segment = self._escape_query_value(segment)
            query = (
                f"name = '{safe_segment}' and "
                f"'{current_folder_id}' in parents and "
                f"mimeType = '{self.FOLDER_MIME_TYPE}' and trashed = false"
            )
            response = service.files().list(
                q=query,
                pageSize=1,
                fields="files(id,name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            files = response.get("files", [])
            if not files:
                raise FileNotFoundError(f"目录不存在: {segment}")
            current_folder_id = files[0]["id"]

        return current_folder_id, normalized_path

    def _find_child_in_parent(
        self,
        service,
        parent_id: str,
        name: str,
        mime_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        safe_name = self._escape_query_value(name)
        query_parts = [
            f"name = '{safe_name}'",
            f"'{parent_id}' in parents",
            "trashed = false"
        ]
        if mime_type:
            query_parts.append(f"mimeType = '{mime_type}'")

        response = service.files().list(
            q=" and ".join(query_parts),
            pageSize=1,
            fields="files(id,name,mimeType,parents,webViewLink,webContentLink,size,modifiedTime)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files = response.get("files", [])
        return files[0] if files else None

    def _resolve_item_by_path(self, service, path: str) -> tuple[Dict[str, Any], str]:
        normalized_path = self._normalize_path(path)
        if not normalized_path:
            raise ValueError("path is required")

        root_folder_id = self.config.get("folder_id") or "root"
        current_folder_id = root_folder_id
        segments = normalized_path.split("/")

        for segment in segments[:-1]:
            folder = self._find_child_in_parent(
                service=service,
                parent_id=current_folder_id,
                name=segment,
                mime_type=self.FOLDER_MIME_TYPE
            )
            if not folder:
                raise FileNotFoundError(f"目录不存在: {segment}")
            current_folder_id = folder["id"]

        leaf_name = segments[-1]
        item = self._find_child_in_parent(
            service=service,
            parent_id=current_folder_id,
            name=leaf_name
        )
        if not item:
            raise FileNotFoundError(f"目标不存在: {leaf_name}")
        return item, normalized_path
    
    async def upload(self, filename: str, content: bytes, content_type: str) -> UploadResult:
        """
        上传文件到 Google Drive
        
        Args:
            filename: 文件名
            content: 文件内容
            content_type: 文件 MIME 类型
            
        Returns:
            UploadResult: 上传结果
        """
        client_id = self.config.get("client_id")
        client_secret = self.config.get("client_secret")
        refresh_token = self.config.get("refresh_token")
        folder_id = self.config.get("folder_id")

        # 验证配置
        if not all([client_id, client_secret, refresh_token]):
            return UploadResult(
                success=False,
                error="Google Drive 配置不完整：缺少必填项（client_id, client_secret, refresh_token）",
                provider="google-drive"
            )
        
        try:
            # 创建 Drive 服务
            service = self._create_service()
            
            # 构建文件元数据
            file_metadata = {
                'name': filename
            }
            
            # 如果指定了文件夹 ID，添加到父文件夹
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            # 创建媒体上传对象
            media = MediaInMemoryUpload(
                content,
                mimetype=content_type,
                resumable=False
            )
            
            # 上传文件
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink,webContentLink'
            ).execute()
            
            file_id = file.get('id')
            
            # 设置文件为公开访问
            try:
                service.permissions().create(
                    fileId=file_id,
                    body={
                        'type': 'anyone',
                        'role': 'reader'
                    }
                ).execute()
            except HttpError:
                # 权限设置失败不影响上传成功
                pass
            
            # 获取公开访问链接
            web_content_link = file.get('webContentLink')
            web_view_link = file.get('webViewLink')
            
            # 如果没有 webContentLink，使用 webViewLink
            public_url = web_content_link or web_view_link or f"https://drive.google.com/file/d/{file_id}/view"
            
            return UploadResult(
                success=True,
                url=public_url,
                provider="google-drive",
                metadata={
                    "file_id": file_id,
                    "folder_id": folder_id,
                    "web_view_link": web_view_link,
                    "web_content_link": web_content_link
                }
            )
        
        except RefreshError as e:
            return UploadResult(
                success=False,
                error=f"Google Drive OAuth2 令牌刷新失败: {str(e)}",
                provider="google-drive"
            )
        except HttpError as e:
            error_details = e.error_details if hasattr(e, 'error_details') else str(e)
            return UploadResult(
                success=False,
                error=f"Google Drive API 错误: {error_details}",
                provider="google-drive"
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=f"Google Drive 上传失败: {str(e)}",
                provider="google-drive"
            )
    
    async def delete(self, file_url: str) -> bool:
        """
        删除文件
        
        Args:
            file_url: 文件 URL
            
        Returns:
            bool: 删除是否成功
        """
        try:
            # 从 URL 中提取文件 ID
            # Google Drive URL 格式: https://drive.google.com/file/d/{fileId}/view
            # 或 webContentLink: https://drive.google.com/uc?id={fileId}&export=download
            
            file_id = None
            
            if '/file/d/' in file_url:
                # 从 webViewLink 提取
                parts = file_url.split('/file/d/')
                if len(parts) > 1:
                    file_id = parts[1].split('/')[0]
            elif 'id=' in file_url:
                # 从 webContentLink 提取
                parsed = urlparse(file_url)
                params = dict(param.split('=') for param in parsed.query.split('&') if '=' in param)
                file_id = params.get('id')
            
            if not file_id:
                return False
            
            # 创建 Drive 服务
            service = self._create_service()
            
            # 删除文件
            service.files().delete(fileId=file_id).execute()
            
            return True
        
        except HttpError:
            return False
        except Exception:
            return False

    async def browse(
        self,
        path: str = "",
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        client_id = self.config.get("client_id")
        client_secret = self.config.get("client_secret")
        refresh_token = self.config.get("refresh_token")

        if not all([client_id, client_secret, refresh_token]):
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": "Google Drive 配置不完整"
            }

        try:
            service = self._create_service()
            folder_id, normalized_path = self._resolve_target_folder(service, path)

            response = service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                pageSize=max(1, min(limit, 1000)),
                pageToken=cursor,
                fields="nextPageToken, files(id,name,mimeType,size,modifiedTime,webViewLink,webContentLink)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()

            items: list[dict] = []
            for file in response.get("files", []):
                is_directory = file.get("mimeType") == self.FOLDER_MIME_TYPE
                relative_path = f"{normalized_path}/{file.get('name')}" if normalized_path else file.get("name")
                file_id = file.get("id")
                web_view_link = file.get("webViewLink")
                web_content_link = file.get("webContentLink")
                url = None if is_directory else (web_content_link or web_view_link or f"https://drive.google.com/file/d/{file_id}/view")

                items.append({
                    "name": file.get("name"),
                    "path": relative_path,
                    "entry_type": "directory" if is_directory else "file",
                    "size": None if is_directory else int(file["size"]) if file.get("size") else None,
                    "updated_at": file.get("modifiedTime"),
                    "url": url
                })

            items.sort(key=lambda item: (0 if item["entry_type"] == "directory" else 1, (item["name"] or "").lower()))

            next_cursor = response.get("nextPageToken")
            return {
                "supported": True,
                "items": items,
                "path": normalized_path,
                "next_cursor": next_cursor,
                "has_more": bool(next_cursor)
            }
        except ValueError as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": str(e)
            }
        except FileNotFoundError as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": str(e)
            }
        except RefreshError as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": f"Google Drive OAuth2 令牌刷新失败: {str(e)}"
            }
        except HttpError as e:
            error_details = e.error_details if hasattr(e, "error_details") else str(e)
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": f"Google Drive API 错误: {error_details}"
            }
        except Exception as e:
            return {
                "supported": False,
                "items": [],
                "next_cursor": None,
                "has_more": False,
                "message": f"Google Drive 浏览失败: {str(e)}"
            }

    async def count_items(self, path: str = "") -> Dict[str, Any]:
        client_id = self.config.get("client_id")
        client_secret = self.config.get("client_secret")
        refresh_token = self.config.get("refresh_token")

        if not all([client_id, client_secret, refresh_token]):
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": "Google Drive 配置不完整"
            }

        try:
            service = self._create_service()
            folder_id, normalized_path = self._resolve_target_folder(service, path)
            page_token = None
            total_count = 0

            while True:
                response = service.files().list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    pageSize=1000,
                    pageToken=page_token,
                    fields="nextPageToken, files(id)",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()

                total_count += len(response.get("files", []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            return {
                "supported": True,
                "path": normalized_path,
                "total_count": total_count
            }
        except ValueError as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": str(e)
            }
        except FileNotFoundError as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": str(e)
            }
        except RefreshError as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": f"Google Drive OAuth2 令牌刷新失败: {str(e)}"
            }
        except HttpError as e:
            error_details = e.error_details if hasattr(e, "error_details") else str(e)
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": f"Google Drive 统计失败: {error_details}"
            }
        except Exception as e:
            return {
                "supported": False,
                "path": path,
                "total_count": None,
                "message": f"Google Drive 统计失败: {str(e)}"
            }

    async def delete_path(
        self,
        path: str,
        is_directory: bool = False,
        file_url: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            service = self._create_service()
            item, _ = self._resolve_item_by_path(service, path)

            is_folder = item.get("mimeType") == self.FOLDER_MIME_TYPE
            if is_directory and not is_folder:
                return {"success": False, "supported": True, "message": "目标不是目录"}
            if not is_directory and is_folder:
                return {"success": False, "supported": True, "message": "目标是目录"}

            service.files().delete(
                fileId=item["id"],
                supportsAllDrives=True
            ).execute()
            return {"success": True, "supported": True, "message": None}
        except ValueError as e:
            return {"success": False, "supported": False, "message": str(e)}
        except FileNotFoundError as e:
            return {"success": False, "supported": True, "message": str(e)}
        except RefreshError as e:
            return {"success": False, "supported": False, "message": f"Google Drive OAuth2 令牌刷新失败: {str(e)}"}
        except HttpError as e:
            error_details = e.error_details if hasattr(e, "error_details") else str(e)
            return {"success": False, "supported": True, "message": f"Google Drive 删除失败: {error_details}"}
        except Exception as e:
            return {"success": False, "supported": True, "message": f"Google Drive 删除失败: {str(e)}"}

    async def rename_path(
        self,
        path: str,
        new_name: str,
        is_directory: bool = False
    ) -> Dict[str, Any]:
        clean_name = (new_name or "").strip()
        if not clean_name:
            return {"success": False, "supported": False, "message": "new_name is required"}

        try:
            service = self._create_service()
            item, normalized_path = self._resolve_item_by_path(service, path)
            is_folder = item.get("mimeType") == self.FOLDER_MIME_TYPE

            if is_directory and not is_folder:
                return {"success": False, "supported": True, "message": "目标不是目录"}
            if not is_directory and is_folder:
                return {"success": False, "supported": True, "message": "目标是目录"}

            path_parts = normalized_path.split("/")
            parent_path = "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
            parent_id, _ = self._resolve_target_folder(service, parent_path) if parent_path else (self.config.get("folder_id") or "root", "")

            existing = self._find_child_in_parent(service, parent_id, clean_name)
            if existing and existing.get("id") != item.get("id"):
                return {"success": False, "supported": True, "message": "同名文件已存在"}

            service.files().update(
                fileId=item["id"],
                body={"name": clean_name},
                fields="id,name",
                supportsAllDrives=True
            ).execute()
            return {"success": True, "supported": True, "message": None}
        except ValueError as e:
            return {"success": False, "supported": False, "message": str(e)}
        except FileNotFoundError as e:
            return {"success": False, "supported": True, "message": str(e)}
        except RefreshError as e:
            return {"success": False, "supported": False, "message": f"Google Drive OAuth2 令牌刷新失败: {str(e)}"}
        except HttpError as e:
            error_details = e.error_details if hasattr(e, "error_details") else str(e)
            return {"success": False, "supported": True, "message": f"Google Drive 重命名失败: {error_details}"}
        except Exception as e:
            return {"success": False, "supported": True, "message": f"Google Drive 重命名失败: {str(e)}"}
    
    async def test(self) -> UploadResult:
        """
        测试配置是否有效
        
        Returns:
            UploadResult: 测试结果
        """
        client_id = self.config.get("client_id")
        client_secret = self.config.get("client_secret")
        refresh_token = self.config.get("refresh_token")

        if not all([client_id, client_secret, refresh_token]):
            return UploadResult(
                success=False,
                error="Google Drive 配置不完整：缺少必填项（client_id, client_secret, refresh_token）",
                provider="google-drive"
            )
        
        try:
            # 创建 Drive 服务并测试连接
            service = self._create_service()
            
            # 尝试获取用户信息（测试 API 访问）
            about = service.about().get(fields='user').execute()
            
            user_email = about.get('user', {}).get('emailAddress', 'Unknown')
            
            return UploadResult(
                success=True,
                provider="google-drive",
                metadata={"user_email": user_email}
            )
        
        except RefreshError as e:
            return UploadResult(
                success=False,
                error=f"Google Drive OAuth2 令牌刷新失败: {str(e)}",
                provider="google-drive"
            )
        except HttpError as e:
            error_details = e.error_details if hasattr(e, 'error_details') else str(e)
            return UploadResult(
                success=False,
                error=f"Google Drive API 错误: {error_details}",
                provider="google-drive"
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=f"Google Drive 测试失败: {str(e)}",
                provider="google-drive"
            )
