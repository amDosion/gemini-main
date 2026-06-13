from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from app.services.agent.workflow_engine import references


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _assert_import_does_not_load_pandas(module_name: str) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_ROOT)
    code = (
        "import importlib, sys\n"
        "sys.modules.pop('pandas', None)\n"
        f"importlib.import_module({module_name!r})\n"
        "print('PANDAS_LOADED=' + str('pandas' in sys.modules))\n"
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


def test_references_import_does_not_load_pandas() -> None:
    _assert_import_does_not_load_pandas("app.services.agent.workflow_engine.references")


def test_workflow_engine_import_does_not_load_pandas() -> None:
    _assert_import_does_not_load_pandas("app.services.agent.workflow_engine.engine")


def test_app_main_import_does_not_load_pandas() -> None:
    _assert_import_does_not_load_pandas("app.main")


def test_amazon_ads_import_does_not_load_pandas() -> None:
    _assert_import_does_not_load_pandas("app.services.agent.workflow_engine.amazon_ads")


def test_reference_table_parsing_imports_pandas_on_demand() -> None:
    references._pd = None
    references._pd_import_attempted = False

    frame = references.text_to_dataframe(SimpleNamespace(), "a,b\n1,2\n")

    assert references._pd_import_attempted is True
    assert list(frame.columns) == ["a", "b"]
    assert frame.iloc[0].to_dict() == {"a": 1, "b": 2}


def test_text_file_reference_context_does_not_import_pandas() -> None:
    references._pd = None
    references._pd_import_attempted = False
    raw = base64.b64encode(b"plain text payload").decode("ascii")
    engine = SimpleNamespace(
        _decode_data_url=lambda _ref: ("text/plain", b"plain text payload"),
        _looks_like_excel_binary=lambda **_kwargs: False,
        _decode_bytes_to_text=lambda payload: payload.decode("utf-8"),
        _build_text_preview=lambda text, **_kwargs: text,
    )

    context = references.build_file_reference_context(
        engine,
        f"data:text/plain;base64,{raw}",
    )

    assert references._pd_import_attempted is False
    assert "plain text payload" in context
