"""
Clear all Python cache files

This script removes all __pycache__ directories and .pyc files
to force Python to reload all modules from source.
"""
import os
import shutil
from pathlib import Path

def clear_pycache():
    """Clear all __pycache__ directories and .pyc files"""
    print("=" * 80)
    print("Clearing Python Cache")
    print("=" * 80)

    backend_dir = Path(__file__).parent
    removed_dirs = 0
    removed_files = 0

    # Remove __pycache__ directories
    for pycache_dir in backend_dir.rglob("__pycache__"):
        try:
            shutil.rmtree(pycache_dir)
            removed_dirs += 1
            print(f"Removed: {pycache_dir.relative_to(backend_dir)}")
        except Exception as e:
            print(f"Failed to remove {pycache_dir}: {e}")

    # Remove .pyc files
    for pyc_file in backend_dir.rglob("*.pyc"):
        try:
            pyc_file.unlink()
            removed_files += 1
            print(f"Removed: {pyc_file.relative_to(backend_dir)}")
        except Exception as e:
            print(f"Failed to remove {pyc_file}: {e}")

    print("\n" + "=" * 80)
    print(f"Cache Cleanup Complete")
    print(f"  Removed {removed_dirs} __pycache__ directories")
    print(f"  Removed {removed_files} .pyc files")
    print("=" * 80)
    print("\nPlease restart the backend server (Ctrl+C then pnpm run dev)")

if __name__ == "__main__":
    clear_pycache()
