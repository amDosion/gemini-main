import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 导入统一的环境变量加载模块（确保 .env 文件已加载）
from .env_loader import _ENV_LOADED  # noqa: F401

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


# 为 Base 添加统一的 to_dict() 方法
def _base_to_dict(self):
    """
    统一的 to_dict() 方法，返回 snake_case 格式

    中间件会自动将 snake_case 转换为 camelCase 发送给前端
    这样保持了架构的一致性：后端内部统一使用 snake_case
    """
    result = {}
    for column in self.__table__.columns:
        value = getattr(self, column.name)
        # 处理特殊类型
        if isinstance(value, datetime):
            # 转换为时间戳（毫秒）
            result[column.name] = int(value.timestamp() * 1000)
        else:
            result[column.name] = value
    return result


Base.to_dict = _base_to_dict


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
