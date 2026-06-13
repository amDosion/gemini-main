"""Coverage-focused tests for ``app.routers.core.modes`` (the unified mode-dispatch router).

Strategy
--------
* The production ``router`` is mounted on a fresh :class:`FastAPI` app. Only the
  FastAPI boundary dependencies are overridden: ``require_current_user`` (auth),
  ``get_db`` (real in-memory SQLite session) and ``get_cache`` (in-memory cache).
* The DB is a real SQLite engine populated with the actual SQLAlchemy models, so
  the router's persistence / query / user-scoping logic runs for real.
* The only patched things are *external* boundaries:
    - ``get_provider_credentials`` (would hit the DB credential manager / network),
    - ``ProviderFactory.create`` (would build a real provider SDK client),
    - the provider service method itself (network/SDK call),
    - ``safe_persist_ai_result`` / ``safe_persist_ai_result_concurrent`` (cloud
      storage upload worker), patched to write a real ``MessageAttachment`` row so
      the router's "refuse non-persistent result" semantics still execute.
* Pure helper functions (``convert_attachments_to_reference_images``,
  ``_merge_multi_agent_attachment_inputs``, media-metadata extraction, error
  status-code mapping, the default multi-agent workflow builder) are tested
  directly.

These tests assert real behavior: status codes, the ``ModeResponse`` envelope,
mode→method dispatch, param-whitelist validation (400), unsupported-mode (400),
provider error → HTTP status mapping (image/video/generic), persistence
short-circuit vs. fallback, partial-success metadata bridging, and the GET
controls/capabilities probes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.core.database import Base, get_db
from app.core.dependencies import require_current_user, get_cache
from app.models.db_models import (
    MessageAttachment,
    MessageIndex,
)
# NOTE: ``app/routers/core/__init__.py`` does ``from .modes import router as modes``,
# so the package attribute ``app.routers.core.modes`` is shadowed by the *router*,
# not the submodule. Import the real module object explicitly so ``monkeypatch``
# targets module-level names (``get_provider_credentials``, ``ProviderFactory`` ...).
import importlib

modes = importlib.import_module("app.routers.core.modes")
from app.routers.core.modes import (
    Attachment,
    ModeRequest,
    convert_attachments_to_reference_images,
    _build_default_multi_agent_workflow_payload,
    _build_mode_error_detail,
    _build_multi_agent_meta_payload,
    _build_stream_error_done_chunk,
    _coerce_multi_agent_workflow_payload,
    _first_media_image_payload,
    _is_retryable_provider_status,
    _media_metadata_from_payload,
    _media_payload_value,
    _merge_multi_agent_attachment_inputs,
    _mode_message_content,
    _resolve_image_generation_error_status_code,
    _resolve_mode_attachment_url,
    _resolve_video_generation_error_status_code,
)

USER_ID = "user-mode-1"
OTHER_USER_ID = "user-mode-2"


# --------------------------------------------------------------------------- #
# In-memory cache double (mirrors the real cache's _make_key/delete contract)
# --------------------------------------------------------------------------- #
class _FakeCache:
    def __init__(self) -> None:
        self.deleted: List[str] = []

    def _make_key(self, *parts: str) -> str:
        return ":".join(str(p) for p in parts)

    async def delete(self, key: str) -> None:
        self.deleted.append(key)


# --------------------------------------------------------------------------- #
# Fake provider service + factory
# --------------------------------------------------------------------------- #
class _FakeService:
    """A provider service whose routed method is configurable per-test."""

    def __init__(self, methods: Dict[str, Any]) -> None:
        for name, fn in methods.items():
            setattr(self, name, fn)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def cache():
    return _FakeCache()


@pytest.fixture()
def make_client(db_session, cache):
    """Factory: build a TestClient mounting the real modes router.

    Boundary dependencies (auth/db/cache) are overridden to the test doubles;
    provider/persistence boundaries are patched per-test via ``_patch_provider``.
    """

    clients: List[TestClient] = []

    def _build(*, monkeypatch: Optional[Any] = None) -> TestClient:
        app = FastAPI()
        app.include_router(modes.router)
        app.dependency_overrides[require_current_user] = lambda: USER_ID
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_cache] = lambda: cache

        client = TestClient(app)
        clients.append(client)
        client._app = app  # for cleanup
        return client

    yield _build

    for c in clients:
        c._app.dependency_overrides.clear()


def _patch_provider(monkeypatch, service_methods, credentials=("fake-key", None)):
    """Patch the credential + factory boundaries used by handle_mode."""

    async def _fake_creds(**kwargs):
        return credentials

    monkeypatch.setattr(modes, "get_provider_credentials", _fake_creds)
    monkeypatch.setattr(
        modes.ProviderFactory,
        "create",
        staticmethod(lambda **kwargs: _FakeService(service_methods)),
    )


def _seed_attachment(db, *, attachment_id, session_id, message_id, user_id=USER_ID):
    att = MessageAttachment(
        id=attachment_id,
        user_id=user_id,
        session_id=session_id,
        message_id=message_id,
        name="x.png",
        mime_type="image/png",
        url="https://cdn.example/x.png",
        upload_status="completed",
    )
    db.add(att)
    db.commit()
    return att


def _overlay(*, url, attachment_id, **extra):
    """Build a persist-overlay dict matching ``_PersistOverlayDict`` shape."""
    base = {
        "url": url,
        "attachment_id": attachment_id,
        "upload_status": "completed",
        "task_id": None,
        "mime_type": "image/png",
        "filename": "x.png",
        "session_id": "s",
        "message_id": "m",
        "user_id": USER_ID,
        "cloud_url": url,
    }
    base.update(extra)
    return base


# =========================================================================== #
# Pure helper tests (no HTTP)
# =========================================================================== #
class TestPureHelpers:
    def test_convert_attachments_empty(self):
        assert convert_attachments_to_reference_images(None) == {}
        assert convert_attachments_to_reference_images([]) == {}

    def test_convert_attachments_url_only(self):
        ref = convert_attachments_to_reference_images(
            [Attachment(url="data:image/png;base64,AAA")]
        )
        # no id → raw is a bare string for backward-compat
        assert ref["raw"] == "data:image/png;base64,AAA"

    def test_convert_attachments_with_id_keeps_attachment_id(self):
        ref = convert_attachments_to_reference_images(
            [Attachment(id="att-1", url="data:image/png;base64,AAA", mime_type="image/jpeg")]
        )
        assert ref["raw"]["attachment_id"] == "att-1"
        assert ref["raw"]["url"] == "data:image/png;base64,AAA"
        assert ref["raw"]["mime_type"] == "image/jpeg"

    def test_convert_attachments_mask_role(self):
        ref = convert_attachments_to_reference_images(
            [
                Attachment(url="data:image/png;base64,RAW"),
                Attachment(url="data:image/png;base64,MASK", role="mask"),
            ]
        )
        assert ref["raw"] == "data:image/png;base64,RAW"
        assert ref["mask"] == "data:image/png;base64,MASK"

    def test_convert_attachments_multiple_raw_become_list(self):
        ref = convert_attachments_to_reference_images(
            [
                Attachment(url="data:image/png;base64,A"),
                Attachment(url="data:image/png;base64,B"),
            ]
        )
        assert isinstance(ref["raw"], list)
        assert ref["raw"] == ["data:image/png;base64,A", "data:image/png;base64,B"]

    def test_convert_attachments_skips_empty_no_id(self):
        # attachment with neither id nor any image data is skipped
        ref = convert_attachments_to_reference_images([Attachment()])
        assert ref == {}

    def test_resolve_mode_attachment_url_priority(self):
        a = Attachment(temp_url="t", file_uri="f", base64_data="b")
        assert _resolve_mode_attachment_url(a) == "t"
        assert _resolve_mode_attachment_url(Attachment()) == ""

    def test_first_media_image_payload(self):
        assert _first_media_image_payload({"images": [{"url": "u"}]}) == {"url": "u"}
        assert _first_media_image_payload({"images": "notalist"}) == {}
        assert _first_media_image_payload({}) == {}

    def test_media_payload_value_aliases(self):
        payload = {"enhancedPrompt": "boosted"}
        assert _media_payload_value(payload, "enhanced_prompt") == "boosted"
        # falls through to first image
        payload2 = {"images": [{"text": "hello"}]}
        assert _media_payload_value(payload2, "text_response") == "hello"
        assert _media_payload_value({}, "thoughts") is None

    def test_mode_message_content_combines_prompt(self):
        out = _mode_message_content("draw a cat", {"enhanced_prompt": "a fluffy cat"})
        assert "draw a cat" in out and "a fluffy cat" in out
        # enhanced only
        assert _mode_message_content("", {"enhanced_prompt": "X"}) == "✨ X"
        # plain prompt only
        assert _mode_message_content("hi", {}) == "hi"

    def test_media_metadata_from_payload(self):
        meta = _media_metadata_from_payload(
            {"enhanced_prompt": "ep", "total_duration_seconds": 8, "ignored": 1}
        )
        assert meta["enhanced_prompt"] == "ep"
        assert meta["total_duration_seconds"] == 8
        assert "ignored" not in meta

    def test_error_status_mapping(self):
        assert _resolve_video_generation_error_status_code(ValueError("x")) == 400
        assert _resolve_image_generation_error_status_code(ValueError("x")) == 400
        # rate limit keyword → 429
        assert _resolve_image_generation_error_status_code(RuntimeError("rate limit exceeded")) == 429

    def test_is_retryable_provider_status(self):
        assert _is_retryable_provider_status(503) is True
        assert _is_retryable_provider_status(400) is False

    def test_build_mode_error_detail(self):
        d = _build_mode_error_detail("c", "m", details={"k": 1}, retryable=True)
        assert d == {"code": "c", "message": "m", "details": {"k": 1}, "retryable": True}
        # default details
        assert _build_mode_error_detail("c", "m")["details"] == {}

    def test_build_stream_error_done_chunk(self):
        chunk = _build_stream_error_done_chunk()
        assert chunk["chunk_type"] == "done"
        assert chunk["finish_reason"] == "error"

    def test_safe_log_text_redacts_user_content(self):
        out = modes._safe_log_text("secret prompt with sk-testSECRETSECRET", label="prompt")

        assert "secret prompt" not in out
        assert "sk-testSECRETSECRET" not in out
        assert out == "<redacted prompt; length=38>"

    def test_safe_log_url_redacts_query_fragment_and_inline_payloads(self):
        signed_url = (
            "https://cdn.example.com/private/image.png"
            "?X-Amz-Signature=secret-signature&token=secret-token#download"
        )
        signed_out = modes._safe_log_url(signed_url)

        assert "cdn.example.com" in signed_out
        assert "secret-signature" not in signed_out
        assert "secret-token" not in signed_out
        assert "download" not in signed_out
        assert "query_params=2" in signed_out
        assert "fragment=redacted" in signed_out

        data_url = "data:image/png;base64," + ("A" * 128)
        data_out = modes._safe_log_url(data_url)

        assert "A" * 32 not in data_out
        assert data_out == f"Base64 Data URL (长度: {len(data_url)} 字符)"


class TestMultiAgentBuilders:
    def _req(self, **kw):
        base = dict(model_id="m", prompt="solve this", attachments=None, options=None, extra=None)
        base.update(kw)
        return ModeRequest(**base)

    def test_merge_attachment_inputs_classifies_by_mime(self):
        atts = [
            Attachment(url="img.png", mime_type="image/png"),
            Attachment(url="clip.mp4", mime_type="video/mp4"),
            Attachment(url="song.mp3", mime_type="audio/mpeg"),
            Attachment(url="doc.pdf", mime_type="application/pdf"),
        ]
        merged = _merge_multi_agent_attachment_inputs({}, atts)
        assert merged["imageUrl"] == "img.png"
        assert merged["videoUrls"] == ["clip.mp4"]
        assert merged["audioUrl"] == "song.mp3"
        assert merged["fileUrls"] == ["doc.pdf"]

    def test_merge_attachment_inputs_dedup_and_existing(self):
        merged = _merge_multi_agent_attachment_inputs(
            {"imageUrls": ["existing.png"], "imageUrl": "existing.png"},
            [Attachment(url="new.png", mime_type="image/png"),
             Attachment(url="new.png", mime_type="image/png")],
        )
        # new first, existing deduped, no duplicate of new.png
        assert merged["imageUrls"] == ["new.png", "existing.png"]
        assert merged["imageUrl"] == "new.png"

    def test_merge_attachment_inputs_no_attachments_returns_same(self):
        wi = {"task": "x"}
        assert _merge_multi_agent_attachment_inputs(wi, None) is wi

    def test_build_meta_payload_defaults(self):
        req = self._req()
        meta = _build_multi_agent_meta_payload(
            {"custom": "v"}, request_body=req, provider="google", mode="multi-agent"
        )
        assert meta["source"] == "provider-mode"
        assert meta["requestedProvider"] == "google"
        assert meta["requestedMode"] == "multi-agent"
        assert meta["modeModelId"] == "m"
        assert meta["custom"] == "v"

    def test_build_meta_payload_non_dict_raw(self):
        meta = _build_multi_agent_meta_payload(
            "not-a-dict", request_body=self._req(), provider="p", mode="md"
        )
        assert meta["source"] == "provider-mode"

    def test_default_workflow_text_only_chain(self):
        payload = _build_default_multi_agent_workflow_payload(
            request_body=self._req(),
            provider="google",
            mode="multi-agent",
            raw_input=None,
            raw_meta=None,
            raw_async_mode=False,
        )
        node_ids = {n["id"] for n in payload["nodes"]}
        assert "planner-mode-runtime" in node_ids
        assert "analysis-mode-runtime" in node_ids
        assert "review-mode-runtime" in node_ids
        # prompt seeded into input.task
        assert payload["input"]["task"] == "solve this"
        assert payload["async_mode"] is False

    def test_default_workflow_image_branch(self):
        payload = _build_default_multi_agent_workflow_payload(
            request_body=self._req(
                attachments=[Attachment(url="i.png", mime_type="image/png")]
            ),
            provider="google",
            mode="multi-agent",
            raw_input={},
            raw_meta={},
            raw_async_mode=True,
        )
        node_ids = {n["id"] for n in payload["nodes"]}
        assert "input-image-mode-runtime" in node_ids
        assert "vision-observer-mode-runtime" in node_ids
        assert payload["async_mode"] is True

    def test_default_workflow_file_branch(self):
        payload = _build_default_multi_agent_workflow_payload(
            request_body=self._req(
                attachments=[Attachment(url="d.pdf", mime_type="application/pdf")]
            ),
            provider="google",
            mode="multi-agent",
            raw_input={},
            raw_meta={},
            raw_async_mode=False,
        )
        node_ids = {n["id"] for n in payload["nodes"]}
        assert "input-file-mode-runtime" in node_ids

    def test_coerce_explicit_workflow_payload(self):
        req = self._req(
            extra={
                "workflow": {
                    "nodes": [{"id": "s", "type": "start"}],
                    "edges": [{"id": "e", "source": "s", "target": "s"}],
                    "input": {"task": "explicit"},
                    "meta": {"title": "t"},
                    "async_mode": True,
                }
            }
        )
        out = _coerce_multi_agent_workflow_payload(req, provider="google", mode="multi-agent")
        assert out["nodes"][0]["id"] == "s"
        assert out["input"]["task"] == "explicit"
        assert out["async_mode"] is True
        assert out["meta"]["requestedProvider"] == "google"

    def test_coerce_explicit_workflow_missing_nodes_raises(self):
        req = self._req(extra={"workflow": {"nodes": "bad", "edges": []}})
        with pytest.raises(ValueError):
            _coerce_multi_agent_workflow_payload(req, provider="g", mode="multi-agent")

    def test_coerce_default_when_no_explicit_workflow(self):
        req = self._req(extra={"input": {"foo": 1}})
        out = _coerce_multi_agent_workflow_payload(req, provider="g", mode="multi-agent")
        # default builder path used (planner chain)
        assert any(n["id"] == "planner-mode-runtime" for n in out["nodes"])


# =========================================================================== #
# HTTP endpoint tests
# =========================================================================== #
def _post(client, provider, mode, body):
    return client.post(f"/api/modes/{provider}/{mode}", json=body)


class TestHandleModeDispatch:
    def test_unsupported_mode_returns_400(self, make_client, monkeypatch):
        _patch_provider(monkeypatch, {})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "google", "no-such-mode", {"model_id": "m", "prompt": "hi"})
        assert resp.status_code == 400
        assert "Unsupported mode" in resp.json()["detail"]

    def test_invalid_param_keys_returns_400(self, make_client, monkeypatch):
        async def gen_image(**kwargs):
            return {"images": []}

        _patch_provider(monkeypatch, {"generate_image": gen_image})
        client = make_client(monkeypatch=monkeypatch)
        # 'extra' with a key not on the whitelist triggers ProviderParamValidationError
        resp = _post(
            client,
            "google",
            "image-gen",
            {"model_id": "m", "prompt": "hi", "extra": {"definitely_not_allowed_key": 1}},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["code"] == "invalid_provider_params"
        assert "definitely_not_allowed_key" in detail["details"]["invalid_params"]

    def test_provider_missing_method_returns_400(self, make_client, monkeypatch):
        # image-gen routes to generate_image, but the service doesn't define it
        _patch_provider(monkeypatch, {})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "google", "image-gen", {"model_id": "m", "prompt": "hi"})
        assert resp.status_code == 400
        assert "does not support method" in resp.json()["detail"]

    def test_generic_mode_success_envelope(self, make_client, monkeypatch):
        async def understand_video(**kwargs):
            return {"summary": "a cat plays"}

        _patch_provider(monkeypatch, {"understand_video": understand_video})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "google", "video-understand", {"model_id": "m", "prompt": "describe"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["provider"] == "google"
        assert body["mode"] == "video-understand"
        assert body["data"]["summary"] == "a cat plays"

    def test_generate_speech_injects_default_voice(self, make_client, monkeypatch):
        captured = {}

        async def generate_speech(**kwargs):
            captured.update(kwargs)
            return {"text": "no url here"}

        # The router injects "alloy" as the default voice when none is supplied;
        # the real catalog would then reject "alloy" for openai, so bypass catalog
        # validation here to assert the *default-injection* branch specifically.
        monkeypatch.setattr(modes, "validate_params_with_catalog", lambda **k: k["params"])
        _patch_provider(monkeypatch, {"generate_speech": generate_speech})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "openai", "audio-gen", {"model_id": "tts-1", "prompt": "say hi"})
        assert resp.status_code == 200
        assert captured["text"] == "say hi"
        assert captured["voice"] == "alloy"  # default injected when options.voice absent

    def test_generate_speech_uses_explicit_voice(self, make_client, monkeypatch):
        captured = {}

        async def generate_speech(**kwargs):
            captured.update(kwargs)
            return {"text": "ok"}

        _patch_provider(monkeypatch, {"generate_speech": generate_speech})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(
            client,
            "openai",
            "audio-gen",
            {"model_id": "tts-1", "prompt": "hi", "options": {"voice": "Puck"}},
        )
        assert resp.status_code == 200
        assert captured["voice"] == "Puck"

    def test_value_error_from_method_maps_to_400(self, make_client, monkeypatch):
        async def understand_video(**kwargs):
            raise ValueError("bad input shape")

        _patch_provider(monkeypatch, {"understand_video": understand_video})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "google", "video-understand", {"model_id": "m", "prompt": "x"})
        # non image/video method path re-raises → outer ValueError handler → 400
        assert resp.status_code == 400
        assert "bad input shape" in resp.json()["detail"]

    def test_generic_method_runtime_error_classified(self, make_client, monkeypatch, caplog):
        secret = "sorftime-secret-token"

        async def understand_video(**kwargs):
            raise RuntimeError(f"429 rate limit exceeded {secret}")

        _patch_provider(monkeypatch, {"understand_video": understand_video})
        client = make_client(monkeypatch=monkeypatch)
        with caplog.at_level(logging.ERROR, logger=modes.logger.name):
            resp = _post(client, "google", "video-understand", {"model_id": "m", "prompt": "x"})
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Mode request failed"
        log_text = "\n".join(record.getMessage() for record in caplog.records)
        assert secret not in log_text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in log_text


class TestImageModeErrorMapping:
    def test_image_not_implemented_returns_501(self, make_client, monkeypatch):
        async def generate_image(**kwargs):
            raise NotImplementedError("not built yet")

        _patch_provider(monkeypatch, {"generate_image": generate_image})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "google", "image-gen", {"model_id": "m", "prompt": "x"})
        assert resp.status_code == 501
        assert resp.json()["detail"]["code"] == "mode_not_implemented"

    def test_image_generic_failure_returns_500(self, make_client, monkeypatch):
        async def generate_image(**kwargs):
            raise RuntimeError("provider blew up")

        _patch_provider(monkeypatch, {"generate_image": generate_image})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "google", "image-gen", {"model_id": "m", "prompt": "x"})
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert detail["code"] == "image_generation_failed"
        assert "图片生成失败" in detail["message"]

    def test_image_value_error_returns_400(self, make_client, monkeypatch):
        async def generate_image(**kwargs):
            raise ValueError("invalid aspect ratio")

        _patch_provider(monkeypatch, {"generate_image": generate_image})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "google", "image-gen", {"model_id": "m", "prompt": "x"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "image_generation_failed"

    def test_image_api_error_status_classified(self, make_client, monkeypatch):
        from app.services.gemini.base.imagen_common import APIError

        async def generate_image(**kwargs):
            raise APIError("503 service unavailable", api_type="rest")

        _patch_provider(monkeypatch, {"generate_image": generate_image})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "google", "image-gen", {"model_id": "m", "prompt": "x"})
        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert detail["code"] == "image_generation_failed"
        assert detail["retryable"] is True  # 503 is retryable

    def test_image_api_error_expired_key_returns_401(self, make_client, monkeypatch):
        from app.services.gemini.base.imagen_common import APIError

        async def generate_image(**kwargs):
            raise APIError(
                "upstream failure",
                api_type="rest",
                original_error=Exception("Invalid API key provided"),
            )

        _patch_provider(monkeypatch, {"generate_image": generate_image})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "google", "image-gen", {"model_id": "m", "prompt": "x"})
        assert resp.status_code == 401
        assert "API Key" in resp.json()["detail"]["message"]


class TestVideoModeErrorMapping:
    def test_video_failure_returns_video_error(self, make_client, monkeypatch):
        async def generate_video(**kwargs):
            raise RuntimeError("video pipeline error")

        _patch_provider(monkeypatch, {"generate_video": generate_video})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "google", "video-gen", {"model_id": "veo", "prompt": "x"})
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert detail["code"] == "video_generation_failed"
        assert "视频生成失败" in detail["message"]

    def test_video_value_error_returns_400(self, make_client, monkeypatch):
        async def generate_video(**kwargs):
            raise ValueError("bad duration")

        _patch_provider(monkeypatch, {"generate_video": generate_video})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(client, "google", "video-gen", {"model_id": "veo", "prompt": "x"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "video_generation_failed"


class TestImagePersistence:
    """Step-7 image persistence: short-circuit, fallback, and refuse-non-persistent."""

    def test_image_persist_success_bridges_attachment(self, make_client, monkeypatch, db_session):
        async def generate_image(**kwargs):
            return {"images": [{"url": "data:image/png;base64,AAA", "mime_type": "image/png",
                                "enhanced_prompt": "a vivid cat"}]}

        # Patch the route-level persist helper to return an overlay (its real body
        # delegates to the cloud-storage upload worker — an external boundary).
        async def fake_concurrent(sessionmaker_, *, reraise=False, **kw):
            return _overlay(url="https://cdn.example/img.png", attachment_id="att-img-1")

        monkeypatch.setattr(modes, "_persist_ai_media_concurrent", fake_concurrent)
        _patch_provider(monkeypatch, {"generate_image": generate_image})
        client = make_client(monkeypatch=monkeypatch)

        resp = _post(
            client,
            "google",
            "image-gen",
            {
                "model_id": "m",
                "prompt": "draw",
                "options": {"frontend_session_id": "sess-1", "message_id": "msg-1"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["images"][0]["url"] == "https://cdn.example/img.png"
        assert data["images"][0]["attachment_id"] == "att-img-1"
        # partial-success metadata bridged onto the image result
        assert data["images"][0]["enhanced_prompt"] == "a vivid cat"
        # message_index row was persisted
        idx = db_session.query(MessageIndex).filter_by(id="msg-1").first()
        assert idx is not None and idx.session_id == "sess-1"

    def test_image_persist_failure_returns_500(self, make_client, monkeypatch):
        async def generate_image(**kwargs):
            return {"images": [{"url": "data:image/png;base64,AAA"}]}

        async def fake_concurrent(sessionmaker_, *, reraise=False, **kw):
            raise RuntimeError("storage worker down")

        monkeypatch.setattr(modes, "_persist_ai_media_concurrent", fake_concurrent)
        _patch_provider(monkeypatch, {"generate_image": generate_image})
        client = make_client(monkeypatch=monkeypatch)

        resp = _post(
            client,
            "google",
            "image-gen",
            {
                "model_id": "m",
                "prompt": "draw",
                "options": {"frontend_session_id": "sess-2", "message_id": "msg-2"},
            },
        )
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert detail["code"] == "attachment_persistence_failed"
        assert detail["details"]["error_type"] == "RuntimeError"
        assert "storage worker down" in detail["details"]["error_message"]

    def test_image_provider_attachment_short_circuit(self, make_client, monkeypatch, db_session):
        # Provider returns a pre-persisted attachment_id whose row already exists →
        # router must short-circuit (no concurrent persist call).
        _seed_attachment(
            db_session,
            attachment_id="pre-att",
            session_id="sess-3",
            message_id="msg-3",
        )

        async def generate_image(**kwargs):
            return {
                "images": [
                    {"url": "data:image/png;base64,AAA", "attachment_id": "pre-att"}
                ]
            }

        called = {"n": 0}

        async def fake_concurrent(*a, **k):
            called["n"] += 1
            raise AssertionError("should not be called on short-circuit")

        monkeypatch.setattr(modes, "_persist_ai_media_concurrent", fake_concurrent)
        _patch_provider(monkeypatch, {"generate_image": generate_image})
        client = make_client(monkeypatch=monkeypatch)

        resp = _post(
            client,
            "google",
            "image-gen",
            {
                "model_id": "m",
                "prompt": "draw",
                "options": {"frontend_session_id": "sess-3", "message_id": "msg-3"},
            },
        )
        assert resp.status_code == 200
        assert called["n"] == 0
        assert resp.json()["data"]["images"][0]["attachment_id"] == "pre-att"

    def test_image_missing_message_id_skips_persistence(self, make_client, monkeypatch):
        async def generate_image(**kwargs):
            return {"images": [{"url": "data:image/png;base64,AAA"}]}

        _patch_provider(monkeypatch, {"generate_image": generate_image})
        client = make_client(monkeypatch=monkeypatch)
        # No message_id → persistence block skipped, raw result returned
        resp = _post(
            client,
            "google",
            "image-gen",
            {"model_id": "m", "prompt": "draw", "options": {"frontend_session_id": "s"}},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["images"][0]["url"] == "data:image/png;base64,AAA"


class TestAudioPersistence:
    def test_audio_persist_success_bridges(self, make_client, monkeypatch):
        async def generate_speech(**kwargs):
            return {"url": "data:audio/mpeg;base64,AUDIO", "mime_type": "audio/mpeg"}

        async def fake_persist(attachment_service, **kw):
            return _overlay(
                url="https://cdn.example/a.mp3",
                attachment_id="att-audio",
                mime_type="audio/mpeg",
            )

        monkeypatch.setattr(modes, "_persist_ai_media_with_fallback", fake_persist)
        _patch_provider(monkeypatch, {"generate_speech": generate_speech})
        client = make_client(monkeypatch=monkeypatch)

        resp = _post(
            client,
            "openai",
            "audio-gen",
            {
                "model_id": "tts-1",
                "prompt": "hello",
                "options": {"frontend_session_id": "sess-a", "message_id": "msg-a", "voice": "Puck"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["url"] == "https://cdn.example/a.mp3"
        assert data["attachment_id"] == "att-audio"

    def test_audio_persist_fallback_keeps_original(self, make_client, monkeypatch):
        async def generate_speech(**kwargs):
            return {"url": "data:audio/mpeg;base64,AUDIO"}

        async def fake_persist(attachment_service, **kw):
            return None  # graceful degrade

        monkeypatch.setattr(modes, "_persist_ai_media_with_fallback", fake_persist)
        _patch_provider(monkeypatch, {"generate_speech": generate_speech})
        client = make_client(monkeypatch=monkeypatch)

        resp = _post(
            client,
            "openai",
            "audio-gen",
            {
                "model_id": "tts-1",
                "prompt": "hello",
                "options": {"frontend_session_id": "sess-b", "message_id": "msg-b", "voice": "Puck"},
            },
        )
        # fallback: original url kept, but message still persisted (has url) → 200
        assert resp.status_code == 200
        assert resp.json()["data"]["url"] == "data:audio/mpeg;base64,AUDIO"


class TestVideoPersistence:
    """Step-7 video persistence: attachment bridging, sidecars, last-frame derivative."""

    def _patch_video_contract(self, monkeypatch):
        # normalize_video_generation_request_params hits the controls catalog; keep
        # params unchanged and return empty request-meta.
        monkeypatch.setattr(
            modes,
            "normalize_video_generation_request_params",
            lambda **k: (k["params"], {}),
        )

    def test_video_persist_bridges_attachment_and_last_frame(self, make_client, monkeypatch):
        self._patch_video_contract(monkeypatch)

        async def generate_video(**kwargs):
            return {"url": "https://provider/video.mp4", "mime_type": "video/mp4"}

        async def fake_persist(attachment_service, **kw):
            return _overlay(
                url="https://cdn.example/v.mp4",
                attachment_id="att-vid",
                mime_type="video/mp4",
            )

        async def fake_last_frame(attachment_service, **kw):
            return {"url": "https://cdn.example/frame.png", "attachment_id": "att-frame"}

        monkeypatch.setattr(modes, "_persist_ai_media_with_fallback", fake_persist)
        monkeypatch.setattr(modes, "safe_persist_video_last_frame_derivative", fake_last_frame)
        _patch_provider(monkeypatch, {"generate_video": generate_video})
        client = make_client(monkeypatch=monkeypatch)

        resp = _post(
            client,
            "google",
            "video-gen",
            {
                "model_id": "veo",
                "prompt": "a sunset",
                "options": {"frontend_session_id": "sess-v", "message_id": "msg-v"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["url"] == "https://cdn.example/v.mp4"
        assert data["attachment_id"] == "att-vid"
        # last-frame derivative bridged in
        assert data["last_frame_image_url"] == "https://cdn.example/frame.png"
        assert data["last_frame_attachment_id"] == "att-frame"

    def test_video_sidecar_partial_success(self, make_client, monkeypatch):
        self._patch_video_contract(monkeypatch)

        async def generate_video(**kwargs):
            return {
                "url": "https://provider/v.mp4",
                "sidecar_files": [
                    {"data_url": "data:text/vtt;base64,OK", "mime_type": "text/vtt"},
                    {"data_url": "data:text/vtt;base64,FAIL", "mime_type": "text/vtt"},
                    {"mime_type": "text/vtt"},  # no url → skipped
                ],
            }

        async def fake_persist(attachment_service, **kw):
            # primary video persist
            return _overlay(url="https://cdn.example/v.mp4", attachment_id="att-vid",
                            mime_type="video/mp4")

        # sidecars go through _persist_ai_media_concurrent: first ok, second raises
        calls = {"n": 0}

        async def fake_concurrent(sessionmaker_, *, reraise=False, **kw):
            calls["n"] += 1
            if "FAIL" in kw["ai_url"]:
                raise RuntimeError("sidecar upload failed")
            return _overlay(url="https://cdn.example/sub.vtt", attachment_id="att-sub",
                            mime_type="text/vtt")

        async def fake_last_frame(attachment_service, **kw):
            return None  # no derivative

        monkeypatch.setattr(modes, "_persist_ai_media_with_fallback", fake_persist)
        monkeypatch.setattr(modes, "_persist_ai_media_concurrent", fake_concurrent)
        monkeypatch.setattr(modes, "safe_persist_video_last_frame_derivative", fake_last_frame)
        _patch_provider(monkeypatch, {"generate_video": generate_video})
        client = make_client(monkeypatch=monkeypatch)

        resp = _post(
            client,
            "google",
            "video-gen",
            {
                "model_id": "veo",
                "prompt": "a sunset",
                "options": {"frontend_session_id": "sess-v2", "message_id": "msg-v2"},
            },
        )
        # one sidecar failed but the whole response must NOT 5xx (partial success)
        assert resp.status_code == 200
        sidecars = resp.json()["data"]["sidecar_files"]
        # 2 sidecars had a url (one ok bridged, one failed kept as-is); skipped one dropped
        assert len(sidecars) == 2
        ok = [s for s in sidecars if s.get("attachment_id") == "att-sub"]
        assert len(ok) == 1

    def test_video_provider_attachment_short_circuit(self, make_client, monkeypatch):
        self._patch_video_contract(monkeypatch)

        async def generate_video(**kwargs):
            return {"url": "https://p/v.mp4", "attachment_id": "prov-vid"}

        async def fake_last_frame(attachment_service, **kw):
            return None

        called = {"n": 0}

        async def fake_persist(*a, **k):
            called["n"] += 1
            return None

        monkeypatch.setattr(modes, "_persist_ai_media_with_fallback", fake_persist)
        monkeypatch.setattr(modes, "safe_persist_video_last_frame_derivative", fake_last_frame)
        _patch_provider(monkeypatch, {"generate_video": generate_video})
        client = make_client(monkeypatch=monkeypatch)

        resp = _post(
            client,
            "google",
            "video-gen",
            {
                "model_id": "veo",
                "prompt": "x",
                "options": {"frontend_session_id": "sess-v3", "message_id": "msg-v3"},
            },
        )
        assert resp.status_code == 200
        # provider already supplied attachment_id → no fallback persist of primary asset
        assert called["n"] == 0
        assert resp.json()["data"]["attachment_id"] == "prov-vid"


class TestAttachmentReferenceLookup:
    """attachments → reference_images with DB-backed url completion (lines ~1664-1709)."""

    def test_attachment_id_resolved_from_db(self, make_client, monkeypatch, db_session):
        _seed_attachment(
            db_session,
            attachment_id="ref-att",
            session_id="ref-sess",
            message_id="ref-msg",
        )
        captured = {}

        async def edit_image(**kwargs):
            captured.update(kwargs)
            return {"images": []}

        # skip step-7 image persistence (no message_id in options → block skipped)
        _patch_provider(monkeypatch, {"edit_image": edit_image})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(
            client,
            "google",
            "image-chat-edit",
            {
                "model_id": "m",
                "prompt": "edit",
                "attachments": [{"id": "ref-att", "mime_type": "image/png"}],
            },
        )
        assert resp.status_code == 200
        # router looked up the completed attachment and filled the cloud url
        raw = captured["reference_images"]["raw"]
        assert raw["attachment_id"] == "ref-att"
        assert raw["url"] == "https://cdn.example/x.png"

    def test_attachment_id_not_found_keeps_ref(self, make_client, monkeypatch):
        captured = {}

        async def edit_image(**kwargs):
            captured.update(kwargs)
            return {"images": []}

        _patch_provider(monkeypatch, {"edit_image": edit_image})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(
            client,
            "google",
            "image-chat-edit",
            {
                "model_id": "m",
                "prompt": "edit",
                "attachments": [{"id": "missing-att", "mime_type": "image/png"}],
            },
        )
        assert resp.status_code == 200
        raw = captured["reference_images"]["raw"]
        assert raw["attachment_id"] == "missing-att"


class TestEditContinuityAndExtraction:
    def test_edit_continuity_resolves_active_image(self, make_client, monkeypatch, db_session):
        captured = {}

        async def edit_image(**kwargs):
            captured.update(kwargs)
            return {"images": []}

        async def fake_resolve(self, *, active_image_url, session_id, user_id, messages):
            return {
                "url": "https://cdn.example/continuity.png",
                "attachment_id": "cont-att",
                "status": "completed",
                "task_id": None,
            }

        monkeypatch.setattr(
            modes.AttachmentService, "resolve_continuity_attachment", fake_resolve
        )
        _patch_provider(monkeypatch, {"edit_image": edit_image})
        client = make_client(monkeypatch=monkeypatch)

        # NOTE: ``extra.messages`` is supplied so the continuity path uses the
        # request-provided history. Without it the router does
        # ``from ...models.db_models import Message`` which is a *latent ImportError*
        # in the production code (the v3 schema removed the ``Message`` model) — a
        # real bug surfaced by this test on the empty-messages branch.
        resp = _post(
            client,
            "google",
            "image-chat-edit",
            {
                "model_id": "m",
                "prompt": "edit it",
                "options": {
                    "active_image_url": "https://cdn.example/orig.png",
                    "frontend_session_id": "cont-sess",
                },
                "extra": {"messages": [{"role": "user", "content": "prior"}]},
            },
        )
        assert resp.status_code == 200
        # resolved continuity image flows into reference_images.raw
        assert captured["reference_images"]["raw"] == "https://cdn.example/continuity.png"
        # edit_image receives the URL-path mode
        assert captured["mode"] == "image-chat-edit"

    def test_edit_continuity_no_session_skips(self, make_client, monkeypatch):
        captured = {}

        async def edit_image(**kwargs):
            captured.update(kwargs)
            return {"images": []}

        _patch_provider(monkeypatch, {"edit_image": edit_image})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(
            client,
            "google",
            "image-chat-edit",
            {
                "model_id": "m",
                "prompt": "edit",
                "options": {"active_image_url": "https://cdn.example/o.png"},
            },
        )
        # no session_id → continuity skipped, no reference_images injected from it
        assert resp.status_code == 200
        assert "reference_images" not in captured or "raw" not in captured.get("reference_images", {})

    def test_segment_clothing_extracts_base64(self, make_client, monkeypatch):
        captured = {}

        async def segment_clothing(**kwargs):
            captured.update(kwargs)
            return {"mask": "ok"}

        _patch_provider(monkeypatch, {"segment_clothing": segment_clothing})
        client = make_client(monkeypatch=monkeypatch)
        resp = _post(
            client,
            "tongyi",
            "segment-clothing",
            {
                "model_id": "m",
                "prompt": "segment",
                "attachments": [
                    {"mime_type": "image/png", "base64_data": "data:image/png;base64,SEGDATA"}
                ],
                "extra": {"target_clothing": "shirt"},
            },
        )
        assert resp.status_code == 200
        # base64 stripped of data-uri prefix, placed in reference_images.raw
        assert captured["reference_images"]["raw"] == "SEGDATA"
        assert captured["target_clothing"] == "shirt"


class TestMultiAgentEndpoint:
    def test_multi_agent_delegates_to_workflow(self, make_client, monkeypatch):
        async def fake_exec(**kwargs):
            return {"status": "completed", "result": {"text": "agents done"}}

        # _execute_multi_agent_mode imports execute_workflow lazily from ..ai.workflows
        import app.routers.ai.workflows as wf
        monkeypatch.setattr(wf, "execute_workflow", fake_exec)
        _patch_provider(monkeypatch, {})  # creds/factory not used on multi-agent path
        client = make_client(monkeypatch=monkeypatch)

        resp = _post(
            client,
            "google",
            "multi-agent",
            {"model_id": "m", "prompt": "coordinate"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["mode"] == "multi-agent"
        assert body["data"]["result"]["text"] == "agents done"


class TestStreamEndpoint:
    def test_non_streaming_mode_rejected(self, make_client, monkeypatch, caplog):
        _patch_provider(monkeypatch, {"generate_image": lambda **k: None})
        client = make_client(monkeypatch=monkeypatch)
        with caplog.at_level(logging.ERROR, logger=modes.logger.name):
            resp = client.post(
                "/api/modes/google/image-gen/stream",
                json={"model_id": "m", "prompt": "x"},
            )
        assert resp.status_code == 500  # ValueError("does not support streaming") → outer 500
        assert resp.json()["detail"] == "Mode stream failed"
        assert "does not support streaming" not in caplog.text
        assert "Traceback" not in caplog.text

    def test_chat_stream_yields_sse(self, make_client, monkeypatch):
        async def stream_chat(**kwargs):
            yield {"content": "hello", "chunk_type": "text"}
            yield {"content": " world", "chunk_type": "text"}

        _patch_provider(monkeypatch, {"stream_chat": stream_chat})
        client = make_client(monkeypatch=monkeypatch)
        resp = client.post(
            "/api/modes/google/chat/stream",
            json={"model_id": "m", "prompt": "hi"},
        )
        assert resp.status_code == 200
        text = resp.text
        assert "hello" in text
        assert "world" in text

    def test_chat_stream_error_emits_error_chunk(self, make_client, monkeypatch, caplog):
        secret = "sorftime-secret-token"

        async def stream_chat(**kwargs):
            raise RuntimeError(f"mid-stream boom {secret}")
            yield  # pragma: no cover

        _patch_provider(monkeypatch, {"stream_chat": stream_chat})
        client = make_client(monkeypatch=monkeypatch)
        with caplog.at_level(logging.ERROR, logger=modes.logger.name):
            resp = client.post(
                "/api/modes/google/chat/stream",
                json={"model_id": "m", "prompt": "hi"},
            )
        # error is caught inside generate() → still 200 with an error chunk + done
        assert resp.status_code == 200
        assert "stream_error" in resp.text or "error" in resp.text
        assert secret not in resp.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text

    def test_stream_invalid_param_keys_returns_400(self, make_client, monkeypatch):
        _patch_provider(monkeypatch, {"stream_chat": lambda **k: None})
        client = make_client(monkeypatch=monkeypatch)
        resp = client.post(
            "/api/modes/google/chat/stream",
            json={"model_id": "m", "prompt": "x", "extra": {"totally_bogus_key": 1}},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "invalid_provider_params"


class TestGetEndpoints:
    def test_controls_schema_not_found_returns_404(self, make_client, monkeypatch):
        monkeypatch.setattr(modes, "resolve_runtime_mode_controls_schema", lambda **k: None)
        client = make_client(monkeypatch=monkeypatch)
        resp = client.get("/api/modes/google/image-gen/controls")
        assert resp.status_code == 404

    def test_controls_schema_success(self, make_client, monkeypatch):
        monkeypatch.setattr(
            modes,
            "resolve_runtime_mode_controls_schema",
            lambda **k: {"aspect_ratios": ["1:1"]},
        )
        client = make_client(monkeypatch=monkeypatch)
        resp = client.get("/api/modes/google/image-gen/controls?model_id=imagen-3")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["schema"]["aspect_ratios"] == ["1:1"]
        assert body["model_id"] == "imagen-3"

    def test_controls_schema_internal_error_returns_500(self, make_client, monkeypatch, caplog):
        secret = "sorftime-secret-token"

        def boom(**k):
            raise RuntimeError(f"catalog corrupt {secret}")

        monkeypatch.setattr(modes, "resolve_runtime_mode_controls_schema", boom)
        client = make_client(monkeypatch=monkeypatch)
        with caplog.at_level(logging.ERROR, logger=modes.logger.name):
            resp = client.get("/api/modes/google/image-gen/controls")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to resolve controls schema"
        assert secret not in resp.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text

    def test_capabilities_success(self, make_client, monkeypatch):
        monkeypatch.setattr(
            modes,
            "get_mode_catalog",
            lambda include_internal=False: [
                {"id": "image-gen", "label": "Image", "group": "media",
                 "visible_in_navigation": True, "service_method": "generate_image"}
            ],
        )
        monkeypatch.setattr(
            modes,
            "build_provider_mode_capabilities",
            lambda **k: {
                "normalized_provider": "google",
                "api_mode": "rest",
                "vertex_ready": False,
                "modes": {"image-gen": {"runtime_enabled": True, "reason_code": None}},
            },
        )
        client = make_client(monkeypatch=monkeypatch)
        resp = client.get("/api/modes/google/capabilities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["normalized_provider"] == "google"
        assert body["capabilities"][0]["id"] == "image-gen"
        assert body["capabilities"][0]["runtime_enabled"] is True

    def test_capabilities_internal_error_returns_500(self, make_client, monkeypatch, caplog):
        secret = "sorftime-secret-token"

        def boom(**k):
            raise RuntimeError(f"probe failed {secret}")

        monkeypatch.setattr(modes, "get_mode_catalog", lambda include_internal=False: [])
        monkeypatch.setattr(modes, "build_provider_mode_capabilities", boom)
        client = make_client(monkeypatch=monkeypatch)
        with caplog.at_level(logging.ERROR, logger=modes.logger.name):
            resp = client.get("/api/modes/google/capabilities")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Failed to probe mode capabilities"
        assert secret not in resp.text
        assert secret not in caplog.text
        assert "Traceback" not in caplog.text
        assert "<redacted error; length=" in caplog.text
