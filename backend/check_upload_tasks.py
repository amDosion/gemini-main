"""
检查 upload_tasks 表的数据

使用方法：
    python backend/check_upload_tasks.py
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.database import engine
from sqlalchemy import text

def check_upload_tasks():
    """检查 upload_tasks 表中的数据"""
    print("=" * 80)
    print("查询 upload_tasks 表")
    print("=" * 80)

    try:
        with engine.begin() as conn:
            # 查询表结构
            print("\n1. 表结构:")
            print("-" * 80)
            result = conn.execute(text("""
                SELECT column_name, data_type, column_default, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'upload_tasks'
                ORDER BY ordinal_position;
            """))

            for row in result:
                print(f"  {row[0]:25s} | {row[1]:20s} | {str(row[2] or 'NULL'):30s} | {row[3]}")
            print("-" * 80)

            # 查询记录数量
            print("\n2. 记录统计:")
            print("-" * 80)
            result = conn.execute(text("SELECT COUNT(*) as total FROM upload_tasks;"))
            total = result.fetchone()[0]
            print(f"  总记录数: {total}")

            # 按状态统计
            result = conn.execute(text("""
                SELECT status, COUNT(*) as count
                FROM upload_tasks
                GROUP BY status;
            """))
            print("\n  按状态统计:")
            for row in result:
                print(f"    - {row[0]}: {row[1]} 条")
            print("-" * 80)

            # 查询最近 10 条记录
            print("\n3. 最近 10 条记录:")
            print("-" * 80)
            result = conn.execute(text("""
                SELECT
                    id,
                    filename,
                    status,
                    priority,
                    retry_count,
                    session_id,
                    message_id,
                    attachment_id,
                    target_url,
                    created_at
                FROM upload_tasks
                ORDER BY created_at DESC
                LIMIT 10;
            """))

            rows = result.fetchall()
            if rows:
                for row in rows:
                    print(f"\n  任务 ID: {row[0]}")
                    print(f"    文件名: {row[1]}")
                    print(f"    状态: {row[2]}")
                    print(f"    优先级: {row[3]}")
                    print(f"    重试次数: {row[4]}")
                    print(f"    会话ID: {row[5][:8] if row[5] else 'NULL'}...")
                    print(f"    消息ID: {row[6][:8] if row[6] else 'NULL'}...")
                    print(f"    附件ID: {row[7][:8] if row[7] else 'NULL'}...")
                    print(f"    目标URL: {row[8] or 'NULL'}")
                    print(f"    创建时间: {row[9]}")
            else:
                print("  ⚠️  表中没有任何记录！")
            print("-" * 80)

        print("\n✅ 查询完成")

    except Exception as e:
        print(f"\n❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    check_upload_tasks()
