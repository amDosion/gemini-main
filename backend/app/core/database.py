import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 尽量从 backend/.env 加载环境变量（避免因启动目录不同导致误用 sqlite/test.db）
_backend_env = Path(__file__).resolve().parents[2] / ".env"
if _backend_env.exists():
    load_dotenv(dotenv_path=_backend_env)
else:
    load_dotenv()  # 回退：从当前工作目录向上查找 .env

# 从环境变量中读取 DATABASE_URL
# 如果未设置，则默认为 SQLite 数据库
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# 根据数据库类型选择不同的参数
if DATABASE_URL.startswith("sqlite"):
    # SQLite 需要特定的 connect_args 来允许多线程访问
    engine_kwargs = {"pool_pre_ping": True}
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}, **engine_kwargs
    )
else:
    # PostgreSQL 或其他数据库不需要这个参数
    engine_kwargs = {
        "pool_pre_ping": True,  # 连接失效时自动检测并重建，减少“重启才恢复”的错觉
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
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
