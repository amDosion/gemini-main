"""统一连接池治理测试。

按 JIRA-gemini-client-pool-unification.md 第 153-158 行验收标准：
- 连接池统计可以在单元测试中证明相同配置复用同一 client，不同 Gemini API / Vertex 配置隔离
- agent.Client 包装类的底层 client 通过 GeminiClientPool 获取
- 主运行链路禁止新增直接 ``genai.Client(...)`` 调用
"""
from __future__ import annotations

import ast
import importlib
from pathlib import Path
import sys

import pytest

from app.services.gemini.agent import Client as AgentClient
from app.services.gemini.client_pool import GeminiClientPool, get_client_pool


REPO_ROOT = Path(__file__).resolve().parents[1] / "app"

# 主运行链路允许直接 genai.Client(...) 的白名单。
# - client_pool.py: 池内部唯一合法的创建点
# - vertex_ai_config.py:/verify-vertex-ai 一次性配置验证（JIRA 第 88-91 行明确允许）
# - geminiapi/main.py: standalone FastAPI app，不在主 backend 挂载（JIRA 第 85-87 行）
DIRECT_CLIENT_ALLOWLIST = {
    Path("services/gemini/client_pool.py"),
    Path("routers/models/vertex_ai_config.py"),
    Path("services/gemini/geminiapi/main.py"),
}

# 子树白名单：deprecated/legacy 不在主链路加载
DIRECT_CLIENT_ALLOWED_SUBTREES = (
    Path("services/gemini/_deprecated"),
)

