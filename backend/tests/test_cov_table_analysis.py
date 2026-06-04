"""Coverage-focused tests for app.services.common.table_analysis_service.

This module is a set of pure functions that parse CSV/XLSX bytes via pandas
and produce structured analysis + markdown. pandas/openpyxl are real, available
dependencies in this venv, so we exercise genuine end-to-end behavior. We mock
only the dependency-absence boundaries (ImportError paths) which cannot be
triggered otherwise.
"""

from __future__ import annotations

# Import pandas (which fully initializes numpy's C extensions) BEFORE importing
# the `app` package. Under `coverage`, importing `app` first pulls numpy into a
# partially-initialized state, and pandas' later hard-dependency re-import of
# numpy then raises "cannot load module more than once per process". Loading
# pandas first makes numpy fully resident in sys.modules so every later
# `import pandas` inside the SUT is a cache hit.
import pandas as _pandas  # noqa: F401,E402

import base64  # noqa: E402
import io  # noqa: E402

import pytest  # noqa: E402

import app.services.common.table_analysis_service as tas  # noqa: E402
from app.services.common.table_analysis_service import (
    InvalidTableInputError,
    TableAnalysisDependencyError,
    UnsupportedTableFormatError,
    _build_correlation_summary,
    _build_quality_flags,
    _resolve_table_format,
    _safe_float,
    _safe_ratio,
    _stringify_list,
    _to_json_value,
    analyze_inline_table_content,
    analyze_table_bytes,
    export_table_analysis,
    render_table_analysis_markdown,
)


# --------------------------------------------------------------------------
# Helpers to build real table bytes
# --------------------------------------------------------------------------
def _csv_bytes(text: str, encoding: str = "utf-8") -> bytes:
    return text.encode(encoding)


def _rich_csv() -> bytes:
    # Numeric (with an outlier), categorical, datetime, and a correlated pair.
    rows = [
        "id,amount,score,category,event_date",
        "1,10,100,alpha,2023-01-01",
        "2,20,200,beta,2023-01-05",
        "3,30,300,alpha,2023-01-10",
        "4,40,400,beta,2023-01-15",
        "5,5000,500,alpha,2023-01-20",  # amount outlier
        "6,60,600,beta,2023-02-01",
    ]
    return _csv_bytes("\n".join(rows))


def _xlsx_bytes() -> bytes:
    pd = __import__("pandas")
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, 4],
            "b": [10, 20, 30, 40],
            "label": ["x", "y", "x", "z"],
        }
    )
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    return buffer.getvalue()


# --------------------------------------------------------------------------
# _resolve_table_format
# --------------------------------------------------------------------------
def test_resolve_format_from_explicit_format():
    assert _resolve_table_format(None, "CSV") == "csv"
    assert _resolve_table_format(None, "  XLSX ") == "xlsx"


def test_resolve_format_from_filename_extension():
    assert _resolve_table_format("data.csv", None) == "csv"
    assert _resolve_table_format("report.XLSX", None) == "xlsx"


def test_resolve_format_explicit_wins_over_filename():
    assert _resolve_table_format("data.xlsx", "csv") == "csv"


def test_resolve_format_unsupported_raises():
    with pytest.raises(UnsupportedTableFormatError):
        _resolve_table_format("data.txt", None)
    with pytest.raises(UnsupportedTableFormatError):
        _resolve_table_format(None, "parquet")
    with pytest.raises(UnsupportedTableFormatError):
        _resolve_table_format("noextension", None)


# --------------------------------------------------------------------------
# _to_json_value, _safe_ratio, _safe_float, _stringify_list
# --------------------------------------------------------------------------
def test_to_json_value_none_and_primitives():
    assert _to_json_value(None) is None
    assert _to_json_value("hello") == "hello"
    assert _to_json_value(7) == 7
    assert _to_json_value(True) is True


def test_to_json_value_nan_and_inf_become_none():
    assert _to_json_value(float("nan")) is None
    assert _to_json_value(float("inf")) is None
    assert _to_json_value(3.5) == 3.5


def test_to_json_value_numpy_scalar_uses_item():
    np = __import__("numpy")
    assert _to_json_value(np.int64(42)) == 42
    assert _to_json_value(np.float64(1.25)) == 1.25


def test_to_json_value_bytes_decoded():
    assert _to_json_value(b"abc") == "abc"
    # invalid utf-8 falls back to replacement decoding
    assert isinstance(_to_json_value(b"\xff\xfe"), str)


def test_to_json_value_datetime_isoformat():
    from datetime import datetime

    out = _to_json_value(datetime(2023, 1, 1, 12, 0, 0))
    assert out.startswith("2023-01-01T12:00:00")


