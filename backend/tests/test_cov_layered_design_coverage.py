"""Thorough unit tests for app.services.common.layered_design_service.

Covers the pure algorithm helpers (color parsing, gradients, contour tracing,
RDP simplification, Chaikin smoothing, SVG/bezier path emission) and the
LayeredDesignService class (mode dispatch, image extraction, LLM-backed
suggest_layout, external decompose_layers, vectorize_mask, and the full
render_layerdoc compositor with every layer type).

External boundaries only are mocked: LLM SDK clients, httpx.AsyncClient, and
the google.genai import. No real network/credentials are used.
"""

import base64
import io
import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import numpy as np
import pytest
from PIL import Image

import app.services.common.layered_design_service as mod
from app.services.common.layered_design_service import (
    LayeredDesignService,
    _apply_opacity_rgba,
    _b64d,
    _b64e,
    _clamp01,
    _contours_to_svg,
    _extract_json_from_llm_response,
    _find_contours_from_mask,
    _linear_gradient_rgba,
    _load_font,
    _pil_to_png_bytes,
    _points_to_bezier_path,
    _points_to_svg_path,
    _rgba_tuple,
    _simplify_contour_rdp,
    _smooth_contour,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _solid_square_mask(size: int = 24, fill: int = 255, square: int = 12) -> bytes:
    """An L-mode mask with an opaque square in the middle (forms a contour)."""
    arr = np.zeros((size, size), dtype=np.uint8)
    lo = (size - square) // 2
    hi = lo + square
    arr[lo:hi, lo:hi] = fill
    return _png_bytes(Image.fromarray(arr, mode="L"))


# ---------------------------------------------------------------------------
# base64 / png helpers
# ---------------------------------------------------------------------------
def test_b64_roundtrip():
    raw = b"hello-bytes-\x00\xff"
    assert _b64d(_b64e(raw)) == raw


def test_pil_to_png_bytes_is_valid_png():
    img = Image.new("RGBA", (4, 4), (1, 2, 3, 255))
    data = _pil_to_png_bytes(img)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    reopened = Image.open(io.BytesIO(data))
    assert reopened.size == (4, 4)


# ---------------------------------------------------------------------------
# _load_font
# ---------------------------------------------------------------------------
def test_load_font_default(monkeypatch):
    # Force the no-FONT_PATH branch so we hit load_default.
    monkeypatch.setattr(mod, "FONT_PATH", "", raising=False)
    _load_font.cache_clear()
    font = _load_font(20)
    assert font is not None


# ---------------------------------------------------------------------------
# _clamp01
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value,expected",
    [(-1.0, 0.0), (0.0, 0.0), (0.5, 0.5), (1.0, 1.0), (2.5, 1.0)],
)
def test_clamp01(value, expected):
    assert _clamp01(value) == expected


# ---------------------------------------------------------------------------
# _rgba_tuple
# ---------------------------------------------------------------------------
def test_rgba_tuple_rrggbb():
    assert _rgba_tuple("#FF8000") == (255, 128, 0, 255)


def test_rgba_tuple_rrggbbaa():
    assert _rgba_tuple("#10203040") == (16, 32, 48, 64)


def test_rgba_tuple_no_hash_defaults_white():
    assert _rgba_tuple("notacolor") == (255, 255, 255, 255)


def test_rgba_tuple_bad_length_defaults_white():
    assert _rgba_tuple("#ABC") == (255, 255, 255, 255)


def test_rgba_tuple_strips_whitespace():
    assert _rgba_tuple("  #00FF00  ") == (0, 255, 0, 255)


# ---------------------------------------------------------------------------
# _apply_opacity_rgba
# ---------------------------------------------------------------------------
def test_apply_opacity_full_returns_same_object():
    img = Image.new("RGBA", (3, 3), (10, 20, 30, 255))
    out = _apply_opacity_rgba(img, 1.0)
    assert out is img


def test_apply_opacity_half_scales_alpha():
    img = Image.new("RGBA", (2, 2), (10, 20, 30, 200))
    out = _apply_opacity_rgba(img, 0.5)
    arr = np.array(out)
    # alpha scaled to ~100
    assert int(arr[0, 0, 3]) == 100
    # RGB untouched
    assert tuple(arr[0, 0, :3]) == (10, 20, 30)


def test_apply_opacity_converts_non_rgba():
    img = Image.new("RGB", (2, 2), (10, 20, 30))
    out = _apply_opacity_rgba(img, 0.5)
    assert out.mode == "RGBA"


# ---------------------------------------------------------------------------
# _extract_json_from_llm_response
# ---------------------------------------------------------------------------
def test_extract_json_from_fenced_json_block():
    text = 'prefix\n```json\n{"a": 1}\n```\nsuffix'
    assert json.loads(_extract_json_from_llm_response(text)) == {"a": 1}


