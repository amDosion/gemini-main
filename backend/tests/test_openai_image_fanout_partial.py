"""Regression tests for OpenAI image fan-out partial success + env config (V-S24).

Findings addressed:
- The fan-out helper used ``asyncio.gather`` WITHOUT ``return_exceptions``,
  so a single failed leg discarded every already-completed (and billed) leg.
  Partial-success semantics require completed legs to survive one failed leg.
- ``IMAGE_FANOUT_MAX_CONCURRENCY`` was a hard-coded module constant (4) that
  could not be tuned per deployment. It must be env-overridable with default 4.
- ``ImageGenerator.generate_image`` raised a ``RuntimeError`` with stale text
  ("native Image API n request did not satisfy the contract") even though the
  request was fanned out into n=1 legs. Partial results must be surfaced with
  a warning rather than discarded, and any error text must be accurate.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import app.services.openai._shared as shared
from app.services.openai._shared import call_image_api_with_fanout
from app.services.openai.image_generator import ImageGenerator


def _fake_data_item(idx: int) -> Any:
    return SimpleNamespace(url=f"https://img/{idx}.png", b64_json=None, revised_prompt=None)


# ---------------------------------------------------------------------------
# Concurrency env override
# ---------------------------------------------------------------------------

def test_concurrency_reads_env_override(monkeypatch):
    # RED: helper does not exist yet.
    monkeypatch.setenv("OPENAI_IMAGE_FANOUT_MAX_CONCURRENCY", "9")
    assert shared.resolve_image_fanout_max_concurrency() == 9


def test_concurrency_defaults_to_four_without_env(monkeypatch):
    monkeypatch.delenv("OPENAI_IMAGE_FANOUT_MAX_CONCURRENCY", raising=False)
    assert shared.resolve_image_fanout_max_concurrency() == 4


def test_concurrency_ignores_invalid_env(monkeypatch):
    monkeypatch.setenv("OPENAI_IMAGE_FANOUT_MAX_CONCURRENCY", "not-a-number")
    assert shared.resolve_image_fanout_max_concurrency() == 4

    monkeypatch.setenv("OPENAI_IMAGE_FANOUT_MAX_CONCURRENCY", "0")
    assert shared.resolve_image_fanout_max_concurrency() == 4


# ---------------------------------------------------------------------------
# Partial-success: one failed leg must not discard completed (billed) legs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fanout_preserves_completed_legs_when_one_leg_fails():
    call_index = {"n": 0}

    async def _request(_n: int) -> Any:
        idx = call_index["n"]
        call_index["n"] += 1
        if idx == 2:
            raise RuntimeError("leg 2 upstream 502")
        return SimpleNamespace(data=[_fake_data_item(idx)])

    response = await call_image_api_with_fanout(_request, 4)

    # 3 of 4 legs succeeded -> their billed images must survive the 1 failure.
    assert len(getattr(response, "data", [])) == 3


@pytest.mark.asyncio
async def test_fanout_raises_only_when_all_legs_fail():
    async def _request(_n: int) -> Any:
        raise RuntimeError("everything down")

    with pytest.raises(RuntimeError, match="everything down"):
        await call_image_api_with_fanout(_request, 3)


@pytest.mark.asyncio
async def test_fanout_single_leg_unchanged():
    async def _request(n: int) -> Any:
        assert n == 1
        return SimpleNamespace(data=[_fake_data_item(0)])

    response = await call_image_api_with_fanout(_request, 1)
    assert len(getattr(response, "data", [])) == 1


# ---------------------------------------------------------------------------
# ImageGenerator surfaces partial results with a warning, accurate error text
# ---------------------------------------------------------------------------

class _FakeImages:
    def __init__(self, fail_on: set) -> None:
        self._fail_on = fail_on
        self._idx = 0

    async def generate(self, **kwargs):
        idx = self._idx
        self._idx += 1
        if idx in self._fail_on:
            raise RuntimeError("upstream 502 on this leg")
        return SimpleNamespace(data=[_fake_data_item(idx)])


class _FakeImageClient:
    def __init__(self, fail_on: set) -> None:
        self.images = _FakeImages(fail_on)


def _make_generator(monkeypatch, fail_on: set) -> ImageGenerator:
    gen = ImageGenerator(api_key="sk-test")
    fake_client = _FakeImageClient(fail_on)
    # Bypass build_async_client/with_openai_image_client_options wrapper.
    monkeypatch.setattr(gen, "_image_request_client", lambda: fake_client)
    return gen


@pytest.mark.asyncio
async def test_generate_image_returns_partial_results_on_one_failed_leg(monkeypatch):
    gen = _make_generator(monkeypatch, fail_on={1})

    results = await gen.generate_image(
        prompt="a calm studio portrait",
        model="gpt-image-2",
        n=3,
    )

    # 2 of 3 legs succeeded; partial billed results must be surfaced, not discarded.
    assert len(results) == 2


@pytest.mark.asyncio
async def test_generate_image_error_text_is_not_stale_native_n(monkeypatch):
    gen = _make_generator(monkeypatch, fail_on={0, 1, 2})

    with pytest.raises(RuntimeError) as exc_info:
        await gen.generate_image(prompt="x", model="gpt-image-2", n=3)

    message = str(exc_info.value)
    # The misleading "native Image API n request" wording must be gone.
    assert "native Image API n request" not in message
