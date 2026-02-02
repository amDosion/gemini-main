"""
应用配置模块
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

# 导入统一的环境变量加载模块（确保 .env 文件已加载）
from .env_loader import _ENV_LOADED  # noqa: F401


class Settings(BaseSettings):
    """应用配置类"""

    # 服务器配置
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "21574"))

    # 数据库配置（必须设置，仅支持 PostgreSQL）
    # 注意：实际的数据库连接由 backend/app/core/database.py 处理，该模块要求必须设置 DATABASE_URL 环境变量
    database_url: str = os.getenv("DATABASE_URL", "")

    # GCP / Vertex AI 配置（用于 Virtual Try-On 等功能）
    gcp_project_id: str | None = os.getenv("GCP_PROJECT_ID")
    gcp_location: str = os.getenv("GCP_LOCATION", "us-central1")
    google_application_credentials: str | None = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

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
    
    # Worker 运行模式
    # - "embedded": 内嵌在主进程中运行（默认，推荐，使用 Redis 队列系统）
    # - "disabled": 禁用 Worker（需要外部 Worker 服务）
    worker_mode: str = os.getenv("WORKER_MODE", "embedded")

    # 认证配置
    allow_registration: bool = os.getenv("ALLOW_REGISTRATION", "false").lower() == "true"
    # 注意：jwt_secret_key 不再从环境变量读取，由 jwt_utils.py 管理
    # 保留此字段仅用于向后兼容，实际使用 jwt_utils.py 中的 JWT_SECRET_KEY
    jwt_access_token_expire_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    jwt_refresh_token_expire_days: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

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
