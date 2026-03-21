"""
应用启动任务模块

包含所有应用启动时需要执行的初始化任务。
"""

import asyncio
import os
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def setup_logger_configuration(log_prefixes: Dict[str, str]):
    """
    重新配置 logger（防止 Uvicorn 覆盖）

    Args:
        log_prefixes: 日志前缀字典
    """
    try:
        from .logger import setup_root_logger, ensure_service_loggers, diagnose_logger_handlers

        # 重新配置根 logger（防止 Uvicorn 覆盖）
        setup_root_logger()
        # 确保所有服务 logger 配置正确
        ensure_service_loggers()
        # 输出诊断信息（验证 handler 数量，应该只有 1 个）
        diag = diagnose_logger_handlers()

        logger.info(f"{log_prefixes['success']} Logger configuration ensured in lifespan")
        logger.info(f"{log_prefixes['info']} Root logger handlers: {diag['handlers_count']} (expected: 1)")
    except Exception as e:
        logger.warning(f"{log_prefixes['warning']} Failed to ensure logger configuration: {e}")


async def initialize_encryption_keys(log_prefixes: Dict[str, str]):
    """
    初始化加密密钥（从 .env 文件读取）

    Args:
        log_prefixes: 日志前缀字典

    Raises:
        Exception: 密钥初始化失败时抛出
    """
    try:
        from .encryption import EncryptionKeyManager
        from .jwt_utils import JWTSecretManager

        # 确保 ENCRYPTION_KEY 已读取（从 .env 文件）
        encryption_key = EncryptionKeyManager.get_or_create_key()
        # 显示前 8 个字符和后 4 个字符，中间用 ... 代替
        masked_key = f"{encryption_key[:8]}...{encryption_key[-4:]}" if len(encryption_key) > 12 else encryption_key
        logger.info(f"{log_prefixes['success']} ENCRYPTION_KEY 已初始化（长度: {len(encryption_key)}, 值: {masked_key}）")

        # 确保 JWT_SECRET_KEY 已读取（从 .env 文件）
        jwt_secret = JWTSecretManager.get_or_create_secret()
        # 显示前 8 个字符和后 4 个字符，中间用 ... 代替
        masked_secret = f"{jwt_secret[:8]}...{jwt_secret[-4:]}" if len(jwt_secret) > 12 else jwt_secret
        logger.info(f"{log_prefixes['success']} JWT_SECRET_KEY 已初始化（长度: {len(jwt_secret)}, 值: {masked_secret}）")
    except Exception as e:
        logger.error(f"{log_prefixes['error']} 密钥初始化失败: {e}")
        raise


async def initialize_system_config(log_prefixes: Dict[str, str]):
    """
    初始化系统配置

    Args:
        log_prefixes: 日志前缀字典
    """
    try:
        from .database import SessionLocal
        from ..services.common.system_config_service import initialize_system_configs

        db = SessionLocal()
        try:
            initialize_system_configs(db)
            logger.info(f"{log_prefixes['success']} System configuration initialized")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"{log_prefixes['warning']} Failed to initialize system config: {e}")


async def migrate_user_admin_schema(log_prefixes: Dict[str, str]):
    """
    兼容旧库：确保 users.is_admin 字段存在，并为历史数据回填管理员。

    规则：
    - 若字段不存在，则执行 ALTER TABLE 添加字段（默认 false）；
    - 若当前无任何管理员，则将最早注册用户设为管理员。
    """
    try:
        from sqlalchemy import inspect, text
        from .database import engine, SessionLocal
        from ..models.db_models import User

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        if "users" not in table_names:
            logger.warning(f"{log_prefixes['warning']} users table not found, skip admin schema migration")
            return

        columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_admin" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"))
            logger.info(f"{log_prefixes['success']} Added users.is_admin column")

        db = SessionLocal()
        try:
            has_admin = db.query(User.id).filter(User.is_admin.is_(True)).first() is not None
            if not has_admin:
                first_user = db.query(User).order_by(User.created_at.asc(), User.id.asc()).first()
                if first_user:
                    first_user.is_admin = True
                    db.commit()
                    logger.info(
                        f"{log_prefixes['success']} Backfilled first user as admin: {first_user.id}"
                    )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"{log_prefixes['warning']} Failed to migrate users.is_admin schema: {e}")


