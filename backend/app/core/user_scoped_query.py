"""
用户范围查询包装器 - 自动添加用户过滤

功能：
1. 自动在查询中添加 user_id 过滤
2. 防止跨用户数据访问
3. 提供便捷的查询方法
"""

from sqlalchemy.orm import Session, Query
from typing import TypeVar, Type, Optional, List, Any, Dict
from ..models.db_models import (
    ChatSession, MessageIndex, ConfigProfile,
    Persona, StorageConfig, MessageAttachment,
    MessagesChat, MessagesImageGen, MessagesVideoGen, MessagesGeneric
)


# 支持用户隔离的模型类型
UserScopedModel = TypeVar('UserScopedModel',
    ChatSession, MessageIndex, ConfigProfile, Persona, StorageConfig,
    MessageAttachment, MessagesChat, MessagesImageGen, MessagesVideoGen, MessagesGeneric
)


class UserScopedQuery:
    """
    用户范围查询包装器
    
    自动为所有查询添加 user_id 过滤，确保用户只能访问自己的数据
    """
    
    # 支持用户隔离的模型列表
    SCOPED_MODELS = {
        ChatSession,
        MessageIndex,
        ConfigProfile,
        Persona,
        StorageConfig,
        MessageAttachment,
        MessagesChat,
        MessagesImageGen,
        MessagesVideoGen,
        MessagesGeneric
    }
    
    def __init__(self, db: Session, user_id: str):
        """
        初始化用户范围查询
        
        Args:
            db: SQLAlchemy 数据库会话
            user_id: 当前用户 ID
        """
        self.db = db
        self.user_id = user_id
    
    def query(self, model: Type[UserScopedModel]) -> Query:
        """
        创建带用户过滤的查询
        
        Args:
            model: 数据库模型类
            
        Returns:
            带用户过滤的查询对象
            
        Raises:
            ValueError: 如果模型不支持用户隔离
        """
        if model not in self.SCOPED_MODELS:
            raise ValueError(f"Model {model.__name__} does not support user scoping")
        
        return self.db.query(model).filter(model.user_id == self.user_id)
    
    def get(self, model: Type[UserScopedModel], id: str) -> Optional[UserScopedModel]:
        """
        获取单个记录（自动过滤用户）
        
        Args:
            model: 数据库模型类
            id: 记录 ID
            
        Returns:
            记录对象或 None（如果不存在或不属于当前用户）
        """
        return self.query(model).filter(model.id == id).first()
    
    def get_all(self, model: Type[UserScopedModel]) -> List[UserScopedModel]:
        """
        获取所有记录（自动过滤用户）
        
        Args:
            model: 数据库模型类
            
        Returns:
            记录列表
        """
        return self.query(model).all()
    
    def create(self, model: Type[UserScopedModel], **kwargs) -> UserScopedModel:
        """
        创建记录（自动添加 user_id）
        
        Args:
            model: 数据库模型类
            **kwargs: 记录字段
            
        Returns:
            创建的记录对象
            
        Raises:
            ValueError: 如果模型不支持用户隔离
        """
        if model not in self.SCOPED_MODELS:
            raise ValueError(f"Model {model.__name__} does not support user scoping")
        
        # 自动添加 user_id
        kwargs['user_id'] = self.user_id
        
        # 创建记录
        instance = model(**kwargs)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        
        return instance
    
    def update(self, model: Type[UserScopedModel], id: str, **kwargs) -> Optional[UserScopedModel]:
        """
        更新记录（自动验证用户归属）
        
        Args:
            model: 数据库模型类
            id: 记录 ID
            **kwargs: 要更新的字段
            
        Returns:
            更新后的记录对象或 None（如果不存在或不属于当前用户）
        """
        instance = self.get(model, id)
        if not instance:
            return None
        
        # 更新字段
        for key, value in kwargs.items():
            if hasattr(instance, key) and key != 'user_id':  # 禁止修改 user_id
                setattr(instance, key, value)
        
        self.db.commit()
        self.db.refresh(instance)
        
        return instance
    
    def delete(self, model: Type[UserScopedModel], id: str) -> bool:
        """
        删除记录（自动验证用户归属）
        
        Args:
            model: 数据库模型类
            id: 记录 ID
            
        Returns:
            True 如果删除成功，False 如果记录不存在或不属于当前用户
        """
        instance = self.get(model, id)
        if not instance:
            return False
        
        self.db.delete(instance)
        self.db.commit()
        
        return True
    
    def count(self, model: Type[UserScopedModel]) -> int:
        """
        统计记录数量（自动过滤用户）
        
        Args:
            model: 数据库模型类
            
        Returns:
            记录数量
        """
        return self.query(model).count()
    
    def exists(self, model: Type[UserScopedModel], id: str) -> bool:
        """
        检查记录是否存在（自动验证用户归属）
        
        Args:
            model: 数据库模型类
            id: 记录 ID
            
        Returns:
            True 如果记录存在且属于当前用户
        """
        return self.query(model).filter(model.id == id).count() > 0
