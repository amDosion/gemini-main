#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从window.__ICE_PAGE_PROPS__提取模型数据 - 修复版
正确处理JSON字符串中的括号
"""

import json
import re
from bs4 import BeautifulSoup

html_file = "全量模型规格参数计费表-大模型服务平台百炼-阿里云.html"

print("读取HTML文件...")
with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 查找window.__ICE_PAGE_PROPS__的起始位置
start_pattern = r'window\.__ICE_PAGE_PROPS__\s*=\s*'
start_match = re.search(start_pattern, content)

if not start_match:
    print("未找到window.__ICE_PAGE_PROPS__")
    exit(1)

start_pos = start_match.end()
print(f"找到起始位置: {start_pos}")

# 从起始位置开始，手动匹配JSON对象，正确处理字符串中的括号
brace_count = 0
in_string = False
escape_next = False
json_start = start_pos
json_end = start_pos

for i in range(start_pos, min(start_pos + 500000, len(content))):  # 限制搜索范围
    char = content[i]
    
    if escape_next:
        escape_next = False
        continue
    
    if char == '\\':
        escape_next = True
        continue
    
    if char == '"':
        in_string = not in_string
        continue
    
    if not in_string:
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                json_end = i + 1
                break

if json_end == start_pos:
    print(f"未找到完整的JSON对象，当前括号计数: {brace_count}")
    exit(1)

json_str = content[json_start:json_end]
print(f"JSON长度: {len(json_str)} 字符")

# 解析JSON
try:
    data = json.loads(json_str)
    print("JSON解析成功")
    
    # 保存完整数据
    with open('page_props.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("完整数据已保存到 page_props.json")
    
    # 提取content字段（包含HTML）
    html_content = data.get('docDetailData', {}).get('storeData', {}).get('data', {}).get('content', '')
    
    if html_content:
        print(f"\nHTML内容长度: {len(html_content)} 字符")
        
        # 解析HTML内容
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 保存提取的HTML
        with open('extracted_content.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print("HTML内容已保存到 extracted_content.html")
        
        # 查找所有表格
        tables = soup.find_all('table')
        print(f"\n找到 {len(tables)} 个表格")
        
        all_models = []
        
        for table_idx, table in enumerate(tables):
            print(f"\n处理表格 #{table_idx + 1}")
            
            # 提取表头
            headers = []
            thead = table.find('thead')
            if thead:
                header_row = thead.find('tr')
                if header_row:
                    headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            
            if not headers:
                # 尝试从第一行获取表头
                first_row = table.find('tr')
                if first_row:
                    headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]
            
            print(f"  表头({len(headers)}列): {headers[:5]}...")  # 只打印前5个
            
            # 提取数据行
            tbody = table.find('tbody')
            rows = tbody.find_all('tr') if tbody else table.find_all('tr')[1:]
            
            for row_idx, row in enumerate(rows):
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 2:
                    model_data = {}
                    for i, col in enumerate(cols):
                        key = headers[i] if i < len(headers) else f'列{i+1}'
                        value = col.get_text(strip=True)
                        if value:
                            model_data[key] = value
                    
                    if model_data:
                        model_data['_table'] = table_idx + 1
                        model_data['_row'] = row_idx + 1
                        all_models.append(model_data)
            
            print(f"  提取 {len(rows)} 行数据")
        
        print(f"\n总共提取 {len(all_models)} 条数据")
        
        # 保存模型数据
        if all_models:
            with open('models.json', 'w', encoding='utf-8') as f:
                json.dump(all_models, f, ensure_ascii=False, indent=2)
            print("模型数据已保存到 models.json")
            
            # 生成Markdown报告
            with open('models.md', 'w', encoding='utf-8') as f:
                f.write("# 阿里云百炼平台模型列表\n\n")
                f.write(f"提取时间: 2025-12-28\n\n")
                f.write(f"总数据条数: {len(all_models)}\n\n")
                f.write(f"表格数量: {len(tables)}\n\n")
                f.write("---\n\n")
                
                current_table = 0
                for i, model in enumerate(all_models, 1):
                    # 表格分组
                    if model.get('_table', 0) != current_table:
                        current_table = model.get('_table', 0)
                        f.write(f"\n## 表格 {current_table}\n\n")
                    
                    # 提取模型名称
                    model_name = None
                    for key in ['模型', '模型名称', 'Model', 'model', 'modelId', '名称', '模型ID']:
                        if key in model:
                            model_name = model[key]
                            break
                    
                    if not model_name:
                        # 使用第一个非元数据字段
                        for key, value in model.items():
                            if not key.startswith('_') and value:
                                model_name = value
                                break
                    
                    f.write(f"### {model_name or f'数据行{i}'}\n\n")
                    
                    for key, value in model.items():
                        if not key.startswith('_'):
                            f.write(f"- **{key}**: {value}\n")
                    
                    f.write("\n")
            
            print("Markdown报告已保存到 models.md")
            
            # 统计信息
            print(f"\n数据统计:")
            print(f"- 表格数量: {len(tables)}")
            print(f"- 总数据行: {len(all_models)}")
            
            # 显示第一条数据示例
            if all_models:
                print(f"\n第一条数据示例:")
                for key, value in list(all_models[0].items())[:5]:
                    if not key.startswith('_'):
                        print(f"  {key}: {value}")
        else:
            print("未提取到数据")
    else:
        print("未找到HTML内容")
        
except json.JSONDecodeError as e:
    print(f"JSON解析失败: {e}")
    print(f"保存前1000字符到debug.txt")
    with open('debug.txt', 'w', encoding='utf-8') as f:
        f.write(json_str[:1000])
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
