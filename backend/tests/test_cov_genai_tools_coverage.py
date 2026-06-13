"""Coverage-focused unit tests for genai_agent tool definitions/dispatch and
advanced-feature transforms.

Targets:
  - app.services.gemini.genai_agent.tools (ToolManager, is_url)
  - app.services.gemini.genai_agent.advanced_features
        (AdvancedResearchAgent, ConversationState, EventType)

External boundaries are mocked (google.genai SDK, the common.browser module,
subprocess execution). The module-under-test logic (registration, dispatch,
filter normalization, local file search, event-stream transforms) is exercised
for real.
"""

import sys
import types as pytypes

from app.services.gemini.genai_agent import tools as tools_mod
from app.services.gemini.genai_agent.tools import ToolManager, is_url
from app.services.gemini.genai_agent import advanced_features as adv_mod
from app.services.gemini.genai_agent.advanced_features import (
    AdvancedResearchAgent,
    ConversationState,
    EventType,
)


# ---------------------------------------------------------------------------
# is_url
# ---------------------------------------------------------------------------

def test_is_url_rejects_non_string_and_empty():
    assert is_url("") is False
    assert is_url(None) is False  # type: ignore[arg-type]
    assert is_url(12345) is False  # type: ignore[arg-type]


def test_is_url_accepts_valid_http_url():
    assert is_url("https://example.com") is True
    assert is_url("  http://example.com/path?x=1  ") is True


def test_is_url_rejects_plain_text():
    assert is_url("just some words") is False


def test_is_url_falls_back_when_shared_import_fails(monkeypatch):
    """If the shared util import fails, the local regex fallback must run."""
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if "shared.utils" in name or name.endswith("shared.utils"):
            raise ImportError("forced")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    # http prefix fast-path inside fallback
    assert is_url("http://localhost:8080") is True
    # fallback regex rejects bare text
    assert is_url("nota url") is False


# ---------------------------------------------------------------------------
# ToolManager registration
# ---------------------------------------------------------------------------

def test_register_google_search_and_code_execution(monkeypatch):
    monkeypatch.setenv(tools_mod.LOCAL_CODE_EXECUTION_ENABLED_ENV, "true")
    tm = ToolManager([
        {"type": "google_search"},
        {"type": "code_execution"},
    ])
    assert "google_search" in tm._registered_tools
    assert "code_execution" in tm._registered_tools
    assert tm._registered_tools["google_search"]["name"] == "google_search"
    assert "query" in tm._registered_tools["google_search"]["parameters"]["properties"]


def test_register_code_execution_requires_explicit_env(monkeypatch):
    monkeypatch.delenv(tools_mod.LOCAL_CODE_EXECUTION_ENABLED_ENV, raising=False)
    tm = ToolManager([{"type": "code_execution"}])
    assert "code_execution" not in tm._registered_tools


def test_register_file_search_only_when_store_names_present():
    with_stores = ToolManager([
        {"type": "file_search", "file_search_store_names": ["/tmp/docs"]},
    ])
    assert "file_search" in with_stores._registered_tools
    assert with_stores._registered_tools["file_search"]["store_names"] == ["/tmp/docs"]

    without_stores = ToolManager([{"type": "file_search"}])
    assert "file_search" not in without_stores._registered_tools


def test_register_unknown_tool_type_is_ignored():
    tm = ToolManager([{"type": "totally_unknown"}])
    assert tm._registered_tools == {}


def _fake_browser_module(extra=None):
    mod = pytypes.ModuleType("app.services.gemini.common.browser")

    def get_tool_declarations():
        return [
            {"name": "web_search", "description": "Web search",
             "parameters": {"type": "object", "properties": {}}},
            {"name": "read_webpage", "description": "Read page",
             "parameters": {"type": "object", "properties": {}}},
        ]

    mod.get_tool_declarations = get_tool_declarations
    mod.web_search = lambda q: '[]'
    mod.AVAILABLE_TOOLS = {}
    if extra:
        for k, v in extra.items():
            setattr(mod, k, v)
    return mod


