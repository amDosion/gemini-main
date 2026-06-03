"""Regression tests for OpenAI image EDIT fan-out partial success (V-S24 sibling).

Findings addressed (mirrors the image_generator.py fix):
- ``ImageEditor.edit_image`` raised a ``RuntimeError`` with stale/misleading text
  ("OpenAI Images Edit returned fewer images than requested ... The native Image
  API n request did not satisfy the contract.") whenever any fan-out leg failed,
  discarding every already-completed (and billed) edit leg.
- Partial-success semantics require completed edit legs to survive one failed
  leg: the available images must be surfaced with a warning instead of discarded.
- A total failure (zero usable images) must still hard-fail, but with accurate
  wording that does NOT contain the misleading "native Image API n request".
"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any, Set

import pytest

from app.services.openai.image_editor import ImageEditor


# A 1x1 transparent PNG so _load_image_bytes accepts the reference source.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
_REFERENCE_DATA_URL = "data:image/png;base64," + base64.b64encode(_PNG_1X1).decode("ascii")


def _fake_data_item(idx: int) -> Any:
    return SimpleNamespace(url=f"https://edited/{idx}.png", b64_json=None, revised_prompt=None)


class _FakeEditImages:
    """Stand-in for client.images.

    Each ``edit`` leg either raises (``fail_on``) or succeeds. A successful leg
    returns one image item unless ``empty_data`` is set, in which case it returns
    an empty ``data`` list (a leg that succeeds but yields no usable payload).
    """

    def __init__(self, fail_on: Set[int], *, empty_data: bool = False) -> None:
        self._fail_on = fail_on
        self._empty_data = empty_data
        self._idx = 0

    async def edit(self, **kwargs):
        idx = self._idx
        self._idx += 1
        if idx in self._fail_on:
            raise RuntimeError("upstream 502 on this edit leg")
        if self._empty_data:
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=[_fake_data_item(idx)])


class _FakeImageClient:
    def __init__(self, fail_on: Set[int], *, empty_data: bool = False) -> None:
        self.images = _FakeEditImages(fail_on, empty_data=empty_data)


def _make_editor(monkeypatch, fail_on: Set[int], *, empty_data: bool = False) -> ImageEditor:
    editor = ImageEditor(api_key="sk-test")
    fake_client = _FakeImageClient(fail_on, empty_data=empty_data)
    # Bypass build_async_client/with_openai_image_client_options wrapper.
    monkeypatch.setattr(editor, "_image_request_client", lambda: fake_client)
    return editor


@pytest.mark.asyncio
async def test_edit_image_returns_partial_results_on_one_failed_leg(monkeypatch):
    editor = _make_editor(monkeypatch, fail_on={1})

    results = await editor.edit_image(
        prompt="brighten the background",
        model="gpt-image-2",
        n=3,
        reference_images={"raw": _REFERENCE_DATA_URL},
    )

    # 2 of 3 edit legs succeeded; partial billed results must be surfaced, not discarded.
    assert len(results) == 2
    assert all(r.get("url") for r in results)


@pytest.mark.asyncio
async def test_edit_image_zero_usable_payload_raises_accurate_wording(monkeypatch):
    # All legs SUCCEED but return no image data -> total 0 usable images.
    # This is the hard-fail path; wording must be accurate, not the stale
    # "native Image API n request" / "fewer images than requested" text.
    editor = _make_editor(monkeypatch, fail_on=set(), empty_data=True)

    with pytest.raises(RuntimeError) as exc_info:
        await editor.edit_image(
            prompt="x",
            model="gpt-image-2",
            n=3,
            reference_images={"raw": _REFERENCE_DATA_URL},
        )

    message = str(exc_info.value)
    # The misleading wording must be gone.
    assert "native Image API n request" not in message
    assert "fewer images than requested" not in message
    # The hard-fail must describe the real condition: no usable image payload.
    assert "usable image" in message.lower()


@pytest.mark.asyncio
async def test_edit_image_all_legs_fail_propagates_upstream_without_stale_wording(monkeypatch):
    # When every fan-out leg fails, the original upstream error propagates
    # (per call_image_api_with_fanout's diagnosable-failure contract). It must
    # never be masked by the misleading "native Image API n request" wording.
    editor = _make_editor(monkeypatch, fail_on={0, 1, 2})

    with pytest.raises(RuntimeError) as exc_info:
        await editor.edit_image(
            prompt="x",
            model="gpt-image-2",
            n=3,
            reference_images={"raw": _REFERENCE_DATA_URL},
        )

    message = str(exc_info.value)
    assert "native Image API n request" not in message
    assert "upstream 502" in message


@pytest.mark.asyncio
async def test_edit_image_full_success_returns_all_results(monkeypatch):
    editor = _make_editor(monkeypatch, fail_on=set())

    results = await editor.edit_image(
        prompt="make it warmer",
        model="gpt-image-2",
        n=2,
        reference_images={"raw": _REFERENCE_DATA_URL},
    )

    assert len(results) == 2
