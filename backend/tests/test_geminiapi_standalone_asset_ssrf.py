from app.services.gemini.geminiapi import main as geminiapi_main
from app.utils.url_security import UnsafeURLError


class _NoNetworkClient:
    async def get(self, *args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("bare http_client.get should not be used")


class _Response:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self) -> None:
        return None


def _doc_with_asset_url(url: str) -> geminiapi_main.LayerDoc:
    return geminiapi_main.LayerDoc(
        width=16,
        height=16,
        layers=[
            geminiapi_main.RasterLayer(
                id="asset",
                type="raster",
                asset_url=url,
            )
        ],
    )


async def test_preload_raster_assets_uses_ssrf_guard_without_bare_get(monkeypatch):
    calls: list[str] = []

    async def fake_guard(client, url, *, max_redirects=5):
        calls.append(url)
        raise UnsafeURLError("blocked unsafe URL")

    monkeypatch.setattr(geminiapi_main, "get_with_redirect_guard", fake_guard)

    assets = await geminiapi_main._preload_raster_assets(
        _doc_with_asset_url("http://127.0.0.1:9/internal.png"),
        _NoNetworkClient(),
    )

    assert assets == {}
    assert calls == ["http://127.0.0.1:9/internal.png"]


async def test_preload_raster_assets_keeps_successful_guarded_fetch(monkeypatch):
    async def fake_guard(client, url, *, max_redirects=5):
        return _Response(b"image-bytes"), url

    monkeypatch.setattr(geminiapi_main, "get_with_redirect_guard", fake_guard)

    assets = await geminiapi_main._preload_raster_assets(
        _doc_with_asset_url("https://cdn.example.test/image.png"),
        _NoNetworkClient(),
    )

    assert assets == {"https://cdn.example.test/image.png": b"image-bytes"}