def test_to_json_value_falls_back_to_str():
    class Weird:
        def __str__(self) -> str:
            return "weird-object"

    assert _to_json_value(Weird()) == "weird-object"


def test_safe_ratio_zero_denominator():
    assert _safe_ratio(5, 0) == 0.0
    assert _safe_ratio(5, -1) == 0.0


def test_safe_ratio_rounding():
    assert _safe_ratio(1, 3) == 0.333333


def test_safe_float_variants():
    assert _safe_float(None) is None
    assert _safe_float("not-a-number") is None
    assert _safe_float(float("nan")) is None
    assert _safe_float(2) == 2.0
    assert _safe_float(1.23456789) == 1.234568


def test_stringify_list_truncates_and_skips_none():
    values = [1, None, 2, 3, 4, 5, 6, 7]
    out = _stringify_list(values)
    # None skipped, first 5 of remaining joined
    assert out == "1, 2, 3, 4, 5"


# --------------------------------------------------------------------------
# analyze_table_bytes - happy path (CSV) with full summary surface
# --------------------------------------------------------------------------
def test_analyze_csv_full_surface():
    result = analyze_table_bytes(
        _rich_csv(),
        file_name="data.csv",
        sample_rows=3,
    )

    summary = result["summary"]
    assert summary["row_count"] == 6
    assert summary["column_count"] == 5
    assert summary["numeric_column_count"] >= 2  # id, amount, score
    assert summary["duplicate_row_count"] == 0

    # fields present for every column
    field_names = {f["name"] for f in result["fields"]}
    assert {"id", "amount", "score", "category", "event_date"} <= field_names

    # numeric summary computed for numeric columns
    assert "amount" in result["numeric_summary"]
    amount_stats = result["numeric_summary"]["amount"]
    assert amount_stats["count"] == 6
    assert amount_stats["max"] == 5000.0
    assert amount_stats["min"] == 10.0

    # categorical summary for category column
    assert "category" in result["categorical_summary"]
    cat = result["categorical_summary"]["category"]
    assert cat["non_null_count"] == 6
    assert cat["unique_count"] == 2
    assert any(tv["value"] in ("alpha", "beta") for tv in cat["top_values"])

    # datetime summary detected for event_date
    assert "event_date" in result["datetime_summary"]
    dt = result["datetime_summary"]["event_date"]
    assert dt["non_null_count"] == 6
    assert dt["span_days"] is not None

    # outlier summary catches the amount outlier (5000)
    assert "amount" in result["outlier_summary"]
    assert result["outlier_summary"]["amount"]["outlier_count"] >= 1

    # correlation summary computed (id, amount, score numeric)
    corr = result["correlation_summary"]
    assert corr["pair_count"] >= 1
    assert isinstance(corr["top_pairs"], list)

    # sample rows respect sample_rows cap
    assert len(result["sample_rows"]) == 3
    assert result["evidence"]["sampling"]["sample_row_count"] == 3

    # evidence metadata
    assert result["evidence"]["source"]["format"] == "csv"
    assert result["evidence"]["source"]["filename"] == "data.csv"
    assert result["evidence"]["parser"]["csv_encoding"] == "utf-8"
    assert result["evidence"]["parser"]["sheet_name"] is None
    assert "generated_at" in result["evidence"]

    # column groups
    assert set(result["column_groups"]["numeric"]) >= {"id", "amount", "score"}


def test_analyze_csv_with_missing_values_and_duplicates():
    rows = [
        "name,value",
        "a,1",
        "a,1",  # duplicate row
        "b,",  # missing value
        ",3",  # missing name
    ]
    result = analyze_table_bytes(_csv_bytes("\n".join(rows)), file_format="csv")
    summary = result["summary"]
    assert summary["row_count"] == 4
    assert summary["duplicate_row_count"] == 1
    assert summary["missing_cell_count"] >= 2
    assert 0.0 < summary["missing_cell_rate"] <= 1.0

    # quality flags reflect missing columns
    qf = result["quality_flags"]
    assert qf["duplicate_row_count"] == 1
    assert isinstance(qf["high_missing_fields"], list)


def test_analyze_csv_default_filename_when_none():
    result = analyze_table_bytes(_csv_bytes("a,b\n1,2"), file_format="csv")
    assert result["evidence"]["source"]["filename"] == "inline_input"


def test_analyze_empty_bytes_raises():
    with pytest.raises(InvalidTableInputError):
        analyze_table_bytes(b"", file_format="csv")


