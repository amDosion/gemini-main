#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析提取的HTML内容，查找真正的模型表格
"""

from bs4 import BeautifulSoup
import json

print("读取extracted_content.html...")
with open('extracted_content.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

# 查找所有表格
tables = soup.find_all('table')
print(f"\n找到 {len(tables)} 个表格\n")

# 分析每个表格，查找包含模型名称的表格
for idx, table in enumerate(tables):
    rows = table.find_all('tr')
    print(f"表格 {idx + 1}: {len(rows)} 行")

    # 获取表头
    first_row = rows[0] if rows else None
    if first_row:
        headers = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]
        print(f"  表头: {headers[:10]}")  # 只显示前10列

    # 检查前几行数据
    sample_rows = rows[1:min(4, len(rows))]
    if sample_rows:
        print(f"  前3行样本:")
        for row_idx, row in enumerate(sample_rows, 1):
            cols = [td.get_text(strip=True)[:50] for td in row.find_all(['td', 'th'])]
            print(f"    行{row_idx}: {cols[:5]}")

    # 检查是否包含模型名称
    table_text = table.get_text()
    model_keywords = ['qwen-turbo', 'qwen-plus', 'qwen-max', 'qwen2.5']
    found_models = [kw for kw in model_keywords if kw in table_text.lower()]
    if found_models:
        print(f"  ✓ 包含模型: {', '.join(found_models)}")

    print()

# 查找所有包含模型名称的div或section
print("\n查找其他可能包含模型数据的元素...")
model_containers = soup.find_all(['div', 'section'], string=lambda text: text and 'qwen' in text.lower())
print(f"找到 {len(model_containers)} 个包含'qwen'的元素")

# 查找所有链接，看是否有指向模型列表的链接
links = soup.find_all('a', href=True)
model_links = [link for link in links if 'model' in link.get('href', '').lower() or '模型' in link.get_text()]
print(f"\n找到 {len(model_links)} 个模型相关链接")
if model_links:
    print("前10个链接:")
    for link in model_links[:10]:
        print(f"  - {link.get_text(strip=True)[:50]} -> {link['href'][:80]}")
