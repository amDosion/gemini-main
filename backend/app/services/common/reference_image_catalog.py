"""
Reference image catalog for workflow templates/presets.

统一维护模板默认参考图 URL，避免多处重复定义。
"""

from typing import Any, List


REFERENCE_IMAGE_URLS: List[str] = [
    # 服装单品（电商主图风格）
    "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=1200&q=80",
    # 服装陈列（品类/风格参考）
    "https://images.unsplash.com/photo-1512436991641-6745cdb1723f?auto=format&fit=crop&w=1200&q=80",
    # 模特人像（服装场景）
    "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=1200&q=80",
    # 街拍穿搭（服装上身效果）
    "https://images.unsplash.com/photo-1483985988355-763728e1935b?auto=format&fit=crop&w=1200&q=80",
    # 电商产品（鞋类）
    "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=1200&q=80",
    # 电商产品（鞋服细节）
    "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?auto=format&fit=crop&w=1200&q=80",
]


def is_placeholder_reference_image_url(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    if "{{" in text or "}}" in text:
        return True
    if "example.com" in text or "example.org" in text:
        return True
    if "<" in text and ">" in text:
        return True
    if "your-image" in text or "placeholder" in text:
        return True
    return False


def pick_reference_image(seed: str = "", index: int = 0) -> str:
    if not REFERENCE_IMAGE_URLS:
        return ""
    seed_text = f"{seed or ''}:{index}"
    position = sum(ord(ch) for ch in seed_text) % len(REFERENCE_IMAGE_URLS)
    return REFERENCE_IMAGE_URLS[position]