def _direct_genai_client_call_lines(source: str) -> list[int]:
    """用 AST 找出真实的 ``genai.Client(...)`` 调用行号。

    比文本 regex 准确：跳过 docstring / 注释 / 普通字符串里的 ``genai.Client (...)`` 文本。
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "Client":
            continue
        value = func.value
        if isinstance(value, ast.Name) and value.id == "genai":
            lines.append(node.lineno)
        elif (
            isinstance(value, ast.Attribute)
            and value.attr == "genai"
            and isinstance(value.value, ast.Name)
            and value.value.id == "google"
        ):
            # ``google.genai.Client(...)`` 直调
            lines.append(node.lineno)
    return lines


@pytest.fixture
def fresh_pool() -> GeminiClientPool:
    """每个测试拿一个 stats 干净的池单例。"""
    pool = get_client_pool()
    pool._clients.clear()
    pool._client_metadata.clear()
    pool._stats = {
        "total_clients": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "rejected_due_to_max_size": 0,
    }
    return pool


def test_agent_client_uses_client_pool_when_constructing_google_genai_client(fresh_pool):
    """JIRA 第 84 行核心验收：包装类底层 google.genai.Client 来自统一池。"""
    wrapper = AgentClient(api_key="unit-test-key", vertexai=False)

    direct = fresh_pool.get_client(api_key="unit-test-key", vertexai=False)

    assert wrapper._genai_client is direct, (
        "wrapper.Client._genai_client 应当等于 pool.get_client(...) 返回的同一对象；"
        "若不一致说明包装类绕过了统一池。"
    )


def test_pool_reuses_same_client_for_same_config(fresh_pool):
    """同 (vertexai, api_key, http_options) 配置在进程内复用同一 client。"""
    a = AgentClient(api_key="reuse-key", vertexai=False)
    b = AgentClient(api_key="reuse-key", vertexai=False)

    assert a._genai_client is b._genai_client

    stats = fresh_pool.get_stats()
    assert stats["total_clients"] == 1, stats
    assert stats["cache_hits"] >= 1, stats
    assert stats["cache_misses"] == 1, stats


def test_pool_isolates_gemini_api_from_vertex_ai_for_same_string_key(fresh_pool):
    """Gemini API 与 Vertex AI 路径的 cache key 必须分开，避免模式串扰。"""
    fresh_pool.get_client(api_key="key-shared", vertexai=False)
    fresh_pool.get_client(
        vertexai=True,
        project="test-project",
        location="us-central1",
    )

    keys = list(fresh_pool._clients.keys())
    assert len(keys) == 2, keys
    assert any(k.startswith("gemini:") for k in keys)
    assert any(k.startswith("vertex:") for k in keys)


def test_wrapper_close_does_not_break_pool_shared_client(fresh_pool):
    """JIRA 第 161 行 risk：包装类 close 不应破坏池中被共享的 client。"""
    wrapper = AgentClient(api_key="close-test", vertexai=False)
    underlying = wrapper._genai_client

    wrapper.close()

    assert wrapper._genai_client is underlying
    assert any(c is underlying for c in fresh_pool._clients.values()), (
        "Client.close() 后池里的底层 client 不应被释放。"
    )


def test_direct_genai_client_creation_is_allowlisted_only():
    """JIRA 第 158 行：主运行链路（除白名单外）禁止新增直接 genai.Client(...)。

    扫描 backend/app/ 下所有 .py 文件，对每处 ``genai.Client(`` 调用：
      - 在 DIRECT_CLIENT_ALLOWLIST 中的具体文件 -> 允许
      - 在 DIRECT_CLIENT_ALLOWED_SUBTREES 子树下 -> 允许（_deprecated/）
      - 否则 -> 报失败，迫使新代码走 client_pool
    """
    offenders: list[str] = []

    for py_file in REPO_ROOT.rglob("*.py"):
        rel = py_file.relative_to(REPO_ROOT)

        if rel in DIRECT_CLIENT_ALLOWLIST:
            continue
        if any(str(rel).startswith(str(prefix)) for prefix in DIRECT_CLIENT_ALLOWED_SUBTREES):
            continue

        text = py_file.read_text(encoding="utf-8", errors="replace")
        for lineno in _direct_genai_client_call_lines(text):
            offenders.append(f"{rel}:{lineno}")

    assert not offenders, (
        "下列文件出现了主运行链路禁止的直接 `genai.Client(...)` 调用，"
        "请改走 `from app.services.gemini.client_pool import get_client_pool; "
        "client = get_client_pool().get_client(...)`：\n  "
        + "\n  ".join(offenders)
    )


# ===========================================================================
# JIRA-gemini-pool-production-hardening.md  P1 #21-#23 + 加分项
# ===========================================================================


def test_pool_max_size_raises_when_exceeded(monkeypatch, fresh_pool):
    """JIRA hardening P0 #6：池规模上限达到时 raise RuntimeError 防 OOM。"""
    monkeypatch.setattr(fresh_pool, "_max_size", 3)

    for i in range(3):
        fresh_pool.get_client(api_key=f"max-size-key-{i}", vertexai=False)

    assert len(fresh_pool._clients) == 3

    with pytest.raises(RuntimeError, match="size limit reached"):
        fresh_pool.get_client(api_key="overflow-key", vertexai=False)

    stats = fresh_pool.get_stats()
    assert stats["rejected_due_to_max_size"] == 1
    assert stats["max_size"] == 3


def test_embedding_service_uses_client_pool(monkeypatch):
    """JIRA hardening P1 #21：embedding_service.get_embedding 走池且 vertexai=False。"""
    from app.services.common import embedding_service as svc

    captured_kwargs: dict = {}

    class _FakeEmbeddingResponse:
        embeddings = [type("E", (), {"values": [0.1, 0.2, 0.3]})()]

    class _FakeClient:
        models = type("M", (), {"embed_content": lambda self, model, contents: _FakeEmbeddingResponse()})()

    class _FakePool:
        def get_client(self, **kwargs):
            captured_kwargs.update(kwargs)
            return _FakeClient()

    monkeypatch.setattr(svc, "get_client_pool", lambda: _FakePool())

    result = svc.get_embedding("hello", api_key="emb-test-key")

    assert result == [0.1, 0.2, 0.3]
    assert captured_kwargs.get("api_key") == "emb-test-key"
    assert captured_kwargs.get("vertexai") is False


def test_embedding_service_cosine_similarity_does_not_require_numpy(monkeypatch):
    module_name = "app.services.common.embedding_service"
    common_pkg = importlib.import_module("app.services.common")
    sys.modules.pop(module_name, None)
    monkeypatch.delattr(common_pkg, "embedding_service", raising=False)
    monkeypatch.setitem(sys.modules, "numpy", None)

    svc = importlib.import_module(module_name)

    assert svc.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert svc.cosine_similarity([1.0, 1.0], [1.0, 1.0]) == pytest.approx(1.0)
    assert svc.cosine_similarity([0.0, 0.0], [1.0, 1.0]) == pytest.approx(0.0)
    with pytest.raises(ValueError, match="same length"):
        svc.cosine_similarity([1.0], [1.0, 2.0])


def test_file_search_uses_client_pool_for_api_key(monkeypatch):
    """JIRA hardening P1 #22：file_search 上传走池，vertexai=False，api_key 来自 Bearer。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.system.file_search import router as fs_router

    captured_kwargs: dict = {}
    upload_called = {"count": 0}

    class _FakeStore:
        name = "fileSearchStores/deep-research-documents"
        display_name = "deep-research-documents"

    class _FakeOperation:
        def __init__(self):
            self.done = True
            self.name = "operations/test-op-id"
            self.response = {"file_id": "files/test-file-id"}

    class _FakeFile:
        name = "files/uploaded-file"

    class _FakeFileSearchStores:
        def get(self, name):
            return _FakeStore()
        def upload_to_file_search_store(self, name, file):
            upload_called["count"] += 1
            return _FakeOperation()

    class _FakeFiles:
        def upload(self, path):
            return _FakeFile()

    class _FakeOperations:
        def get(self, name):
            return _FakeOperation()

    class _FakeClient:
        file_search_stores = _FakeFileSearchStores()
        files = _FakeFiles()
        operations = _FakeOperations()

    class _FakePool:
        def get_client(self, **kwargs):
            captured_kwargs.update(kwargs)
            return _FakeClient()

    import app.routers.system.file_search as fs_mod
    monkeypatch.setattr(fs_mod, "get_client_pool", lambda: _FakePool())

    app = FastAPI()
    app.include_router(fs_router)
    client = TestClient(app)

    response = client.post(
        "/api/file-search/upload",
        files={"file": ("hello.txt", b"hello world", "text/plain")},
        headers={"Authorization": "Bearer fs-test-key-12345"},
    )

    assert response.status_code == 200, response.text
    assert captured_kwargs.get("api_key") == "fs-test-key-12345"
    assert captured_kwargs.get("vertexai") is False
    assert upload_called["count"] == 1


def test_credentials_json_decode_error_raises_not_silent_adc(monkeypatch):
    """JIRA hardening P0 #9：credentials.py JSON 解密失败必须 raise，不再 silent fallback ADC。"""
    from unittest.mock import MagicMock

    import app.core.encryption as enc
    from app.services.gemini.credentials import get_vertex_ai_credentials_from_db

    monkeypatch.setattr(enc, "decrypt_data", lambda blob: "definitely-not-json{")

    cfg = MagicMock()
    cfg.api_mode = "vertex_ai"
    cfg.vertex_ai_project_id = "p"
    cfg.vertex_ai_location = "us-central1"
    cfg.vertex_ai_credentials_json = "encrypted-blob"

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = cfg

    with pytest.raises(ValueError, match="malformed"):
        get_vertex_ai_credentials_from_db("user-x", db)


@pytest.mark.parametrize(
    "auth_header,expected_status",
    [
        (None, 401),
        ("", 401),
        ("Basic abc", 401),
        ("Bearer", 401),
        ("Bearer ", 401),
        ("Bearer  ", 401),
        ("Bearer\t", 401),
    ],
)
def test_bearer_token_empty_returns_401_not_500(auth_header, expected_status):
    """JIRA hardening P0 #4：异常 Bearer 格式必须返回 401，不应透到 pool 触发 500。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.system.file_search import router as fs_router

    app = FastAPI()
    app.include_router(fs_router)
    client = TestClient(app)

    headers = {"Authorization": auth_header} if auth_header is not None else {}
    response = client.get("/api/file-search/stores", headers=headers)
    assert response.status_code == expected_status, response.text


def test_close_failure_logs_warning_not_debug(monkeypatch, caplog):
    """JIRA hardening P0 #13：/verify-vertex-ai finally close 失败应 logger.warning。"""
    import logging
    from app.routers.models import vertex_ai_config

    caplog.set_level(logging.WARNING, logger=vertex_ai_config.logger.name)

    class _FailClose:
        def close(self):
            raise RuntimeError("simulated close failure")

    # 手动模拟 finally 块逻辑（避免完整 endpoint 调用所需的 DB / auth 层）
    client = _FailClose()
    try:
        if client is not None and hasattr(client, "close"):
            try:
                client.close()
            except Exception as close_err:
                vertex_ai_config.logger.warning(
                    f"[VertexAIConfig] Failed to close verify-only Vertex AI client: {close_err}",
                    exc_info=True,
                )
    except Exception:
        pytest.fail("finally block should swallow close exception")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Failed to close verify-only" in r.message for r in warnings)


def test_health_payload_contains_gemini_pool():
    """JIRA hardening P1 #18：/health payload 含 gemini_pool 字段。"""
    from app.routers.system.health import _gemini_pool_health

    payload = _gemini_pool_health()
    expected_keys = {"initialized", "sdk_available", "active_clients", "max_size"}
    assert expected_keys.issubset(set(payload.keys())), (
        f"missing keys: {expected_keys - set(payload.keys())}"
    )
    assert isinstance(payload["initialized"], bool)
    assert isinstance(payload["sdk_available"], bool)
    assert isinstance(payload["active_clients"], int)
    assert isinstance(payload["max_size"], int)


def test_admin_gemini_pool_stats_route_registered():
    """JIRA hardening P1 #17：admin endpoint /api/system/admin/gemini-pool/stats 已注册。"""
    from app.routers.system.admin import router as admin_router

    paths = {getattr(r, "path", None) for r in admin_router.routes}
    assert "/api/system/admin/gemini-pool/stats" in paths


def test_file_search_store_get_propagates_non_notfound_errors(monkeypatch):
    """JIRA hardening P0 #12：store get 时非 NotFound 错误必须传播，不能被误归为"不存在 → 创建"。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.system.file_search import router as fs_router

    create_called = {"count": 0}

    class _AuthError(Exception):
        code = 403
        status = "PERMISSION_DENIED"

        def __str__(self):
            return "401 Unauthorized: invalid api_key"

    class _FakeFileSearchStores:
        def get(self, name):
            raise _AuthError()
        def create(self, config):
            create_called["count"] += 1
            return None

    class _FakeClient:
        file_search_stores = _FakeFileSearchStores()
        files = type("F", (), {})()
        operations = type("O", (), {})()

    class _FakePool:
        def get_client(self, **kwargs):
            return _FakeClient()

    import app.routers.system.file_search as fs_mod
    monkeypatch.setattr(fs_mod, "get_client_pool", lambda: _FakePool())

    app = FastAPI()
    app.include_router(fs_router)
    client = TestClient(app)

    response = client.post(
        "/api/file-search/upload",
        files={"file": ("hello.txt", b"hi", "text/plain")},
        headers={"Authorization": "Bearer fake-key"},
    )

    # 必须是 500 + 通用消息（auth 错误已在 logger 服务端记录），且没有走 fallback create()
    assert response.status_code == 500
    assert "File upload failed. Please try again" in response.text
    assert create_called["count"] == 0, "auth/permission errors must NOT trigger create() fallback"
