"""
Check source_file_path in upload_tasks table
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.database import engine
from sqlalchemy import text

def check_source_paths():
    """Check source_file_path values in upload_tasks"""
    print("=" * 80)
    print("Source File Path Check")
    print("=" * 80)

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT
                    id,
                    filename,
                    source_file_path,
                    status,
                    created_at
                FROM upload_tasks
                ORDER BY created_at DESC
                LIMIT 10;
            """))

            rows = result.fetchall()

            if not rows:
                print("\nNo records found")
                return

            print(f"\nFound {len(rows)} records:\n")
            print("-" * 80)

            for row in rows:
                task_id = row[0]
                filename = row[1]
                source_path = row[2]
                status = row[3]
                created_at = row[4]

                print(f"\nTask ID: {task_id[:8]}...")
                print(f"  Filename: {filename}")
                print(f"  Status: {status}")
                print(f"  Source Path: {source_path if source_path else 'NULL'}")
                print(f"  Created: {created_at}")

                # Check if path exists
                if source_path:
                    import os
                    exists = os.path.exists(source_path)
                    print(f"  File Exists: {'YES' if exists else 'NO'}")

                    # Check if it's absolute or relative
                    if os.path.isabs(source_path):
                        print(f"  Path Type: ABSOLUTE")

                        # Check if it's in backend/temp/
                        if "backend\\temp\\" in source_path or "backend/temp/" in source_path:
                            print(f"  Location: backend/temp/ (CORRECT)")
                        else:
                            print(f"  Location: System temp (WRONG - should be backend/temp/)")
                    else:
                        print(f"  Path Type: RELATIVE")

                print("-" * 80)

        print("\nCheck complete")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_source_paths()
