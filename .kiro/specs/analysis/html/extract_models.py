#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿里云百炼平台模型信息提取工具
从HTML文件中提取所有模型的详细信息
"""

import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Any


def extract_models_from_html(html_file: str) -> List[Dict[str, Any]]:
    """从HTML文件中提取模型信息"""
    
    # 读取HTML文件
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    models = []
    
    # 策略1: 查找script标签中的JSON数据
    script_tags = soup.find_all('script')
    for script in script_tags:
        if script.string:
            # 查找可能的JSON对象
            json_patterns = [
                r'(?:window\.__DATA__|modelData|models)\s*=\s*(\{.*?\});',
                r'var\s+\w+\s*=\s*(\[.*?\]);',
                r'const\s+\w+\s*=\s*(\[.*?\]);'
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, script.string, re.DOTALL)
                for match in matches:
                    try:
                        data = json.loads(match)
                        if isinstance(data, list):
                            models.extend(data)
                        elif isinstance(data, dict) and 'models' in data:
                            models.extend(data['models'])
                    except:
                        continue
    
    # 策略2: 查找表格数据
    tables = soup.find_all('table')
    for table in tables:
        headers = []
        header_row = table.find('thead')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        
        rows = table.find_all('tr')
        for row in rows[1:]:  # 跳过表头
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 2:
                model_data = {}
                for i, col in enumerate(cols):
                    key = headers[i] if i < len(headers) else f'column_{i}'
                    model_data[key] = col.get_text(strip=True)
                
                if model_data:
                    models.append(model_data)
    
    # 策略3: 查找特定class的div或section
    model_containers = soup.find_all(['div', 'section'], class_=re.compile(r'model|card|item'))
    for container in model_containers:
        model_data = extract_model_from_element(container)
        if model_data:
            models.append(model_data)
    
    # 策略4: 查找列表项
    lists = soup.find_all(['ul', 'ol'], class_=re.compile(r'model|list'))
    for ul in lists:
        items = ul.find_all('li')
        for item in items:
            model_data = extract_model_from_element(item)
            if model_data:
                models.append(model_data)
    
    return models


def extract_model_from_element(element) -> Dict[str, Any]:
    """从HTML元素中提取模型信息"""
    model_data = {}
    
    # 提取所有文本内容
    text = element.get_text(separator='|', strip=True)
    
    # 提取模型名称（通常包含qwen、通义等关键词）
    name_patterns = [
        r'(qwen[^\s|]*)',
        r'(通义[^\s|]*)',
        r'([a-z]+[-_][a-z0-9]+)',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            model_data['name'] = match.group(1)
            break
    
    # 提取参数量
    param_match = re.search(r'(\d+\.?\d*)\s*[BM]', text, re.IGNORECASE)
    if param_match:
        model_data['parameters'] = param_match.group(0)
    
    # 提取上下文长度
    context_match = re.search(r'(\d+)k?\s*(?:tokens?|上下文)', text, re.IGNORECASE)
    if context_match:
        model_data['context_length'] = context_match.group(1)
    
    # 提取价格信息
    price_patterns = [
        r'¥?\s*(\d+\.?\d*)\s*元?/\s*(千tokens?|万tokens?|M tokens?)',
        r'(\d+\.?\d*)\s*分/\s*(千tokens?|万tokens?)',
    ]
    
    for pattern in price_patterns:
        price_match = re.search(pattern, text, re.IGNORECASE)
        if price_match:
            model_data['price'] = price_match.group(0)
            break
    
    # 如果没有提取到有效信息，返回空
    if len(model_data) < 2:
        return None
    
    # 添加原始文本（用于调试）
    model_data['raw_text'] = text[:200]  # 限制长度
    
    return model_data


def save_models_to_json(models: List[Dict], output_file: str):
    """保存模型信息为JSON文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(models, f, ensure_ascii=False, indent=2)
    print(f"已保存 {len(models)} 个模型到 {output_file}")


def save_models_to_markdown(models: List[Dict], output_file: str):
    """保存模型信息为Markdown文档"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 阿里云百炼平台模型列表\n\n")
        f.write(f"提取时间: {Path(__file__).stat().st_mtime}\n\n")
        f.write(f"模型总数: {len(models)}\n\n")
        f.write("---\n\n")
        
        for i, model in enumerate(models, 1):
            f.write(f"## {i}. {model.get('name', '未知模型')}\n\n")
            
            for key, value in model.items():
                if key != 'raw_text' and key != 'name':
                    f.write(f"- **{key}**: {value}\n")
            
            # 如果有原始文本，作为详情添加
            if 'raw_text' in model:
                f.write(f"\n<details>\n<summary>原始文本</summary>\n\n")
                f.write(f"```\n{model['raw_text']}\n```\n\n")
                f.write(f"</details>\n\n")
            
            f.write("---\n\n")
    
    print(f"已生成Markdown文档: {output_file}")


def main():
    """主函数"""
    html_file = "全量模型规格参数计费表-大模型服务平台百炼-阿里云.html"
    
    if not Path(html_file).exists():
        print(f"错误: 找不到文件 {html_file}")
        return
    
    print("开始解析HTML文件...")
    models = extract_models_from_html(html_file)
    
    if not models:
        print("警告: 未提取到模型信息，尝试使用备选方案...")
        # 可以在这里添加更多提取策略
    
    # 去重（基于模型名称）
    unique_models = []
    seen_names = set()
    for model in models:
        # 过滤掉非字典类型的数据
        if not isinstance(model, dict):
            continue
        
        name = model.get('name', '')
        if name and name not in seen_names:
            unique_models.append(model)
            seen_names.add(name)
    
    print(f"提取到 {len(models)} 个条目，去重后 {len(unique_models)} 个唯一模型")
    
    # 保存结果
    if unique_models:
        save_models_to_json(unique_models, "models.json")
        save_models_to_markdown(unique_models, "models.md")
    else:
        print("未提取到有效的模型信息")
        # 输出HTML的基本结构用于调试
        with open(html_file, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            print("\nHTML结构预览:")
            print(f"- script标签数量: {len(soup.find_all('script'))}")
            print(f"- table标签数量: {len(soup.find_all('table'))}")
            print(f"- div标签数量: {len(soup.find_all('div'))}")
            
            # 显示前几个有意义的文本内容
            texts = [t.strip() for t in soup.stripped_strings if len(t.strip()) > 10][:20]
            print("\n前20个文本片段:")
            for t in texts:
                print(f"  - {t[:100]}")


if __name__ == "__main__":
    main()
