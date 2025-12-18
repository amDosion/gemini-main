"""
应用配置模块
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 尽量从 backend/.env 加载环境变量（避免因启动目录不同导致读取不到 Redis/DB 配置）
_backend_env = Path(__file__).resolve().parents[2] / ".env"
if _backend_env.exists():
    load_dotenv(dotenv_path=_backend_env)
else:
    load_dotenv()


class Settings(BaseSettings):
    """应用配置类"""

    # 数据库配置
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./test.db")

    # Redis 配置
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: str | None = os.getenv("REDIS_PASSWORD")

    # 上传队列配置
    upload_queue_workers: int = int(os.getenv("UPLOAD_QUEUE_WORKERS", "5"))
    upload_queue_max_retries: int = int(os.getenv("UPLOAD_QUEUE_MAX_RETRIES", "3"))
    upload_queue_retry_delay: float = float(os.getenv("UPLOAD_QUEUE_RETRY_DELAY", "2.0"))
    upload_queue_rate_limit: int = int(os.getenv("UPLOAD_QUEUE_RATE_LIMIT", "10"))

    @property
    def redis_url(self) -> str:
        """构建 Redis URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    class Config:
        env_file = ".env"
        extra = "ignore"  # 忽略未定义的环境变量（如 PYTHONUNBUFFERED、LOG_LEVEL 等）


# 全局配置实例
settings = Settings()
