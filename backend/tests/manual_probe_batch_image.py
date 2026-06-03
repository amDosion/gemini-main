"""手动经验性探针: 用本机真实 OpenAI profile(url+key)对真实网关跑批量矩阵。

目的: 经验性确认 gpt-image-2 在我们这条网关上,
  - 原生 n>1 是否可行(官方文档说 1-10 合法);
  - 换模型/换形态是否能绕过;
  - fan-out(并发 n=1)是否能拿回 N 张。

安全: key 通过后端 decrypt_api_key 进程内取得,只打印 host 与 key 长度,绝不打印 key。
运行(在 backend/ 目录, 用 venv):
  $ .venv\\Scripts\\python.exe -m tests.manual_probe_batch_image
注意: 会发起真实生成请求(走订阅), 已尽量用小尺寸/低质量/最小 n 控制开销。
"""
from __future__ import annotations
import asyncio
import sys
import time
from urllib.parse import urlsplit

# 仅打印结果, 不打印 key
sys.stdout.reconfigure(encoding="utf-8")

from app.core.database import SessionLocal
from app.core.encryption import decrypt_api_key
from app.models.db_models import ConfigProfile
from openai import AsyncOpenAI

PROMPT = "A small glossy red ceramic teapot on a seamless studio backdrop"
SIZE = "1024x1024"        # 小尺寸, 省时省钱
QUALITY = "low"           # 低质量, 加速


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


async def one_call(client: AsyncOpenAI, *, model: str, n: int, label: str) -> str:
    started = time.perf_counter()
    try:
        resp = await client.images.generate(
            model=model, prompt=PROMPT, n=n, size=SIZE, quality=QUALITY, output_format="png",
        )
        ms = (time.perf_counter() - started) * 1000
        return f"{label:<34} -> OK   imgs={len(resp.data)} ({ms:.0f}ms)"
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - started) * 1000
        code = getattr(e, "status_code", "?")
        return f"{label:<34} -> FAIL status={code} ({ms:.0f}ms) {type(e).__name__}: {str(e)[:180]}"


async def fanout(client: AsyncOpenAI, *, model: str, count: int, label: str) -> str:
    started = time.perf_counter()
    try:
        resps = await asyncio.gather(*(
            client.images.generate(model=model, prompt=PROMPT, n=1, size=SIZE,
                                    quality=QUALITY, output_format="png")
            for _ in range(count)
        ))
        ms = (time.perf_counter() - started) * 1000
        total = sum(len(r.data) for r in resps)
        return f"{label:<34} -> OK   imgs={total} ({ms:.0f}ms, {count}x并发n=1)"
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - started) * 1000
        code = getattr(e, "status_code", "?")
        return f"{label:<34} -> FAIL status={code} ({ms:.0f}ms) {type(e).__name__}: {str(e)[:180]}"


async def main() -> None:
    api_key, base_url = load_openai_credentials()
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=300.0, max_retries=0)
    print(f"\n矩阵 (size={SIZE} quality={QUALITY}) ——\n")

    # 1) 基线 + 原生批量 + 换模型(顺序跑, 拿干净的逐条结论)
    print(await one_call(client, model="gpt-image-2", n=1, label="A. gpt-image-2 原生 n=1"))
    print(await one_call(client, model="gpt-image-2", n=2, label="B. gpt-image-2 原生 n=2"))
    print(await one_call(client, model="gpt-image-1.5", n=2, label="C. gpt-image-1.5 原生 n=2"))
    print(await one_call(client, model="gpt-image-1", n=2, label="D. gpt-image-1 原生 n=2"))
    # 2) fan-out 对照(我们要修复采用的方案)
    print(await fanout(client, model="gpt-image-2", count=2, label="E. gpt-image-2 fan-out=2"))


if __name__ == "__main__":
    asyncio.run(main())