def test_register_browser_tools_success(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "app.services.gemini.common.browser", _fake_browser_module()
    )
    tm = ToolManager([{"type": "browser"}])
    assert "web_search" in tm._registered_tools
    assert "read_webpage" in tm._registered_tools


def test_register_browser_tools_import_error_is_swallowed(monkeypatch):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name.endswith("common.browser") or "common.browser" in name:
            raise ImportError("no browser")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    tm = ToolManager([{"type": "enable_browser"}])
    # No browser tools registered, but construction did not raise.
    assert "web_search" not in tm._registered_tools


# ---------------------------------------------------------------------------
# ToolManager.get_tools
# ---------------------------------------------------------------------------

def test_get_tools_returns_none_when_empty():
    tm = ToolManager([])
    assert tm.get_tools() is None


def test_get_tools_genai_format():
    tm = ToolManager([{"type": "google_search"}])
    result = tm.get_tools()
    assert result is not None
    assert len(result) == 1
    # genai Tool object exposes function_declarations
    tool = result[0]
    assert hasattr(tool, "function_declarations")
    assert tool.function_declarations[0].name == "google_search"


def test_get_tools_dict_fallback_when_genai_unavailable(monkeypatch):
    monkeypatch.setenv(tools_mod.LOCAL_CODE_EXECUTION_ENABLED_ENV, "true")
    tm = ToolManager([{"type": "code_execution"}])
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "google.genai" or name.startswith("google.genai"):
            raise ImportError("no genai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    result = tm.get_tools()
    assert result is not None
    assert result[0]["function_declarations"][0]["name"] == "code_execution"


# ---------------------------------------------------------------------------
# ToolManager.execute_tool dispatch
# ---------------------------------------------------------------------------

async def test_execute_tool_unknown_returns_error():
    tm = ToolManager([])
    result = await tm.execute_tool("does_not_exist", {})
    assert result == {"error": "Unknown tool: does_not_exist"}


async def test_execute_tool_dispatches_google_search(monkeypatch):
    tm = ToolManager([{"type": "google_search"}])

    async def fake_gsearch(query):
        return {"success": True, "query": query, "results": ["a"]}

    monkeypatch.setattr(tm, "_execute_google_search", fake_gsearch)
    out = await tm.execute_tool("google_search", {"query": "hi"})
    assert out["results"] == ["a"]


async def test_execute_tool_dispatches_file_search_with_defaults(monkeypatch):
    tm = ToolManager([{"type": "file_search", "file_search_store_names": ["/d"]}])
    captured = {}

    async def fake_fs(query, store_names, top_k=20, metadata_filter=None):
        captured["store_names"] = store_names
        captured["top_k"] = top_k
        return {"success": True, "matches": []}

    monkeypatch.setattr(tm, "_execute_file_search", fake_fs)
    # No store_names passed -> falls back to registered default
    await tm.execute_tool("file_search", {"query": "x"})
    assert captured["store_names"] == ["/d"]
    assert captured["top_k"] == 20


async def test_execute_tool_dispatches_code(monkeypatch):
    monkeypatch.setenv(tools_mod.LOCAL_CODE_EXECUTION_ENABLED_ENV, "true")
    tm = ToolManager([{"type": "code_execution"}])

    async def fake_code(code):
        return {"success": True, "output": code}

    monkeypatch.setattr(tm, "_execute_code", fake_code)
    out = await tm.execute_tool("code_execution", {"code": "print(1)"})
    assert out["output"] == "print(1)"


async def test_execute_tool_browser_branch(monkeypatch):
    tm = ToolManager([])

    async def fake_browser(name, args):
        return {"result": "ok", "success": True}

    monkeypatch.setattr(tm, "_execute_browser_tool", fake_browser)
    out = await tm.execute_tool("web_search", {"query": "q"})
    assert out["success"] is True


async def test_execute_tool_wraps_exceptions(monkeypatch):
    tm = ToolManager([{"type": "google_search"}])

    async def boom(query):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(tm, "_execute_google_search", boom)
    out = await tm.execute_tool("google_search", {"query": "x"})
    assert out["error"] == "kaboom"


# ---------------------------------------------------------------------------
# _execute_google_search
# ---------------------------------------------------------------------------

async def test_google_search_requires_query():
    tm = ToolManager([])
    out = await tm._execute_google_search("   ")
    assert out["success"] is False
    assert out["error"] == "query is required"


async def test_google_search_parses_json_list(monkeypatch):
    mod = _fake_browser_module(extra={"web_search": lambda q: '[{"title": "T"}]'})
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    tm = ToolManager([])
    out = await tm._execute_google_search("hello")
    assert out["success"] is True
    assert out["results"] == [{"title": "T"}]


async def test_google_search_parses_dict_results(monkeypatch):
    mod = _fake_browser_module(
        extra={"web_search": lambda q: {"results": [{"u": 1}]}}
    )
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    tm = ToolManager([])
    out = await tm._execute_google_search("hello")
    assert out["results"] == [{"u": 1}]


async def test_google_search_unparseable_yields_empty(monkeypatch):
    mod = _fake_browser_module(extra={"web_search": lambda q: 12345})
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    tm = ToolManager([])
    out = await tm._execute_google_search("hello")
    assert out["results"] == []


async def test_google_search_handles_exception(monkeypatch):
    def raising(q):
        raise ValueError("net down")

    mod = _fake_browser_module(extra={"web_search": raising})
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    tm = ToolManager([])
    out = await tm._execute_google_search("hello")
    assert out["success"] is False
    assert "net down" in out["error"]


# ---------------------------------------------------------------------------
# filter normalization & file matching helpers
# ---------------------------------------------------------------------------

def test_normalize_file_filters_non_dict_returns_empty():
    assert ToolManager._normalize_file_filters(None) == {}
    assert ToolManager._normalize_file_filters("nope") == {}


def test_normalize_file_filters_full():
    raw = {
        "extensions": ["py", ".txt", "", None],
        "path_contains": "Docs",
        "file_glob": "*.py",
        "max_file_size_bytes": "1024",
    }
    norm = ToolManager._normalize_file_filters(raw)
    assert norm["extensions"] == {".py", ".txt"}
    assert norm["path_contains"] == ["docs"]
    assert norm["file_glob"] == ["*.py"]
    assert norm["max_file_size_bytes"] == 1024


def test_normalize_file_filters_list_variants_and_bad_size():
    raw = {
        "path_contains": ["A", "  ", "b"],
        "file_glob": ["*.md", ""],
        "max_file_size_bytes": "not-a-number",
    }
    norm = ToolManager._normalize_file_filters(raw)
    assert norm["path_contains"] == ["a", "b"]
    assert norm["file_glob"] == ["*.md"]
    assert "max_file_size_bytes" not in norm  # bad size silently dropped


def test_file_matches_filters_empty_always_true(tmp_path):
    tm = ToolManager([])
    f = tmp_path / "x.py"
    f.write_text("hi")
    assert tm._file_matches_filters(f, {}) is True


def test_file_matches_filters_extension_reject(tmp_path):
    tm = ToolManager([])
    f = tmp_path / "x.bin"
    f.write_text("hi")
    assert tm._file_matches_filters(f, {"extensions": {".py"}}) is False


def test_file_matches_filters_path_contains(tmp_path):
    tm = ToolManager([])
    sub = tmp_path / "docs"
    sub.mkdir()
    f = sub / "x.py"
    f.write_text("hi")
    assert tm._file_matches_filters(f, {"path_contains": ["docs"]}) is True
    assert tm._file_matches_filters(f, {"path_contains": ["zzz"]}) is False


def test_file_matches_filters_glob_and_size(tmp_path):
    tm = ToolManager([])
    f = tmp_path / "x.py"
    f.write_text("0123456789")
    assert tm._file_matches_filters(f, {"file_glob": ["*.py"]}) is True
    assert tm._file_matches_filters(f, {"file_glob": ["*.md"]}) is False
    assert tm._file_matches_filters(f, {"max_file_size_bytes": 5}) is False
    assert tm._file_matches_filters(f, {"max_file_size_bytes": 1000}) is True


def test_is_text_searchable_file():
    from pathlib import Path
    assert ToolManager._is_text_searchable_file(Path("a.py")) is True
    assert ToolManager._is_text_searchable_file(Path("a.png")) is False


def test_resolve_local_search_files(tmp_path, monkeypatch):
    tm = ToolManager([])
    f1 = tmp_path / "a.txt"
    f1.write_text("x")
    sub = tmp_path / "nested"
    sub.mkdir()
    f2 = sub / "b.md"
    f2.write_text("y")
    monkeypatch.setenv(tools_mod.FILE_SEARCH_ALLOWED_ROOTS_ENV, str(tmp_path))
    # one file path, one directory path, one blank, one missing
    resolved = tm._resolve_local_search_files(
        [str(f1), str(tmp_path), "  ", str(tmp_path / "missing")]
    )
    names = {p.name for p in resolved}
    assert "a.txt" in names and "b.md" in names


def test_resolve_local_search_files_rejects_outside_allowed_root(tmp_path, monkeypatch):
    tm = ToolManager([])
    allowed = tmp_path / "allowed"
    denied = tmp_path / "denied"
    allowed.mkdir()
    denied.mkdir()
    public_file = allowed / "public.txt"
    public_file.write_text("ok")
    secret_file = denied / "secret.txt"
    secret_file.write_text("secret")
    monkeypatch.setenv(tools_mod.FILE_SEARCH_ALLOWED_ROOTS_ENV, str(allowed))

    resolved = tm._resolve_local_search_files([str(allowed), str(denied), str(secret_file)])

    assert public_file.resolve() in resolved
    assert secret_file.resolve() not in resolved


# ---------------------------------------------------------------------------
# _execute_file_search (real local search)
# ---------------------------------------------------------------------------

async def test_file_search_requires_query():
    tm = ToolManager([])
    out = await tm._execute_file_search("", ["/tmp"])
    assert out["success"] is False
    assert out["error"] == "query is required"


async def test_file_search_no_files_found(tmp_path, monkeypatch):
    tm = ToolManager([])
    monkeypatch.setenv(tools_mod.FILE_SEARCH_ALLOWED_ROOTS_ENV, str(tmp_path))
    out = await tm._execute_file_search("hello", [str(tmp_path / "nope")])
    assert out["success"] is False
    assert "No readable local files" in out["error"]


async def test_file_search_requires_explicit_allowed_root(tmp_path, monkeypatch):
    tm = ToolManager([])
    f = tmp_path / "doc.txt"
    f.write_text("needle\n")
    monkeypatch.delenv(tools_mod.FILE_SEARCH_ALLOWED_ROOTS_ENV, raising=False)

    out = await tm._execute_file_search("needle", [str(f)])

    assert out["success"] is False
    assert out["matches"] == []


async def test_file_search_finds_matches(tmp_path, monkeypatch):
    tm = ToolManager([])
    f = tmp_path / "doc.txt"
    f.write_text("first line\nThe needle is here\nlast line\n")
    monkeypatch.setenv(tools_mod.FILE_SEARCH_ALLOWED_ROOTS_ENV, str(tmp_path))
    out = await tm._execute_file_search("needle", [str(f)], top_k=5)
    assert out["success"] is True
    assert out["searched_files"] == 1
    assert len(out["matches"]) == 1
    m = out["matches"][0]
    assert m["line"] == 2
    assert "needle" in m["snippet"]
    assert m["highlights"][0]["end"] > m["highlights"][0]["start"]


async def test_file_search_respects_top_k_clamp(tmp_path, monkeypatch):
    tm = ToolManager([])
    f = tmp_path / "doc.txt"
    f.write_text("\n".join(["needle"] * 10))
    monkeypatch.setenv(tools_mod.FILE_SEARCH_ALLOWED_ROOTS_ENV, str(tmp_path))
    out = await tm._execute_file_search("needle", [str(f)], top_k=3)
    assert out["top_k"] == 3
    assert len(out["matches"]) == 3


async def test_file_search_skips_non_text_files(tmp_path, monkeypatch):
    tm = ToolManager([])
    f = tmp_path / "img.png"
    f.write_text("needle inside but png")
    monkeypatch.setenv(tools_mod.FILE_SEARCH_ALLOWED_ROOTS_ENV, str(tmp_path))
    out = await tm._execute_file_search("needle", [str(f)])
    # png is not text-searchable so it is "searched_files" but yields no matches
    assert out["success"] is True
    assert out["matches"] == []


async def test_file_search_metadata_filter_serialized(tmp_path, monkeypatch):
    tm = ToolManager([])
    f = tmp_path / "code.py"
    f.write_text("def needle():\n    pass\n")
    monkeypatch.setenv(tools_mod.FILE_SEARCH_ALLOWED_ROOTS_ENV, str(tmp_path))
    out = await tm._execute_file_search(
        "needle", [str(f)], metadata_filter={"extensions": ["py"]}
    )
    assert out["metadata_filter"]["extensions"] == [".py"]
    assert len(out["matches"]) == 1


# ---------------------------------------------------------------------------
# _execute_code (real subprocess)
# ---------------------------------------------------------------------------

async def test_execute_code_requires_code():
    tm = ToolManager([])
    out = await tm._execute_code("   ")
    assert out["success"] is False
    assert out["status"] == "invalid_input"


async def test_execute_code_disabled_by_default(monkeypatch):
    monkeypatch.delenv(tools_mod.LOCAL_CODE_EXECUTION_ENABLED_ENV, raising=False)
    tm = ToolManager([])
    out = await tm._execute_code("print('should-not-run')")
    assert out["success"] is False
    assert out["status"] == "disabled"
    assert out["output"] == ""


async def test_execute_code_success(monkeypatch):
    monkeypatch.setenv(tools_mod.LOCAL_CODE_EXECUTION_ENABLED_ENV, "true")
    tm = ToolManager([])
    out = await tm._execute_code("print('hello-from-test')")
    assert out["success"] is True
    assert out["status"] == "success"
    assert "hello-from-test" in out["output"]
    assert out["return_code"] == 0


async def test_execute_code_failure_nonzero_exit(monkeypatch):
    monkeypatch.setenv(tools_mod.LOCAL_CODE_EXECUTION_ENABLED_ENV, "true")
    tm = ToolManager([])
    out = await tm._execute_code("import sys; sys.exit(3)")
    assert out["success"] is False
    assert out["status"] == "failed"
    assert out["return_code"] == 3


async def test_execute_code_timeout(monkeypatch):
    monkeypatch.setenv(tools_mod.LOCAL_CODE_EXECUTION_ENABLED_ENV, "true")
    tm = ToolManager([])
    monkeypatch.setenv("GEMINI_TOOL_CODE_TIMEOUT_SEC", "1")
    out = await tm._execute_code("import time; time.sleep(5)")
    assert out["success"] is False
    assert out["status"] == "timeout"
    assert out["return_code"] is None


# ---------------------------------------------------------------------------
# _execute_browser_tool
# ---------------------------------------------------------------------------

async def test_browser_tool_not_found(monkeypatch):
    mod = _fake_browser_module()
    mod.AVAILABLE_TOOLS = {}
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    tm = ToolManager([])
    out = await tm._execute_browser_tool("web_search", {})
    assert out["error"] == "Browser tool web_search not found"


async def test_browser_tool_sync_function(monkeypatch):
    def sync_search(query):
        return "sync result for " + query

    mod = _fake_browser_module()
    mod.AVAILABLE_TOOLS = {"web_search": sync_search}
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    tm = ToolManager([])
    out = await tm._execute_browser_tool("web_search", {"query": "abc"})
    assert out["success"] is True
    assert "sync result for abc" in out["result"]


async def test_browser_tool_async_function(monkeypatch):
    async def async_search(query):
        return "async result"

    mod = _fake_browser_module()
    mod.AVAILABLE_TOOLS = {"web_search": async_search}
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    tm = ToolManager([])
    out = await tm._execute_browser_tool("web_search", {"query": "abc"})
    assert out["result"] == "async result"


async def test_browser_tool_selenium_success(monkeypatch):
    def selenium(url):
        return {"content": "page text", "screenshot": "b64data"}

    mod = _fake_browser_module()
    mod.AVAILABLE_TOOLS = {"selenium_browse": selenium}
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    tm = ToolManager([])
    out = await tm._execute_browser_tool("selenium_browse", {"url": "http://x"})
    assert out["success"] is True
    assert out["result"] == "page text"
    assert out["screenshot"] == "b64data"


async def test_browser_tool_selenium_error(monkeypatch):
    def selenium(url):
        return {"error": "page failed"}

    mod = _fake_browser_module()
    mod.AVAILABLE_TOOLS = {"selenium_browse": selenium}
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    tm = ToolManager([])
    out = await tm._execute_browser_tool("selenium_browse", {"url": "http://x"})
    assert out["error"] == "page failed"


async def test_browser_tool_handles_exception(monkeypatch):
    def boom(query):
        raise RuntimeError("driver crashed")

    mod = _fake_browser_module()
    mod.AVAILABLE_TOOLS = {"web_search": boom}
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    tm = ToolManager([])
    out = await tm._execute_browser_tool("web_search", {"query": "q"})
    assert out["success"] is False
    assert "driver crashed" in out["error"]


# ===========================================================================
# advanced_features
# ===========================================================================

def test_event_type_enum_values():
    assert EventType.INTERACTION_START.value == "interaction.start"
    assert EventType.TOOL_CALL.value == "tool.call"
    assert EventType.ERROR == "error"  # StrEnum equality


def test_conversation_state_defaults():
    state = ConversationState(session_id="sid")
    assert state.session_id == "sid"
    assert state.messages == []
    assert state.thinking_history == []
    assert state.status == "in_progress"
    assert state.interaction_id is None


def test_agent_init_and_get_state():
    agent = AdvancedResearchAgent(
        client=object(), model="gemini-2.0", tools=[], config=object()
    )
    assert agent.model == "gemini-2.0"
    assert agent.get_conversation_state() is None


def test_build_system_instruction():
    agent = AdvancedResearchAgent(client=None, model="m", tools=[], config=None)
    instr = agent._build_system_instruction()
    assert "研究助手" in instr


def test_prepare_tools_none_when_empty():
    agent = AdvancedResearchAgent(client=None, model="m", tools=[], config=None)
    assert agent._prepare_tools() is None


def test_prepare_tools_builds_search_tools():
    agent = AdvancedResearchAgent(
        client=None, model="m",
        tools=[{"type": "google_search"}, {"type": "file_search"}, {"type": "other"}],
        config=None,
    )
    result = agent._prepare_tools()
    assert result is not None
    assert len(result) == 2  # google_search + file_search; 'other' ignored
    names = {t.function_declarations[0].name for t in result}
    assert names == {"google_search", "file_search"}


def test_build_contents_with_history():
    agent = AdvancedResearchAgent(client=None, model="m", tools=[], config=None)
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "model", "content": "more"},
    ]
    contents = agent._build_contents("now", history)
    # 3 history + 1 current = 4
    assert len(contents) == 4
    assert contents[-1].role == "user"