def test_extract_json_from_plain_fence():
    text = '```\n{"b": 2}\n```'
    assert json.loads(_extract_json_from_llm_response(text)) == {"b": 2}


def test_extract_json_from_brace_scan():
    text = 'some words {"c": 3} trailing text'
    assert json.loads(_extract_json_from_llm_response(text)) == {"c": 3}


def test_extract_json_returns_text_when_no_json():
    text = "no braces here at all"
    assert _extract_json_from_llm_response(text) == "no braces here at all"


# ---------------------------------------------------------------------------
# _linear_gradient_rgba
# ---------------------------------------------------------------------------
def test_linear_gradient_two_stops_endpoints():
    stops = [(0.0, (0, 0, 0, 255)), (1.0, (255, 255, 255, 255))]
    img = _linear_gradient_rgba(16, 16, 0.0, stops)
    assert img.mode == "RGBA"
    assert img.size == (16, 16)
    arr = np.array(img)
    # left edge dark, right edge light along a 0-degree gradient
    assert arr[8, 0, 0] < arr[8, -1, 0]


def test_linear_gradient_unsorted_stops_handled():
    stops = [(1.0, (255, 255, 255, 255)), (0.0, (0, 0, 0, 255))]
    img = _linear_gradient_rgba(8, 8, 45.0, stops)
    assert img.size == (8, 8)


def test_linear_gradient_three_stops():
    stops = [
        (0.0, (255, 0, 0, 255)),
        (0.5, (0, 255, 0, 255)),
        (1.0, (0, 0, 255, 255)),
    ]
    img = _linear_gradient_rgba(20, 4, 0.0, stops)
    arr = np.array(img)
    # red somewhere on the left half, blue on the far right
    assert arr[2, 0, 0] > arr[2, -1, 0]
    assert arr[2, -1, 2] > arr[2, 0, 2]


# ---------------------------------------------------------------------------
# _find_contours_from_mask
# ---------------------------------------------------------------------------
def test_find_contours_empty_mask():
    arr = np.zeros((10, 10), dtype=np.uint8)
    assert _find_contours_from_mask(arr) == []


def test_find_contours_single_square():
    arr = np.zeros((20, 20), dtype=np.uint8)
    arr[5:15, 5:15] = 255
    contours = _find_contours_from_mask(arr, threshold=128)
    assert len(contours) >= 1
    # all points within bounds
    for cx, cy in contours[0]:
        assert 0 <= cx < 20 and 0 <= cy < 20


def test_find_contours_respects_threshold():
    arr = np.full((12, 12), 100, dtype=np.uint8)
    arr[3:9, 3:9] = 200
    # threshold above 100 keeps only the bright square
    contours = _find_contours_from_mask(arr, threshold=150)
    assert len(contours) >= 1


# ---------------------------------------------------------------------------
# _simplify_contour_rdp
# ---------------------------------------------------------------------------
def test_rdp_short_contour_unchanged():
    pts = [(0, 0), (1, 1)]
    assert _simplify_contour_rdp(pts, 1.0) == pts


def test_rdp_collinear_points_collapse():
    pts = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
    out = _simplify_contour_rdp(pts, 0.5)
    # collinear interior points removed -> endpoints kept
    assert out[0] == (0, 0)
    assert out[-1] == (4, 0)
    assert len(out) <= 3


def test_rdp_preserves_corner():
    pts = [(0, 0), (5, 0), (10, 0), (10, 5), (10, 10)]
    out = _simplify_contour_rdp(pts, 0.5)
    # the corner (10, 0) should survive simplification
    assert (10, 0) in out


def test_rdp_zero_length_segment_distance():
    # start == end forces the dx==dy==0 perpendicular distance branch
    pts = [(2, 2), (5, 9), (2, 2)]
    out = _simplify_contour_rdp(pts, 0.1)
    assert out[0] == (2, 2)
    assert out[-1] == (2, 2)


# ---------------------------------------------------------------------------
# _smooth_contour
# ---------------------------------------------------------------------------
def test_smooth_contour_short_returns_floats():
    pts = [(0, 0), (1, 1)]
    out = _smooth_contour(pts, iterations=2)
    assert out == [(0.0, 0.0), (1.0, 1.0)]
    assert all(isinstance(v, float) for p in out for v in p)


def test_smooth_contour_doubles_points():
    pts = [(0, 0), (10, 0), (10, 10)]
    out = _smooth_contour(pts, iterations=1)
    # Chaikin emits two points per original vertex
    assert len(out) == 2 * len(pts)


def test_smooth_contour_zero_iterations_noop():
    pts = [(0, 0), (10, 0), (10, 10)]
    out = _smooth_contour(pts, iterations=0)
    assert out == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]


