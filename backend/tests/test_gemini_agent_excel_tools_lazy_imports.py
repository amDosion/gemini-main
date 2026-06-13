from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

from app.services.gemini.agent.tools import excel_tools


BACKEND_ROOT = Path(__file__).resolve().parents[1]
HEAVY_MODULE_ROOTS = ("pandas", "numpy", "matplotlib")


def _assert_excel_source_import_keeps_heavy_modules_lazy() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_ROOT)
    excel_tools_path = BACKEND_ROOT / "app" / "services" / "gemini" / "agent" / "tools" / "excel_tools.py"
    code = (
        "import importlib.util, sys\n"
        f"roots = {HEAVY_MODULE_ROOTS!r}\n"
        "for name in list(sys.modules):\n"
        "    if any(name == root or name.startswith(root + '.') for root in roots):\n"
        "        sys.modules.pop(name, None)\n"
        f"spec = importlib.util.spec_from_file_location('excel_tools_lazy_check', {str(excel_tools_path)!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "assert spec.loader is not None\n"
        "spec.loader.exec_module(module)\n"
        "for root in roots:\n"
        "    loaded = any(name == root or name.startswith(root + '.') for name in sys.modules)\n"
        "    print(f'{root.upper()}_LOADED={loaded}')\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=True,
    )

    stdout = result.stdout.decode("utf-8", errors="replace")
    assert "PANDAS_LOADED=False" in stdout
    assert "NUMPY_LOADED=False" in stdout
    assert "MATPLOTLIB_LOADED=False" in stdout


def _assert_tool_registry_import_does_not_load_excel_implementation() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_ROOT)
    code = (
        "import importlib, sys\n"
        "for name in list(sys.modules):\n"
        "    if name == 'pandas' or name.startswith('pandas.'):\n"
        "        sys.modules.pop(name, None)\n"
        "    if name == 'matplotlib' or name.startswith('matplotlib.'):\n"
        "        sys.modules.pop(name, None)\n"
        "importlib.import_module('app.services.gemini.agent.tool_registry')\n"
        "print('EXCEL_TOOLS_LOADED=' + str('app.services.gemini.agent.tools.excel_tools' in sys.modules))\n"
        "print('PANDAS_LOADED=' + str(any(name == 'pandas' or name.startswith('pandas.') for name in sys.modules)))\n"
        "print('MATPLOTLIB_LOADED=' + str(any(name == 'matplotlib' or name.startswith('matplotlib.') for name in sys.modules)))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=True,
    )

    stdout = result.stdout.decode("utf-8", errors="replace")
    assert "EXCEL_TOOLS_LOADED=False" in stdout
    assert "PANDAS_LOADED=False" in stdout
    assert "MATPLOTLIB_LOADED=False" in stdout


def test_excel_tools_import_keeps_heavy_modules_lazy() -> None:
    _assert_excel_source_import_keeps_heavy_modules_lazy()


def test_tool_registry_import_does_not_load_excel_implementation() -> None:
    _assert_tool_registry_import_does_not_load_excel_implementation()


