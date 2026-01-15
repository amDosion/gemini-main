"""
Image Edit Workflow - 图像编辑工作流

参考 Google ADK Marketing Agency Agent 示例：
- 多步骤图像编辑流程
- 使用 SequentialAgent 执行
- 集成图像分析和编辑工具
"""

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass

from ..sequential_agent import SequentialAgent
from ..agent_registry import AgentRegistryService
from ..tool_registry import ToolRegistry

if TYPE_CHECKING:
    from ...google_service import GoogleService

logger = logging.getLogger(__name__)


class ImageEditWorkflow:
    """
    图像编辑工作流
    
    流程：
    1. ImageAnalyzer - 分析图像内容、风格、质量
    2. EditAdvisor - 根据分析结果提供编辑建议
    3. ImageEditor - 执行图像编辑
    4. QualityChecker - 验证编辑质量
    """
    
    def __init__(
        self,
        google_service: GoogleService,
        agent_registry: AgentRegistryService,
        tool_registry: ToolRegistry,
        user_id: str
    ):
        """
        初始化图像编辑工作流
        
        Args:
            google_service: GoogleService 实例
            agent_registry: AgentRegistryService 实例
            tool_registry: ToolRegistry 实例（已注册图像工具）
            user_id: 用户 ID
        """
        self.google_service = google_service
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry
        self.user_id = user_id
        
        # 注册工作流工具
        self.tool_registry.register_workflow_tools(google_service=google_service)

        # 注意：代理注册将在 execute() 方法中延迟执行
        # 因为 __init__ 不是 async 方法，不能使用 await
        self._agents_registered = False

        # 创建子代理配置
        self.sub_agents = [
            {
                "agent_id": "image-analyzer",
                "agent_name": "图像分析代理",
                "output_key": "analysis_result",
                "tools": ["analyze_image"]
            },
            {
                "agent_id": "edit-advisor",
                "agent_name": "编辑建议代理",
                "input_key": "analysis_result",
                "output_key": "edit_advice",
                "tools": []
            },
            {
                "agent_id": "image-editor",
                "agent_name": "图像编辑代理",
                "input_key": "edit_advice",
                "output_key": "edited_image",
                "tools": ["edit_image_with_imagen"]
            },
            {
                "agent_id": "quality-checker",
                "agent_name": "质量检查代理",
                "input_key": "edited_image",
                "output_key": "quality_report",
                "tools": ["analyze_image"]
            }
        ]
        
        # 顺序代理将在 execute 时创建（需要先注册代理）
        self.workflow = None
        
        logger.info("[ImageEditWorkflow] Initialized")
    
    async def _ensure_agents_registered(self):
        """确保工作流所需的代理已注册"""
        agent_ids = ["image-analyzer", "edit-advisor", "image-editor", "quality-checker"]
        
        for agent_id in agent_ids:
            try:
                agent = await self.agent_registry.get_agent(self.user_id, agent_id)
                if not agent:
                    # 注册代理
                    await self.agent_registry.register_agent(
                        user_id=self.user_id,
                        name=agent_id.replace("-", " ").title(),
                        agent_type="adk",
                        agent_card={
                            "name": agent_id,
                            "description": f"{agent_id} for image editing workflow",
                            "capabilities": ["图像处理"] if "image" in agent_id else ["分析", "建议"]
                        },
                        tools=["analyze_image"] if "analyzer" in agent_id or "checker" in agent_id else 
                              ["edit_image_with_imagen"] if "editor" in agent_id else []
                    )
                    logger.info(f"[ImageEditWorkflow] Registered agent: {agent_id}")
            except Exception as e:
                logger.warning(f"[ImageEditWorkflow] Failed to register agent {agent_id}: {e}")
    
    async def execute(
        self,
        image_url: str,
        edit_prompt: str,
        edit_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行图像编辑工作流
        
        Args:
            image_url: 原始图像 URL
            edit_prompt: 编辑需求描述
            edit_mode: 编辑模式（可选，默认由代理决定）
            
        Returns:
            编辑结果和质量报告
        """
        logger.info(f"[ImageEditWorkflow] Starting execution: {edit_prompt[:50]}...")
        
        # 确保代理已注册
        await self._ensure_agents_registered()
        
        # 创建顺序代理（如果尚未创建）
        if self.workflow is None:
            self.workflow = SequentialAgent(
                name="ImageEditWorkflow",
                sub_agents=self.sub_agents,
                agent_registry=self.agent_registry,
                google_service=self.google_service,
                tool_registry=self.tool_registry
            )
        
        # 准备初始输入（包含图像 URL 和编辑提示）
        initial_input = {
            "image_url": image_url,
            "edit_prompt": edit_prompt,
            "edit_mode": edit_mode
        }
        
        # 执行工作流
        result = await self.workflow.execute(
            user_id=self.user_id,
            initial_input=initial_input,
            context={
                "workflow_type": "image_edit",
                "image_url": image_url,
                "edit_prompt": edit_prompt
            }
        )
        
        return {
            "success": result.get("success", False),
            "workflow": "image_edit",
            "image_url": image_url,
            "edit_prompt": edit_prompt,
            "analysis_result": result.get("session_state", {}).get("analysis_result"),
            "edit_advice": result.get("session_state", {}).get("edit_advice"),
            "edited_image": result.get("session_state", {}).get("edited_image"),
            "quality_report": result.get("session_state", {}).get("quality_report"),
            "final_output": result.get("final_output"),
            "steps": result.get("session_state", {}).get("steps", [])
        }