# ---------------------------------------------------------------------------
# _points_to_svg_path
# ---------------------------------------------------------------------------
def test_points_to_svg_path_too_few_points():
    assert _points_to_svg_path([(0.0, 0.0)]) == ""


def test_points_to_svg_path_closed():
    d = _points_to_svg_path([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], closed=True)
    assert d.startswith("M 0.00 0.00")
    assert " L 10.00 0.00" in d
    assert d.endswith("Z")


def test_points_to_svg_path_open():
    d = _points_to_svg_path([(0.0, 0.0), (10.0, 0.0)], closed=False)
    assert not d.endswith("Z")


# ---------------------------------------------------------------------------
# _points_to_bezier_path
# ---------------------------------------------------------------------------
def test_bezier_too_few_points():
    assert _points_to_bezier_path([(0.0, 0.0)]) == ""


def test_bezier_two_points_is_line():
    d = _points_to_bezier_path([(0.0, 0.0), (5.0, 5.0)], closed=True)
    assert d.startswith("M 0.00 0.00")
    assert "L 5.00 5.00" in d
    assert d.endswith("Z")


def test_bezier_two_points_open_no_z():
    d = _points_to_bezier_path([(0.0, 0.0), (5.0, 5.0)], closed=False)
    assert not d.endswith("Z")


def test_bezier_closed_curve():
    pts = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    d = _points_to_bezier_path(pts, closed=True, smoothness=0.3)
    assert "C " in d
    assert d.endswith("Z")


def test_bezier_open_curve():
    pts = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    d = _points_to_bezier_path(pts, closed=False)
    assert "C " in d
    assert not d.endswith("Z")


def test_bezier_handles_duplicate_points():
    # duplicate points force the d01/d12 < 1e-6 guard
    pts = [(0.0, 0.0), (0.0, 0.0), (10.0, 10.0), (0.0, 0.0)]
    d = _points_to_bezier_path(pts, closed=True)
    assert d.startswith("M 0.00 0.00")


# ---------------------------------------------------------------------------
# _contours_to_svg
# ---------------------------------------------------------------------------
def test_contours_to_svg_bezier():
    contour = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    svg = _contours_to_svg([contour], width=20, height=20, use_bezier=True)
    assert svg.startswith("<?xml")
    assert 'viewBox="0 0 20 20"' in svg
    assert 'id="contour_0"' in svg


def test_contours_to_svg_plain_path():
    contour = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    svg = _contours_to_svg([contour], width=15, height=15, use_bezier=False)
    assert "<path" in svg
    assert " Z" in svg


def test_contours_to_svg_skips_degenerate():
    # a 2-point contour is skipped (needs >= 3)
    svg = _contours_to_svg([[(0.0, 0.0), (1.0, 1.0)]], width=5, height=5)
    assert "<path" not in svg


# ===========================================================================
# LayeredDesignService
# ===========================================================================
def test_init_defaults():
    svc = LayeredDesignService()
    assert svc.llm_client is None
    assert svc.llm_model == "gemini-2.5-flash"
    assert svc.http_client is None


def test_init_custom_model():
    svc = LayeredDesignService(llm_client=object(), llm_model="qwen-vl-max")
    assert svc.llm_model == "qwen-vl-max"


# ---------------------------------------------------------------------------
# _extract_image_data
# ---------------------------------------------------------------------------
def test_extract_image_data_empty():
    svc = LayeredDesignService()
    assert svc._extract_image_data({}) is None


def test_extract_image_data_no_raw_key():
    svc = LayeredDesignService()
    assert svc._extract_image_data({"other": 1}) is None


def test_extract_image_data_bytes_passthrough():
    svc = LayeredDesignService()
    raw = b"\x89PNG-data"
    assert svc._extract_image_data({"raw": raw}) == raw


def test_extract_image_data_data_url():
    svc = LayeredDesignService()
    payload = base64.b64encode(b"img-content").decode()
    url = f"data:image/png;base64,{payload}"
    assert svc._extract_image_data({"raw": url}) == b"img-content"


def test_extract_image_data_plain_base64():
    svc = LayeredDesignService()
    payload = base64.b64encode(b"plain-b64").decode()
    assert svc._extract_image_data({"raw": payload}) == b"plain-b64"


def test_extract_image_data_http_url_unsupported():
    svc = LayeredDesignService()
    assert svc._extract_image_data({"raw": "https://example.com/x.png"}) is None


def test_extract_image_data_dict_with_url():
    svc = LayeredDesignService()
    payload = base64.b64encode(b"nested").decode()
    raw = {"url": f"data:image/png;base64,{payload}"}
    assert svc._extract_image_data({"raw": raw}) == b"nested"


def test_extract_image_data_dict_with_data_key():
    svc = LayeredDesignService()
    raw = {"data": b"nested-bytes"}
    assert svc._extract_image_data({"raw": raw}) == b"nested-bytes"


