#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取第106行的超长数据
"""

import json
import re

html_file = "全量模型规格参数计费表-大模型服务平台百炼-阿里云.html"

print("读取HTML文件...")
with open(html_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"文件总行数: {len(lines)}")

# 第106行（索引105）
if len(lines) > 105:
    line_106 = lines[105]
    print(f"第106行长度: {len(line_106)} 字符")
    
    # 保存到文件
    with open('line_106.txt', 'w', encoding='utf-8') as f:
        f.write(line_106)
    print("第106行已保存到 line_106.txt")
    
    # 尝试提取JSON数据
    # 查找所有可能的JSON结构
    json_objects = []
    
    # 匹配大括号包围的JSON
    brace_count = 0
    start_pos = -1
    
    for i, char in enumerate(line_106):
        if char == '{':
            if brace_count == 0:
                start_pos = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_pos >= 0:
                json_str = line_106[start_pos:i+1]
                # 只处理长度大于100的JSON
                if len(json_str) > 100:
                    try:
                        data = json.loads(json_str)
                        json_objects.append(data)
                        print(f"找到JSON对象 #{len(json_objects)}, 长度: {len(json_str)}")
                    except:
                        pass
    
    print(f"\n共找到 {len(json_objects)} 个有效JSON对象")
    
    # 保存所有JSON对象
    if json_objects:
        with open('extracted_jsons.json', 'w', encoding='utf-8') as f:
            json.dump(json_objects, f, ensure_ascii=False, indent=2)
        print("已保存到 extracted_jsons.json")
        
        # 分析第一个大对象
        if json_objects:
            largest = max(json_objects, key=lambda x: len(json.dumps(x)))
            print(f"\n最大JSON对象的根键: {list(largest.keys()) if isinstance(largest, dict) else 'not a dict'}")
            
            # 递归查找包含qwen的键值
            def find_qwen(obj, path="root"):
                results = []
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if 'qwen' in str(k).lower() or 'qwen' in str(v).lower():
                            results.append((f"{path}.{k}", v))
                        results.extend(find_qwen(v, f"{path}.{k}"))
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        results.extend(find_qwen(item, f"{path}[{i}]"))
                return results
            
            qwen_data = find_qwen(largest)
            print(f"\n找到 {len(qwen_data)} 个包含'qwen'的路径")
            
            if qwen_data:
                print("\n前10个路径:")
                for path, value in qwen_data[:10]:
                    value_str = str(value)[:100]
                    print(f"  {path}: {value_str}")
else:
    print("文件不足106行")
