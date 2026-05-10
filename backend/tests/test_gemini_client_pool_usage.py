"""统一连接池治理测试。

按 JIRA-gemini-client-pool-unification.md 第 153-158 行验收标准：
- 连接池统计可以在单元测试中证明相同配置复用同一 client，不同 Gemini API / Vertex 配置隔离
- agent.Client 包装类的底层 client 通过 GeminiClientPool 获取
- 主运行链路禁止新增直接 ``genai.Client(...)`` 调用
"""
from __future__ import annotations

import ast
from pathlib import Path

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
    pool._stats = {"total_clients": 0, "cache_hits": 0, "cache_misses": 0}
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