def test_read_csv_imports_pandas_on_demand(tmp_path, monkeypatch, caplog) -> None:
    csv_path = tmp_path / "source-secret-token.csv"
    csv_path.write_text("name,value\nalpha,1\nbeta,\n", encoding="utf-8")
    monkeypatch.setenv(excel_tools.ALLOWED_TABLE_ROOTS_ENV, str(tmp_path))
    excel_tools._pd = None
    excel_tools._np = None
    excel_tools._pandas_import_attempted = False

    with caplog.at_level(logging.INFO, logger=excel_tools.logger.name):
        result = asyncio.run(excel_tools.read_excel_file(str(csv_path)))

    assert excel_tools._pandas_import_attempted is True
    assert result["shape"] == [2, 2]
    assert result["sample_data"][0] == {"name": "alpha", "value": 1.0}
    assert result["sample_data"][1] == {"name": "beta", "value": None}

    records = [
        record
        for record in caplog.records
        if record.name == excel_tools.logger.name
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted file_path; length=" in log_text
    assert "secret-token" not in log_text


def test_read_excel_error_log_summarizes_path_without_exc_info(caplog) -> None:
    file_path = r"C:\private\secret-token\source.xlsx"

    with caplog.at_level(logging.ERROR, logger=excel_tools.logger.name):
        result = asyncio.run(excel_tools.read_excel_file(file_path))

    assert "secret-token" in result["error"] or "secret-token" in result["file_path"]
    records = [
        record
        for record in caplog.records
        if record.name == excel_tools.logger.name
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert f"<redacted file_path; length={len(file_path)}>" in log_text
    assert "<redacted read_error; length=" in log_text
    assert file_path not in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_clean_dataframe_logs_rules_and_errors_as_summaries(monkeypatch, caplog) -> None:
    rules = {"fill_value": "secret-token", "handle_nulls": "fill"}

    monkeypatch.setattr(excel_tools, "_get_pandas_numpy", lambda: (object(), object()))
    monkeypatch.setattr(
        excel_tools,
        "_build_dataframe_from_payload",
        lambda _payload: (_ for _ in ()).throw(RuntimeError("clean echoed secret-token")),
    )

    with caplog.at_level(logging.INFO, logger=excel_tools.logger.name):
        result = asyncio.run(excel_tools.clean_dataframe({"records": []}, rules))

    assert "secret-token" in result["error"]
    records = [
        record
        for record in caplog.records
        if record.name == excel_tools.logger.name
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert "<redacted cleaning_rules; length=" in log_text
    assert "<redacted clean_error; length=" in log_text
    assert "secret-token" not in log_text
    assert str(rules) not in log_text
    assert all(record.exc_info is None for record in records)


def test_generate_chart_logs_columns_title_and_errors_as_summaries(monkeypatch, caplog) -> None:
    class FakePyplot:
        def close(self):
            return None

    chart_type = "bar"
    x_column = "private-x-secret-token"
    y_column = "private-y-secret-token"
    title = "private chart secret-token"

    monkeypatch.setattr(excel_tools, "_get_pandas_numpy", lambda: (object(), None))
    monkeypatch.setattr(excel_tools, "_get_pyplot", lambda: FakePyplot())
    monkeypatch.setattr(
        excel_tools,
        "_build_dataframe_from_payload",
        lambda _payload: (_ for _ in ()).throw(RuntimeError("chart echoed secret-token")),
    )

    with caplog.at_level(logging.INFO, logger=excel_tools.logger.name):
        result = asyncio.run(
            excel_tools.generate_chart(
                {"records": []},
                chart_type,
                x_column,
                y_column,
                title,
            )
        )

    assert result == ""
    records = [
        record
        for record in caplog.records
        if record.name == excel_tools.logger.name
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert f"<redacted chart_type; length={len(chart_type)}>" in log_text
    assert f"<redacted x_column; length={len(x_column)}>" in log_text
    assert f"<redacted y_column; length={len(y_column)}>" in log_text
    assert f"<redacted title; length={len(title)}>" in log_text
    assert "<redacted chart_error; length=" in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)


def test_excel_analysis_workflow_logs_reference_and_error_as_summaries(monkeypatch, caplog) -> None:
    from app.services.gemini.agent.workflows import excel_analysis_workflow as workflow_module

    class FakeAgentLLMService:
        def __init__(self, *args, **kwargs):
            pass

    class FakeWorkflowEngine:
        def __init__(self, *args, **kwargs):
            pass

        async def execute(self, *args, **kwargs):
            raise RuntimeError("workflow echoed secret-token")

    file_reference = "https://cdn.example.test/private/source.xlsx?token=secret-token"

    monkeypatch.setattr(workflow_module, "AgentLLMService", FakeAgentLLMService)
    monkeypatch.setattr(workflow_module, "WorkflowEngine", FakeWorkflowEngine)

    workflow = workflow_module.ExcelAnalysisWorkflow(db=object(), user_id="user-1")
    with caplog.at_level(logging.INFO, logger=workflow_module.logger.name):
        result = asyncio.run(
            workflow.execute(
                file_reference=file_reference,
                analysis_type="statistics",
                cleaning_rules={"fill_value": "secret-token"},
            )
        )

    assert result["success"] is False
    assert result["file_reference"] == file_reference
    assert "secret-token" in result["error"]

    records = [
        record
        for record in caplog.records
        if record.name == workflow_module.logger.name
    ]
    assert records
    log_text = "\n".join(record.getMessage() for record in records)
    assert f"<redacted file_reference; length={len(file_reference)}>" in log_text
    assert "<redacted workflow_error; length=" in log_text
    assert file_reference not in log_text
    assert "secret-token" not in log_text
    assert all(record.exc_info is None for record in records)
