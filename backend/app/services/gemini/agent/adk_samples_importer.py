"""
ADK Samples Template Importer - 从 GitHub adk-samples 导入模板

提供：
- 从 GitHub 仓库获取 ADK samples 模板
- 转换为工作流模板格式
- 导入到数据库
"""

import logging
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import httpx

from ....models.db_models import WorkflowTemplate

logger = logging.getLogger(__name__)

# ADK Samples GitHub 仓库信息
ADK_SAMPLES_REPO = "google/adk-samples"
ADK_SAMPLES_BASE_URL = f"https://api.github.com/repos/{ADK_SAMPLES_REPO}"

# 预定义的 ADK samples 模板映射
ADK_TEMPLATES = {
    "marketing-agency": {
        "name": "Marketing Agency Agent",
        "description": "图像编辑和 Logo 创建工作流（参考 ADK Marketing Agency Agent）",
        "category": "image-edit",
        "workflow_type": "sequential",
        "path": "python/agents/marketing-agency",
        "config": {
            "nodes": [
                {
                    "id": "image-analyzer",
                    "type": "agent",
                    "label": "图像分析代理",
                    "agentId": "image-analyzer",
                    "position": {"x": 100, "y": 100}
                },
                {
                    "id": "edit-suggester",
                    "type": "agent",
                    "label": "编辑建议代理",
                    "agentId": "edit-suggester",
                    "position": {"x": 300, "y": 100}
                },
                {
                    "id": "image-editor",
                    "type": "agent",
                    "label": "图像编辑代理",
                    "agentId": "image-editor",
                    "position": {"x": 500, "y": 100}
                },
                {
                    "id": "quality-checker",
                    "type": "agent",
                    "label": "质量检查代理",
                    "agentId": "quality-checker",
                    "position": {"x": 700, "y": 100}
                }
            ],
            "edges": [
                {"id": "e1", "source": "image-analyzer", "target": "edit-suggester"},
                {"id": "e2", "source": "edit-suggester", "target": "image-editor"},
                {"id": "e3", "source": "image-editor", "target": "quality-checker"}
            ]
        }
    },
    "data-engineering": {
        "name": "Data Engineering Agent",
        "description": "Excel 数据分析和处理工作流（参考 ADK Data Engineering Agent）",
        "category": "excel-analysis",
        "workflow_type": "sequential",
        "path": "python/agents/data-engineering",
        "config": {
            "nodes": [
                {
                    "id": "data-reader",
                    "type": "agent",
                    "label": "数据读取代理",
                    "agentId": "data-reader",
                    "position": {"x": 100, "y": 100}
                },
                {
                    "id": "data-cleaner",
                    "type": "agent",
                    "label": "数据清理代理",
                    "agentId": "data-cleaner",
                    "position": {"x": 300, "y": 100}
                },
                {
                    "id": "data-analyzer",
                    "type": "agent",
                    "label": "数据分析代理",
                    "agentId": "data-analyzer",
                    "position": {"x": 500, "y": 100}
                },
                {
                    "id": "report-generator",
                    "type": "agent",
                    "label": "报告生成代理",
                    "agentId": "report-generator",
                    "position": {"x": 700, "y": 100}
                }
            ],
            "edges": [
                {"id": "e1", "source": "data-reader", "target": "data-cleaner"},
                {"id": "e2", "source": "data-cleaner", "target": "data-analyzer"},
                {"id": "e3", "source": "data-analyzer", "target": "report-generator"}
            ]
        }
    },
    "customer-service": {
        "name": "Customer Service Agent",
        "description": "客户服务协调代理（Coordinator/Dispatcher 模式）",
        "category": "general",
        "workflow_type": "coordinator",
        "path": "python/agents/customer-service",
        "config": {
            "nodes": [
                {
                    "id": "coordinator",
                    "type": "agent",
                    "label": "协调代理",
                    "agentId": "coordinator",
                    "position": {"x": 400, "y": 100}
                },
                {
                    "id": "billing-specialist",
                    "type": "agent",
                    "label": "账单专家",
                    "agentId": "billing-specialist",
                    "position": {"x": 200, "y": 250}
                },
                {
                    "id": "tech-support",
                    "type": "agent",
                    "label": "技术支持",
                    "agentId": "tech-support",
                    "position": {"x": 600, "y": 250}
                }
            ],
            "edges": [
                {"id": "e1", "source": "coordinator", "target": "billing-specialist"},
                {"id": "e2", "source": "coordinator", "target": "tech-support"}
            ]
        }
    },
    "camel": {
        "name": "CAMEL Agent",
        "description": "多代理协作框架（CAMEL 模式）",
        "category": "general",
        "workflow_type": "parallel",
        "path": "python/agents/camel",
        "config": {
            "nodes": [
                {
                    "id": "task-decomposer",
                    "type": "agent",
                    "label": "任务分解代理",
                    "agentId": "task-decomposer",
                    "position": {"x": 300, "y": 100}
                },
                {
                    "id": "agent-1",
                    "type": "agent",
                    "label": "代理 1",
                    "agentId": "agent-1",
                    "position": {"x": 100, "y": 250}
                },
                {
                    "id": "agent-2",
                    "type": "agent",
                    "label": "代理 2",
                    "agentId": "agent-2",
                    "position": {"x": 500, "y": 250}
                },
                {
                    "id": "result-merger",
                    "type": "agent",
                    "label": "结果合并代理",
                    "agentId": "result-merger",
                    "position": {"x": 300, "y": 400}
                }
            ],
            "edges": [
                {"id": "e1", "source": "task-decomposer", "target": "agent-1"},
                {"id": "e2", "source": "task-decomposer", "target": "agent-2"},
                {"id": "e3", "source": "agent-1", "target": "result-merger"},
                {"id": "e4", "source": "agent-2", "target": "result-merger"}
            ]
        }
    }
}