def test_build_contents_no_history():
    agent = AdvancedResearchAgent(client=None, model="m", tools=[], config=None)
    contents = agent._build_contents("solo", None)
    assert len(contents) == 1
    assert contents[0].role == "user"


# ----------------------- _execute_tool -----------------------

async def test_adv_execute_tool_browser_not_found(monkeypatch):
    mod = _fake_browser_module()
    mod.AVAILABLE_TOOLS = {}
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    agent = AdvancedResearchAgent(client=None, model="m", tools=[], config=None)
    out = await agent._execute_tool("web_search", {})
    assert out["error"] == "Browser tool web_search not found"


async def test_adv_execute_tool_browser_sync(monkeypatch):
    mod = _fake_browser_module()
    mod.AVAILABLE_TOOLS = {"web_search": lambda query: "found: " + query}
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    agent = AdvancedResearchAgent(client=None, model="m", tools=[], config=None)
    out = await agent._execute_tool("web_search", {"query": "x"})
    assert out["success"] is True
    assert "found: x" in out["result"]


async def test_adv_execute_tool_browser_async(monkeypatch):
    async def async_tool(query):
        return "async-out"

    mod = _fake_browser_module()
    mod.AVAILABLE_TOOLS = {"web_search": async_tool}
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    agent = AdvancedResearchAgent(client=None, model="m", tools=[], config=None)
    out = await agent._execute_tool("web_search", {"query": "x"})
    assert out["result"] == "async-out"


