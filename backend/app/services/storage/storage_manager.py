"""
Storage Manager - High-level service for managing storage configurations.

This service handles:
- CRUD operations for storage configurations
- Configuration encryption/decryption
- User-scoped access control
- Configuration testing
- File uploads with automatic provider selection
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from ...models.db_models import StorageConfig, ActiveStorage
from ...core.encryption import encrypt_config, decrypt_config, mask_sensitive_fields
from ...core.user_scoped_query import UserScopedQuery
from .storage_service import StorageService

logger = logging.getLogger(__name__)


class StorageManager:
    """High-level storage configuration manager"""
    
    def __init__(self, db: Session, user_id: str):
        """
        Initialize StorageManager.
        
        Args:
            db: Database session
            user_id: User ID for access control
        """
        self.db = db
        self.user_id = user_id
        self.user_query = UserScopedQuery(db, user_id)

    def _resolve_storage_config(self, storage_id: Optional[str] = None) -> StorageConfig:
        """
        解析并校验存储配置（优先使用传入 storage_id，否则使用 active storage）。
        """
        if storage_id:
            config = self.user_query.get(StorageConfig, storage_id)
        else:
            active = self.db.query(ActiveStorage).filter(
                ActiveStorage.user_id == self.user_id
            ).first()

            if not active or not active.storage_id:
                raise HTTPException(
                    status_code=400,
                    detail="No active storage configuration. Please activate one first."
                )

            config = self.user_query.get(StorageConfig, active.storage_id)

        if not config:
            raise HTTPException(
                status_code=404,
                detail="Storage configuration not found or access denied"
            )

        if not config.enabled:
            raise HTTPException(
                status_code=400,
                detail="Storage configuration is disabled"
            )

        return config
    
    def get_all_configs(self, include_disabled: bool = True) -> List[Dict[str, Any]]:
        """
        Get all storage configurations for the current user.
        
        Args:
            include_disabled: Whether to include disabled configurations
            
        Returns:
            List of storage configurations (with decrypted config fields)
        """
        try:
            configs = self.user_query.get_all(StorageConfig)
            
            if not include_disabled:
                configs = [c for c in configs if c.enabled]
            
            result = []
            for config in configs:
                config_dict = config.to_dict()
                # Decrypt configuration before returning
                config_dict['config'] = decrypt_config(config_dict['config'])
                result.append(config_dict)
            
            logger.info(f"Retrieved {len(result)} storage configs for user {self.user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get storage configs: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve storage configurations: {str(e)}"
            )
    
    def get_config(self, config_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific storage configuration.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            Storage configuration dict or None if not found
        """
        try:
            config = self.user_query.get(StorageConfig, config_id)
            
            if not config:
                return None
            
            config_dict = config.to_dict()
            # Decrypt configuration before returning
            config_dict['config'] = decrypt_config(config_dict['config'])
            
            return config_dict
            
        except Exception as e:
            logger.error(f"Failed to get storage config {config_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve storage configuration: {str(e)}"
            )
    
    def create_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new storage configuration.
        
        Automatically encrypts sensitive fields and sets user_id.
        
        Args:
            config_data: Configuration data including:
                - id: Configuration ID
                - name: Configuration name
                - provider: Provider type
                - enabled: Whether enabled (default: True)
                - config: Provider-specific configuration
                
        Returns:
            Created configuration dict
        """
        try:
            # Encrypt sensitive fields in config
            encrypted_config = encrypt_config(config_data.get('config', {}))
            
            # Log masked config for debugging
            masked_config = mask_sensitive_fields(config_data.get('config', {}))
            logger.info(
                f"Creating storage config for user {self.user_id}: "
                f"provider={config_data.get('provider')}, "
                f"config={masked_config}"
            )
            
            # Create database record
            config = StorageConfig(
                id=config_data['id'],
                user_id=self.user_id,
                name=config_data['name'],
                provider=config_data['provider'],
                enabled=config_data.get('enabled', True),
                config=encrypted_config,
                created_at=config_data.get('created_at', int(datetime.now().timestamp() * 1000)),
                updated_at=config_data.get('updated_at', int(datetime.now().timestamp() * 1000))
            )
            
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
            
            logger.info(f"Created storage config {config.id} for user {self.user_id}")
            
            # Return with decrypted config
            result = config.to_dict()
            result['config'] = decrypt_config(result['config'])
            return result
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create storage config: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create storage configuration: {str(e)}"
            )
    
    def update_config(self, config_id: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing storage configuration.
        
        Verifies user_id ownership before updating.
        
        Args:
            config_id: Configuration ID
            config_data: Updated configuration data
            
        Returns:
            Updated configuration dict
        """
        try:
            # Verify ownership
            config = self.user_query.get(StorageConfig, config_id)
            if not config:
                raise HTTPException(
                    status_code=404,
                    detail="Configuration not found or access denied"
                )
            
            # Update fields
            if 'name' in config_data:
                config.name = config_data['name']
            
            if 'enabled' in config_data:
                config.enabled = config_data['enabled']
            
            if 'config' in config_data:
                # Encrypt sensitive fields
                encrypted_config = encrypt_config(config_data['config'])
                config.config = encrypted_config
                
                # Log masked config
                masked_config = mask_sensitive_fields(config_data['config'])
                logger.info(
                    f"Updating storage config {config_id}: "
                    f"config={masked_config}"
                )
            
            config.updated_at = int(datetime.now().timestamp() * 1000)
            
            self.db.commit()
            self.db.refresh(config)
            
            logger.info(f"Updated storage config {config_id} for user {self.user_id}")
            
            # Return with decrypted config
            result = config.to_dict()
            result['config'] = decrypt_config(result['config'])
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update storage config {config_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update storage configuration: {str(e)}"
            )
    
    def delete_config(self, config_id: str) -> bool:
        """
        Delete a storage configuration.
        
        Verifies user_id ownership before deleting.
        
        Args:
            config_id: Configuration ID
            
        Returns:
            True if deleted successfully
        """
        try:
            # Verify ownership
            config = self.user_query.get(StorageConfig, config_id)
            if not config:
                raise HTTPException(
                    status_code=404,
                    detail="Configuration not found or access denied"
                )
            
            self.db.delete(config)
            self.db.commit()
            
            logger.info(f"Deleted storage config {config_id} for user {self.user_id}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete storage config {config_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete storage configuration: {str(e)}"
            )
    
    async def test_config(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test a storage configuration without saving it.
        
        Attempts to upload a small test file to verify the configuration works.
        
        Args:
            config_data: Configuration to test including:
                - provider: Provider type
                - config: Provider-specific configuration
                
        Returns:
            Test result dict with success status and message
        """
        try:
            provider = config_data.get('provider')
            config = config_data.get('config', {})
            
            if not provider:
                raise ValueError("Provider type is required")
            
            # Decrypt config if it's encrypted
            decrypted_config = decrypt_config(config)
            
            # Log masked config
            masked_config = mask_sensitive_fields(decrypted_config)
            logger.info(
                f"Testing storage config for user {self.user_id}: "
                f"provider={provider}, config={masked_config}"
            )
            
            # Create a small test file
            test_content = b"Storage configuration test"
            test_filename = f"test_{int(datetime.now().timestamp())}.txt"
            
            # Attempt upload
            result = await StorageService.upload_file(
                filename=test_filename,
                content=test_content,
                content_type="text/plain",
                provider=provider,
                config=decrypted_config
            )
            
            if result.get('success'):
                logger.info(f"Storage config test successful for user {self.user_id}")
                return {
                    "success": True,
                    "message": "Configuration test successful",
                    "test_url": result.get('url')
                }
            else:
                return {
                    "success": False,
                    "message": result.get('error', 'Test failed')
                }
                
        except Exception as e:
            logger.error(f"Storage config test failed: {e}")
            return {
                "success": False,
                "message": f"Test failed: {str(e)}"
            }
    
    async def upload_file(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        storage_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file using a storage configuration.
        
        If storage_id is not provided, uses the active storage configuration.
        Verifies that the configuration is enabled before uploading.
        
        Args:
            filename: File name
            content: File content (bytes)
            content_type: MIME type
            storage_id: Optional storage configuration ID
            
        Returns:
            Upload result dict
        """
        try:
            config = self._resolve_storage_config(storage_id)
            
            # Decrypt configuration
            decrypted_config = decrypt_config(config.config)
            
            # Upload file
            logger.info(
                f"Uploading file for user {self.user_id}: "
                f"filename={filename}, provider={config.provider}"
            )
            
            result = await StorageService.upload_file(
                filename=filename,
                content=content,
                content_type=content_type,
                provider=config.provider,
                config=decrypted_config
            )
            
            logger.info(f"File upload successful for user {self.user_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"File upload failed: {str(e)}"
            )

    async def browse_storage(
        self,
        storage_id: Optional[str] = None,
        path: str = "",
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        浏览指定 storage（未指定时使用 active storage）目录内容。
        """
        try:
            config = self._resolve_storage_config(storage_id)
            decrypted_config = decrypt_config(config.config)

            browse_result = await StorageService.browse_files(
                provider=config.provider,
                config=decrypted_config,
                path=path,
                limit=limit,
                cursor=cursor
            )

            return {
                "storage_id": config.id,
                "storage_name": config.name,
                "provider": config.provider,
                "path": path,
                **browse_result
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Browse storage failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to browse storage: {str(e)}"
            )

    async def count_storage_items(
        self,
        storage_id: Optional[str] = None,
        path: str = "",
    ) -> Dict[str, Any]:
        """
        统计指定 storage（未指定时使用 active storage）目录下的真实顶层条目数量。
        """
        try:
            config = self._resolve_storage_config(storage_id)
            decrypted_config = decrypt_config(config.config)

            count_result = await StorageService.count_files(
                provider=config.provider,
                config=decrypted_config,
                path=path,
            )

            return {
                "storage_id": config.id,
                "storage_name": config.name,
                "provider": config.provider,
                "path": path,
                **count_result,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Count storage items failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to count storage items: {str(e)}"
            )

    async def delete_storage_item(
        self,
        storage_id: Optional[str],
        path: str,
        is_directory: bool = False,
        file_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        删除存储中的文件或目录。
        """
        try:
            config = self._resolve_storage_config(storage_id)
            decrypted_config = decrypt_config(config.config)
            result = await StorageService.delete_item(
                provider=config.provider,
                config=decrypted_config,
                path=path,
                is_directory=is_directory,
                file_url=file_url
            )
            return {
                "storage_id": config.id,
                "storage_name": config.name,
                "provider": config.provider,
                "path": path,
                **result
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Delete storage item failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete storage item: {str(e)}"
            )

    async def rename_storage_item(
        self,
        storage_id: Optional[str],
        path: str,
        new_name: str,
        is_directory: bool = False
    ) -> Dict[str, Any]:
        """
        重命名存储中的文件或目录。
        """
        try:
            config = self._resolve_storage_config(storage_id)
            decrypted_config = decrypt_config(config.config)
            result = await StorageService.rename_item(
                provider=config.provider,
                config=decrypted_config,
                path=path,
                new_name=new_name,
                is_directory=is_directory
            )
            return {
                "storage_id": config.id,
                "storage_name": config.name,
                "provider": config.provider,
                "path": path,
                "new_name": new_name,
                **result
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rename storage item failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to rename storage item: {str(e)}"
            )

    async def browse_active_storage(
        self,
        path: str = "",
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        浏览当前激活存储配置下的目录内容。
        """
        return await self.browse_storage(
            storage_id=None,
            path=path,
            limit=limit,
            cursor=cursor
        )

    async def count_active_storage_items(
        self,
        path: str = "",
    ) -> Dict[str, Any]:
        """
        统计当前激活存储配置目录下的真实顶层条目数量。
        """
        return await self.count_storage_items(
            storage_id=None,
            path=path,
        )
    
    def get_active_storage_id(self) -> Optional[str]:
        """
        Get the active storage configuration ID for the current user.
        
        Returns:
            Active storage ID or None
        """
        try:
            active = self.db.query(ActiveStorage).filter(
                ActiveStorage.user_id == self.user_id
            ).first()
            
            return active.storage_id if active else None
            
        except Exception as e:
            logger.error(f"Failed to get active storage: {e}")
            return None
    
    def set_active_storage(self, storage_id: str) -> bool:
        """
        Set the active storage configuration for the current user.
        
        Verifies that the storage configuration exists and belongs to the user.
        
        Args:
            storage_id: Storage configuration ID
            
        Returns:
            True if set successfully
        """
        try:
            # Verify ownership
            config = self.user_query.get(StorageConfig, storage_id)
            if not config:
                raise HTTPException(
                    status_code=404,
                    detail="Storage configuration not found or access denied"
                )
            
            # Update or create active storage record
            active = self.db.query(ActiveStorage).filter(
                ActiveStorage.user_id == self.user_id
            ).first()
            
            if not active:
                active = ActiveStorage(
                    user_id=self.user_id,
                    storage_id=storage_id
                )
                self.db.add(active)
            else:
                active.storage_id = storage_id
            
            self.db.commit()
            
            logger.info(f"Set active storage to {storage_id} for user {self.user_id}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to set active storage: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to set active storage: {str(e)}"
            )
