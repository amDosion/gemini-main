import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()  # 从 .env 文件加载环境变量

# 从环境变量中读取 DATABASE_URL
# 如果未设置，则默认为 SQLite 数据库
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# 根据数据库类型选择不同的参数
if DATABASE_URL.startswith("sqlite"):
    # SQLite 需要特定的 connect_args 来允许多线程访问
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL 或其他数据库不需要这个参数
    engine = create_engine(DATABASE_URL)

# 创建数据库会话类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建我们 ORM 模型将继承的基类
Base = declarative_base()