async def test_adv_execute_tool_selenium_error(monkeypatch):
    mod = _fake_browser_module()
    mod.AVAILABLE_TOOLS = {"selenium_browse": lambda url: {"error": "boom"}}
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    agent = AdvancedResearchAgent(client=None, model="m", tools=[], config=None)
    out = await agent._execute_tool("selenium_browse", {"url": "u"})
    assert out["error"] == "boom"


async def test_adv_execute_tool_selenium_success(monkeypatch):
    mod = _fake_browser_module()
    mod.AVAILABLE_TOOLS = {
        "selenium_browse": lambda url: {"content": "c", "screenshot": "s"}
    }
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    agent = AdvancedResearchAgent(client=None, model="m", tools=[], config=None)
    out = await agent._execute_tool("selenium_browse", {"url": "u"})
    assert out["result"] == "c"
    assert out["screenshot"] == "s"


async def test_adv_execute_tool_unimplemented():
    agent = AdvancedResearchAgent(client=None, model="m", tools=[], config=None)
    out = await agent._execute_tool("some_other_tool", {})
    assert "not yet implemented" in out["error"]


async def test_adv_execute_tool_exception(monkeypatch):
    mod = _fake_browser_module()

    def boom(query):
        raise RuntimeError("explode")

    mod.AVAILABLE_TOOLS = {"web_search": boom}
    monkeypatch.setitem(sys.modules, "app.services.gemini.common.browser", mod)
    agent = AdvancedResearchAgent(client=None, model="m", tools=[], config=None)
    out = await agent._execute_tool("web_search", {"query": "x"})
    assert "explode" in out["error"]


