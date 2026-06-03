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

from .path_utils import ensure_credentials_dir

logger = logging.getLogger(__name__)


def _optional_ddl_info_prefix(log_prefixes: Dict[str, str]) -> str:
    return log_prefixes.get("info") or log_prefixes.get("success") or "[INFO]"


def _is_optional_ddl_permission_error(exc: Exception) -> bool:
    original = getattr(exc, "orig", None)
    pgcode = getattr(original, "pgcode", None) or getattr(original, "sqlstate", None)
    if pgcode == "42501":
        return True

    message = str(exc).lower()
    return (
        "must be owner of table" in message
        or "permission denied" in message
        or "insufficientprivilege" in message
    )


def _table_schema_is_manageable(conn: Any, table: str) -> bool:
    if getattr(conn.dialect, "name", "") != "postgresql":
        return True

    from sqlalchemy import text

    result = conn.execute(
        text(
            """
            SELECT COALESCE(
                (
                    SELECT pg_has_role(c.relowner, 'MEMBER')
                    FROM pg_catalog.pg_class c
                    WHERE c.oid = to_regclass(:table_name)
                ),
                FALSE
            )
            """
        ),
        {"table_name": table},
    ).scalar()
    return bool(result)


def _ensure_optional_index(
    *,
    engine: Any,
    table_names: set[str],
    table: str,
    index_name: str,
    sql: str,
    log_prefixes: Dict[str, str],
) -> bool:
    if table not in table_names:
        return False

    from sqlalchemy import text

    info_prefix = _optional_ddl_info_prefix(log_prefixes)
    try:
        with engine.connect() as conn:
            if not _table_schema_is_manageable(conn, table):
                logger.info(
                    f"{info_prefix} Skipping optional index {index_name} on {table}: "
                    "database user is not the table owner"
                )
                return False
    except Exception as exc:
        logger.info(
            f"{info_prefix} Skipping optional index {index_name} on {table}: "
            f"could not verify table ownership ({exc})"
        )
        return False

    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
        logger.info(f"{log_prefixes['success']} Ensured index {index_name} on {table}")
        return True
    except Exception as exc:
        if _is_optional_ddl_permission_error(exc):
            logger.info(
                f"{info_prefix} Skipping optional index {index_name} on {table}: "
                "database user cannot create indexes on this table"
            )
        else:
            logger.warning(f"{log_prefixes['warning']} Failed to ensure {index_name}: {exc}")
        return False


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


def assert_jwt_secret_configured(log_prefixes: Dict[str, str]) -> None:
    """启动前置断言：JWT_SECRET_KEY 必须已配置。

    jwt_utils 现在延迟解析密钥（import 不再有副作用），因此配置缺失不会再以
    不透明的 import-chain 失败暴露。为保留"配置错误立即失败"的语义，这里在
    启动阶段显式做一次 fail-fast 校验，给出清晰的错误信息，而不是等到第一次
    登录请求才在请求路径里报错。

    Raises:
        RuntimeError: JWT_SECRET_KEY 未配置。
    """
    from .jwt_utils import _get_cached_jwt_secret, clear_jwt_secret_cache

    # 清缓存以确保读取的是当前进程环境中的真实配置（支持启动期热轮换语义）。
    clear_jwt_secret_cache()
    try:
        _get_cached_jwt_secret()
    except RuntimeError as exc:
        logger.error(
            f"{log_prefixes['error']} JWT_SECRET_KEY 未配置，应用无法安全启动: {exc}"
        )
        raise RuntimeError(
            "JWT_SECRET_KEY is not configured. Set it via environment variable "
            "or secret manager before starting the application."
        ) from exc


async def initialize_database_schema(log_prefixes: Dict[str, str]):
    """
    初始化数据库表结构（Base.metadata.create_all）。

    之前此调用内联在 main.py 的模块导入阶段执行（import 即建表），属于一个
    重副作用：导入应用包就会连库建表，污染测试/只读/CLI 等场景，并且把数据库
    可用性耦合进 import-chain。现移至 lifespan 启动期，作为显式启动任务，
    使建表只在应用真正启动时发生。

    与旧行为保持一致：建表失败仅告警（不中断启动），交由后续迁移任务/手工修复。

    Args:
        log_prefixes: 日志前缀字典
    """
    try:
        from .database import Base, engine

        Base.metadata.create_all(bind=engine)
        logger.info(f"{log_prefixes['success']} Database tables initialized")
    except Exception as e:
        logger.warning(f"{log_prefixes['warning']} Database initialization failed: {e}")


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


async def migrate_ip_login_history_index(log_prefixes: Dict[str, str]):
    """
    ✅ A-9: 在 ip_login_history 上幂等补建复合索引 (user_id, action, created_at)。

    AuthService.get_current_user() 会按 user_id+action='login' 过滤并按 created_at
    倒序取首条；缺索引时会退化为表扫描 + sort，登录期间显著影响延迟。
    declarative 模型已声明该索引，但已有库需要在启动期通过
    CREATE INDEX IF NOT EXISTS 补建（项目当前无 alembic）。
    """
    try:
        from sqlalchemy import inspect, text
        from .database import engine

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        if "ip_login_history" not in table_names:
            logger.info(
                f"{log_prefixes.get('info', log_prefixes['success'])} "
                "ip_login_history table not found, skip index migration"
            )
            return

        _ensure_optional_index(
            engine=engine,
            table_names=table_names,
            table="ip_login_history",
            index_name="ix_ip_login_user_action_time",
            sql=(
                "CREATE INDEX IF NOT EXISTS ix_ip_login_user_action_time "
                "ON ip_login_history (user_id, action, created_at)"
            ),
            log_prefixes=log_prefixes,
        )
    except Exception as e:
        logger.warning(
            f"{log_prefixes['warning']} Failed to ensure ip_login_history index: {e}"
        )


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


