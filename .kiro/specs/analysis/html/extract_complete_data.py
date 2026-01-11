#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整提取HTML中的所有模型信息和表格数据
包括qwen和wanx模型
"""

import re
import json
from bs4 import BeautifulSoup
from collections import defaultdict

html_file = "全量模型规格参数计费表-大模型服务平台百炼-阿里云.html"

print("读取HTML文件...")
with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"文件大小: {len(content)} 字符\n")

# 查找所有包含价格信息的行
print("查找包含价格/参数信息的数据...")
price_pattern = r'(qwen[0-9a-z.-]*|wanx[0-9a-z.-]*)[^\n]*(?:上下文长度|输入价格|输出价格|tokens|免费额度|元/)'
matches = re.findall(price_pattern, content, re.IGNORECASE)
print(f"找到 {len(matches)} 处包含价格/参数的引用\n")

# 解析page_props.json中的HTML内容
print("解析嵌入的HTML内容...")
json_pattern = r'window\.__ICE_PAGE_PROPS__\s*=\s*(\{.*?\});'
json_match = re.search(json_pattern, content, re.DOTALL)

all_tables_data = []

if json_match:
    # 手动提取JSON（处理字符串中的括号）
    json_start = json_match.start(1)
    brace_count = 0
    in_string = False
    escape_next = False
    json_end = json_start

    for i in range(json_start, min(json_start + 500000, len(content))):
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

    json_str = content[json_start:json_end]

    try:
        data = json.loads(json_str)
        html_content = data.get('docDetailData', {}).get('storeData', {}).get('data', {}).get('content', '')

        if html_content:
            print(f"成功提取嵌入的HTML内容，长度: {len(html_content)} 字符\n")

            # 解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # 查找所有表格
            tables = soup.find_all('table')
            print(f"找到 {len(tables)} 个表格\n")

            for table_idx, table in enumerate(tables):
                print(f"处理表格 {table_idx + 1}...")

                # 提取表头
                headers = []
                thead = table.find('thead')
                if thead:
                    header_row = thead.find('tr')
                    if header_row:
                        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

                if not headers:
                    first_row = table.find('tr')
                    if first_row:
                        headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]

                print(f"  表头 ({len(headers)} 列): {headers[:5]}...")

                # 提取数据行
                tbody = table.find('tbody')
                rows = tbody.find_all('tr') if tbody else table.find_all('tr')[1:]

                table_data = {
                    'table_index': table_idx + 1,
                    'headers': headers,
                    'rows': []
                }

                for row in rows:
                    cols = row.find_all(['td', 'th'])
                    row_data = {}

                    for i, col in enumerate(cols):
                        header = headers[i] if i < len(headers) else f'列{i+1}'
                        value = col.get_text(strip=True)
                        if value:
                            row_data[header] = value

                    if row_data:
                        table_data['rows'].append(row_data)

                print(f"  提取 {len(table_data['rows'])} 行数据")

                # 检查是否包含模型信息
                table_text = str(table).lower()
                has_models = 'qwen' in table_text or 'wanx' in table_text
                has_price = '价格' in table_text or '元/' in table_text or 'tokens' in table_text

                print(f"  检查: has_models={has_models}, has_price={has_price}")
                
                # 先提取所有表格，不进行筛选
                print(f"  >>> 添加表格到结果")
                all_tables_data.append(table_data)

                print()

    except Exception as e:
        print(f"解析JSON失败: {e}")

# 提取所有模型名称（包括qwen和wanx）
print("\n提取所有模型名称...")
model_patterns = [
    r'(qwen[0-9]*(?:\.[0-9]+)?-[a-z0-9-]+)',
    r'(qwen[0-9]*(?:\.[0-9]+)?)',
    r'(wanx-[a-z0-9-]+)',
    r'(wanx)',
]

all_model_names = set()
for pattern in model_patterns:
    matches = re.findall(pattern, content, re.IGNORECASE)
    all_model_names.update([m.lower() for m in matches if len(m) >= 4])

# 过滤掉不是模型名的字符串
filtered_models = []
exclude_keywords = ['api-reference', 'by-calling', 'function-calling', 'structured-output']

for model in sorted(all_model_names):
    # 排除文档链接等
    if any(kw in model for kw in exclude_keywords):
        continue
    if model in ['qwen', 'wanx']:  # 太短的排除
        continue
    filtered_models.append(model)

print(f"找到 {len(filtered_models)} 个唯一模型\n")

# 分类
qwen_models = [m for m in filtered_models if m.startswith('qwen')]
wanx_models = [m for m in filtered_models if m.startswith('wanx')]

print(f"Qwen模型: {len(qwen_models)} 个")
print(f"Wanx模型: {len(wanx_models)} 个\n")

# 保存结果
result = {
    'summary': {
        'total_models': len(filtered_models),
        'qwen_models_count': len(qwen_models),
        'wanx_models_count': len(wanx_models),
        'tables_count': len(all_tables_data)
    },
    'models': {
        'qwen': qwen_models,
        'wanx': wanx_models,
        'all': filtered_models
    },
    'tables': all_tables_data
}

# 保存为JSON
with open('complete_models_data.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(">>> 已保存到 complete_models_data.json")

# 生成详细报告
with open('complete_models_report.md', 'w', encoding='utf-8') as f:
    f.write("# 阿里云百炼平台完整模型数据\n\n")
    f.write(f"提取时间: 2025-12-28\n\n")
    f.write(f"## 统计摘要\n\n")
    f.write(f"- 总模型数: {len(filtered_models)}\n")
    f.write(f"- Qwen系列: {len(qwen_models)} 个\n")
    f.write(f"- Wanx系列: {len(wanx_models)} 个\n")
    f.write(f"- 数据表格: {len(all_tables_data)} 个\n\n")
    f.write("---\n\n")

    # Qwen模型列表
    f.write("## Qwen模型列表\n\n")
    for model in qwen_models:
        f.write(f"- `{model}`\n")
    f.write("\n")

    # Wanx模型列表
    f.write("## Wanx模型列表\n\n")
    for model in wanx_models:
        f.write(f"- `{model}`\n")
    f.write("\n")

    # 表格数据
    if all_tables_data:
        f.write("---\n\n")
        f.write("## 表格数据\n\n")

        for table in all_tables_data:
            f.write(f"### 表格 {table['table_index']}\n\n")

            if table['headers']:
                f.write("#### 表头\n\n")
                for header in table['headers']:
                    f.write(f"- {header}\n")
                f.write("\n")

            if table['rows']:
                f.write(f"#### 数据 ({len(table['rows'])} 行)\n\n")

                # 显示前10行作为样本
                for i, row in enumerate(table['rows'][:10], 1):
                    f.write(f"**行 {i}:**\n\n")
                    for key, value in row.items():
                        f.write(f"- **{key}**: {value}\n")
                    f.write("\n")

                if len(table['rows']) > 10:
                    f.write(f"...(还有 {len(table['rows']) - 10} 行)\n\n")

            f.write("---\n\n")

print(">>> 已保存到 complete_models_report.md")

print(f"\n完成！")
print(f"- Qwen模型样本: {qwen_models[:5]}")
print(f"- Wanx模型样本: {wanx_models[:5]}")