# ----------------------- stream_research_advanced -----------------------

class _FakeChunk:
    """Minimal stand-in for a genai stream chunk."""

    def __init__(self, text=None, thinking=None, function_calls=None):
        if text is not None:
            self.text = text
        if thinking is not None:
            self.thinking = thinking
        if function_calls is not None:
            self.function_calls = function_calls


class _FakeFuncCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args


class _FakeModels:
    def __init__(self, chunks=None, raise_exc=None):
        self._chunks = chunks or []
        self._raise = raise_exc

    def generate_content_stream(self, model, contents, config):
        if self._raise is not None:
            raise self._raise
        return iter(self._chunks)


class _FakeClient:
    def __init__(self, chunks=None, raise_exc=None):
        self.models = _FakeModels(chunks=chunks, raise_exc=raise_exc)


async def _collect(agen):
    return [item async for item in agen]


async def test_stream_emits_text_and_completes():
    chunks = [
        _FakeChunk(text="Hello "),
        _FakeChunk(text="World"),
    ]
    agent = AdvancedResearchAgent(
        client=_FakeClient(chunks=chunks), model="gemini-2.0", tools=[], config=None
    )
    events = await _collect(agent.stream_research_advanced("prompt"))
    types_seen = [e["event_type"] for e in events]
    assert EventType.INTERACTION_START in types_seen
    assert EventType.CONTENT_DELTA in types_seen
    assert EventType.INTERACTION_COMPLETE in types_seen
    # final state recorded
    state = agent.get_conversation_state()
    assert state.status == "completed"
    assert state.messages[-1]["content"] == "Hello World"


