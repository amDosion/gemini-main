"""
统一的环境变量加载模块

确保 .env 文件只加载一次，避免重复加载。
所有需要环境变量的模块都应该导入此模块。
"""
from pathlib import Path
from dotenv import load_dotenv

# 尽量从 backend/.env 加载环境变量（避免因启动目录不同导致读取不到配置）
_backend_env = Path(__file__).resolve().parents[2] / ".env"
if _backend_env.exists():
    load_dotenv(dotenv_path=_backend_env, override=False)
else:
    load_dotenv(override=False)  # 回退：从当前工作目录向上查找 .env

# 标记已加载（用于调试）
_ENV_LOADED = True