async def migrate_workflow_idempotency_schema(log_prefixes: Dict[str, str]):
    """
    兼容旧库：确保 workflow_executions.idempotency_key 与跨实例唯一约束存在。

    说明：
    - 使用部分唯一索引 (user_id, idempotency_key) WHERE idempotency_key IS NOT NULL；
    - 等价于“同用户同幂等键仅允许一个执行记录”，且允许空值重复。
    """
    try:
        from sqlalchemy import inspect, text
        from .database import engine

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        if "workflow_executions" not in table_names:
            logger.warning(
                f"{log_prefixes['warning']} workflow_executions table not found, skip idempotency schema migration"
            )
            return

        columns = {column["name"] for column in inspector.get_columns("workflow_executions")}
        with engine.begin() as conn:
            if "idempotency_key" not in columns:
                conn.execute(
                    text("ALTER TABLE workflow_executions ADD COLUMN idempotency_key VARCHAR(128)")
                )
                logger.info(
                    f"{log_prefixes['success']} Added workflow_executions.idempotency_key column"
                )

            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_workflow_execution_user_idempotency_key
                    ON workflow_executions (user_id, idempotency_key)
                    WHERE idempotency_key IS NOT NULL
                    """
                )
            )
        logger.info(
            f"{log_prefixes['success']} Ensured workflow idempotency unique index"
        )
    except Exception as e:
        logger.warning(f"{log_prefixes['warning']} Failed to migrate workflow idempotency schema: {e}")


async def initialize_redis_pool(log_prefixes: Dict[str, str]):
    """
    初始化全局 Redis 连接池

    Args:
        log_prefixes: 日志前缀字典
    """
    try:
        from ..services.common.redis_queue_service import GlobalRedisConnectionPool

        global_redis_pool = GlobalRedisConnectionPool.get_instance()
        await global_redis_pool.initialize()
        logger.info(f"{log_prefixes['success']} Global Redis connection pool initialized")
    except Exception as e:
        logger.error(f"{log_prefixes['error']} Failed to initialize global Redis connection pool: {e}")
        logger.error("WARNING: Application will continue but Redis operations may fail!")
        import traceback
        traceback.print_exc()


async def cleanup_expired_tokens(log_prefixes: Dict[str, str]):
    """
    启动时清理过期的 refresh_tokens

    Args:
        log_prefixes: 日志前缀字典
    """
    try:
        from .database import SessionLocal
        from ..models.db_models import RefreshToken

        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            # 删除已过期或已撤销超过 7 天的记录
            cleanup_threshold = now - timedelta(days=7)
            deleted_count = db.query(RefreshToken).filter(
                (RefreshToken.expires_at < now) |
                (
                    (RefreshToken.revoked_at.isnot(None)) &
                    (RefreshToken.revoked_at < cleanup_threshold)
                )
            ).delete()
            db.commit()
            if deleted_count > 0:
                logger.info(f"{log_prefixes['success']} Cleaned up {deleted_count} expired/revoked refresh tokens on startup")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"{log_prefixes['warning']} Failed to cleanup refresh tokens: {e}")


async def reconcile_orphan_workflow_executions(
    log_prefixes: Dict[str, str],
    session_factory: Optional[Any] = None,
):
    """
    启动时回收“孤儿工作流执行”。

    场景：
    - 后端重启前，执行状态仍是 running；
    - 内存任务已丢失，继续保持 running 会导致 UI 长时间显示“执行中”。
    """
    try:
        if session_factory is None:
            from .database import SessionLocal
            session_factory = SessionLocal

        from ..models.db_models import WorkflowExecution, NodeExecution

        db = session_factory()
        try:
            running_rows = db.query(WorkflowExecution).filter(
                WorkflowExecution.status == "running"
            ).all()
            if not running_rows:
                return

            now = int(time.time() * 1000)
            execution_ids = [str(row.id) for row in running_rows if row.id]
            for row in running_rows:
                row.status = "cancelled"
                if not row.completed_at:
                    row.completed_at = now
                if not row.error:
                    row.error = (
                        "Execution cancelled after backend restart "
                        "(orphan running task recovered)."
                    )

            running_node_updated = 0
            pending_node_updated = 0
            if execution_ids:
                running_node_updated = db.query(NodeExecution).filter(
                    NodeExecution.execution_id.in_(execution_ids),
                    NodeExecution.status == "running",
                ).update(
                    {
                        "status": "failed",
                        "completed_at": now,
                        "error": "Node cancelled because backend restarted during execution.",
                    },
                    synchronize_session=False,
                )
                pending_node_updated = db.query(NodeExecution).filter(
                    NodeExecution.execution_id.in_(execution_ids),
                    NodeExecution.status == "pending",
                ).update(
                    {
                        "status": "skipped",
                        "completed_at": now,
                        "error": "Node skipped due to upstream cancellation after backend restart.",
                    },
                    synchronize_session=False,
                )

            db.commit()
            logger.warning(
                f"{log_prefixes['warning']} Reconciled {len(execution_ids)} orphan workflow executions "
                f"(running_nodes={int(running_node_updated or 0)}, pending_nodes={int(pending_node_updated or 0)})"
            )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"{log_prefixes['warning']} Failed to reconcile orphan workflow executions: {e}")


async def validate_provider_configs(log_prefixes: Dict[str, str]):
    """
    验证 provider 配置

    Args:
        log_prefixes: 日志前缀字典
    """
    logger.info(f"{log_prefixes['info']} Validating provider configurations...")
    try:
        from ..services.common.provider_config import ProviderConfig

        validation_results = ProviderConfig.validate_all_configs()
        invalid_providers = [p for p, valid in validation_results.items() if not valid]

        if invalid_providers:
            warning_msg = f"{log_prefixes['warning']} Some providers have invalid configurations: {', '.join(invalid_providers)}"
            logger.warning(warning_msg)
        else:
            logger.info(f"{log_prefixes['success']} All provider configurations validated successfully")
    except Exception as e:
        logger.error(f"{log_prefixes['error']} Failed to validate provider configurations: {e}")
        logger.error("WARNING: Application will continue but some providers may not work correctly!")


async def start_worker_pool(
    worker_pool: Any,
    worker_pool_available: bool,
    log_prefixes: Dict[str, str]
) -> str:
    """
    启动 Worker 池

    Args:
        worker_pool: Worker 池实例
        worker_pool_available: Worker 池是否可用
        log_prefixes: 日志前缀字典

    Returns:
        str: Worker 模式 ('embedded', 'disabled', 或 'unavailable')
    """
    # 获取 Worker 运行模式
    try:
        from .config import settings
        worker_mode = settings.worker_mode.lower()
    except Exception as e:
        logger.warning(f"{log_prefixes['warning']} Could not read worker_mode from settings: {e}, using 'embedded'")
        worker_mode = "embedded"

    if worker_pool_available and worker_mode != "disabled":
        if worker_mode == "embedded":
            # 模式：内嵌在主进程中（默认，推荐）
            logger.info(f"{log_prefixes['info']} Starting upload worker pool (embedded mode, on-demand)...")
            try:
                await worker_pool.start()
                logger.info(f"{log_prefixes['success']} Upload worker pool started successfully (embedded mode)")
                logger.warning(f"{log_prefixes['success']} Worker pool startup verification passed (on-demand mode)")
                logger.info(f"{log_prefixes['info']} Workers will start on-demand when tasks are submitted")
            except Exception as e:
                logger.error(f"{log_prefixes['error']} Failed to start upload worker pool: {e}")
                logger.error("WARNING: Application will continue but async uploads will NOT work!")
                import traceback
                traceback.print_exc()
        else:
            logger.warning(f"{log_prefixes['warning']} Unknown worker_mode: {worker_mode}, valid values: 'embedded', 'disabled'")
            logger.warning(f"{log_prefixes['warning']} Falling back to 'embedded' mode")
            try:
                await worker_pool.start()
                logger.info(f"{log_prefixes['success']} Upload worker pool started (fallback to embedded mode)")
            except Exception as e:
                logger.error(f"{log_prefixes['error']} Failed to start upload worker pool: {e}")
    elif worker_mode == "disabled":
        logger.info(f"{log_prefixes['info']} Worker mode is 'disabled', skipping worker startup")
        logger.info(f"{log_prefixes['info']} Make sure an external worker service is running")
    else:
        logger.warning(f"{log_prefixes['warning']} Upload worker pool not available, async uploads will not work")
        worker_mode = "unavailable"

    return worker_mode


async def run_all_startup_tasks(
    worker_pool: Any,
    worker_pool_available: bool,
    log_prefixes: Dict[str, str]
) -> Dict[str, Any]:
    """
    执行所有启动任务

    Args:
        worker_pool: Worker 池实例
        worker_pool_available: Worker 池是否可用
        log_prefixes: 日志前缀字典

    Returns:
        Dict: 启动任务结果，包含 worker_mode 等信息
    """
    # 1. 配置 logger
    await setup_logger_configuration(log_prefixes)

    # 2. 初始化密钥
    await initialize_encryption_keys(log_prefixes)

    # 3. 初始化系统配置
    await initialize_system_config(log_prefixes)

    # 4. 迁移 users 管理员字段（兼容旧库）
    await migrate_user_admin_schema(log_prefixes)

    # 5. 迁移 workflow 幂等字段/索引（兼容旧库）
    await migrate_workflow_idempotency_schema(log_prefixes)

    # 6. 初始化 Redis 连接池
    await initialize_redis_pool(log_prefixes)

    # 7. 清理过期 tokens
    await cleanup_expired_tokens(log_prefixes)

    # 8. 回收重启遗留的 running 工作流执行
    await reconcile_orphan_workflow_executions(log_prefixes)

    # 9. 验证 provider 配置
    await validate_provider_configs(log_prefixes)

    # 10. 启动 Worker 池
    worker_mode = await start_worker_pool(worker_pool, worker_pool_available, log_prefixes)

    return {
        'worker_mode': worker_mode,
        'current_pid': os.getpid()
    }
