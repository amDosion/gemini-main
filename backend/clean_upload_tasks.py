"""
清理 upload_tasks 表中的所有数据

使用方法：
    python backend/clean_upload_tasks.py
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.database import engine
from sqlalchemy import text

def clean_upload_tasks():
    """清理 upload_tasks 表"""
    print("=" * 80)
    print("清理 upload_tasks 表")
    print("=" * 80)

    try:
        with engine.begin() as conn:
            # 查询当前记录数
            result = conn.execute(text("SELECT COUNT(*) FROM upload_tasks;"))
            count_before = result.fetchone()[0]
            print(f"\n清理前记录数: {count_before}")

            if count_before == 0:
                print("表中没有数据，无需清理")
                return

            # 清空表
            conn.execute(text("DELETE FROM upload_tasks;"))
            print(f"✅ 已删除 {count_before} 条记录")

            # 验证
            result = conn.execute(text("SELECT COUNT(*) FROM upload_tasks;"))
            count_after = result.fetchone()[0]
            print(f"清理后记录数: {count_after}")

        print("\n✅ 清理完成")

    except Exception as e:
        print(f"\n❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    clean_upload_tasks()
