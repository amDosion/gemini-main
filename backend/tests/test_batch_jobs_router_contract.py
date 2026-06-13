from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.tools import batch_jobs


def _progress_payload(status: str = "queued"):
    return {
        "job_id": "job-1",
        "status": status,
        "progress_percent": 50,
        "stop_on_error": True,
        "cancel_requested": False,
        "item_timeout_seconds": 30.0,
        "counts": {
            "total": 1,
            "pending": 0,
            "running": 1,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        },
        "created_at": 1_765_497_600_000,
        "updated_at": 1_765_497_601_000,
        "items": [
            {
                "item_id": "item-1",
                "label": "table.csv",
                "workload": "table_analysis",
                "status": "running",
                "attempts": 1,
                "error": None,
                "started_at": 1_765_497_600_500,
                "completed_at": None,
            }
        ],
    }


def _summary_payload():
    return {
        "job_id": "job-1",
        "status": "completed",
        "item_timeout_seconds": 30.0,
        "created_at": 1_765_497_600_000,
        "updated_at": 1_765_497_602_000,
        "counts": {
            "total": 1,
            "pending": 0,
            "running": 0,
            "completed": 1,
            "failed": 0,
            "cancelled": 0,
        },
        "failed_item_ids": [],
        "cancelled_item_ids": [],
        "table_metrics": {
            "total_rows": 10,
            "total_columns": 3,
        },
        "completed_items": [
            {
                "item_id": "item-1",
                "label": "table.csv",
                "workload": "table_analysis",
                "summary": {"row_count": 10, "missing_cell_rate": 0.0},
            }
        ],
    }


class FakeBatchJobOrchestrator:
    async def submit_job(self, **kwargs):
        assert kwargs["user_id"] == "user-1"
        assert kwargs["items"][0]["workload"] == "table_analysis"
        assert kwargs["item_timeout_seconds"] == 30.0
        return _progress_payload("queued")

    async def get_progress(self, **kwargs):
        assert kwargs == {"user_id": "user-1", "job_id": "job-1"}
        return _progress_payload("running")

    async def retry_job(self, **kwargs):
        assert kwargs == {"user_id": "user-1", "job_id": "job-1", "include_completed": True}
        return _progress_payload("queued")

    async def resume_job(self, **kwargs):
        assert kwargs == {"user_id": "user-1", "job_id": "job-1", "skip_failed": False}
        return _progress_payload("queued")

    async def cancel_job(self, **kwargs):
        assert kwargs == {"user_id": "user-1", "job_id": "job-1"}
        return _progress_payload("cancelled")

    async def get_summary(self, **kwargs):
        assert kwargs == {"user_id": "user-1", "job_id": "job-1"}
        return _summary_payload()


def _client(monkeypatch):
    app = FastAPI()
    app.include_router(batch_jobs.router)
    app.dependency_overrides[batch_jobs.require_current_user] = lambda: "user-1"
    monkeypatch.setattr(batch_jobs, "_batch_job_orchestrator", FakeBatchJobOrchestrator())
    return TestClient(app)


def test_batch_submit_response_model(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.post(
            "/api/batch-jobs/submit",
            json={
                "items": [
                    {
                        "workload": "table_analysis",
                        "file_name": "table.csv",
                        "content": "a,b\n1,2",
                    }
                ],
                "item_timeout_seconds": 30,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "job-1"
    assert body["counts"]["total"] == 1
    assert body["items"][0]["item_id"] == "item-1"


def test_batch_progress_transition_response_models(monkeypatch):
    with _client(monkeypatch) as client:
        progress = client.get("/api/batch-jobs/job-1/progress")
        retry = client.post("/api/batch-jobs/job-1/retry", json={"include_completed": True})
        resume = client.post("/api/batch-jobs/job-1/resume", json={"skip_failed": False})
        cancel = client.post("/api/batch-jobs/job-1/cancel")

    assert progress.status_code == 200
    assert progress.json()["status"] == "running"
    assert retry.status_code == 200
    assert retry.json()["status"] == "queued"
    assert resume.status_code == 200
    assert resume.json()["status"] == "queued"
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"


def test_batch_summary_response_model_preserves_summary_json(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/api/batch-jobs/job-1/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["table_metrics"] == {"total_rows": 10, "total_columns": 3}
    assert body["completed_items"][0]["summary"] == {
        "row_count": 10,
        "missing_cell_rate": 0.0,
    }
