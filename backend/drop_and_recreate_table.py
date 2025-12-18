"""
删除并重建 upload_tasks 表

警告：此操作会删除表中的所有数据！仅用于开发环境。

使用方法：
    python backend/drop_and_recreate_table.py
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.database import engine
from sqlalchemy import text

def drop_and_recreate_table():
    """删除并重建 upload_tasks 表"""
    sql_file = Path(__file__).parent / "migrations" / "DROP_AND_RECREATE.sql"

    print(f"[Drop & Recreate] 读取 SQL 文件: {sql_file}")

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    print("[Drop & Recreate] 执行删除并重建操作...")
    print("⚠️  警告：这将删除 upload_tasks 表中的所有数据！")

    try:
        # 分割并执行每个语句
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

        for i, statement in enumerate(statements, 1):
            if statement:
                print(f"[Drop & Recreate] 执行语句 {i}/{len(statements)}...")
                with engine.begin() as conn:
                    result = conn.execute(text(statement))

                    # 如果是 SELECT 语句，打印结果
                    if statement.strip().upper().startswith('SELECT'):
                        print("\n表结构验证:")
                        print("-" * 80)
                        for row in result:
                            print(f"  {row[0]:20s} | {row[1]:20s} | {str(row[2]):30s} | {row[3]}")
                        print("-" * 80)
                    else:
                        print(f"[Drop & Recreate] ✓ 语句 {i} 执行成功")

        print("\n[Drop & Recreate] ✅ 操作成功完成！")
        print("[Drop & Recreate] upload_tasks 表已重建，包含以下新字段:")
        print("  - priority (VARCHAR(20), 默认 'normal')")
        print("  - retry_count (INTEGER, 默认 0)")

    except Exception as e:
        print(f"[Drop & Recreate] ❌ 操作失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("删除并重建 upload_tasks 表")
    print("=" * 60)

    # 二次确认
    response = input("\n⚠️  此操作将删除 upload_tasks 表中的所有数据！\n确认继续吗？(输入 'yes' 继续): ")

    if response.lower() == 'yes':
        drop_and_recreate_table()
    else:
        print("[Drop & Recreate] 操作已取消")
        sys.exit(0)