async def test_stream_emits_thinking_delta():
    chunks = [_FakeChunk(thinking="reasoning...")]
    agent = AdvancedResearchAgent(
        client=_FakeClient(chunks=chunks), model="m", tools=[], config=None
    )
    events = await _collect(agent.stream_research_advanced("p"))
    thought_events = [
        e for e in events
        if e["event_type"] == EventType.CONTENT_DELTA
        and e["delta"].get("type") == "thought_summary"
    ]
    assert len(thought_events) == 1
    assert thought_events[0]["delta"]["content"]["text"] == "reasoning..."


async def test_stream_tool_call_and_result(monkeypatch):
    fc = _FakeFuncCall("web_search", {"query": "x"})
    chunks = [_FakeChunk(function_calls=[fc])]
    agent = AdvancedResearchAgent(
        client=_FakeClient(chunks=chunks), model="m", tools=[], config=None
    )

    async def fake_exec(name, args):
        return {"result": "tool-ran", "success": True}

    monkeypatch.setattr(agent, "_execute_tool", fake_exec)
    events = await _collect(agent.stream_research_advanced("p"))
    tool_calls = [e for e in events if e["event_type"] == EventType.TOOL_CALL]
    tool_results = [e for e in events if e["event_type"] == EventType.TOOL_RESULT]
    assert tool_calls and tool_calls[0]["tool_call"]["name"] == "web_search"
    assert tool_results and tool_results[0]["tool_result"]["result"] == "tool-ran"
    state = agent.get_conversation_state()
    assert state.tool_calls[0]["name"] == "web_search"
    assert state.tool_results[0]["result"]["result"] == "tool-ran"


