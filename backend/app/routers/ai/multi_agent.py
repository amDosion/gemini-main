"""
Multi-Agent API Router - 多智能体系统 API 路由

提供：
- POST /api/multi-agent/orchestrate：编排多智能体任务
- GET /api/multi-agent/agents：列出可用智能体
- POST /api/multi-agent/agents/register：注册智能体
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi import Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import logging

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...services.gemini.agent.orchestrator import Orchestrator
from ...services.gemini.agent.agent_registry import AgentRegistryService
from ...services.common.provider_factory import ProviderFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/multi-agent", tags=["multi-agent"])


# ==================== Health Check Endpoint ====================

@router.get("/health")
async def health_check():
    """健康检查端点，用于验证路由是否正常工作"""
    return {"status": "ok", "message": "Multi-Agent API is working"}


# ==================== Request/Response Models ====================

class OrchestrateRequest(BaseModel):
    """编排任务请求"""
    task: str
    agent_ids: Optional[List[str]] = None
    mode: Optional[str] = None  # 模式：coordinator, sequential, parallel, default
    workflow_config: Optional[Dict[str, Any]] = None  # 工作流配置（用于 sequential/parallel 模式）


class RegisterAgentRequest(BaseModel):
    """注册智能体请求"""
    name: str
    agent_type: str
    agent_card: Optional[Dict[str, Any]] = None
    endpoint_url: Optional[str] = None
    tools: Optional[List[str]] = None  # 工具名称列表
    mcp_session_id: Optional[str] = None  # MCP 会话 ID（用于加载 MCP 工具）


# ==================== API Endpoints ====================

@router.post("/orchestrate")
async def orchestrate(
    request_body: OrchestrateRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    编排多智能体任务
    
    使用智能任务分解（如果可用）：
    - 自动分解任务为子任务
    - 智能匹配代理
    - 考虑依赖关系和负载均衡
    
    Returns:
        聚合结果
    """
    try:
        
        # 尝试获取 GoogleService 用于智能任务分解
        google_service = None
        try:
            # 从数据库获取 Google API key
            from ...models.db_models import UserSettings, ConfigProfile
            from ...core.encryption import decrypt_api_key
            
            settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            active_profile_id = settings.active_profile_id if settings else None
            
            matching_profiles = db.query(ConfigProfile).filter(
                ConfigProfile.provider_id == 'google',
                ConfigProfile.user_id == user_id
            ).all()
            
            if matching_profiles:
                # 优先使用激活配置
                if active_profile_id:
                    for profile in matching_profiles:
                        if profile.id == active_profile_id and profile.api_key:
                            api_key = decrypt_api_key(profile.api_key)
                            google_service = ProviderFactory.create(
                                provider='google',
                                api_key=api_key,
                                user_id=user_id,
                                db=db
                            )
                            break
                
                # 回退：使用第一个匹配的配置
                if not google_service:
                    for profile in matching_profiles:
                        if profile.api_key:
                            api_key = decrypt_api_key(profile.api_key)
                            google_service = ProviderFactory.create(
                                provider='google',
                                api_key=api_key,
                                user_id=user_id,
                                db=db
                            )
                            break
        except Exception as e:
            logger.warning(f"[Multi-Agent API] Failed to create GoogleService for smart decomposition: {e}")
            # 继续使用简单任务分解
        
        # 根据模式选择执行方式
        mode = request_body.mode or "default"
        
        if mode == "coordinator":
            # Coordinator/Dispatcher Pattern
            from ...services.gemini.agent.coordinator_agent import CoordinatorAgent
            from ...services.gemini.agent.agent_registry import AgentRegistryService
            
            agent_registry = AgentRegistryService(db=db)
            coordinator = CoordinatorAgent(
                google_service=google_service,
                agent_registry=agent_registry,
                model="gemini-2.0-flash-exp"
            )
            
            result = await coordinator.coordinate(
                user_id=user_id,
                task=request_body.task,
                context=request_body.workflow_config
            )
            
            return result
            
        elif mode == "sequential":
            # Sequential Pipeline Pattern
            if not request_body.workflow_config or "sub_agents" not in request_body.workflow_config:
                raise HTTPException(
                    status_code=400,
                    detail="Sequential mode requires workflow_config with sub_agents"
                )
            
            from ...services.gemini.agent.sequential_agent import SequentialAgent
            from ...services.gemini.agent.agent_registry import AgentRegistryService
            from ...services.gemini.agent.tool_registry import ToolRegistry
            from ...services.mcp.mcp_manager import get_mcp_manager
            
            agent_registry = AgentRegistryService(db=db)
            mcp_manager = get_mcp_manager()
            tool_registry = ToolRegistry(mcp_manager=mcp_manager)
            
            sequential_agent = SequentialAgent(
                name=request_body.workflow_config.get("name", "SequentialWorkflow"),
                sub_agents=request_body.workflow_config["sub_agents"],
                agent_registry=agent_registry,
                google_service=google_service,
                tool_registry=tool_registry
            )
            
            result = await sequential_agent.execute(
                user_id=user_id,
                initial_input=request_body.task,
                context=request_body.workflow_config.get("context")
            )
            
            return result
            
        elif mode == "parallel":
            # Parallel Fan-Out/Gather Pattern
            if not request_body.workflow_config or "sub_agents" not in request_body.workflow_config:
                raise HTTPException(
                    status_code=400,
                    detail="Parallel mode requires workflow_config with sub_agents"
                )
            
            from ...services.gemini.agent.parallel_agent import ParallelAgent
            from ...services.gemini.agent.agent_registry import AgentRegistryService
            from ...services.gemini.agent.tool_registry import ToolRegistry
            from ...services.mcp.mcp_manager import get_mcp_manager
            
            agent_registry = AgentRegistryService(db=db)
            mcp_manager = get_mcp_manager()
            tool_registry = ToolRegistry(mcp_manager=mcp_manager)
            
            parallel_agent = ParallelAgent(
                name=request_body.workflow_config.get("name", "ParallelWorkflow"),
                sub_agents=request_body.workflow_config["sub_agents"],
                agent_registry=agent_registry,
                google_service=google_service,
                tool_registry=tool_registry,
                default_timeout=request_body.workflow_config.get("timeout", 60.0)
            )
            
            result = await parallel_agent.execute(
                user_id=user_id,
                shared_input=request_body.task,
                context=request_body.workflow_config.get("context")
            )
            
            return result
            
        else:
            # Default mode: 使用 Orchestrator（智能任务分解 + 执行图）
            orchestrator = Orchestrator(
                db=db,
                google_service=google_service,
                use_smart_decomposition=google_service is not None
            )
            
            result = await orchestrator.orchestrate(
                user_id=user_id,
                task=request_body.task,
                agent_ids=request_body.agent_ids
            )
            
            return result
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error orchestrating task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def list_agents(
    agent_type: Optional[str] = None,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    列出可用智能体
    
    Returns:
        智能体列表
    """
    try:
        
        registry = AgentRegistryService(db=db)
        agents = await registry.list_agents(
            user_id=user_id,
            agent_type=agent_type
        )
        
        return {"agents": agents, "count": len(agents)}
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error listing agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/register")
async def register_agent(
    request_body: RegisterAgentRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    注册智能体
    
    Returns:
        注册的智能体信息
    """
    try:
        
        registry = AgentRegistryService(db=db)
        agent = await registry.register_agent(
            user_id=user_id,
            name=request_body.name,
            agent_type=request_body.agent_type,
            agent_card=request_body.agent_card,
            endpoint_url=request_body.endpoint_url,
            tools=request_body.tools,
            mcp_session_id=request_body.mcp_session_id
        )
        
        return agent
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error registering agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Workflow Templates API ====================

class ImageEditWorkflowRequest(BaseModel):
    """图像编辑工作流请求"""
    image_url: str
    edit_prompt: str
    edit_mode: Optional[str] = None


class ExcelAnalysisWorkflowRequest(BaseModel):
    """Excel 分析工作流请求"""
    file_path: str
    analysis_type: Optional[str] = "comprehensive"
    cleaning_rules: Optional[Dict[str, Any]] = None


@router.post("/workflows/image-edit")
async def execute_image_edit_workflow(
    request_body: ImageEditWorkflowRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    执行图像编辑工作流
    
    Returns:
        编辑结果和质量报告
    """
    try:
        
        # 获取 GoogleService
        from ...models.db_models import UserSettings, ConfigProfile
        from ...core.encryption import decrypt_api_key
        
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        active_profile_id = settings.active_profile_id if settings else None
        
        matching_profiles = db.query(ConfigProfile).filter(
            ConfigProfile.provider_id == 'google',
            ConfigProfile.user_id == user_id
        ).all()
        
        if not matching_profiles:
            raise HTTPException(
                status_code=401,
                detail="Google API key not found. Please configure it in Settings → Profiles."
            )
        
        api_key = None
        if active_profile_id:
            for profile in matching_profiles:
                if profile.id == active_profile_id and profile.api_key:
                    api_key = decrypt_api_key(profile.api_key)
                    break
        
        if not api_key:
            for profile in matching_profiles:
                if profile.api_key:
                    api_key = decrypt_api_key(profile.api_key)
                    break
        
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Google API key not found"
            )
        
        # 创建服务实例
        google_service = ProviderFactory.create(
            provider='google',
            api_key=api_key,
            user_id=user_id,
            db=db
        )
        
        agent_registry = AgentRegistryService(db=db)
        from ...services.mcp.mcp_manager import get_mcp_manager
        from ...services.gemini.agent.tool_registry import ToolRegistry
        mcp_manager = get_mcp_manager()
        tool_registry = ToolRegistry(mcp_manager=mcp_manager)
        
        # 创建并执行工作流
        from ...services.gemini.agent.workflows.image_edit_workflow import ImageEditWorkflow
        
        workflow = ImageEditWorkflow(
            google_service=google_service,
            agent_registry=agent_registry,
            tool_registry=tool_registry,
            user_id=user_id
        )
        
        result = await workflow.execute(
            image_url=request_body.image_url,
            edit_prompt=request_body.edit_prompt,
            edit_mode=request_body.edit_mode
        )
        
        return result
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error executing image edit workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/excel-analysis")
async def execute_excel_analysis_workflow(
    request_body: ExcelAnalysisWorkflowRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    执行 Excel 分析工作流
    
    Returns:
        分析报告和可视化结果
    """
    try:
        
        # 获取 GoogleService
        from ...models.db_models import UserSettings, ConfigProfile
        from ...core.encryption import decrypt_api_key
        
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        active_profile_id = settings.active_profile_id if settings else None
        
        matching_profiles = db.query(ConfigProfile).filter(
            ConfigProfile.provider_id == 'google',
            ConfigProfile.user_id == user_id
        ).all()
        
        if not matching_profiles:
            raise HTTPException(
                status_code=401,
                detail="Google API key not found. Please configure it in Settings → Profiles."
            )
        
        api_key = None
        if active_profile_id:
            for profile in matching_profiles:
                if profile.id == active_profile_id and profile.api_key:
                    api_key = decrypt_api_key(profile.api_key)
                    break
        
        if not api_key:
            for profile in matching_profiles:
                if profile.api_key:
                    api_key = decrypt_api_key(profile.api_key)
                    break
        
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Google API key not found"
            )
        
        # 创建服务实例
        google_service = ProviderFactory.create(
            provider='google',
            api_key=api_key,
            user_id=user_id,
            db=db
        )
        
        agent_registry = AgentRegistryService(db=db)
        from ...services.mcp.mcp_manager import get_mcp_manager
        from ...services.gemini.agent.tool_registry import ToolRegistry
        mcp_manager = get_mcp_manager()
        tool_registry = ToolRegistry(mcp_manager=mcp_manager)
        
        # 创建并执行工作流
        from ...services.gemini.agent.workflows.excel_analysis_workflow import ExcelAnalysisWorkflow
        
        workflow = ExcelAnalysisWorkflow(
            google_service=google_service,
            agent_registry=agent_registry,
            tool_registry=tool_registry,
            user_id=user_id
        )
        
        result = await workflow.execute(
            file_path=request_body.file_path,
            analysis_type=request_body.analysis_type,
            cleaning_rules=request_body.cleaning_rules
        )
        
        return result
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error executing Excel analysis workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Workflow Templates Management API ====================

class CreateWorkflowTemplateRequest(BaseModel):
    """创建工作流模板请求"""
    name: str
    description: Optional[str] = None
    category: str  # image-edit, excel-analysis, general等
    workflowType: str  # sequential, parallel, coordinator (前端使用 camelCase)
    config: Dict[str, Any]  # 工作流配置（节点、边、参数等）
    isPublic: Optional[bool] = False  # 前端使用 camelCase
    
    class Config:
        # 允许使用字段别名，支持前端 camelCase 和后端 snake_case
        validate_by_name = True


class UpdateWorkflowTemplateRequest(BaseModel):
    """更新工作流模板请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    workflowType: Optional[str] = None  # 前端使用 camelCase
    config: Optional[Dict[str, Any]] = None
    isPublic: Optional[bool] = None  # 前端使用 camelCase
    
    class Config:
        validate_by_name = True


@router.post("/workflows/templates")
async def create_workflow_template(
    request_body: CreateWorkflowTemplateRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    创建工作流模板
    
    Returns:
        创建的模板信息
    """
    try:
        
        from ...services.gemini.agent.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(db=db)
        template = await service.create_template(
            user_id=user_id,
            name=request_body.name,
            description=request_body.description,
            category=request_body.category,
            workflow_type=request_body.workflowType,  # 使用前端字段名
            config=request_body.config,
            is_public=request_body.isPublic  # 使用前端字段名
        )
        
        return template
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error creating workflow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/templates")
async def list_workflow_templates(
    category: Optional[str] = None,
    workflow_type: Optional[str] = None,
    search: Optional[str] = None,
    include_public: bool = True,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    列出工作流模板
    
    Returns:
        模板列表
    """
    logger.info(f"[Multi-Agent API] GET /workflows/templates called: category={category}, workflow_type={workflow_type}, search={search}, include_public={include_public}")
    
    try:
        logger.info(f"[Multi-Agent API] User authenticated: {user_id}")
        
        from ...services.gemini.agent.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(db=db)
        templates = await service.list_templates(
            user_id=user_id,
            category=category,
            workflow_type=workflow_type,
            search=search,
            include_public=include_public
        )
        
        logger.info(f"[Multi-Agent API] Found {len(templates)} templates for user {user_id}")
        return {"templates": templates, "count": len(templates)}
        
    except HTTPException:
        raise  # 重新抛出HTTP异常（401, 404等）
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error listing workflow templates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/workflows/templates/{template_id}")
async def get_workflow_template(
    template_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取工作流模板
    
    Returns:
        模板信息
    """
    try:
        
        from ...services.gemini.agent.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(db=db)
        template = await service.get_template(template_id, user_id=user_id)
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        return template
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error getting workflow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/workflows/templates/{template_id}")
async def update_workflow_template(
    template_id: str,
    request_body: UpdateWorkflowTemplateRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    更新工作流模板
    
    Returns:
        更新后的模板信息
    """
    try:
        
        from ...services.gemini.agent.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(db=db)
        template = await service.update_template(
            user_id=user_id,
            template_id=template_id,
            name=request_body.name,
            description=request_body.description,
            category=request_body.category,
            workflow_type=request_body.workflowType if request_body.workflowType is not None else None,  # 使用前端字段名
            config=request_body.config,
            is_public=request_body.isPublic if request_body.isPublic is not None else None  # 使用前端字段名
        )
        
        return template
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error updating workflow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/workflows/templates/{template_id}")
async def delete_workflow_template(
    template_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    删除工作流模板
    
    Returns:
        删除结果
    """
    try:
        
        from ...services.gemini.agent.workflow_template_service import WorkflowTemplateService
        
        service = WorkflowTemplateService(db=db)
        success = await service.delete_template(user_id=user_id, template_id=template_id)
        
        return {"success": success}
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error deleting workflow template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ADK Samples Template Import API ====================

@router.get("/workflows/adk-samples/templates")
async def list_adk_samples_templates(
    request_obj: Request
):
    """
    列出可用的 ADK samples 模板
    
    Returns:
        可用的 ADK samples 模板列表
    """
    try:
        from ...services.gemini.agent.adk_samples_importer import ADKSamplesImporter
        from ...core.database import SessionLocal
        
        db = SessionLocal()
        try:
            importer = ADKSamplesImporter(db=db)
            templates = await importer.list_available_templates()
            return {"templates": templates, "count": len(templates)}
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error listing ADK samples templates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ImportADKSampleRequest(BaseModel):
    """导入 ADK sample 模板请求"""
    template_id: str  # marketing-agency, data-engineering, customer-service, camel
    custom_name: Optional[str] = None  # 自定义模板名称
    isPublic: Optional[bool] = False  # 前端使用 camelCase
    
    class Config:
        validate_by_name = True


@router.post("/workflows/adk-samples/import")
async def import_adk_samples_template(
    request_body: ImportADKSampleRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    从 ADK samples 导入模板
    
    Returns:
        导入的模板信息
    """
    try:
        
        from ...services.gemini.agent.adk_samples_importer import ADKSamplesImporter
        
        importer = ADKSamplesImporter(db=db)
        template = await importer.import_template(
            user_id=user_id,
            template_id=request_body.template_id,
            custom_name=request_body.custom_name,
            is_public=request_body.isPublic  # 使用前端字段名
        )
        
        return template
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error importing ADK samples template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/adk-samples/import-all")
async def import_all_adk_samples_templates(
    isPublic: bool = False,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    导入所有可用的 ADK samples 模板
    
    Returns:
        导入的模板列表
    """
    try:
        
        from ...services.gemini.agent.adk_samples_importer import ADKSamplesImporter
        
        importer = ADKSamplesImporter(db=db)
        templates = await importer.import_all_templates(
            user_id=user_id,
            is_public=isPublic
        )
        
        return {"templates": templates, "count": len(templates)}
        
    except Exception as e:
        logger.error(f"[Multi-Agent API] Error importing all ADK samples templates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
