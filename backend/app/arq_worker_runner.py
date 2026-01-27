"""
ARQ Worker 启动脚本

用于在子进程中启动 ARQ Worker，避免命令行参数解析问题。
"""

import sys
import os
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 设置工作目录
os.chdir(str(project_root))

# 导入环境变量加载（必须在其他导入之前）
try:
    from backend.app.core.env_loader import _ENV_LOADED  # noqa: F401
except ImportError:
    try:
        from app.core.env_loader import _ENV_LOADED  # noqa: F401
    except ImportError:
        from core.env_loader import _ENV_LOADED  # noqa: F401

# 运行 ARQ Worker
if __name__ == "__main__":
    try:
        from arq.worker import Worker
        from backend.app.arq_worker import WorkerSettings
        
        # 创建并运行 Worker
        # Worker.run() 会阻塞直到 Worker 停止，并自动处理事件循环
        worker = Worker(WorkerSettings)
        worker.run()  # 阻塞运行，自动创建事件循环
    except ImportError as e:
        print(f"[ARQ Worker] Error: ARQ is not installed: {e}")
        print("[ARQ Worker] Please install it: pip install arq")
        sys.exit(1)
    except KeyboardInterrupt:
        print("[ARQ Worker] Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"[ARQ Worker] Error starting worker: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
