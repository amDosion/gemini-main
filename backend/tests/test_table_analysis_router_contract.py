from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.tools import table_analysis


def _analysis_payload():
    return {
        "summary": {"row_count": 1, "column_count": 2},
        "fields": [{"name": "sku", "dtype": "object"}],
        "numeric_summary": {},
        "categorical_summary": {},
        "datetime_summary": {},
        "outlier_summary": {},
        "correlation_summary": {},
        "quality_flags": {},
        "column_groups": {},
        "sample_rows": [{"sku": "A1", "qty": 2}],
        "evidence": {"format": "csv"},
    }


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(table_analysis.router)
    app.dependency_overrides[table_analysis.require_current_user] = lambda: "user-1"
    return TestClient(app)


def test_inline_analysis_uses_typed_response_model(monkeypatch):
    def fake_analyze_inline_table_content(**kwargs):
        assert kwargs["file_name"] == "table.csv"
        assert kwargs["content"] == "sku,qty\nA1,2"
        assert kwargs["sample_rows"] == 5
        return _analysis_payload()

    monkeypatch.setattr(
        table_analysis,
        "analyze_inline_table_content",
        fake_analyze_inline_table_content,
    )

    with _client() as client:
        response = client.post(
            "/api/table/analysis/inline",
            json={"file_name": "table.csv", "content": "sku,qty\nA1,2"},
        )

    assert response.status_code == 200
    assert response.json()["fields"] == [{"name": "sku", "dtype": "object"}]
    assert response.json()["sample_rows"] == [{"sku": "A1", "qty": 2}]


def test_export_analysis_returns_markdown_media_type(monkeypatch):
    def fake_export_table_analysis(*, analysis, export_format):
        assert analysis == _analysis_payload()
        assert export_format == "markdown"
        return "# Table analysis\n"

    monkeypatch.setattr(table_analysis, "export_table_analysis", fake_export_table_analysis)

    with _client() as client:
        response = client.post(
            "/api/table/analysis/export",
            json={"format": "markdown", "analysis": _analysis_payload()},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.text == "# Table analysis\n"


def test_export_analysis_returns_json_media_type(monkeypatch):
    def fake_export_table_analysis(*, analysis, export_format):
        assert analysis == _analysis_payload()
        assert export_format == "json"
        return _analysis_payload()

    monkeypatch.setattr(table_analysis, "export_table_analysis", fake_export_table_analysis)

    with _client() as client:
        response = client.post(
            "/api/table/analysis/export",
            json={"format": "json", "analysis": _analysis_payload()},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["summary"] == {"row_count": 1, "column_count": 2}
