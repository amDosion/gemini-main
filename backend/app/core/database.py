import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 尽量从 backend/.env 加载环境变量
_backend_env = Path(__file__).resolve().parents[2] / ".env"
if _backend_env.exists():
    load_dotenv(dotenv_path=_backend_env)
else:
    load_dotenv()  # 回退：从当前工作目录向上查找 .env

# 从环境变量中读取 DATABASE_URL（必须设置，仅支持 PostgreSQL）
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL 环境变量未设置。"
        "请在后端 .env 文件中设置 DATABASE_URL，例如："
        "DATABASE_URL=postgresql+psycopg2://user:password@host:port/database"
    )

# 验证数据库类型（仅支持 PostgreSQL）
if not DATABASE_URL.startswith(("postgresql", "postgresql+psycopg2", "postgresql+asyncpg")):
    raise ValueError(
        f"不支持的数据库类型: {DATABASE_URL.split('://')[0] if '://' in DATABASE_URL else 'unknown'}。"
        "仅支持 PostgreSQL 数据库。"
    )

# PostgreSQL 数据库引擎配置
engine_kwargs = {
    "pool_pre_ping": True,  # 连接失效时自动检测并重建，减少"重启才恢复"的错觉
    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),  # 连接池回收时间（秒）
    "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),  # 连接池大小
    "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),  # 最大溢出连接数
}
engine = create_engine(DATABASE_URL, **engine_kwargs)

# 创建数据库会话类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建我们 ORM 模型将继承的基类
Base = declarative_base()


# 依赖注入：获取数据库会话
def get_db():
    """
    FastAPI 依赖注入函数，用于获取数据库会话
    使用 yield 确保请求结束后自动关闭会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
