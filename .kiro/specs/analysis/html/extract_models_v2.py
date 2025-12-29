#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取阿里云百炼平台模型数据 - 简化版
直接从window.__ICE_APP_DATA__中提取JSON数据
"""

import json
import re
from pathlib import Path


def extract_ice_app_data(html_file: str):
    """提取window.__ICE_APP_DATA__中的数据"""
    
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找window.__ICE_APP_DATA__的赋值
    pattern = r'window\.__ICE_APP_DATA__\s*=\s*(\{.*?\});'
    
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("未找到window.__ICE_APP_DATA__")
        return None
    
    json_str = match.group(1)
    print(f"找到数据，长度: {len(json_str)} 字符")
    
    try:
        data = json.loads(json_str)
        print(f"JSON解析成功，根键: {list(data.keys())}")
        return data
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        # 保存原始数据用于调试
        with open('raw_data.txt', 'w', encoding='utf-8') as f:
            f.write(json_str[:10000])  # 保存前10000字符
        return None


def find_models_in_data(data, path=""):
    """递归查找数据中的模型信息"""
    models = []
    
    if isinstance(data, dict):
        # 检查是否包含模型相关字段
        if 'modelId' in data or 'model_id' in data or 'name' in data:
            # 可能是模型数据
            model_name = data.get('modelId') or data.get('model_id') or data.get('name')
            if model_name and ('qwen' in str(model_name).lower() or '通义' in str(model_name)):
                models.append(data)
        
        # 递归搜索
        for key, value in data.items():
            sub_models = find_models_in_data(value, f"{path}.{key}")
            models.extend(sub_models)
    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            sub_models = find_models_in_data(item, f"{path}[{i}]")
            models.extend(sub_models)
    
    return models


def save_models_report(models, output_file):
    """生成模型报告"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 阿里云百炼平台模型列表\n\n")
        f.write(f"提取到 {len(models)} 个模型\n\n")
        f.write("---\n\n")
        
        for i, model in enumerate(models, 1):
            # 提取模型名称
            model_id = model.get('modelId') or model.get('model_id') or model.get('name', f'模型{i}')
            f.write(f"## {i}. {model_id}\n\n")
            
            # 提取关键字段
            key_fields = [
                'modelId', 'model_id', 'name', 'displayName', 'display_name',
                'description', 'contextLength', 'context_length', 'maxTokens', 'max_tokens',
                'inputPrice', 'input_price', 'outputPrice', 'output_price',
                'price', 'pricing', 'parameters', 'version', 'type', 'category'
            ]
            
            f.write("### 基本信息\n\n")
            for field in key_fields:
                if field in model:
                    f.write(f"- **{field}**: {model[field]}\n")
            
            # 其他字段
            other_fields = {k: v for k, v in model.items() if k not in key_fields}
            if other_fields:
                f.write("\n### 其他属性\n\n")
                for key, value in other_fields.items():
                    if not isinstance(value, (dict, list)):
                        f.write(f"- **{key}**: {value}\n")
            
            f.write("\n---\n\n")
    
    print(f"报告已生成: {output_file}")


def main():
    html_file = "全量模型规格参数计费表-大模型服务平台百炼-阿里云.html"
    
    if not Path(html_file).exists():
        print(f"错误: 找不到文件 {html_file}")
        return
    
    print("正在提取数据...")
    data = extract_ice_app_data(html_file)
    
    if not data:
        print("数据提取失败")
        return
    
    # 保存完整数据
    with open('full_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("完整数据已保存到 full_data.json")
    
    # 查找模型数据
    print("\n正在查找模型信息...")
    models = find_models_in_data(data)
    
    print(f"找到 {len(models)} 个模型")
    
    if models:
        # 保存模型数据
        with open('models.json', 'w', encoding='utf-8') as f:
            json.dump(models, f, ensure_ascii=False, indent=2)
        print("模型数据已保存到 models.json")
        
        # 生成报告
        save_models_report(models, 'models.md')
    else:
        print("\n未找到模型数据，数据结构可能不同")
        print("请检查 full_data.json 文件手动分析")


if __name__ == "__main__":
    main()