async def ensure_performance_indexes(log_prefixes: Dict[str, str]):
    """
    兼容旧库：为已部署实例补建 declarative 模型新增的复合索引。

    覆盖的索引：
    - message_index(session_id, seq) + (session_id, mode, seq) — 修正之前只在注释里的索引
    - workflow_executions(user_id, started_at) — 按用户最近优先
    - node_executions(execution_id, node_id, status) — 节点状态更新
    - config_profiles(user_id, provider_id text_pattern_ops) — LIKE 'google%' 前缀匹配

    `CREATE INDEX IF NOT EXISTS` 幂等执行，已存在时不报错。
    """
    try:
        from sqlalchemy import inspect, text
        from .database import engine

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())

        migrations: list[tuple[str, str, str]] = [
            (
                "message_index",
                "idx_message_index_session_seq",
                "CREATE INDEX IF NOT EXISTS idx_message_index_session_seq "
                "ON message_index (session_id, seq)",
            ),
            (
                "message_index",
                "idx_message_index_session_mode_seq",
                "CREATE INDEX IF NOT EXISTS idx_message_index_session_mode_seq "
                "ON message_index (session_id, mode, seq)",
            ),
            (
                "workflow_executions",
                "ix_workflow_exec_user_started_desc",
                "CREATE INDEX IF NOT EXISTS ix_workflow_exec_user_started_desc "
                "ON workflow_executions (user_id, started_at)",
            ),
            (
                "node_executions",
                "ix_node_exec_execution_node_status",
                "CREATE INDEX IF NOT EXISTS ix_node_exec_execution_node_status "
                "ON node_executions (execution_id, node_id, status)",
            ),
            (
                "config_profiles",
                "ix_config_profiles_user_provider",
                "CREATE INDEX IF NOT EXISTS ix_config_profiles_user_provider "
                "ON config_profiles (user_id, provider_id text_pattern_ops)",
            ),
        ]

        for table, index_name, sql in migrations:
            _ensure_optional_index(
                engine=engine,
                table_names=table_names,
                table=table,
                index_name=index_name,
                sql=sql,
                log_prefixes=log_prefixes,
            )
    except Exception as e:
        logger.warning(f"{log_prefixes['warning']} Failed to ensure performance indexes: {e}")


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
                logger.info(f"{log_prefixes['success']} Worker pool startup verification passed (on-demand mode)")
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
    # 1. 配置 logger（必须最先完成，后续任务依赖日志）
    await setup_logger_configuration(log_prefixes)

    # 1.5 凭证目录（同步、幂等、放在加密密钥初始化之前）
    # 之前由 path_utils 导入时副作用创建，已挪到此处以避免 read-only / pytest 等场景 import 即崩溃
    try:
        ensure_credentials_dir()
    except OSError as e:
        logger.error(f"{log_prefixes['error']} Failed to ensure credentials dir: {e}")
        raise

    # 1.6 JWT_SECRET_KEY 前置校验（fail-fast）。
    # jwt_utils 现在延迟解析密钥，配置缺失不会再在 import 期崩溃，因此在此处
    # 显式断言，使误配置以清晰的启动错误暴露，而非在首个登录请求时报错。
    assert_jwt_secret_configured(log_prefixes)

    # 1.7 初始化数据库表结构（之前在 main.py import 期内联执行，现移至启动期）。
    # 必须在依赖表存在的迁移任务（Group 2）之前完成。
    await initialize_database_schema(log_prefixes)

    # 2. Group 1: 无依赖的初始化任务（并行）
    await asyncio.gather(
        initialize_encryption_keys(log_prefixes),
        initialize_system_config(log_prefixes),
        initialize_redis_pool(log_prefixes),
    )

    # 3. Group 2: 依赖 Group 1 的任务（并行）
    # validate_provider_configs 从 Group 1 移到此处作为防御深度——若未来在 validate
    # 中加入"测试解密样例凭证"等逻辑，需要 encryption_keys 已就绪。
    await asyncio.gather(
        validate_provider_configs(log_prefixes),
        migrate_user_admin_schema(log_prefixes),
        migrate_workflow_idempotency_schema(log_prefixes),
        migrate_ip_login_history_index(log_prefixes),
        ensure_performance_indexes(log_prefixes),
    )

    # 4. Group 3: 清理任务（依赖迁移完成，并行）
    await asyncio.gather(
        cleanup_expired_tokens(log_prefixes),
        reconcile_orphan_workflow_executions(log_prefixes),
    )

    # 5. 启动 Worker 池（最后执行）
    worker_mode = await start_worker_pool(worker_pool, worker_pool_available, log_prefixes)

    return {
        'worker_mode': worker_mode,
        'current_pid': os.getpid()
    }
