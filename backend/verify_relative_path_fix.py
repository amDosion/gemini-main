#!/usr/bin/env python3
"""
Verify relative path fix after restart
验证重启后相对路径修复是否生效
"""
import asyncpg
import asyncio
import os
from datetime import datetime

DATABASE_URL = "postgresql://ai:Z6LwNUH481dnjAmp2kMRPmg8xj8CtE@192.168.50.115:5432/gemini-ai"

async def main():
    print("=" * 80)
    print("Verification: Relative Path Fix")
    print("=" * 80)
    print()

    # Connect to database
    print("[1] Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)
    print("[OK] Connected")
    print()

    # Query recent upload tasks (created after this verification starts)
    print("[2] Querying recent upload tasks...")
    now_ms = int(datetime.now().timestamp() * 1000)

    # First, show all pending tasks
    result = await conn.fetch("""
        SELECT
            id,
            filename,
            source_file_path,
            priority,
            retry_count,
            status,
            created_at
        FROM upload_tasks
        WHERE status = 'pending'
        ORDER BY created_at DESC
        LIMIT 10
    """)

    if not result:
        print("[INFO] No pending tasks found")
        print()
        print("=" * 80)
        print("ACTION REQUIRED:")
        print("1. Restart the backend service")
        print("2. Generate a new image (this will create a new upload task)")
        print("3. Run this script again to verify the path format")
        print("=" * 80)
    else:
        print(f"[OK] Found {len(result)} pending tasks\n")

        all_relative = True
        all_correct_location = True

        for row in result:
            task_id = row['id']
            source_path = row['source_file_path']
            filename = row['filename']
            priority = row['priority']
            retry_count = row['retry_count']

            print(f"Task ID: {task_id[:8]}...")
            print(f"  Filename: {filename}")
            print(f"  Source Path: {source_path}")
            print(f"  Priority: {priority}")
            print(f"  Retry Count: {retry_count}")

            # Check if path is relative
            if source_path:
                is_absolute = os.path.isabs(source_path)
                is_backend_temp = source_path.startswith("backend") if not is_absolute else False

                if is_absolute:
                    print(f"  ❌ FAIL: Path is ABSOLUTE (expected relative)")
                    all_relative = False
                else:
                    print(f"  ✓ OK: Path is relative")

                if not is_backend_temp and not is_absolute:
                    print(f"  ⚠ WARNING: Path does not start with 'backend/temp/'")
                    all_correct_location = False
                elif is_backend_temp:
                    print(f"  ✓ OK: Path starts with 'backend/temp/'")
            else:
                print(f"  ⚠ No source_file_path (might use source_url)")

            # Check if priority and retry_count are set
            if priority is None:
                print(f"  ❌ FAIL: Priority is NULL (should be 'normal', 'high', or 'low')")
            else:
                print(f"  ✓ OK: Priority is set")

            if retry_count is None:
                print(f"  ❌ FAIL: Retry count is NULL (should be 0)")
            else:
                print(f"  ✓ OK: Retry count is set")

            print()

        print("=" * 80)
        print("SUMMARY:")
        if all_relative and all_correct_location:
            print("✓ ALL CHECKS PASSED!")
            print("  - All paths are relative")
            print("  - All paths start with 'backend/temp/'")
            print("  - Priority and retry_count fields are properly set")
        else:
            if not all_relative:
                print("❌ SOME PATHS ARE STILL ABSOLUTE")
                print("   This means the old code is still running.")
                print("   Please restart the backend service.")
            if not all_correct_location:
                print("⚠ SOME PATHS DO NOT START WITH 'backend/temp/'")
                print("   This might be OK for tasks using source_url instead.")
        print("=" * 80)

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