def test_analyze_invalid_csv_decode_error():
    # byte 0xff is invalid utf-8 when forced as utf-8
    with pytest.raises(InvalidTableInputError):
        analyze_table_bytes(b"col\n\xff\xfe", file_format="csv", csv_encoding="utf-8")


def test_analyze_sample_rows_clamped_to_minimum():
    # sample_rows=0 should clamp to at least 1
    result = analyze_table_bytes(_csv_bytes("a,b\n1,2\n3,4"), file_format="csv", sample_rows=0)
    assert len(result["sample_rows"]) >= 1


# --------------------------------------------------------------------------
# analyze_table_bytes - XLSX happy path
# --------------------------------------------------------------------------
def test_analyze_xlsx_full_surface():
    result = analyze_table_bytes(_xlsx_bytes(), file_name="book.xlsx", sheet_name=0)
    assert result["summary"]["row_count"] == 4
    assert result["evidence"]["source"]["format"] == "xlsx"
    assert result["evidence"]["parser"]["sheet_name"] == 0
    assert result["evidence"]["parser"]["csv_encoding"] is None
    assert "a" in result["numeric_summary"]
    assert "label" in result["categorical_summary"]


# --------------------------------------------------------------------------
# analyze_inline_table_content
# --------------------------------------------------------------------------
def test_inline_plain_csv():
    result = analyze_inline_table_content(
        file_name="inline.csv",
        content="x,y\n1,2\n3,4",
    )
    assert result["summary"]["row_count"] == 2
    assert result["evidence"]["source"]["filename"] == "inline.csv"


def test_inline_base64_csv():
    raw = "x,y\n1,2\n3,4"
    encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    result = analyze_inline_table_content(
        file_name="inline.csv",
        content=encoded,
        content_encoding="base64",
    )
    assert result["summary"]["row_count"] == 2


def test_inline_invalid_base64_raises():
    with pytest.raises(InvalidTableInputError):
        analyze_inline_table_content(
            file_name="inline.csv",
            content="!!!not base64!!!",
            content_encoding="base64",
        )


def test_inline_xlsx_plain_rejected():
    with pytest.raises(InvalidTableInputError):
        analyze_inline_table_content(
            file_name="book.xlsx",
            content="not-allowed-plain",
            content_encoding="plain",
        )


def test_inline_xlsx_base64_roundtrip():
    encoded = base64.b64encode(_xlsx_bytes()).decode("ascii")
    result = analyze_inline_table_content(
        file_name="book.xlsx",
        content=encoded,
        content_encoding="base64",
    )
    assert result["summary"]["row_count"] == 4


# --------------------------------------------------------------------------
# _build_correlation_summary direct (edge: < 2 numeric columns)
# --------------------------------------------------------------------------
def test_correlation_summary_too_few_columns():
    pd = __import__("pandas")
    df = pd.DataFrame({"only": [1, 2, 3]})
    out = _build_correlation_summary(df, ["only"])
    assert out == {"pair_count": 0, "strong_pair_count": 0, "top_pairs": []}


def test_correlation_summary_strong_pair_detected():
    pd = __import__("pandas")
    # perfectly correlated columns
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [2, 4, 6, 8, 10]})
    out = _build_correlation_summary(df, ["a", "b"])
    assert out["pair_count"] == 1
    assert out["strong_pair_count"] == 1
    assert out["top_pairs"][0]["direction"] == "positive"
    assert out["top_pairs"][0]["absolute_correlation"] >= 0.7


def test_correlation_summary_negative_direction():
    pd = __import__("pandas")
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [10, 8, 6, 4, 2]})
    out = _build_correlation_summary(df, ["a", "b"])
    assert out["top_pairs"][0]["direction"] == "negative"


# --------------------------------------------------------------------------
# _build_quality_flags direct
# --------------------------------------------------------------------------
def test_quality_flags_classification():
    fields = [
        {"name": "id", "missing_rate": 0.0, "non_null_count": 10, "unique_count": 10},
        {"name": "mid", "missing_rate": 0.3, "non_null_count": 7, "unique_count": 5},
        {"name": "sparse", "missing_rate": 0.6, "non_null_count": 4, "unique_count": 3},
        {"name": "", "missing_rate": 0.9},  # skipped (no name)
        "not-a-dict",  # skipped
    ]
    out = _build_quality_flags(fields=fields, row_count=10, duplicate_row_count=2)
    assert out["duplicate_row_count"] == 2
    assert out["duplicate_row_rate"] == _safe_ratio(2, 10)
    assert "mid" in out["high_missing_fields"]
    assert "sparse" in out["high_missing_fields"]
    assert "sparse" in out["sparse_fields"]
    assert "mid" not in out["sparse_fields"]
    assert "id" in out["candidate_key_fields"]


