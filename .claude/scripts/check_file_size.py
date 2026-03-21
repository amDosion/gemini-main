#!/usr/bin/env python3
"""
检查文件大小是否符合模块化原则
后端文件 < 300 行（理想）
前端文件 < 200 行（理想）
"""
import sys
import os

def check_file_size(file_path):
    """检查文件行数"""
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return 1
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = len(f.readlines())
    
    # 判断文件类型
    is_backend = 'backend' in file_path and file_path.endswith('.py')
    is_frontend = 'frontend' in file_path and (file_path.endswith('.ts') or file_path.endswith('.tsx'))
    
    # 设置阈值
    if is_backend:
        ideal_limit = 300
        max_limit = 500
        file_type = "后端 Python"
    elif is_frontend:
        ideal_limit = 200
        max_limit = 400
        file_type = "前端 TypeScript"
    else:
        # 未知类型，不检查
        return 0
    
    # 检查文件大小
    if lines <= ideal_limit:
        print(f"✅ {file_type} 文件大小合适: {lines} 行 (理想 < {ideal_limit} 行)")
        return 0
    elif lines <= max_limit:
        print(f"⚠️  {file_type} 文件偏大: {lines} 行 (理想 < {ideal_limit} 行)")
        print(f"   建议：考虑拆分为多个模块")
        return 0  # 警告但不阻止
    else:
        print(f"❌ {file_type} 文件过大: {lines} 行 (最大 < {max_limit} 行)")
        print(f"   必须：拆分为多个模块")
        print(f"   参考：.kiro/steering/structure.md 的模块化原则")
        return 1  # 错误，阻止操作

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python check_file_size.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    sys.exit(check_file_size(file_path))
