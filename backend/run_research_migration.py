"""
数据库迁移脚本 - 创建 research_tasks 表

使用方法：
    python backend/run_research_migration.py
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.database import engine
from sqlalchemy import text

def run_migration():
    """执行数据库迁移"""
    migration_file = Path(__file__).parent / "migrations" / "002_create_research_tasks.sql"

    print(f"[Migration] 读取迁移文件: {migration_file}")

    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    print("[Migration] 执行数据库迁移...")

    try:
        # 直接执行整个 SQL 文件（PostgreSQL 支持多语句执行）
        with engine.begin() as conn:
            conn.execute(text(sql))
        
        print("\n[Migration] ✅ 迁移成功完成！")
        print("[Migration] research_tasks 表已创建，包含以下字段:")
        print("  - id (VARCHAR(36), PRIMARY KEY)")
        print("  - user_id (VARCHAR(255))")
        print("  - prompt (TEXT)")
        print("  - prompt_hash (VARCHAR(64))")
        print("  - agent (VARCHAR(50))")
        print("  - status (VARCHAR(20))")
        print("  - result (TEXT)")
        print("  - error (TEXT)")
        print("  - usage (TEXT)")
        print("  - created_at (TIMESTAMP)")
        print("  - updated_at (TIMESTAMP)")
        print("  - completed_at (TIMESTAMP)")
        print("\n[Migration] 索引已创建:")
        print("  - idx_research_tasks_user_id")
        print("  - idx_research_tasks_status")
        print("  - idx_research_tasks_prompt_hash")
        print("  - idx_research_tasks_created_at")

    except Exception as e:
        print(f"[Migration] ❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移: 创建 research_tasks 表")
    print("=" * 60)
    run_migration()
