"""手动实弹验证: 走真实 ImageGenerator 代码路径(含本次 fan-out 修复),
用本机真实 OpenAI profile(url+key)对真实网关请求 n=3, 确认拿回 3 张图。

复现原始报错场景: gpt-image-2 + n>1 在修复前为 502(tools[0].n)。
安全: key 经后端 decrypt_api_key 进程内取得, 只打印 host 与 key 长度, 绝不打印 key。
运行(在 backend/ 目录, 用 venv):
  $ .venv\\Scripts\\python.exe -m tests.manual_verify_fanout_generate
注意: 会发起真实生成请求(走订阅), 已用小尺寸/低质量控制开销。
"""
from __future__ import annotations
import asyncio
import sys
from urllib.parse import urlsplit

sys.stdout.reconfigure(encoding="utf-8")

from app.core.database import SessionLocal
from app.core.encryption import decrypt_api_key
from app.models.db_models import ConfigProfile
from app.services.openai.image_generator import ImageGenerator


def load_openai_credentials() -> tuple[str, str]:
    db = SessionLocal()
    try:
        profile = (
            db.query(ConfigProfile)
            .filter(ConfigProfile.provider_id == "openai")
            .order_by(ConfigProfile.updated_at.desc())
            .first()
        )
        if not profile:
            raise SystemExit("未找到 provider_id='openai' 的 config_profile")
        api_key = decrypt_api_key(profile.api_key, silent=True)
        base_url = (profile.base_url or "https://api.openai.com/v1").strip()
        host = urlsplit(base_url).netloc or base_url
        print(f"[creds] profile='{profile.name}' base_url_host={host} key_len={len(api_key or '')}")
        return api_key, base_url
    finally:
        db.close()


async def main() -> None:
    api_key, base_url = load_openai_credentials()
    generator = ImageGenerator(api_key=api_key, base_url=base_url)

    print("\n[verify] ImageGenerator.generate_image(gpt-image-2, n=3) 走真实网关 ...")
    results = await generator.generate_image(
        "A small glossy red ceramic teapot on a seamless studio backdrop",
        "gpt-image-2",
        number_of_images=3,
        image_resolution="1K",
        image_aspect_ratio="1:1",
        quality="low",
        output_format="png",
    )
    print(f"[result] 返回图像数 = {len(results)} (期望 3)")
    for i, r in enumerate(results):
        url = r.get("url", "")
        print(f"  - img[{i}] mime={r.get('mime_type')} url_len={len(url)} head={url[:32]!r}")
    assert len(results) == 3, f"期望 3 张, 实得 {len(results)}"
    print("\n[OK] fan-out 修复在真实网关上验证通过: n=3 -> 3 张图。")


if __name__ == "__main__":
    asyncio.run(main())