class ADKSamplesImporter:
    """
    ADK Samples 模板导入器
    
    负责：
    - 从 GitHub 获取 ADK samples 信息
    - 转换为工作流模板格式
    - 导入到数据库
    """
    
    def __init__(self, db: Session):
        """
        初始化 ADK Samples 导入器
        
        Args:
            db: 数据库会话
        """
        self.db = db
        logger.info("[ADKSamplesImporter] Initialized")
    
    async def list_available_templates(self) -> List[Dict[str, Any]]:
        """
        列出可用的 ADK samples 模板
        
        Returns:
            模板列表
        """
        templates = []
        for template_id, template_info in ADK_TEMPLATES.items():
            templates.append({
                "id": template_id,
                "name": template_info["name"],
                "description": template_info["description"],
                "category": template_info["category"],
                "workflow_type": template_info["workflow_type"],
                "path": template_info["path"],
                "source": "adk-samples"
            })
        
        logger.info(f"[ADKSamplesImporter] Found {len(templates)} available templates")
        return templates
    
    async def import_template(
        self,
        user_id: str,
        template_id: str,
        custom_name: Optional[str] = None,
        is_public: bool = False
    ) -> Dict[str, Any]:
        """
        导入 ADK samples 模板到数据库
        
        Args:
            user_id: 用户 ID
            template_id: 模板 ID（如 "marketing-agency", "data-engineering"）
            custom_name: 自定义模板名称（可选）
            is_public: 是否公开（可选，默认 False）
            
        Returns:
            导入的模板信息
            
        Raises:
            ValueError: 如果模板 ID 不存在
        """
        if template_id not in ADK_TEMPLATES:
            raise ValueError(f"Template '{template_id}' not found. Available templates: {list(ADK_TEMPLATES.keys())}")
        
        template_info = ADK_TEMPLATES[template_id]
        
        # 检查是否已存在同名模板
        existing = self.db.query(WorkflowTemplate).filter(
            WorkflowTemplate.user_id == user_id,
            WorkflowTemplate.name == (custom_name or template_info["name"])
        ).first()
        
        if existing:
            logger.warning(f"[ADKSamplesImporter] Template '{custom_name or template_info['name']}' already exists for user {user_id}")
            # 更新现有模板
            now = int(time.time() * 1000)
            existing.description = template_info["description"]
            existing.category = template_info["category"]
            existing.workflow_type = template_info["workflow_type"]
            existing.config_json = json.dumps(template_info["config"])
            existing.is_public = is_public
            existing.updated_at = now
            existing.version += 1
            
            self.db.commit()
            self.db.refresh(existing)
            
            logger.info(f"[ADKSamplesImporter] Updated existing template {existing.id}")
            return existing.to_dict()
        
        # 创建新模板
        now = int(time.time() * 1000)
        template_db_id = str(uuid.uuid4())
        
        template = WorkflowTemplate(
            id=template_db_id,
            user_id=user_id,
            name=custom_name or template_info["name"],
            description=template_info["description"],
            category=template_info["category"],
            workflow_type=template_info["workflow_type"],
            config_json=json.dumps(template_info["config"]),
            is_public=is_public,
            version=1,
            created_at=now,
            updated_at=now
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"[ADKSamplesImporter] Imported template {template_id} as {template_db_id} for user {user_id}")
        return template.to_dict()
    
    async def import_all_templates(
        self,
        user_id: str,
        is_public: bool = False
    ) -> List[Dict[str, Any]]:
        """
        导入所有可用的 ADK samples 模板
        
        Args:
            user_id: 用户 ID
            is_public: 是否公开（可选，默认 False）
            
        Returns:
            导入的模板列表
        """
        imported = []
        for template_id in ADK_TEMPLATES.keys():
            try:
                result = await self.import_template(
                    user_id=user_id,
                    template_id=template_id,
                    is_public=is_public
                )
                imported.append(result)
            except Exception as e:
                logger.error(f"[ADKSamplesImporter] Failed to import template {template_id}: {e}")
        
        logger.info(f"[ADKSamplesImporter] Imported {len(imported)}/{len(ADK_TEMPLATES)} templates")
        return imported
    
    async def get_template_info(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        获取模板信息（不导入）
        
        Args:
            template_id: 模板 ID
            
        Returns:
            模板信息或 None
        """
        if template_id not in ADK_TEMPLATES:
            return None
        
        template_info = ADK_TEMPLATES[template_id].copy()
        template_info["id"] = template_id
        template_info["source"] = "adk-samples"
        return template_info