def test_extract_image_data_bad_base64_returns_none():
    svc = LayeredDesignService()
    # not a URL, not valid base64 -> decode failure path returns None
    out = svc._extract_image_data({"raw": "!!!notbase64!!!"})
    assert out is None


def test_extract_image_data_unsupported_type():
    svc = LayeredDesignService()
    assert svc._extract_image_data({"raw": 12345}) is None


# ---------------------------------------------------------------------------
# _get_layerdoc_schema_hint
# ---------------------------------------------------------------------------
def test_schema_hint_uses_canvas_dims():
    svc = LayeredDesignService()
    hint = svc._get_layerdoc_schema_hint(800, 600)
    assert hint["width"] == 800
    assert hint["height"] == 600
    assert isinstance(hint["layers"], list)
    assert any(l["type"] == "text" for l in hint["layers"])


# ---------------------------------------------------------------------------
# process() dispatch
# ---------------------------------------------------------------------------
async def test_process_unknown_mode_raises():
    svc = LayeredDesignService()
    with pytest.raises(ValueError, match="Unknown layered design mode"):
        await svc.process(mode="nope", prompt="x", reference_images={})


async def test_process_render_requires_layerdoc():
    svc = LayeredDesignService()
    with pytest.raises(ValueError, match="requires 'layerDoc'"):
        await svc.process(mode="image-layered-render", prompt="", reference_images={})


async def test_process_dispatch_vectorize():
    svc = LayeredDesignService()
    mask = _solid_square_mask()
    payload = base64.b64encode(mask).decode()
    result = await svc.process(
        mode="image-layered-vectorize",
        prompt="",
        reference_images={"raw": f"data:image/png;base64,{payload}"},
    )
    assert result["success"] is True
    assert "svg" in result


async def test_process_dispatch_decompose_service_unavailable(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "", raising=False)
    svc = LayeredDesignService()
    payload = base64.b64encode(b"img").decode()
    result = await svc.process(
        mode="image-layered-decompose",
        prompt="",
        reference_images={"raw": f"data:image/png;base64,{payload}"},
    )
    assert result["success"] is False
    assert result["code"] == "SERVICE_NOT_AVAILABLE"


async def test_process_dispatch_suggest_passes_kwargs():
    fake = MagicMock()
    svc = LayeredDesignService(llm_client=fake)
    # Patch the actual LLM call so we only verify dispatch + JSON handling.

    async def fake_call(prompt, image_bytes):
        return '```json\n{"layers": [1, 2]}\n```'

    svc._call_llm_with_image = fake_call  # type: ignore
    payload = base64.b64encode(b"img-bytes").decode()
    result = await svc.process(
        mode="image-layered-suggest",
        prompt="make a banner",
        reference_images={"raw": f"data:image/png;base64,{payload}"},
        canvasW=1000,
        canvasH=500,
        maxTextBoxes=2,
        locale="en-US",
    )
    assert result["success"] is True
    assert result["layerDoc"] == {"layers": [1, 2]}


async def test_process_dispatch_render():
    svc = LayeredDesignService()
    doc = {"width": 10, "height": 10, "layers": []}
    result = await svc.process(
        mode="image-layered-render", prompt="", reference_images={}, layerDoc=doc
    )
    assert result["success"] is True
    assert result["mime_type"] == "image/png"


# ---------------------------------------------------------------------------
# suggest_layout
# ---------------------------------------------------------------------------
async def test_suggest_layout_no_client_raises():
    svc = LayeredDesignService()
    with pytest.raises(ValueError, match="requires an LLM client"):
        await svc.suggest_layout(image_bytes=b"x", goal="g")


async def test_suggest_layout_no_image_raises():
    svc = LayeredDesignService(llm_client=MagicMock())
    with pytest.raises(ValueError, match="requires image data"):
        await svc.suggest_layout(image_bytes=b"", goal="g")


async def test_suggest_layout_success():
    svc = LayeredDesignService(llm_client=MagicMock())

    async def fake_call(prompt, image_bytes):
        return '{"width": 100, "layers": [{"type": "text"}]}'

    svc._call_llm_with_image = fake_call  # type: ignore
    result = await svc.suggest_layout(image_bytes=b"img", goal="banner")
    assert result["success"] is True
    assert result["layerDoc"]["width"] == 100


async def test_suggest_layout_bad_json_returns_error():
    svc = LayeredDesignService(llm_client=MagicMock())

    async def fake_call(prompt, image_bytes):
        return "this is not json {"

    svc._call_llm_with_image = fake_call  # type: ignore
    result = await svc.suggest_layout(image_bytes=b"img", goal="banner")
    assert result["success"] is False
    assert "Failed to parse LayerDoc JSON" in result["error"]


