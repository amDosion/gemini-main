"""手动实弹验证: chat-edit(OpenAI)首轮走 ImageEditor.edit_image (images.edits),
验证本次 fan-out 修复在编辑路径上对 n>1 是否拿回 N 张。

流程: 真实网关先生成 1 张底图 -> 用它作参考图请求 edit(number_of_images=2)。
安全: key 经后端 decrypt_api_key 进程内取得, 只打印 host 与 key 长度, 绝不打印 key。
运行(backend/ 目录): .venv\\Scripts\\python.exe -m tests.manual_verify_fanout_edit
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
from app.services.openai.image_editor import ImageEditor


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

    print("\n[step1] 先生成 1 张底图(n=1)作为编辑参考 ...")
    generator = ImageGenerator(api_key=api_key, base_url=base_url)
    base = await generator.generate_image(
        "A plain white coffee mug centered on a light gray studio background",
        "gpt-image-2",
        number_of_images=1,
        image_resolution="1K",
        image_aspect_ratio="1:1",
        quality="low",
        output_format="png",
    )
    ref_url = base[0]["url"]
    print(f"[step1] 底图就绪 url_len={len(ref_url)}")

    print("\n[step2] ImageEditor.edit_image(gpt-image-2, number_of_images=2) 走真实网关 ...")
    editor = ImageEditor(api_key=api_key, base_url=base_url)
    results = await editor.edit_image(
        prompt="Add a small red heart latte-art pattern on the surface of the drink.",
        model="gpt-image-2",
        reference_images={"raw": ref_url},
        number_of_images=2,
        image_resolution="1K",
        image_aspect_ratio="1:1",
        quality="low",
        output_format="png",
    )
    print(f"[result] 编辑返回图像数 = {len(results)} (期望 2)")
    for i, r in enumerate(results):
        url = r.get("url", "")
        print(f"  - img[{i}] mime={r.get('mime_type')} url_len={len(url)} head={url[:32]!r}")
    assert len(results) == 2, f"期望 2 张, 实得 {len(results)}"
    print("\n[OK] fan-out 修复在编辑路径(images.edits/OAuth)上验证通过: n=2 -> 2 张图。")


if __name__ == "__main__":
    asyncio.run(main())
