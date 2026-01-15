"""
Excel Analysis Workflow - Excel 分析工作流

参考 Google ADK Data Engineering Agent 示例：
- 多步骤数据分析流程
- 使用 SequentialAgent 执行
- 集成 Excel 读取、清理、分析和报告生成工具
"""

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
import os

from ..sequential_agent import SequentialAgent
from ..agent_registry import AgentRegistryService
from ..tool_registry import ToolRegistry

if TYPE_CHECKING:
    from ...google_service import GoogleService

logger = logging.getLogger(__name__)


class ExcelAnalysisWorkflow:
    """
    Excel 分析工作流
    
    流程：
    1. DataReader - 读取 Excel 文件并理解数据结构
    2. DataCleaner - 清理和预处理数据
    3. DataAnalyzer - 执行数据分析和统计
    4. ReportGenerator - 生成分析报告和可视化
    """
    
    def __init__(
        self,
        google_service: GoogleService,
        agent_registry: AgentRegistryService,
        tool_registry: ToolRegistry,
        user_id: str
    ):
        """
        初始化 Excel 分析工作流
        
        Args:
            google_service: GoogleService 实例
            agent_registry: AgentRegistryService 实例
            tool_registry: ToolRegistry 实例（已注册 Excel 工具）
            user_id: 用户 ID
        """
        self.google_service = google_service
        self.agent_registry = agent_registry
        self.tool_registry = tool_registry
        self.user_id = user_id
        
        # 注册工作流工具
        self.tool_registry.register_workflow_tools(google_service=google_service)
        
        # 创建子代理配置
        self.sub_agents = [
            {
                "agent_id": "data-reader",
                "agent_name": "数据读取代理",
                "output_key": "raw_data",
                "tools": ["read_excel_file"]
            },
            {
                "agent_id": "data-cleaner",
                "agent_name": "数据清理代理",
                "input_key": "raw_data",
                "output_key": "cleaned_data",
                "tools": ["clean_dataframe"]
            },
            {
                "agent_id": "data-analyzer",
                "agent_name": "数据分析代理",
                "input_key": "cleaned_data",
                "output_key": "analysis_results",
                "tools": ["analyze_dataframe"]
            },
            {
                "agent_id": "report-generator",
                "agent_name": "报告生成代理",
                "input_key": "analysis_results",
                "output_key": "report",
                "tools": ["generate_chart"]
            }
        ]
        
        # 首先注册代理（如果不存在）
        # 注意：这需要在异步上下文中调用，所以延迟到 execute 时注册
        
        # 创建顺序代理（代理注册将在 execute 时进行）
        self.workflow = None  # 延迟创建
        
        logger.info("[ExcelAnalysisWorkflow] Initialized")
    
    async def _ensure_agents_registered(self):
        """确保工作流所需的代理已注册"""
        agent_ids = ["data-reader", "data-cleaner", "data-analyzer", "report-generator"]
        
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
                            "description": f"{agent_id} for Excel analysis workflow",
                            "capabilities": ["数据分析", "Excel处理"]
                        },
                        tools=["read_excel_file"] if "reader" in agent_id else
                              ["clean_dataframe"] if "cleaner" in agent_id else
                              ["analyze_dataframe"] if "analyzer" in agent_id else
                              ["generate_chart"]
                    )
                    logger.info(f"[ExcelAnalysisWorkflow] Registered agent: {agent_id}")
            except Exception as e:
                logger.warning(f"[ExcelAnalysisWorkflow] Failed to register agent {agent_id}: {e}")
    
    async def execute(
        self,
        file_path: str,
        analysis_type: str = "comprehensive",
        cleaning_rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行 Excel 分析工作流
        
        Args:
            file_path: Excel 文件路径
            analysis_type: 分析类型（'basic' | 'advanced' | 'comprehensive'）
            cleaning_rules: 清理规则（可选）
            
        Returns:
            分析报告和可视化结果
        """
        logger.info(f"[ExcelAnalysisWorkflow] Starting execution: {file_path}")
        
        # 验证文件存在
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        # 确保代理已注册
        await self._ensure_agents_registered()
        
        # 创建顺序代理（如果尚未创建）
        if self.workflow is None:
            self.workflow = SequentialAgent(
                name="ExcelAnalysisWorkflow",
                sub_agents=self.sub_agents,
                agent_registry=self.agent_registry,
                google_service=self.google_service,
                tool_registry=self.tool_registry
            )
        
        # 准备初始输入
        initial_input = {
            "file_path": file_path,
            "analysis_type": analysis_type,
            "cleaning_rules": cleaning_rules or {
                "handle_nulls": "fill",
                "fill_value": 0,
                "remove_outliers": True,
                "standardize": False
            }
        }
        
        # 执行工作流
        result = await self.workflow.execute(
            user_id=self.user_id,
            initial_input=initial_input,
            context={
                "workflow_type": "excel_analysis",
                "file_path": file_path,
                "analysis_type": analysis_type
            }
        )
        
        return {
            "success": result.get("success", False),
            "workflow": "excel_analysis",
            "file_path": file_path,
            "raw_data": result.get("session_state", {}).get("raw_data"),
            "cleaned_data": result.get("session_state", {}).get("cleaned_data"),
            "analysis_results": result.get("session_state", {}).get("analysis_results"),
            "report": result.get("session_state", {}).get("report"),
            "final_output": result.get("final_output"),
            "steps": result.get("session_state", {}).get("steps", [])
        }