async def test_stream_tool_call_execution_error(monkeypatch):
    fc = _FakeFuncCall("web_search", {"query": "x"})
    chunks = [_FakeChunk(function_calls=[fc])]
    agent = AdvancedResearchAgent(
        client=_FakeClient(chunks=chunks), model="m", tools=[], config=None
    )

    async def fake_exec(name, args):
        raise RuntimeError("tool blew up")

    monkeypatch.setattr(agent, "_execute_tool", fake_exec)
    events = await _collect(agent.stream_research_advanced("p"))
    errors = [e for e in events if e["event_type"] == EventType.ERROR]
    assert errors
    assert errors[0]["error"]["tool"] == "web_search"
    assert "tool blew up" in errors[0]["error"]["message"]


async def test_stream_handles_stream_exception_generic():
    agent = AdvancedResearchAgent(
        client=_FakeClient(raise_exc=ValueError("generic failure")),
        model="m", tools=[], config=None,
    )
    events = await _collect(agent.stream_research_advanced("p"))
    error_events = [e for e in events if e["event_type"] == EventType.ERROR]
    assert error_events
    assert error_events[0]["error"]["message"] == "generic failure"
    assert agent.get_conversation_state().status == "failed"


async def test_stream_handles_interactions_api_error_message():
    exc = RuntimeError("INVALID_ARGUMENT: model only supports Interactions API")
    agent = AdvancedResearchAgent(
        client=_FakeClient(raise_exc=exc),
        model="gemini-special", tools=[], config=None,
    )
    events = await _collect(agent.stream_research_advanced("p"))
    error_events = [e for e in events if e["event_type"] == EventType.ERROR]
    assert error_events
    msg = error_events[0]["error"]["message"]
    # The friendly remapped message references the model name.
    assert "gemini-special" in msg
    assert "Interactions API" in msg
    # original error preserved
    assert "INVALID_ARGUMENT" in error_events[0]["error"]["original_error"]


def test_module_imports_present():
    # Sanity: both modules are importable and expose their public API.
    assert hasattr(tools_mod, "ToolManager")
    assert hasattr(adv_mod, "AdvancedResearchAgent")
