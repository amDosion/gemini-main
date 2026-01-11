"""
数据库迁移脚本：添加 upload_tasks 表
用于记录图片上传到云存储的任务

运行方式：
python -m backend.app.migrations.add_upload_task_table
"""

from sqlalchemy import create_engine, Column, String, BigInteger, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 获取数据库 URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# 创建引擎
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# 定义表结构
class UploadTask(Base):
    __tablename__ = "upload_tasks"

    id = Column(String, primary_key=True, index=True)
    session_id = Column(String, nullable=True)  # 新增：关联的会话ID
    message_id = Column(String, nullable=True)
    attachment_id = Column(String, nullable=True)
    source_url = Column(String, nullable=True)  # 修改：允许为空
    source_file_path = Column(String, nullable=True)  # 新增：本地临时文件路径
    target_url = Column(String, nullable=True)
    filename = Column(String, nullable=False)
    storage_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default='pending')
    error_message = Column(String, nullable=True)
    created_at = Column(BigInteger, nullable=False)
    completed_at = Column(BigInteger, nullable=True)


def migrate():
    """执行迁移"""
    print("开始迁移：添加/更新 upload_tasks 表...")
    
    try:
        # 先尝试删除旧表（如果存在）
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS upload_tasks"))
            conn.comm


if __name__ == "__main__":
    migrate()