# --------------------------------------------------------------------------
# render_table_analysis_markdown
# --------------------------------------------------------------------------
def test_render_markdown_full():
    analysis = analyze_table_bytes(_rich_csv(), file_name="data.csv")
    md = render_table_analysis_markdown(analysis)
    assert "# Table Analysis Report" in md
    assert "## Summary" in md
    assert "## Field Summary" in md
    assert "## Numeric Summary" in md
    assert "## Categorical Summary" in md
    assert "## Datetime Summary" in md
    assert "## Outlier Summary" in md
    assert "## Correlation Summary" in md
    assert "## Quality Flags" in md
    assert "## Sample Rows" in md
    assert "## Evidence" in md
    # table headers present
    assert "| Field | Type |" in md


def test_render_markdown_empty_sections():
    # minimal analysis: no numeric/categorical/datetime/outlier/correlation data
    analysis = {
        "summary": {"row_count": 0, "column_count": 0},
        "fields": [],
        "numeric_summary": {},
        "categorical_summary": {},
        "datetime_summary": {},
        "outlier_summary": {},
        "correlation_summary": {"top_pairs": []},
        "quality_flags": {},
        "sample_rows": [],
        "evidence": {"source": {}},
    }
    md = render_table_analysis_markdown(analysis)
    assert "No numeric columns detected." in md
    assert "No categorical columns detected." in md
    assert "No datetime-like columns detected." in md
    assert "No numeric outliers detected by IQR rule." in md
    assert "No numeric correlation pairs detected." in md


def test_render_markdown_none_optional_sections_default_to_empty():
    analysis = {
        "summary": {"row_count": 1, "column_count": 1},
        "fields": [{"name": "a", "dtype": "int64", "missing_rate": 0.0}],
        "numeric_summary": {},
        "categorical_summary": None,
        "datetime_summary": None,
        "outlier_summary": None,
        "correlation_summary": None,
        "quality_flags": None,
        "sample_rows": [],
        "evidence": {"source": {}},
    }
    md = render_table_analysis_markdown(analysis)
    assert "No categorical columns detected." in md
    assert "## Quality Flags" in md


@pytest.mark.parametrize(
    "missing_key",
    ["summary", "fields", "numeric_summary", "sample_rows", "evidence"],
)
def test_render_markdown_missing_required_keys_raise(missing_key):
    analysis = {
        "summary": {"row_count": 0},
        "fields": [],
        "numeric_summary": {},
        "categorical_summary": {},
        "datetime_summary": {},
        "outlier_summary": {},
        "correlation_summary": {},
        "quality_flags": {},
        "sample_rows": [],
        "evidence": {"source": {}},
    }
    analysis.pop(missing_key)
    with pytest.raises(InvalidTableInputError):
        render_table_analysis_markdown(analysis)


@pytest.mark.parametrize(
    "bad_key,bad_value",
    [
        ("summary", "not-a-dict"),
        ("fields", "not-a-list"),
        ("numeric_summary", "not-a-dict"),
        ("categorical_summary", "not-a-dict"),
        ("datetime_summary", 123),
        ("outlier_summary", 123),
        ("correlation_summary", 123),
        ("quality_flags", 123),
        ("sample_rows", "not-a-list"),
        ("evidence", "not-a-dict"),
    ],
)
def test_render_markdown_wrong_types_raise(bad_key, bad_value):
    analysis = {
        "summary": {"row_count": 0},
        "fields": [],
        "numeric_summary": {},
        "categorical_summary": {},
        "datetime_summary": {},
        "outlier_summary": {},
        "correlation_summary": {},
        "quality_flags": {},
        "sample_rows": [],
        "evidence": {"source": {}},
    }
    analysis[bad_key] = bad_value
    with pytest.raises(InvalidTableInputError):
        render_table_analysis_markdown(analysis)


