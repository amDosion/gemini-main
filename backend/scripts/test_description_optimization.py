"""
测试脚本：验证描述优化，避免与名称重复
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.common.model_capabilities import get_model_name, get_model_description

test_cases = [
    'gemini-2.5-flash-lite-preview-09-2025',
    'gemini-2.5-pro',
    'imagen-4.0-generate-001',
    'veo-3.1-generate-001',
    'gemini-3-pro-image-preview'
]

print('=' * 80)
print('测试描述优化（避免与名称重复）')
print('=' * 80)
print()

for model_id in test_cases:
    name = get_model_name(model_id)
    desc = get_model_description('google', model_id)
    
    # 检查描述是否包含名称中的关键词
    name_words = set(name.lower().split())
    desc_words = set(desc.lower().split())
    common_words = name_words.intersection(desc_words)
    
    # 移除常见词（如 "model", "with", "and", "the" 等）
    common_words_filtered = {w for w in common_words if w not in ['model', 'with', 'and', 'the', 'a', 'an', 'for', 'to', 'of', 'in', 'on', 'at', 'by']}
    
    print(f'模型 ID: {model_id}')
    print(f'  名称: {name}')
    print(f'  描述: {desc}')
    print(f'  共同词: {common_words_filtered if common_words_filtered else "无"}')
    print(f'  描述长度: {len(desc)}')
    print()
