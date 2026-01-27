"""
语言检测模块

检测文本语言（中文/英文），并提供对应的魔法词组。
"""
from typing import Literal

# 魔法词组配置
MAGIC_SUFFIX = {
    "zh": "超清，4K，电影级构图",
    "en": "Ultra HD, 4K, cinematic composition",
}


def detect_language(text: str) -> Literal["zh", "en"]:
    """
    检测文本语言

    通过检测 CJK（中日韩）字符范围判断是否为中文。

    Args:
        text: 输入文本

    Returns:
        'zh' 表示中文，'en' 表示英文
    """
    # CJK 字符范围
    cjk_ranges = [
        ('\u4e00', '\u9fff'),   # CJK Unified Ideographs (基本汉字)
        ('\u3400', '\u4dbf'),   # CJK Unified Ideographs Extension A
        ('\uf900', '\ufaff'),   # CJK Compatibility Ideographs
    ]

    for char in text:
        for start, end in cjk_ranges:
            if start <= char <= end:
                return 'zh'

    return 'en'


def get_magic_suffix(language: Literal["zh", "en"]) -> str:
    """
    获取对应语言的魔法词组

    Args:
        language: 语言代码 ('zh' 或 'en')

    Returns:
        魔法词组字符串
    """
    return MAGIC_SUFFIX.get(language, MAGIC_SUFFIX["en"])


def is_chinese_text(text: str) -> bool:
    """
    判断文本是否主要为中文

    Args:
        text: 输入文本

    Returns:
        True 如果文本主要为中文
    """
    return detect_language(text) == "zh"
