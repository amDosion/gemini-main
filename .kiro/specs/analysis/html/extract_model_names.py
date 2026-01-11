#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从HTML中提取所有Qwen模型名称
"""

import re
from collections import OrderedDict

html_file = "全量模型规格参数计费表-大模型服务平台百炼-阿里云.html"

print("读取HTML文件...")
with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"文件大小: {len(content)} 字符\n")

# 定义模型名称的正则模式
patterns = [
    r'qwen[0-9]*(?:\.[0-9]+)?-[a-z0-9-]+',  # qwen-plus, qwen2.5-max等
    r'qwen[0-9]*(?:\.[0-9]+)?',  # qwen, qwen2, qwen2.5等
]

# 提取所有匹配的模型名称
all_models = set()

for pattern in patterns:
    matches = re.findall(pattern, content, re.IGNORECASE)
    all_models.update([m.lower() for m in matches])

# 过滤和排序
# 移除太短或明显不是模型名的
filtered_models = []
for model in sorted(all_models):
    # 基本过滤
    if len(model) < 4:
        continue
    if model in ['qwen', 'qwenvl', 'qwenlong']:
        continue

    filtered_models.append(model)

# 去重并排序
unique_models = list(OrderedDict.fromkeys(filtered_models))

print(f"找到 {len(unique_models)} 个唯一的模型名称:\n")

# 按类别分组
text_models = []
vision_models = []
audio_models = []
long_models = []
coder_models = []
math_models = []
other_models = []

for model in unique_models:
    if 'vl' in model or 'vision' in model:
        vision_models.append(model)
    elif 'audio' in model:
        audio_models.append(model)
    elif 'long' in model:
        long_models.append(model)
    elif 'coder' in model or 'code' in model:
        coder_models.append(model)
    elif 'math' in model:
        math_models.append(model)
    else:
        text_models.append(model)

# 打印分类结果
if text_models:
    print("### 文本模型 (Text Models)")
    for model in text_models:
        print(f"  - {model}")
    print()

if vision_models:
    print("### 视觉模型 (Vision Models)")
    for model in vision_models:
        print(f"  - {model}")
    print()

if audio_models:
    print("### 音频模型 (Audio Models)")
    for model in audio_models:
        print(f"  - {model}")
    print()

if long_models:
    print("### 长文本模型 (Long Context Models)")
    for model in long_models:
        print(f"  - {model}")
    print()

if coder_models:
    print("### 代码模型 (Coder Models)")
    for model in coder_models:
        print(f"  - {model}")
    print()

if math_models:
    print("### 数学模型 (Math Models)")
    for model in math_models:
        print(f"  - {model}")
    print()

if other_models:
    print("### 其他模型 (Other Models)")
    for model in other_models:
        print(f"  - {model}")
    print()

# 保存结果
print(f"\n总计: {len(unique_models)} 个模型")

# 保存为JSON
import json
models_data = {
    "text_models": text_models,
    "vision_models": vision_models,
    "audio_models": audio_models,
    "long_models": long_models,
    "coder_models": coder_models,
    "math_models": math_models,
    "other_models": other_models,
    "all_models": unique_models
}

with open('extracted_models.json', 'w', encoding='utf-8') as f:
    json.dump(models_data, f, ensure_ascii=False, indent=2)
print("\n已保存到 extracted_models.json")

# 生成Markdown
with open('extracted_models.md', 'w', encoding='utf-8') as f:
    f.write("# 阿里云百炼平台模型列表\n\n")
    f.write(f"提取时间: 2025-12-28\n\n")
    f.write(f"总计: {len(unique_models)} 个模型\n\n")
    f.write("---\n\n")

    if text_models:
        f.write("## 文本模型 (Text Models)\n\n")
        for model in text_models:
            f.write(f"- `{model}`\n")
        f.write("\n")

    if vision_models:
        f.write("## 视觉模型 (Vision Models)\n\n")
        for model in vision_models:
            f.write(f"- `{model}`\n")
        f.write("\n")

    if audio_models:
        f.write("## 音频模型 (Audio Models)\n\n")
        for model in audio_models:
            f.write(f"- `{model}`\n")
        f.write("\n")

    if long_models:
        f.write("## 长文本模型 (Long Context Models)\n\n")
        for model in long_models:
            f.write(f"- `{model}`\n")
        f.write("\n")

    if coder_models:
        f.write("## 代码模型 (Coder Models)\n\n")
        for model in coder_models:
            f.write(f"- `{model}`\n")
        f.write("\n")

    if math_models:
        f.write("## 数学模型 (Math Models)\n\n")
        for model in math_models:
            f.write(f"- `{model}`\n")
        f.write("\n")

    if other_models:
        f.write("## 其他模型 (Other Models)\n\n")
        for model in other_models:
            f.write(f"- `{model}`\n")
        f.write("\n")

    f.write("---\n\n")
    f.write("## 完整列表\n\n")
    for model in unique_models:
        f.write(f"- `{model}`\n")

print("已保存到 extracted_models.md")
