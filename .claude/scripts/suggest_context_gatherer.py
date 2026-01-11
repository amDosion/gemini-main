#!/usr/bin/env python3
"""
当读取大型 Steering 文档时建议使用 context-gatherer
"""
import sys
import os

def suggest_context_gatherer(file_path):
    """建议使用 context-gatherer"""
    if not os.path.exists(file_path):
        return 0
    
    # 检查文件大小
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = len(f.readlines())
    
    # 如果文件超过 200 行，建议使用 context-gatherer
    if lines > 200:
        print(f"\n💡 提示：此文档较大 ({lines} 行)")
        print(f"   建议通过 context-gatherer 子 Agent 获取摘要，避免上下文超载")
        print(f"\n   使用方法：")
        print(f"   invokeSubAgent(")
        print(f"       name=\"context-gatherer\",")
        print(f"       prompt=\"Read and summarize {os.path.basename(file_path)}\",")
        print(f"       explanation=\"Getting document summary\"")
        print(f"   )\n")
    
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python suggest_context_gatherer.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    sys.exit(suggest_context_gatherer(file_path))
