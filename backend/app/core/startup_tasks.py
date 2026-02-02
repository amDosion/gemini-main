"""
应用启动任务模块

包含所有应用启动时需要执行的初始化任务。
"""

import asyncio
import os
import logging
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

    # 4. 初始化 Redis 连接池
    await initialize_redis_pool(log_prefixes)

    # 5. 清理过期 tokens
    await cleanup_expired_tokens(log_prefixes)

    # 6. 验证 provider 配置
    await validate_provider_configs(log_prefixes)

    # 7. 启动 Worker 池
    worker_mode = await start_worker_pool(worker_pool, worker_pool_available, log_prefixes)

    return {
        'worker_mode': worker_mode,
        'current_pid': os.getpid()
    }
