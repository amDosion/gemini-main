"""
测试 TEMP_DIR 路径计算

验证 storage.py 中的 TEMP_DIR 是否正确指向 backend/temp/
"""
import os
from pathlib import Path

# 模拟 storage.py 的路径计算
# __file__ 在 storage.py 中会是: backend/app/routers/storage.py

storage_file = Path("D:/gemini-main/gemini-main/backend/app/routers/storage.py")

print("=" * 80)
print("TEMP_DIR 路径计算测试")
print("=" * 80)

print(f"\n当前文件 (__file__): {storage_file}")
print(f"  os.path.dirname(__file__): {storage_file.parent}")
print(f"  os.path.dirname(os.path.dirname(__file__)): {storage_file.parent.parent}")
print(f"  os.path.dirname(os.path.dirname(os.path.dirname(__file__))): {storage_file.parent.parent.parent}")

# 第 22 行的计算
temp_dir = storage_file.parent.parent.parent / "temp"
print(f"\nTEMP_DIR 计算结果: {temp_dir}")
print(f"  预期路径: D:/gemini-main/gemini-main/backend/temp")
print(f"  实际路径: {temp_dir}")
print(f"  是否匹配: {'✅ 正确' if str(temp_dir) == 'D:/gemini-main/gemini-main/backend/temp' else '❌ 错误'}")

# 正确的计算方式
print("\n" + "-" * 80)
print("正确的路径计算:")
print("-" * 80)

# 方法 1: 使用 pathlib
backend_dir = storage_file.parent.parent.parent
temp_dir_correct = backend_dir / "temp"
print(f"方法 1 (pathlib): {temp_dir_correct}")

# 方法 2: 使用 os.path
backend_dir_os = os.path.dirname(os.path.dirname(os.path.dirname(str(storage_file))))
temp_dir_correct_os = os.path.join(backend_dir_os, "temp")
print(f"方法 2 (os.path): {temp_dir_correct_os}")

print("\n✅ 测试完成")
