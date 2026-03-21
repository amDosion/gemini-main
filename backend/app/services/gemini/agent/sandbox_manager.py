"""
Sandbox Manager - 沙箱管理器

提供：
- 沙箱资源管理（CPU、内存配置）
- Artifact 管理（GCS 自动保存）
- 状态持久化（14天）
- 安全隔离
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ....models.db_models import AgentCodeSandbox, AgentArtifact
from .code_executor import AgentEngineSandboxCodeExecutor, BuiltInCodeExecutor

logger = logging.getLogger(__name__)


class SandboxManager:
    """
    沙箱管理器
    
    负责：
    - 沙箱资源管理（创建、配置、删除）
    - Artifact 管理（列表、下载、清理）
    - 状态持久化（14天）
    - 安全隔离
    """
    
    def __init__(
        self,
        db: Session,
        use_vertex_ai: bool = True,
        project: Optional[str] = None,
        location: Optional[str] = None
    ):
        """
        初始化沙箱管理器
        
        Args:
            db: 数据库会话
            use_vertex_ai: 是否使用 Vertex AI Sandbox
            project: Google Cloud 项目 ID
            location: Google Cloud 位置
        """
        self.db = db
        
        if use_vertex_ai:
            self.executor = AgentEngineSandboxCodeExecutor(
                db=db,
                project=project,
                location=location
            )
        else:
            self.executor = BuiltInCodeExecutor(db=db)
        
        logger.info(f"[SandboxManager] Initialized (use_vertex_ai={use_vertex_ai})")
    
    async def create_sandbox(
        self,
        user_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建沙箱
        
        Args:
            user_id: 用户 ID
            config: 沙箱配置（可选）
            
        Returns:
            沙箱信息
        """
        now = int(time.time() * 1000)
        
        sandbox = AgentCodeSandbox(
            user_id=user_id,
            config_json=json.dumps(config) if config else None,
            status="active",
            created_at=now,
            updated_at=now
        )
        
        self.db.add(sandbox)
        self.db.commit()
        self.db.refresh(sandbox)
        
        logger.info(f"[SandboxManager] Created sandbox {sandbox.id} for user {user_id}")
        return sandbox.to_dict()
    
    async def get_sandbox(
        self,
        user_id: str,
        sandbox_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取沙箱
        
        Args:
            user_id: 用户 ID
            sandbox_id: 沙箱 ID
            
        Returns:
            沙箱信息，如果不存在则返回 None
        """
        sandbox = self.db.query(AgentCodeSandbox).filter(
            AgentCodeSandbox.id == sandbox_id,
            AgentCodeSandbox.user_id == user_id
        ).first()
        
        if sandbox:
            return sandbox.to_dict()
        return None
    
    async def list_sandboxes(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        列出用户的所有沙箱
        
        Args:
            user_id: 用户 ID
            
        Returns:
            沙箱列表
        """
        sandboxes = self.db.query(AgentCodeSandbox).filter(
            AgentCodeSandbox.user_id == user_id
        ).order_by(AgentCodeSandbox.created_at.desc()).all()
        
        return [sb.to_dict() for sb in sandboxes]
    
    async def execute_code(
        self,
        user_id: str,
        code: str,
        language: str = "python",
        sandbox_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行代码
        
        Args:
            user_id: 用户 ID
            code: 要执行的代码
            language: 编程语言（默认：python）
            sandbox_id: 沙箱 ID（可选）
            
        Returns:
            执行结果
        """
        return await self.executor.execute_code(
            user_id=user_id,
            code=code,
            language=language,
            sandbox_id=sandbox_id
        )
    
    async def get_artifacts(
        self,
        user_id: str,
        sandbox_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取 Artifact 列表
        
        Args:
            user_id: 用户 ID
            sandbox_id: 沙箱 ID（可选）
            
        Returns:
            Artifact 列表
        """
        return await self.executor.get_artifacts(
            user_id=user_id,
            sandbox_id=sandbox_id
        )
    
    async def get_artifact(
        self,
        user_id: str,
        artifact_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取 Artifact
        
        Args:
            user_id: 用户 ID
            artifact_id: Artifact ID
            
        Returns:
            Artifact 信息，如果不存在则返回 None
        """
        artifact = self.db.query(AgentArtifact).filter(
            AgentArtifact.id == artifact_id,
            AgentArtifact.user_id == user_id
        ).first()
        
        if artifact:
            return artifact.to_dict()
        return None
    
    async def delete_sandbox(
        self,
        user_id: str,
        sandbox_id: str
    ) -> bool:
        """
        删除沙箱
        
        Args:
            user_id: 用户 ID
            sandbox_id: 沙箱 ID
            
        Returns:
            是否删除成功
        """
        sandbox = self.db.query(AgentCodeSandbox).filter(
            AgentCodeSandbox.id == sandbox_id,
            AgentCodeSandbox.user_id == user_id
        ).first()
        
        if sandbox:
            sandbox.status = "inactive"
            self.db.commit()
            logger.info(f"[SandboxManager] Deleted sandbox {sandbox_id} for user {user_id}")
            return True
        
        return False