def test_render_markdown_with_populated_summaries():
    # Hand-built analysis to drive table-row rendering branches.
    analysis = {
        "summary": {
            "row_count": 5,
            "column_count": 3,
            "missing_cell_count": 1,
            "missing_cell_rate": 0.06,
            "duplicate_row_count": 0,
            "numeric_column_count": 1,
            "categorical_column_count": 1,
            "datetime_column_count": 1,
            "correlation_pair_count": 1,
            "strong_correlation_pair_count": 1,
        },
        "fields": [
            {
                "name": "a",
                "dtype": "int64",
                "missing_rate": 0.0,
                "missing_count": 0,
                "non_null_count": 5,
                "unique_count": 5,
                "sample_values": [1, 2, 3],
            },
            "skip-non-dict-field",
        ],
        "numeric_summary": {
            "a": {
                "count": 5,
                "mean": 3.0,
                "std": 1.5,
                "min": 1,
                "p25": 2,
                "p50": 3,
                "p75": 4,
                "max": 5,
            },
            "bad": "not-a-dict",
        },
        "categorical_summary": {
            "cat": {
                "non_null_count": 5,
                "unique_count": 2,
                "top_values": [
                    {"value": "x", "count": 3},
                    "skip-non-dict",
                ],
            },
            "bad": "not-a-dict",
        },
        "datetime_summary": {
            "dt": {"non_null_count": 5, "min": "2023-01-01", "max": "2023-02-01", "span_days": 31.0},
            "bad": "not-a-dict",
        },
        "outlier_summary": {
            "a": {
                "count": 5,
                "outlier_count": 1,
                "outlier_rate": 0.2,
                "iqr_lower": 0,
                "iqr_upper": 6,
            },
            "bad": "not-a-dict",
        },
        "correlation_summary": {
            "top_pairs": [
                {"left": "a", "right": "b", "correlation": 0.9, "direction": "positive"},
                "skip-non-dict",
            ]
        },
        "quality_flags": {
            "duplicate_row_count": 0,
            "high_missing_fields": ["x"],
            "sparse_fields": [],
            "candidate_key_fields": ["a"],
        },
        "sample_rows": [{"a": 1}],
        "evidence": {"source": {"filename": "f.csv"}},
    }
    md = render_table_analysis_markdown(analysis)
    assert "| a | int64 |" in md
    assert "x (3)" in md  # categorical top value rendering
    assert "positive" in md  # correlation direction
    assert "Candidate Key Fields: a" in md


# --------------------------------------------------------------------------
# export_table_analysis
# --------------------------------------------------------------------------
def test_export_json_returns_same_object():
    analysis = analyze_table_bytes(_csv_bytes("a,b\n1,2"), file_format="csv")
    assert export_table_analysis(analysis, "json") is analysis


def test_export_markdown_returns_string():
    analysis = analyze_table_bytes(_csv_bytes("a,b\n1,2"), file_format="csv")
    out = export_table_analysis(analysis, "markdown")
    assert isinstance(out, str)
    assert out.startswith("# Table Analysis Report")


def test_export_unsupported_format_raises():
    analysis = analyze_table_bytes(_csv_bytes("a,b\n1,2"), file_format="csv")
    with pytest.raises(InvalidTableInputError):
        export_table_analysis(analysis, "xml")  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Dependency-absence boundaries (mock-only ImportError paths)
# --------------------------------------------------------------------------
def test_missing_pandas_raises_dependency_error(monkeypatch):
    # Setting sys.modules["pandas"] = None makes `import pandas` raise ImportError
    # without globally patching builtins.__import__ (which corrupts numpy's lazy
    # C-extension imports under coverage tracing). monkeypatch restores it after.
    import sys

    monkeypatch.setitem(sys.modules, "pandas", None)
    with pytest.raises(TableAnalysisDependencyError):
        tas._ensure_pandas()


def test_xlsx_missing_openpyxl_value_error(monkeypatch):
    pd = __import__("pandas")

    def fake_read_excel(*args, **kwargs):
        raise ValueError("Missing optional dependency 'openpyxl'.")

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)
    with pytest.raises(TableAnalysisDependencyError):
        analyze_table_bytes(b"fake-xlsx-bytes", file_format="xlsx")


def test_xlsx_import_error_maps_to_dependency_error(monkeypatch):
    pd = __import__("pandas")

    def fake_read_excel(*args, **kwargs):
        raise ImportError("openpyxl not found")

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)
    with pytest.raises(TableAnalysisDependencyError):
        analyze_table_bytes(b"fake-xlsx-bytes", file_format="xlsx")


def test_xlsx_generic_value_error_maps_to_invalid_input(monkeypatch):
    pd = __import__("pandas")

    def fake_read_excel(*args, **kwargs):
        raise ValueError("totally broken workbook")

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)
    with pytest.raises(InvalidTableInputError):
        analyze_table_bytes(b"fake-xlsx-bytes", file_format="xlsx")


def test_xlsx_generic_exception_maps_to_invalid_input(monkeypatch):
    pd = __import__("pandas")

    def fake_read_excel(*args, **kwargs):
        raise RuntimeError("corrupt")

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)
    with pytest.raises(InvalidTableInputError):
        analyze_table_bytes(b"fake-xlsx-bytes", file_format="xlsx")
