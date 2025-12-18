#!/usr/bin/env python3
"""
Force clear all Python cache files
Removes __pycache__ directories and .pyc files
"""
import os
import shutil
from pathlib import Path

def clear_all_cache():
    """Clear all Python cache files"""
    backend_dir = Path(__file__).parent
    removed_count = 0

    print(f"[Clear Cache] Scanning directory: {backend_dir}")

    # 1. Remove all __pycache__ directories
    for pycache_dir in backend_dir.rglob("__pycache__"):
        try:
            shutil.rmtree(pycache_dir)
            print(f"[OK] Removed: {pycache_dir}")
            removed_count += 1
        except Exception as e:
            print(f"[FAIL] Failed to remove: {pycache_dir}, error: {e}")

    # 2. Remove all .pyc files
    for pyc_file in backend_dir.rglob("*.pyc"):
        try:
            pyc_file.unlink()
            print(f"[OK] Removed: {pyc_file}")
            removed_count += 1
        except Exception as e:
            print(f"[FAIL] Failed to remove: {pyc_file}, error: {e}")

    print(f"\n[Done] Removed {removed_count} cache files/directories")

if __name__ == "__main__":
    clear_all_cache()
