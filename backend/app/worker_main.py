"""
独立 Worker 服务入口

此文件可以作为独立进程运行，也可以被 main.py 通过 multiprocessing 调用。

用法:
    独立运行: python -m backend.app.worker_main
    或通过 main.py 自动启动（推荐）
"""

import asyncio
import signal
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 导入环境变量加载（必须在其他导入之前）
try:
    from backend.app.core.env_loader import _ENV_LOADED  # noqa: F401
except ImportError:
    try:
        from app.core.env_loader import _ENV_LOADED  # noqa: F401
    except ImportError:
        from core.env_loader import _ENV_LOADED  # noqa: F401

from backend.app.core.logger import setup_logger, LOG_PREFIXES
from backend.app.services.common.upload_worker_pool import UploadWorkerPool
from backend.app.services.common.redis_queue_service import GlobalRedisConnectionPool

logger = setup_logger("worker")


class WorkerService:
    """独立 Worker 服务"""

    def __init__(self):
        self.worker_pool = UploadWorkerPool()
        self.redis_pool = GlobalRedisConnectionPool.get_instance()
        self._shutdown_event = asyncio.Event()
        self._running = False

    async def start(self):
        """启动 Worker 服务"""
        if self._running:
            logger.warning(f"{LOG_PREFIXES['warning']} Worker service already running")
            return

        self._running = True
        logger.info("=" * 60)
        logger.info("🚀 Starting Upload Worker Service...")
        logger.info("=" * 60)

        try:
            # 初始化 Redis 连接池
            await self.redis_pool.initialize()
            logger.info(f"{LOG_PREFIXES['success']} Redis connection pool initialized")

            # 启动 Worker 池
            await self.worker_pool.start()
            logger.info(f"{LOG_PREFIXES['success']} Worker pool started successfully")

            logger.info("=" * 60)
            logger.info("✅ Worker Service started successfully")
            logger.info("=" * 60)

            # 等待关闭信号
            await self._shutdown_event.wait()
        except Exception as e:
            logger.error(f"{LOG_PREFIXES['error']} Failed to start worker service: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def stop(self):
        """停止 Worker 服务"""
        if not self._running:
            return

        logger.info("🛑 Stopping Worker Service...")

        try:
            await self.worker_pool.stop()
            logger.info(f"{LOG_PREFIXES['success']} Worker pool stopped")

            await self.redis_pool.close()
            logger.info(f"{LOG_PREFIXES['success']} Redis connection pool closed")

            logger.info("✅ Worker Service stopped")
        except Exception as e:
            logger.error(f"{LOG_PREFIXES['error']} Error stopping worker service: {e}")
        finally:
            self._running = False

    def signal_shutdown(self):
        """触发关闭"""
        self._shutdown_event.set()


async def worker_main_async():
    """Worker 主函数（异步版本）"""
    service = WorkerService()

    # 注册信号处理（仅在主线程中有效）
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果事件循环已经在运行，使用 add_signal_handler
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, service.signal_shutdown)
                except (ValueError, RuntimeError):
                    # Windows 或非主线程中可能不支持
                    pass
        else:
            # 如果事件循环未运行，在 Windows 上使用 signal.signal
            if sys.platform == 'win32':
                signal.signal(signal.SIGINT, lambda s, f: service.signal_shutdown())
                signal.signal(signal.SIGTERM, lambda s, f: service.signal_shutdown())
    except Exception as e:
        logger.warning(f"{LOG_PREFIXES['warning']} Could not register signal handlers: {e}")

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info(f"{LOG_PREFIXES['info']} Received interrupt signal")
    except Exception as e:
        logger.error(f"{LOG_PREFIXES['error']} Worker service error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.stop()


def worker_main():
    """Worker 主函数（同步入口，用于 multiprocessing）"""
    try:
        asyncio.run(worker_main_async())
    except KeyboardInterrupt:
        logger.info(f"{LOG_PREFIXES['info']} Worker service interrupted")
    except Exception as e:
        logger.error(f"{LOG_PREFIXES['error']} Worker service failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    worker_main()
