"""
Code Execution API Router - 代码执行 API 路由

提供：
- POST /api/code-execution/execute：执行代码
- GET /api/code-execution/artifacts：获取 Artifact
- GET /api/code-execution/artifacts/{artifact_id}：下载 Artifact
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import logging

from ...core.database import get_db
from ...core.dependencies import require_current_user
from ...services.gemini.agent.sandbox_manager import SandboxManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/code-execution", tags=["code-execution"])


# ==================== Request/Response Models ====================

class ExecuteCodeRequest(BaseModel):
    """执行代码请求"""
    code: str
    language: str = "python"
    sandbox_id: Optional[str] = None


class CreateSandboxRequest(BaseModel):
    """创建沙箱请求"""
    config: Optional[Dict[str, Any]] = None


# ==================== API Endpoints ====================

@router.post("/sandboxes")
async def create_sandbox(
    request: CreateSandboxRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    创建沙箱
    
    Returns:
        沙箱信息
    """
    try:
        
        manager = SandboxManager(db=db)
        sandbox = await manager.create_sandbox(
            user_id=user_id,
            config=request.config
        )
        
        return sandbox
        
    except Exception as e:
        logger.error(f"[Code Execution API] Error creating sandbox: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sandboxes")
async def list_sandboxes(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    列出用户的所有沙箱
    
    Returns:
        沙箱列表
    """
    try:
        
        manager = SandboxManager(db=db)
        sandboxes = await manager.list_sandboxes(user_id=user_id)
        
        return {"sandboxes": sandboxes}
        
    except Exception as e:
        logger.error(f"[Code Execution API] Error listing sandboxes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sandboxes/{sandbox_id}")
async def get_sandbox(
    sandbox_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取沙箱
    
    Returns:
        沙箱信息
    """
    try:
        
        manager = SandboxManager(db=db)
        sandbox = await manager.get_sandbox(
            user_id=user_id,
            sandbox_id=sandbox_id
        )
        
        if not sandbox:
            raise HTTPException(status_code=404, detail="Sandbox not found")
        
        return sandbox
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Code Execution API] Error getting sandbox: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sandboxes/{sandbox_id}")
async def delete_sandbox(
    sandbox_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    删除沙箱
    
    Returns:
        删除结果
    """
    try:
        
        manager = SandboxManager(db=db)
        success = await manager.delete_sandbox(
            user_id=user_id,
            sandbox_id=sandbox_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Sandbox not found")
        
        return {"success": True, "message": "Sandbox deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Code Execution API] Error deleting sandbox: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_code(
    request_body: ExecuteCodeRequest,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    执行代码
    
    Returns:
        执行结果
    """
    try:
        
        manager = SandboxManager(db=db)
        result = await manager.execute_code(
            user_id=user_id,
            code=request_body.code,
            language=request_body.language,
            sandbox_id=request_body.sandbox_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"[Code Execution API] Error executing code: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts")
async def list_artifacts(
    sandbox_id: Optional[str] = None,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取 Artifact 列表
    
    Returns:
        Artifact 列表
    """
    try:
        
        manager = SandboxManager(db=db)
        artifacts = await manager.get_artifacts(
            user_id=user_id,
            sandbox_id=sandbox_id
        )
        
        return {"artifacts": artifacts, "count": len(artifacts)}
        
    except Exception as e:
        logger.error(f"[Code Execution API] Error listing artifacts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    获取 Artifact
    
    Returns:
        Artifact 信息
    """
    try:
        
        manager = SandboxManager(db=db)
        artifact = await manager.get_artifact(
            user_id=user_id,
            artifact_id=artifact_id
        )
        
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        
        return artifact
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Code Execution API] Error getting artifact: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
