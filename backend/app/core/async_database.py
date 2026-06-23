"""
异步数据库引擎与会话（与同步 engine 并行存在，可逐步迁移）

本模块在不破坏现有同步 SQLAlchemy 调用路径的前提下，引入 asyncpg
驱动的 async engine 与 AsyncSession，供新代码与高流量路由按 PR
逐步迁移使用。

设计要点（保持极简，避免破坏现有 ~440+ 处同步 db.query/execute/commit）：
- 继续读取统一的 DATABASE_URL；自动将 `postgresql://` 或
  `postgresql+psycopg2://` 重写为 `postgresql+asyncpg://`。
  已显式声明 `+asyncpg` 的 URL 原样使用。
- 复用同步引擎的连接池规模/回收等环境变量。
- 提供 FastAPI 依赖注入 `get_async_db`，签名与现有 `get_db` 对称。
- ORM Base 不重复定义；继续从 `app.core.database` 导入 Base
  以保持模型映射一致（同一份 metadata，sync/async 路径都能使用）。

切勿在本文件中改动同步 engine 或 SessionLocal。这是 ARCH-A 迁移的
基础设施层；路由迁移在后续 PR 中分阶段进行（见 app/core/MIGRATION.md）。
"""
from __future__ import annotations

import os
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# 复用已有 .env 加载与 DATABASE_URL 校验（同步模块已完成校验）
from .database import Base, DATABASE_URL  # noqa: F401  (Base re-export 供 async 路径使用)

# database.py raises ValueError when DATABASE_URL is falsy; keep the runtime
# guard here too so optimized Python builds do not remove the check.
if DATABASE_URL is None:
    raise RuntimeError("DATABASE_URL must be set (validated in database.py)")


def _to_async_url(url: str) -> str:
    """将同步 DATABASE_URL 转换为 asyncpg 驱动 URL。

    支持的输入前缀：
      - postgresql://...
      - postgresql+psycopg2://...
      - postgresql+asyncpg://...  (原样返回)
    """
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+asyncpg://" + url[len("postgresql+psycopg2://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    # 其它前缀直接返回，由上游 SQLAlchemy 报错
    return url


ASYNC_DATABASE_URL = _to_async_url(DATABASE_URL)

# 异步引擎参数：与同步侧保持一致的池配置
_async_engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
    "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
    "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
}

async_engine = create_async_engine(ASYNC_DATABASE_URL, **_async_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # FastAPI 响应序列化时避免触发 lazy load IO
)


async def get_async_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 异步依赖：提供请求级 AsyncSession，请求结束自动关闭。

    与同步 `get_db` 对称使用：

        @router.get("/...")
        async def handler(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(Model).where(...))
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


__all__ = [
    "ASYNC_DATABASE_URL",
    "AsyncSessionLocal",
    "async_engine",
    "Base",
    "get_async_db",
]
