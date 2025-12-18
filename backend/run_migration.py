"""
数据库迁移脚本 - 添加 priority 和 retry_count 字段

使用方法：
    python backend/run_migration.py
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
    migration_file = Path(__file__).parent / "migrations" / "001_add_priority_retry_count.sql"

    print(f"[Migration] 读取迁移文件: {migration_file}")

    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    print("[Migration] 执行数据库迁移...")

    try:
        # 分割 SQL 语句（按分号分割）
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

        # 执行每个语句（每个语句单独提交）
        for i, statement in enumerate(statements, 1):
            if statement:
                print(f"[Migration] 执行语句 {i}/{len(statements)}...")
                with engine.begin() as conn:
                    conn.execute(text(statement))
                print(f"[Migration] ✓ 语句 {i} 执行成功")

        print("\n[Migration] ✅ 迁移成功完成！")
        print("[Migration] 新字段已添加:")
        print("  - priority (VARCHAR, 默认 'normal')")
        print("  - retry_count (INTEGER, 默认 0)")

    except Exception as e:
        print(f"[Migration] ❌ 迁移失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移: 添加 priority 和 retry_count 字段")
    print("=" * 60)
    run_migration()
