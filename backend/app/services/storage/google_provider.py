"""
Google Drive 存储提供商
支持上传文件到 Google Drive
"""

from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from googleapiclient.errors import HttpError
from typing import Dict, Any
from urllib.parse import urlparse
from .base import BaseStorageProvider, UploadResult


class GoogleProvider(BaseStorageProvider):
    """Google Drive 存储提供商"""
    
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