async def test_suggest_layout_call_exception_returns_error():
    svc = LayeredDesignService(llm_client=MagicMock())

    async def fake_call(prompt, image_bytes):
        raise RuntimeError("llm exploded")

    svc._call_llm_with_image = fake_call  # type: ignore
    result = await svc.suggest_layout(image_bytes=b"img", goal="banner")
    assert result["success"] is False
    assert "llm exploded" in result["error"]


# ---------------------------------------------------------------------------
# _call_llm_with_image dispatch
# ---------------------------------------------------------------------------
async def test_call_llm_dispatch_unsupported_client():
    # Plain object: no "Client" in name, no models/chat attrs.
    class Bare:
        pass

    svc = LayeredDesignService(llm_client=Bare())
    with pytest.raises(ValueError, match="Unsupported LLM client type"):
        await svc._call_llm_with_image("p", b"img")


async def test_call_llm_dispatch_to_google():
    svc = LayeredDesignService(llm_client=MagicMock())
    called = {}

    async def fake_google(prompt, image_bytes):
        called["google"] = True
        return "g"

    svc._call_google_llm = fake_google  # type: ignore
    # MagicMock has a `models` attribute -> routes to google.
    out = await svc._call_llm_with_image("p", b"img")
    assert out == "g"
    assert called.get("google") is True


async def test_call_llm_dispatch_to_tongyi():
    # NOTE: class name must NOT contain "Client" (dispatch routes any
    # "*Client" type to the Google path) and must NOT expose `models`.
    class QwenNativeProvider:
        async def chat(self, **kwargs):
            return {"content": "ok"}

    svc = LayeredDesignService(llm_client=QwenNativeProvider())
    called = {}

    async def fake_tongyi(prompt, image_bytes):
        called["tongyi"] = True
        return "t"

    svc._call_tongyi_llm = fake_tongyi  # type: ignore
    out = await svc._call_llm_with_image("p", b"img")
    assert out == "t"
    assert called.get("tongyi") is True


