"""
Workflow Template Service - 工作流模板服务

提供：
- 工作流模板保存
- 工作流模板加载
- 工作流模板列表和搜索
- 模板版本管理
"""

import logging
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ....models.db_models import WorkflowTemplate

logger = logging.getLogger(__name__)


class WorkflowTemplateService:
    """
    工作流模板服务
    
    负责：
    - 工作流模板的 CRUD 操作
    - 模板搜索和过滤
    - 模板版本管理
    """
    
    def __init__(self, db: Session):
        """
        初始化工作流模板服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        logger.info("[WorkflowTemplateService] Initialized")
    
    async def create_template(
        self,
        user_id: str,
        name: str,
        category: str,
        workflow_type: str,
        config: Dict[str, Any],
        description: Optional[str] = None,
        is_public: bool = False
    ) -> Dict[str, Any]:
        """
        创建工作流模板
        
        Args:
            user_id: 用户 ID
            name: 模板名称
            category: 模板分类（image-edit, excel-analysis, general等）
            workflow_type: 工作流类型（sequential, parallel, coordinator）
            config: 工作流配置（节点、边、参数等）
            description: 模板描述（可选）
            is_public: 是否公开（可选，默认 False）
            
        Returns:
            创建的模板信息
        """
        now = int(time.time() * 1000)
        template_id = str(uuid.uuid4())
        
        template = WorkflowTemplate(
            id=template_id,
            user_id=user_id,
            name=name,
            description=description,
            category=category,
            workflow_type=workflow_type,
            config_json=json.dumps(config),
            is_public=is_public,
            version=1,
            created_at=now,
            updated_at=now
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"[WorkflowTemplateService] Created template {template_id} for user {user_id}")
        return template.to_dict()
    
    async def update_template(
        self,
        user_id: str,
        template_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        workflow_type: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        is_public: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        更新工作流模板
        
        Args:
            user_id: 用户 ID
            template_id: 模板 ID
            name: 模板名称（可选）
            description: 模板描述（可选）
            category: 模板分类（可选）
            workflow_type: 工作流类型（可选）
            config: 工作流配置（可选）
            is_public: 是否公开（可选）
            
        Returns:
            更新后的模板信息
        """
        template = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id,
            WorkflowTemplate.user_id == user_id
        ).first()
        
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        now = int(time.time() * 1000)
        
        if name is not None:
            template.name = name
        if description is not None:
            template.description = description
        if category is not None:
            template.category = category
        if workflow_type is not None:
            template.workflow_type = workflow_type
        if config is not None:
            template.config_json = json.dumps(config)
        if is_public is not None:
            template.is_public = is_public
        
        template.updated_at = now
        template.version += 1
        
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"[WorkflowTemplateService] Updated template {template_id}")
        return template.to_dict()
    
    async def get_template(
        self,
        template_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取工作流模板
        
        Args:
            template_id: 模板 ID
            user_id: 用户 ID（可选，用于权限检查）
            
        Returns:
            模板信息，如果不存在则返回 None
        """
        query = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id
        )
        
        # 如果提供了 user_id，检查权限（用户自己的模板或公开模板）
        if user_id:
            query = query.filter(
                (WorkflowTemplate.user_id == user_id) | (WorkflowTemplate.is_public == True)
            )
        
        template = query.first()
        
        if template:
            return template.to_dict()
        return None
    
    async def list_templates(
        self,
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        workflow_type: Optional[str] = None,
        search: Optional[str] = None,
        include_public: bool = True
    ) -> List[Dict[str, Any]]:
        """
        列出工作流模板
        
        Args:
            user_id: 用户 ID（可选，如果提供则只返回该用户的模板和公开模板）
            category: 模板分类过滤（可选）
            workflow_type: 工作流类型过滤（可选）
            search: 搜索关键词（可选，搜索名称和描述）
            include_public: 是否包含公开模板（默认 True）
            
        Returns:
            模板列表
        """
        query = self.db.query(WorkflowTemplate)
        
        # 用户过滤
        if user_id:
            if include_public:
                query = query.filter(
                    (WorkflowTemplate.user_id == user_id) | (WorkflowTemplate.is_public == True)
                )
            else:
                query = query.filter(WorkflowTemplate.user_id == user_id)
        elif not include_public:
            # 如果没有 user_id 且不包含公开模板，返回空列表
            return []
        
        # 分类过滤
        if category:
            query = query.filter(WorkflowTemplate.category == category)
        
        # 工作流类型过滤
        if workflow_type:
            query = query.filter(WorkflowTemplate.workflow_type == workflow_type)
        
        # 搜索过滤
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (WorkflowTemplate.name.like(search_pattern)) |
                (WorkflowTemplate.description.like(search_pattern))
            )
        
        templates = query.order_by(WorkflowTemplate.created_at.desc()).all()
        
        return [template.to_dict() for template in templates]
    
    async def delete_template(
        self,
        user_id: str,
        template_id: str
    ) -> bool:
        """
        删除工作流模板
        
        Args:
            user_id: 用户 ID
            template_id: 模板 ID
            
        Returns:
            是否删除成功
        """
        template = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.id == template_id,
            WorkflowTemplate.user_id == user_id
        ).first()
        
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        self.db.delete(template)
        self.db.commit()
        
        logger.info(f"[WorkflowTemplateService] Deleted template {template_id}")
        return True
