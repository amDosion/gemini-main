"""
统一初始化 API 路由
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
import logging

from ...core.database import SessionLocal
from ...core.dependencies import require_current_user
from ...services.common.init_service import get_init_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["init"])


def get_db():
    """数据库会话依赖"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/init")
async def get_init(
    user_id: str = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    统一初始化端点 - 返回应用启动所需的所有数据
    
    返回：
    - profiles: 所有配置列表
    - activeProfileId: 当前激活的配置 ID
    - activeProfile: 当前激活的配置（完整数据）
    - dashscopeKey: 通义千问的 API Key
    - storageConfigs: 云存储配置列表
    - activeStorageId: 当前激活的存储配置 ID
    - sessions: 会话列表（含消息和附件）
    - personas: 角色列表
    - cachedModels: 缓存的模型列表（可选）
    - _metadata: 元数据（时间戳、部分失败标记）
    
    错误处理：
    - 401: 未认证（由 require_current_user 抛出）
    - 500: 数据库连接失败或关键错误
    - 200 + _metadata.partialFailures: 部分数据加载失败
    """
    
    try:
        # 调用 init_service 获取所有初始化数据
        init_data = await get_init_data(user_id, db)
        return init_data
    except Exception as e:
        # 记录错误日志
        logger.error(f"Failed to load initialization data for user {user_id}: {e}", exc_info=True)
        # 返回 500 错误
        raise HTTPException(
            status_code=500,
            detail="Failed to load initialization data. Please try again later."
        )