# ---------------------------------------------------------------------------
# _call_google_llm
# ---------------------------------------------------------------------------
async def test_call_google_llm_async_aio(monkeypatch):
    # Force the genai_types import to fail so we exercise the None branch.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "google.genai":
            raise ImportError("no genai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    client = MagicMock()
    # has `aio` attribute -> async path
    client.aio = MagicMock()
    resp = MagicMock()
    resp.text = "async-text"
    client.aio.models.generate_content = AsyncMock(return_value=resp)

    svc = LayeredDesignService(llm_client=client, llm_model="gemini-x")
    out = await svc._call_google_llm("prompt", b"imgbytes")
    assert out == "async-text"
    client.aio.models.generate_content.assert_awaited_once()


async def test_call_google_llm_sync_no_aio(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "google.genai":
            raise ImportError("no genai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # object without `aio` -> sync path. Use a custom class so hasattr(aio) is False.
    class SyncClient:
        def __init__(self):
            self.models = MagicMock()

    client = SyncClient()
    resp = MagicMock()
    resp.text = "sync-text"
    client.models.generate_content = MagicMock(return_value=resp)

    svc = LayeredDesignService(llm_client=client)
    out = await svc._call_google_llm("prompt", b"imgbytes")
    assert out == "sync-text"


# ---------------------------------------------------------------------------
# _call_tongyi_llm
# ---------------------------------------------------------------------------
async def test_call_tongyi_llm_dict_content():
    client = MagicMock()
    client.chat = AsyncMock(return_value={"content": "hello-content"})
    svc = LayeredDesignService(llm_client=client, llm_model="qwen-vl-max")
    out = await svc._call_tongyi_llm("prompt", b"imgbytes")
    assert out == "hello-content"
    client.chat.assert_awaited_once()


async def test_call_tongyi_llm_dict_text_fallback():
    client = MagicMock()
    client.chat = AsyncMock(return_value={"text": "from-text"})
    svc = LayeredDesignService(llm_client=client)
    out = await svc._call_tongyi_llm("prompt", b"imgbytes")
    assert out == "from-text"


async def test_call_tongyi_llm_str_response():
    client = MagicMock()
    client.chat = AsyncMock(return_value="raw-string")
    svc = LayeredDesignService(llm_client=client)
    out = await svc._call_tongyi_llm("prompt", b"imgbytes")
    assert out == "raw-string"


# ---------------------------------------------------------------------------
# decompose_layers
# ---------------------------------------------------------------------------
async def test_decompose_no_endpoint(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "", raising=False)
    svc = LayeredDesignService()
    result = await svc.decompose_layers(image_bytes=b"img")
    assert result["success"] is False
    assert result["code"] == "SERVICE_NOT_AVAILABLE"


async def test_decompose_no_image(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "http://svc/decompose", raising=False)
    svc = LayeredDesignService()
    result = await svc.decompose_layers(image_bytes=b"")
    assert result["success"] is False
    assert "requires image data" in result["error"]


def _mk_response(status_code=200, json_body=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if json_body is not None:
        resp.json = MagicMock(return_value=json_body)
    else:
        resp.json = MagicMock(side_effect=json.JSONDecodeError("x", "y", 0))
    return resp


async def test_decompose_success(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "http://svc/decompose", raising=False)
    monkeypatch.setattr(mod, "QWEN_LAYERED_API_KEY", "secret", raising=False)
    http = MagicMock()
    http.post = AsyncMock(
        return_value=_mk_response(
            200, {"success": True, "layers": [{"i": 1}, {"i": 2}], "total": 2}
        )
    )
    svc = LayeredDesignService(http_client=http)
    result = await svc.decompose_layers(image_bytes=b"img", layers=3, seed=42, prompt="cat")
    assert result["success"] is True
    assert result["total"] == 2
    # Authorization header was set from the API key.
    _, kwargs = http.post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    assert kwargs["data"]["prompt"] == "cat"


async def test_decompose_success_total_from_len(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "http://svc/decompose", raising=False)
    monkeypatch.setattr(mod, "QWEN_LAYERED_API_KEY", "", raising=False)
    http = MagicMock()
    http.post = AsyncMock(
        return_value=_mk_response(200, {"success": True, "layers": [{"i": 1}]})
    )
    svc = LayeredDesignService(http_client=http)
    result = await svc.decompose_layers(image_bytes=b"img")
    assert result["success"] is True
    # no Authorization header when api key empty
    _, kwargs = http.post.call_args
    assert "Authorization" not in kwargs["headers"]


async def test_decompose_service_reports_failure(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "http://svc/decompose", raising=False)
    http = MagicMock()
    http.post = AsyncMock(
        return_value=_mk_response(200, {"success": False, "error": "boom"})
    )
    svc = LayeredDesignService(http_client=http)
    result = await svc.decompose_layers(image_bytes=b"img")
    assert result["success"] is False
    assert result["error"] == "boom"


async def test_decompose_401(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "http://svc/decompose", raising=False)
    http = MagicMock()
    http.post = AsyncMock(return_value=_mk_response(401))
    svc = LayeredDesignService(http_client=http)
    result = await svc.decompose_layers(image_bytes=b"img")
    assert result["code"] == "AUTH_FAILED"


async def test_decompose_403(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "http://svc/decompose", raising=False)
    http = MagicMock()
    http.post = AsyncMock(return_value=_mk_response(403))
    svc = LayeredDesignService(http_client=http)
    result = await svc.decompose_layers(image_bytes=b"img")
    assert result["code"] == "ACCESS_DENIED"


async def test_decompose_500(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "http://svc/decompose", raising=False)
    http = MagicMock()
    http.post = AsyncMock(return_value=_mk_response(500, text="server error detail"))
    svc = LayeredDesignService(http_client=http)
    result = await svc.decompose_layers(image_bytes=b"img")
    assert result["success"] is False
    assert "500" in result["error"]
    assert "server error detail" in result["error"]


async def test_decompose_timeout(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "http://svc/decompose", raising=False)
    http = MagicMock()
    http.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    svc = LayeredDesignService(http_client=http)
    result = await svc.decompose_layers(image_bytes=b"img")
    assert result["code"] == "TIMEOUT"


async def test_decompose_request_error(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "http://svc/decompose", raising=False)
    http = MagicMock()
    http.post = AsyncMock(side_effect=httpx.RequestError("conn refused"))
    svc = LayeredDesignService(http_client=http)
    result = await svc.decompose_layers(image_bytes=b"img")
    assert result["code"] == "CONNECTION_ERROR"
    assert "conn refused" in result["error"]


async def test_decompose_invalid_json(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "http://svc/decompose", raising=False)
    http = MagicMock()
    http.post = AsyncMock(return_value=_mk_response(200, json_body=None))
    svc = LayeredDesignService(http_client=http)
    result = await svc.decompose_layers(image_bytes=b"img")
    assert result["code"] == "INVALID_RESPONSE"


async def test_decompose_creates_and_closes_own_client(monkeypatch):
    monkeypatch.setattr(mod, "QWEN_LAYERED_ENDPOINT", "http://svc/decompose", raising=False)
    fake_client = MagicMock()
    fake_client.post = AsyncMock(
        return_value=_mk_response(200, {"success": True, "layers": [], "total": 0})
    )
    fake_client.aclose = AsyncMock()
    monkeypatch.setattr(mod.httpx, "AsyncClient", MagicMock(return_value=fake_client))

    # no http_client passed -> service builds and closes its own
    svc = LayeredDesignService()
    result = await svc.decompose_layers(image_bytes=b"img")
    assert result["success"] is True
    fake_client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# vectorize_mask
# ---------------------------------------------------------------------------
def test_vectorize_no_mask():
    svc = LayeredDesignService()
    result = svc.vectorize_mask(mask_bytes=b"")
    assert result["success"] is False
    assert "requires mask data" in result["error"]


def test_vectorize_square_bezier():
    svc = LayeredDesignService()
    result = svc.vectorize_mask(mask_bytes=_solid_square_mask())
    assert result["success"] is True
    assert result["contours_count"] >= 1
    assert result["svg"].startswith("<?xml")
    # svg_base64 decodes back to the svg
    assert base64.b64decode(result["svg_base64"]).decode("utf-8") == result["svg"]
    assert isinstance(result["paths"], list)


def test_vectorize_square_polyline():
    svc = LayeredDesignService()
    result = svc.vectorize_mask(
        mask_bytes=_solid_square_mask(), use_bezier=False, smooth_iterations=0
    )
    assert result["success"] is True


def test_vectorize_with_blur():
    svc = LayeredDesignService()
    result = svc.vectorize_mask(mask_bytes=_solid_square_mask(), blur_radius=1.5)
    assert result["success"] is True


def test_vectorize_rgba_mask_uses_alpha():
    arr = np.zeros((20, 20, 4), dtype=np.uint8)
    arr[5:15, 5:15, 3] = 255  # opaque square in alpha channel
    mask = _png_bytes(Image.fromarray(arr, mode="RGBA"))
    svc = LayeredDesignService()
    result = svc.vectorize_mask(mask_bytes=mask)
    assert result["success"] is True
    assert result["width"] == 20
    assert result["height"] == 20


def test_vectorize_la_mask():
    arr = np.zeros((16, 16, 2), dtype=np.uint8)
    arr[4:12, 4:12, 1] = 255
    mask = _png_bytes(Image.fromarray(arr, mode="LA"))
    svc = LayeredDesignService()
    result = svc.vectorize_mask(mask_bytes=mask)
    assert result["success"] is True


def test_vectorize_rgb_mask_converted():
    img = Image.new("RGB", (16, 16), (0, 0, 0))
    arr = np.array(img)
    arr[4:12, 4:12] = (255, 255, 255)
    mask = _png_bytes(Image.fromarray(arr, mode="RGB"))
    svc = LayeredDesignService()
    result = svc.vectorize_mask(mask_bytes=mask)
    assert result["success"] is True


def test_vectorize_empty_mask_no_contours():
    mask = _png_bytes(Image.new("L", (10, 10), 0))
    svc = LayeredDesignService()
    result = svc.vectorize_mask(mask_bytes=mask)
    assert result["success"] is True
    assert result["contours_count"] == 0


def test_vectorize_invalid_bytes_returns_error():
    svc = LayeredDesignService()
    result = svc.vectorize_mask(mask_bytes=b"not-a-png-file")
    assert result["success"] is False
    assert "Vectorization failed" in result["error"]


# ---------------------------------------------------------------------------
# render_layerdoc
# ---------------------------------------------------------------------------
async def test_render_empty_doc():
    svc = LayeredDesignService()
    result = await svc.render_layerdoc({"width": 20, "height": 20, "layers": []})
    assert result["success"] is True
    assert result["width"] == 20
    assert result["height"] == 20
    decoded = base64.b64decode(result["image_base64"])
    img = Image.open(io.BytesIO(decoded))
    assert img.size == (20, 20)


async def test_render_with_background():
    svc = LayeredDesignService()
    doc = {"width": 8, "height": 8, "background": "#FF0000FF", "layers": []}
    result = await svc.render_layerdoc(doc)
    img = Image.open(io.BytesIO(base64.b64decode(result["image_base64"])))
    assert np.array(img.convert("RGBA"))[0, 0, 0] == 255


async def test_render_gradient_layer():
    svc = LayeredDesignService()
    doc = {
        "width": 16,
        "height": 16,
        "layers": [
            {
                "type": "gradient",
                "z": 0,
                "angle": 0,
                "opacity": 1.0,
                "stops": [[0.0, "#000000FF"], [1.0, "#FFFFFFFF"]],
            }
        ],
    }
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_gradient_dict_stops_and_opacity():
    svc = LayeredDesignService()
    doc = {
        "width": 16,
        "height": 16,
        "layers": [
            {
                "type": "gradient",
                "z": 0,
                "angle": 90,
                "opacity": 0.5,
                "stops": [
                    {"position": 0.0, "color": "#000000FF"},
                    {"position": 1.0, "color": "#FFFFFFFF"},
                ],
            }
        ],
    }
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_gradient_single_stop_solid_fill():
    svc = LayeredDesignService()
    doc = {
        "width": 12,
        "height": 12,
        "layers": [{"type": "gradient", "z": 0, "stops": [[0.0, "#00FF00FF"]]}],
    }
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_gradient_empty_stops_skipped():
    svc = LayeredDesignService()
    doc = {"width": 12, "height": 12, "layers": [{"type": "gradient", "z": 0, "stops": []}]}
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_shape_layers_all_types():
    svc = LayeredDesignService()
    doc = {
        "width": 40,
        "height": 40,
        "layers": [
            {
                "type": "shape",
                "z": 1,
                "shape": "rect",
                "bbox": [0, 0, 10, 10],
                "style": {"fill": "#FF0000FF"},
                "opacity": 1.0,
            },
            {
                "type": "shape",
                "z": 2,
                "shape": "round_rect",
                "bbox": [10, 10, 10, 10],
                "style": {"fill": "#00FF00FF", "radius": 4},
                "opacity": 0.5,
            },
            {
                "type": "shape",
                "z": 3,
                "shape": "ellipse",
                "bbox": [20, 20, 10, 10],
                "style": {"fill": "#0000FFFF"},
            },
        ],
    }
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_shape_no_fill():
    svc = LayeredDesignService()
    doc = {
        "width": 20,
        "height": 20,
        "layers": [{"type": "shape", "z": 1, "bbox": [0, 0, 10, 10], "style": {}}],
    }
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_text_layer_with_box():
    svc = LayeredDesignService()
    doc = {
        "width": 200,
        "height": 80,
        "layers": [
            {
                "type": "text",
                "z": 5,
                "text": "Hello",
                "bbox": [0, 0, 180, 60],
                "style": {"font_size": 20, "font_color": "#111827FF"},
                "box_fill": "#FFFFFFFF",
                "box_radius": 8,
                "box_padding": 6,
                "opacity": 0.9,
            }
        ],
    }
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_text_layer_no_box():
    svc = LayeredDesignService()
    doc = {
        "width": 120,
        "height": 50,
        "layers": [
            {
                "type": "text",
                "z": 5,
                "text": "NoBox",
                "bbox": [0, 0, 100, 40],
                "style": {"font_size": 16},
            }
        ],
    }
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_raster_layer():
    raster = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    raster_b64 = base64.b64encode(_png_bytes(raster)).decode()
    svc = LayeredDesignService()
    doc = {
        "width": 30,
        "height": 30,
        "layers": [
            {
                "type": "raster",
                "z": 1,
                "png_base64": raster_b64,
                "transform": {"x": 5, "y": 5},
                "opacity": 0.8,
            }
        ],
    }
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_raster_bad_base64_swallowed():
    svc = LayeredDesignService()
    doc = {
        "width": 20,
        "height": 20,
        "layers": [{"type": "raster", "z": 1, "png_base64": "!!!bad!!!"}],
    }
    # bad raster is logged + skipped, render still succeeds
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_raster_no_png_noop():
    svc = LayeredDesignService()
    doc = {"width": 20, "height": 20, "layers": [{"type": "raster", "z": 1}]}
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_unknown_layer_type_ignored():
    svc = LayeredDesignService()
    doc = {"width": 10, "height": 10, "layers": [{"type": "mystery", "z": 0}]}
    result = await svc.render_layerdoc(doc)
    assert result["success"] is True


async def test_render_layers_sorted_by_z():
    svc = LayeredDesignService()
    # green (z=2) drawn over red (z=1) covering whole canvas -> top-left is green
    doc = {
        "width": 10,
        "height": 10,
        "layers": [
            {
                "type": "shape",
                "z": 2,
                "shape": "rect",
                "bbox": [0, 0, 10, 10],
                "style": {"fill": "#00FF00FF"},
            },
            {
                "type": "shape",
                "z": 1,
                "shape": "rect",
                "bbox": [0, 0, 10, 10],
                "style": {"fill": "#FF0000FF"},
            },
        ],
    }
    result = await svc.render_layerdoc(doc)
    img = Image.open(io.BytesIO(base64.b64decode(result["image_base64"]))).convert("RGBA")
    px = np.array(img)[0, 0]
    assert px[1] == 255 and px[0] == 0  # green on top


async def test_render_failure_returns_error(monkeypatch):
    svc = LayeredDesignService()

    def boom(doc):
        raise RuntimeError("render kaboom")

    monkeypatch.setattr(svc, "_render_layerdoc_impl", boom)
    result = await svc.render_layerdoc({"width": 10, "height": 10})
    assert result["success"] is False
    assert "render kaboom" in result["error"]


async def test_render_default_dims_when_missing():
    svc = LayeredDesignService()
    # no width/height keys -> falls back to DEFAULT_CANVAS_* but width reported as 0
    result = await svc.render_layerdoc({"layers": []})
    assert result["success"] is True
    assert result["width"] == 0
