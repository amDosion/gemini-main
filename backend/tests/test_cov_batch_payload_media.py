"""Coverage-focused genuine tests for two service helpers.

Modules under test (SUT):
  - app.services.common.batch_job_orchestrator
        In-memory async batch queue: submit/validate, drain worker, partial
        success vs stop-on-error, retry/resume/cancel state transitions,
        per-item timeout, progress/summary serialization, user scoping.
  - app.services.agent.workflow_engine.payload_media
        Pure-ish payload/reference/media-url helpers extracted from
        WorkflowEngine: image/file/video/audio URL normalization & extraction,
        provider reference image rewriting, SSRF guard helpers, generic path
        resolution, source-video packing, agent reference resolution, arg coercion.

Strategy
--------
* batch_job_orchestrator: drive the REAL ``BatchJobOrchestrator`` end-to-end
  with in-process handlers (sync, async, raising, slow). The drain task runs on
  the live event loop; we ``await`` ``orchestrator._drain_task`` to deterministically
  let the queue empty, then assert real status/counts. Only the *handlers* are
  test doubles — orchestration, queue, locking, finalization logic is real.

* payload_media: every public function takes the live ``WorkflowEngine`` as its
  first arg and delegates recursion back through ``engine._<helper>`` — which are
  the very same module functions bound onto the engine. So we build ONE real
  ``WorkflowEngine`` (db = trivial fake, no provider calls) and call the helpers
  directly. We mock ONLY ``engine._load_binary_from_reference`` (filesystem/network
  boundary) for the provider-reference rewrite path. Everything else is real.

asyncio_mode=auto (plain ``async def`` tests run). filterwarnings=error::RuntimeWarning
is active, so every coroutine boundary is awaited.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import app.services.common.batch_job_orchestrator as bjo
from app.services.common.batch_job_orchestrator import (
    BatchJobConflictError,
    BatchJobDependencyError,
    BatchJobNotFoundError,
    BatchJobOrchestrator,
    BatchJobValidationError,
    create_batch_job_orchestrator,
)
from app.services.agent.workflow_engine import WorkflowEngine
from app.services.agent.workflow_engine import payload_media as pm
from app.services.agent.execution_context import ExecutionContext


# ===========================================================================
# Fixtures / helpers
# ===========================================================================


class _FakeQuery:
    def filter(self, *a, **k):
        return self

    def first(self):
        return None


class _FakeDb:
    def query(self, _model):
        return _FakeQuery()


def _make_engine(user_id="media-user") -> WorkflowEngine:
    return WorkflowEngine(db=_FakeDb(), llm_service=SimpleNamespace(user_id=user_id))


@pytest.fixture
def engine() -> WorkflowEngine:
    return _make_engine()


async def _drain(orchestrator: BatchJobOrchestrator) -> None:
    """Deterministically wait for the live drain task to finish processing."""
    task = orchestrator._drain_task
    if task is not None:
        await task


def _echo_handler(payload):
    return {"echo": payload}


async def _async_echo_handler(payload):
    await asyncio.sleep(0)
    return {"echo_async": payload}


def _table_handler(payload):
    return {
        "summary": {
            "row_count": int(payload.get("rows", 0)),
            "column_count": int(payload.get("cols", 0)),
            "missing_cell_count": 1,
            "missing_cell_rate": 0.01,
        }
    }


def _pdf_handler(payload):
    return {"success": True, "data": {"a": 1, "b": 2, "c": 3}}


def _boom_handler(payload):
    raise RuntimeError("handler exploded")


# ===========================================================================
# batch_job_orchestrator: submission validation
# ===========================================================================


@pytest.mark.asyncio
class TestSubmitValidation:
    async def test_empty_items_rejected(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        with pytest.raises(BatchJobValidationError, match="at least one item"):
            await orch.submit_job(user_id="u", items=[])

    async def test_missing_workload_rejected(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        with pytest.raises(BatchJobValidationError, match="workload is required"):
            await orch.submit_job(user_id="u", items=[{"payload": {}}])

    async def test_unsupported_workload_rejected(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        with pytest.raises(BatchJobValidationError, match="Unsupported batch workload"):
            await orch.submit_job(
                user_id="u", items=[{"workload": "nope", "payload": {}}]
            )

    async def test_non_dict_payload_rejected(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        with pytest.raises(BatchJobValidationError, match="payload must be an object"):
            await orch.submit_job(
                user_id="u", items=[{"workload": "echo", "payload": "x"}]
            )

    async def test_invalid_timeout_string_rejected(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        with pytest.raises(BatchJobValidationError, match="positive number"):
            await orch.submit_job(
                user_id="u",
                items=[{"workload": "echo", "payload": {}}],
                item_timeout_seconds="not-a-number",
            )

    async def test_non_positive_timeout_rejected(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        with pytest.raises(BatchJobValidationError, match="positive number"):
            await orch.submit_job(
                user_id="u",
                items=[{"workload": "echo", "payload": {}}],
                item_timeout_seconds=0,
            )

    async def test_register_handler_empty_workload_rejected(self):
        orch = BatchJobOrchestrator()
        with pytest.raises(BatchJobValidationError, match="workload cannot be empty"):
            orch.register_handler("  ", _echo_handler)

    async def test_register_handler_normalizes_case(self):
        orch = BatchJobOrchestrator()
        orch.register_handler("PDF_Extract", _pdf_handler)
        # workload is lowered/normalized; submission with mixed case still routes.
        snap = await orch.submit_job(
            user_id="u", items=[{"workload": "PDF_EXTRACT", "payload": {}}]
        )
        await _drain(orch)
        prog = await orch.get_progress(user_id="u", job_id=snap["job_id"])
        assert prog["status"] == "completed"


# ===========================================================================
# batch_job_orchestrator: happy path / partial success / stop-on-error
# ===========================================================================


@pytest.mark.asyncio
class TestExecutionSemantics:
    async def test_all_items_complete(self):
        orch = create_batch_job_orchestrator(handlers={"echo": _echo_handler})
        snap = await orch.submit_job(
            user_id="u",
            items=[
                {"workload": "echo", "payload": {"i": 1}, "label": "first"},
                {"workload": "echo", "payload": {"i": 2}},
            ],
        )
        assert snap["status"] in {"queued", "running"}
        await _drain(orch)
        prog = await orch.get_progress(user_id="u", job_id=snap["job_id"])
        assert prog["status"] == "completed"
        assert prog["progress_percent"] == 100
        assert prog["counts"]["completed"] == 2
        assert prog["counts"]["failed"] == 0
        # explicit label preserved, missing label falls back to workload.
        assert prog["items"][0]["label"] == "first"
        assert prog["items"][1]["label"] == "echo"
        assert prog["items"][0]["attempts"] == 1

    async def test_async_handler_executes(self):
        orch = BatchJobOrchestrator(handlers={"echo": _async_echo_handler})
        snap = await orch.submit_job(
            user_id="u", items=[{"workload": "echo", "payload": {"k": "v"}}]
        )
        await _drain(orch)
        prog = await orch.get_progress(user_id="u", job_id=snap["job_id"])
        assert prog["status"] == "completed"

    async def test_stop_on_error_pauses_and_skips_remaining(self):
        orch = BatchJobOrchestrator(
            handlers={"echo": _echo_handler, "boom": _boom_handler}
        )
        snap = await orch.submit_job(
            user_id="u",
            items=[
                {"workload": "boom", "payload": {}},
                {"workload": "echo", "payload": {}},
            ],
            stop_on_error=True,
        )
        await _drain(orch)
        prog = await orch.get_progress(user_id="u", job_id=snap["job_id"])
        # First item failed; with stop_on_error the job pauses, item 2 stays pending.
        assert prog["status"] == "paused"
        assert prog["counts"]["failed"] == 1
        assert prog["counts"]["pending"] == 1
        assert "handler exploded" in prog["items"][0]["error"]

    async def test_partial_success_continues_when_not_stop_on_error(self):
        orch = BatchJobOrchestrator(
            handlers={"echo": _echo_handler, "boom": _boom_handler}
        )
        snap = await orch.submit_job(
            user_id="u",
            items=[
                {"workload": "boom", "payload": {}},
                {"workload": "echo", "payload": {"ok": True}},
                {"workload": "boom", "payload": {}},
            ],
            stop_on_error=False,
        )
        await _drain(orch)
        prog = await orch.get_progress(user_id="u", job_id=snap["job_id"])
        # One success between two failures: completed item must not be lost.
        assert prog["status"] == "failed"
        assert prog["counts"]["completed"] == 1
        assert prog["counts"]["failed"] == 2
        assert prog["progress_percent"] == 100

    async def test_item_timeout_marks_failure(self):
        async def _slow(payload):
            await asyncio.sleep(5)
            return {"never": True}

        orch = BatchJobOrchestrator(handlers={"slow": _slow})
        snap = await orch.submit_job(
            user_id="u",
            items=[{"workload": "slow", "payload": {}}],
            item_timeout_seconds=0.01,
            stop_on_error=False,
        )
        await _drain(orch)
        prog = await orch.get_progress(user_id="u", job_id=snap["job_id"])
        assert prog["status"] == "failed"
        assert prog["counts"]["failed"] == 1
        assert "timed out" in prog["items"][0]["error"]


# ===========================================================================
# batch_job_orchestrator: retry / resume / cancel
# ===========================================================================


@pytest.mark.asyncio
class TestRetryResumeCancel:
    async def _run_to_paused(self):
        orch = BatchJobOrchestrator(
            handlers={"echo": _echo_handler, "boom": _boom_handler}
        )
        snap = await orch.submit_job(
            user_id="u",
            items=[
                {"workload": "boom", "payload": {}},
                {"workload": "echo", "payload": {}},
            ],
            stop_on_error=True,
        )
        await _drain(orch)
        return orch, snap["job_id"]

    async def test_retry_resets_failed_and_reruns(self):
        orch, job_id = await self._run_to_paused()
        # Swap the failing handler so retry can succeed this time.
        orch.register_handler("boom", _echo_handler)
        snap = await orch.retry_job(user_id="u", job_id=job_id)
        assert snap["status"] in {"queued", "running"}
        await _drain(orch)
        prog = await orch.get_progress(user_id="u", job_id=job_id)
        assert prog["status"] == "completed"
        assert prog["counts"]["completed"] == 2
        # The previously-failed item was retried (attempts incremented again).
        assert prog["items"][0]["attempts"] == 2

    async def test_retry_with_no_eligible_items_rejected(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        snap = await orch.submit_job(
            user_id="u", items=[{"workload": "echo", "payload": {}}]
        )
        await _drain(orch)
        # All completed, include_completed defaults to False -> nothing to retry.
        with pytest.raises(BatchJobValidationError, match="No failed/cancelled"):
            await orch.retry_job(user_id="u", job_id=snap["job_id"])

    async def test_retry_include_completed_reruns_done_items(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        snap = await orch.submit_job(
            user_id="u", items=[{"workload": "echo", "payload": {}}]
        )
        await _drain(orch)
        snap2 = await orch.retry_job(
            user_id="u", job_id=snap["job_id"], include_completed=True
        )
        assert snap2["status"] in {"queued", "running"}
        await _drain(orch)
        prog = await orch.get_progress(user_id="u", job_id=snap["job_id"])
        assert prog["items"][0]["attempts"] == 2

    async def test_resume_paused_job_runs_pending(self):
        orch, job_id = await self._run_to_paused()
        # Resume skips the failed item and runs the still-pending one.
        snap = await orch.resume_job(user_id="u", job_id=job_id, skip_failed=True)
        assert snap["status"] in {"queued", "running"}
        await _drain(orch)
        prog = await orch.get_progress(user_id="u", job_id=job_id)
        assert prog["counts"]["completed"] == 1
        assert prog["counts"]["failed"] == 1

    async def test_resume_blocked_by_failed_when_not_skipping(self):
        orch, job_id = await self._run_to_paused()
        with pytest.raises(BatchJobValidationError, match="Resume blocked by failed"):
            await orch.resume_job(user_id="u", job_id=job_id, skip_failed=False)

    async def test_resume_completed_job_rejected(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        snap = await orch.submit_job(
            user_id="u", items=[{"workload": "echo", "payload": {}}]
        )
        await _drain(orch)
        with pytest.raises(BatchJobValidationError, match="already completed"):
            await orch.resume_job(user_id="u", job_id=snap["job_id"])

    async def test_cancel_marks_pending_items_cancelled(self):
        orch, job_id = await self._run_to_paused()
        snap = await orch.cancel_job(user_id="u", job_id=job_id)
        assert snap["status"] == "cancelled"
        assert snap["cancel_requested"] is True
        prog = await orch.get_progress(user_id="u", job_id=job_id)
        assert prog["counts"]["cancelled"] >= 1
        # The already-failed item keeps its failed status, not overwritten.
        assert prog["counts"]["failed"] == 1

    async def test_cancel_already_terminal_is_idempotent(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        snap = await orch.submit_job(
            user_id="u", items=[{"workload": "echo", "payload": {}}]
        )
        await _drain(orch)
        # Completed job: cancel returns current snapshot without changing status.
        out = await orch.cancel_job(user_id="u", job_id=snap["job_id"])
        assert out["status"] == "completed"

    async def test_cancel_then_resume_rejected(self):
        orch, job_id = await self._run_to_paused()
        await orch.cancel_job(user_id="u", job_id=job_id)
        with pytest.raises(BatchJobConflictError, match="was cancelled"):
            await orch.resume_job(user_id="u", job_id=job_id)


# ===========================================================================
# batch_job_orchestrator: scoping, lookups, summaries
# ===========================================================================


@pytest.mark.asyncio
class TestScopingAndSummary:
    async def test_other_user_cannot_read_job(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        snap = await orch.submit_job(
            user_id="owner", items=[{"workload": "echo", "payload": {}}]
        )
        await _drain(orch)
        with pytest.raises(BatchJobNotFoundError):
            await orch.get_progress(user_id="intruder", job_id=snap["job_id"])

    async def test_unknown_job_id_not_found(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        with pytest.raises(BatchJobNotFoundError):
            await orch.get_progress(user_id="u", job_id="does-not-exist")

    async def test_summary_aggregates_table_metrics(self):
        orch = BatchJobOrchestrator(handlers={"table_analysis": _table_handler})
        snap = await orch.submit_job(
            user_id="u",
            items=[
                {"workload": "table_analysis", "payload": {"rows": 10, "cols": 3}},
                {"workload": "table_analysis", "payload": {"rows": 5, "cols": 4}},
            ],
        )
        await _drain(orch)
        summary = await orch.get_summary(user_id="u", job_id=snap["job_id"])
        assert summary["status"] == "completed"
        assert summary["table_metrics"]["total_rows"] == 15
        assert summary["table_metrics"]["total_columns"] == 7
        assert len(summary["completed_items"]) == 2
        # table_analysis summary projects the expected keys.
        first = summary["completed_items"][0]["summary"]
        assert first["row_count"] == 10
        assert first["column_count"] == 3
        assert "missing_cell_rate" in first

    async def test_summary_pdf_extract_field_preview(self):
        orch = BatchJobOrchestrator(handlers={"pdf_extract": _pdf_handler})
        snap = await orch.submit_job(
            user_id="u", items=[{"workload": "pdf_extract", "payload": {}}]
        )
        await _drain(orch)
        summary = await orch.get_summary(user_id="u", job_id=snap["job_id"])
        item_summary = summary["completed_items"][0]["summary"]
        assert item_summary["success"] is True
        assert item_summary["field_count"] == 3
        assert set(item_summary["fields_preview"]) == {"a", "b", "c"}

    async def test_summary_generic_workload_keys_preview(self):
        orch = BatchJobOrchestrator(handlers={"echo": _echo_handler})
        snap = await orch.submit_job(
            user_id="u", items=[{"workload": "echo", "payload": {"q": 1}}]
        )
        await _drain(orch)
        summary = await orch.get_summary(user_id="u", job_id=snap["job_id"])
        item_summary = summary["completed_items"][0]["summary"]
        assert item_summary["keys_preview"] == ["echo"]

    async def test_failed_and_cancelled_id_lists_in_summary(self):
        orch = BatchJobOrchestrator(
            handlers={"echo": _echo_handler, "boom": _boom_handler}
        )
        snap = await orch.submit_job(
            user_id="u",
            items=[
                {"workload": "boom", "payload": {}, "id": "failit"},
                {"workload": "echo", "payload": {}, "id": "pendit"},
            ],
            stop_on_error=True,
        )
        await _drain(orch)
        await orch.cancel_job(user_id="u", job_id=snap["job_id"])
        summary = await orch.get_summary(user_id="u", job_id=snap["job_id"])
        assert summary["failed_item_ids"] == ["failit"]
        assert "pendit" in summary["cancelled_item_ids"]


@pytest.mark.asyncio
class TestSummaryResultShapes:
    async def test_pdf_extract_without_data_dict(self):
        def _pdf_no_data(payload):
            return {"success": False}

        orch = BatchJobOrchestrator(handlers={"pdf_extract": _pdf_no_data})
        snap = await orch.submit_job(
            user_id="u", items=[{"workload": "pdf_extract", "payload": {}}]
        )
        await _drain(orch)
        summary = await orch.get_summary(user_id="u", job_id=snap["job_id"])
        item_summary = summary["completed_items"][0]["summary"]
        # No "data" dict -> only the success flag is summarized.
        assert item_summary == {"success": False}

    async def test_non_dict_result_excluded_from_summary(self):
        def _scalar(payload):
            return "just-a-string"

        orch = BatchJobOrchestrator(handlers={"echo": _scalar})
        snap = await orch.submit_job(
            user_id="u", items=[{"workload": "echo", "payload": {}}]
        )
        await _drain(orch)
        summary = await orch.get_summary(user_id="u", job_id=snap["job_id"])
        # Non-dict result yields no summary payload, so it is omitted entirely.
        assert summary["completed_items"] == []
        assert summary["counts"]["completed"] == 1

    async def test_table_analysis_without_summary_dict_excluded(self):
        def _table_no_summary(payload):
            return {"summary": "not-a-dict"}

        orch = BatchJobOrchestrator(handlers={"table_analysis": _table_no_summary})
        snap = await orch.submit_job(
            user_id="u", items=[{"workload": "table_analysis", "payload": {}}]
        )
        await _drain(orch)
        summary = await orch.get_summary(user_id="u", job_id=snap["job_id"])
        assert summary["completed_items"] == []
        assert summary["table_metrics"]["total_rows"] == 0


@pytest.mark.asyncio
async def test_invoke_handler_missing_registration_raises():
    """_invoke_handler raises a dependency error when handler vanished."""
    orch = BatchJobOrchestrator()
    with pytest.raises(BatchJobDependencyError, match="No handler registered"):
        await orch._invoke_handler("ghost", {})


def test_status_counts_ignores_unknown_status():
    items = [
        bjo.BatchJobItem(id="1", workload="w", payload={}, label="l", status="completed"),
        bjo.BatchJobItem(id="2", workload="w", payload={}, label="l", status="weird"),
    ]
    counts = BatchJobOrchestrator._status_counts(items)
    assert counts["total"] == 2
    assert counts["completed"] == 1
    # Unknown status is counted only in total, not in any bucket.
    assert sum(counts[k] for k in ("pending", "running", "completed", "failed", "cancelled")) == 1


# ===========================================================================
# payload_media: simple classifiers
# ===========================================================================


class TestExcelDetection:
    def test_extension_detected(self, engine):
        assert pm.looks_like_excel_binary(engine, file_name="report.XLSX") is True
        assert pm.looks_like_excel_binary(engine, file_name="data.xlsb?token=1") is True

    def test_mime_detected(self, engine):
        assert pm.looks_like_excel_binary(
            engine, mime_type="application/vnd.ms-excel"
        ) is True
        assert pm.looks_like_excel_binary(
            engine,
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ) is True

    def test_non_excel_rejected(self, engine):
        assert pm.looks_like_excel_binary(engine, file_name="x.png", mime_type="image/png") is False


class TestToBoolAndToolArg:
    def test_to_bool_truthy_and_falsy_strings(self, engine):
        assert pm.to_bool(engine, "yes") is True
        assert pm.to_bool(engine, "off") is False
        assert pm.to_bool(engine, None, default=True) is True
        assert pm.to_bool(engine, True) is True
        assert pm.to_bool(engine, 0) is False
        assert pm.to_bool(engine, 3) is True
        assert pm.to_bool(engine, "garbage", default=True) is True

    def test_get_tool_arg_first_present_wins(self, engine):
        args = {"a": None, "b": "  value ", "c": "other"}
        assert pm.get_tool_arg(engine, args, "a", "b", "c") == "value"

    def test_get_tool_arg_skips_template_placeholder(self, engine):
        args = {"x": "{{some.template}}", "y": "real"}
        assert pm.get_tool_arg(engine, args, "x", "y") == "real"

    def test_get_tool_arg_none_when_missing(self, engine):
        assert pm.get_tool_arg(engine, {"x": ""}, "x", "missing") is None


# ===========================================================================
# payload_media: SSRF guard helpers
# ===========================================================================


class TestReferenceIpHostGuards:
    def test_parse_ipv4_and_ipv6(self, engine):
        assert str(pm.parse_reference_ip_host(engine, "8.8.8.8")) == "8.8.8.8"
        assert pm.parse_reference_ip_host(engine, "::1") is not None

    def test_parse_dotted_octal_form(self, engine):
        # inet_aton accepts shorthand integer host forms.
        parsed = pm.parse_reference_ip_host(engine, "2130706433")
        assert str(parsed) == "127.0.0.1"

    def test_parse_invalid_host_returns_none(self, engine):
        assert pm.parse_reference_ip_host(engine, "not-an-ip") is None
        assert pm.parse_reference_ip_host(engine, "") is None

    def test_metadata_ip_is_disallowed(self, engine):
        meta_ip = next(iter(engine.REFERENCE_METADATA_IPS))
        assert pm.is_disallowed_reference_ip(engine, meta_ip) is True

    def test_private_and_loopback_disallowed(self, engine):
        import ipaddress

        assert pm.is_disallowed_reference_ip(engine, ipaddress.ip_address("10.0.0.1")) is True
        assert pm.is_disallowed_reference_ip(engine, ipaddress.ip_address("127.0.0.1")) is True

    def test_public_ip_allowed(self, engine):
        import ipaddress

        assert pm.is_disallowed_reference_ip(engine, ipaddress.ip_address("8.8.8.8")) is False

    def test_hostname_guards(self, engine):
        assert pm.is_disallowed_reference_hostname(engine, "") is True
        assert pm.is_disallowed_reference_hostname(engine, "localhost") is True
        assert pm.is_disallowed_reference_hostname(engine, "app.localhost") is True
        assert pm.is_disallowed_reference_hostname(engine, "metadata.google.internal") is True
        meta_host = next(iter(engine.REFERENCE_METADATA_HOSTS))
        assert pm.is_disallowed_reference_hostname(engine, meta_host) is True
        assert pm.is_disallowed_reference_hostname(engine, "example.com") is False


# ===========================================================================
# payload_media: generic path resolution
# ===========================================================================


class TestResolveGenericPath:
    def test_empty_path_returns_data(self, engine):
        data = {"a": 1}
        assert pm.resolve_generic_path(engine, data, "") is data

    def test_nested_dict_and_list_index(self, engine):
        data = {"outer": {"items": [{"name": "x"}, {"name": "y"}]}}
        assert pm.resolve_generic_path(engine, data, "outer.items[1].name") == "y"

    def test_missing_dict_key_returns_none(self, engine):
        assert pm.resolve_generic_path(engine, {"a": 1}, "b.c") is None

    def test_list_index_out_of_range_returns_none(self, engine):
        assert pm.resolve_generic_path(engine, {"xs": [1]}, "xs[5]") is None

    def test_non_digit_index_on_list_returns_none(self, engine):
        assert pm.resolve_generic_path(engine, {"xs": [1, 2]}, "xs.name") is None

    def test_traverse_into_scalar_returns_none(self, engine):
        assert pm.resolve_generic_path(engine, {"a": 5}, "a.b") is None


# ===========================================================================
# payload_media: image URL normalization & extraction
# ===========================================================================


class TestImageUrlNormalization:
    def test_non_string_and_empty(self, engine):
        assert pm.normalize_possible_image_url(engine, None) is None
        assert pm.normalize_possible_image_url(engine, "   ") is None

    def test_data_and_blob_and_scheme_urls(self, engine):
        assert pm.normalize_possible_image_url(engine, "data:image/png;base64,AAAA").startswith("data:")
        assert pm.normalize_possible_image_url(engine, "oss://bucket/k.png") == "oss://bucket/k.png"
        assert pm.normalize_possible_image_url(engine, "file:///tmp/a.png") == "file:///tmp/a.png"

    def test_long_bare_base64_wrapped_as_data_uri(self, engine):
        blob = "A" * 200
        out = pm.normalize_possible_image_url(engine, blob)
        assert out == f"data:image/png;base64,{blob}"

    def test_http_with_image_extension(self, engine):
        assert pm.normalize_possible_image_url(engine, "https://x.com/a/photo.jpeg") == "https://x.com/a/photo.jpeg"

    def test_http_with_image_key_hint(self, engine):
        assert pm.normalize_possible_image_url(
            engine, "https://x.com/blob/123", key_hint="imageUrl"
        ) == "https://x.com/blob/123"

    def test_http_with_image_path_token(self, engine):
        assert pm.normalize_possible_image_url(
            engine, "https://x.com/uploads/file123"
        ) == "https://x.com/uploads/file123"

    def test_http_non_image_rejected(self, engine):
        assert pm.normalize_possible_image_url(engine, "https://x.com/doc.pdf") is None

    def test_non_url_text_rejected(self, engine):
        assert pm.normalize_possible_image_url(engine, "just some text") is None


class TestExtractImageUrls:
    def test_extract_all_image_urls_walks_nested(self, engine):
        payload = {
            "a": "https://x.com/p1.png",
            "nested": {"b": "https://x.com/p2.jpg", "ignore": "plain text"},
            "list": ["https://x.com/p3.webp", "https://x.com/p1.png"],
        }
        urls = pm.extract_all_image_urls(engine, payload)
        # dedupes p1, gathers p1/p2/p3 in first-seen order.
        assert urls == [
            "https://x.com/p1.png",
            "https://x.com/p2.jpg",
            "https://x.com/p3.webp",
        ]

    def test_extract_result_image_urls_prefers_explicit_keys(self, engine):
        payload = {
            "imageUrl": "https://x.com/main.png",
            "images": [
                {"url": "https://x.com/i1.png"},
                {"imageUrl": "https://x.com/i2.png"},
                "https://x.com/i3.png",
            ],
        }
        urls = pm.extract_result_image_urls(engine, payload)
        assert "https://x.com/main.png" in urls
        assert "https://x.com/i1.png" in urls
        assert "https://x.com/i3.png" in urls

    def test_extract_result_image_urls_falls_back_to_walk(self, engine):
        payload = {"deep": {"pic": "https://x.com/found.png"}}
        urls = pm.extract_result_image_urls(engine, payload)
        assert urls == ["https://x.com/found.png"]

    def test_extract_first_image_url(self, engine):
        assert pm.extract_first_image_url(
            engine, {"x": "https://x.com/a.png"}
        ) == "https://x.com/a.png"
        assert pm.extract_first_image_url(engine, {"x": "no"}) is None


# ===========================================================================
# payload_media: file / result-media URL normalization
# ===========================================================================


class TestFileAndResultMediaUrls:
    def test_normalize_file_url_passthrough(self, engine):
        assert pm.normalize_possible_file_url(engine, "https://x.com/a.bin") == "https://x.com/a.bin"
        # svc-agent-3: only recognised schemes are valid file references; an
        # absolute path is accepted, but an arbitrary relative string is not.
        assert pm.normalize_possible_file_url(engine, "/abs/name.txt") == "/abs/name.txt"
        assert pm.normalize_possible_file_url(engine, "relative/name.txt") is None

    def test_normalize_file_url_rejects_template(self, engine):
        assert pm.normalize_possible_file_url(engine, "{{x}}") is None

    def test_normalize_file_url_rejects_non_string(self, engine):
        assert pm.normalize_possible_file_url(engine, 5) is None
        assert pm.normalize_possible_file_url(engine, "  ") is None

    def test_result_media_url_http_and_oss(self, engine):
        assert pm.normalize_possible_result_media_url(engine, "https://x.com/v.mp4") == "https://x.com/v.mp4"
        assert pm.normalize_possible_result_media_url(engine, "oss://b/v.mp4") == "oss://b/v.mp4"

    def test_result_media_url_api_path(self, engine):
        assert pm.normalize_possible_result_media_url(engine, "/api/media/123") == "/api/media/123"

    def test_result_media_url_google_video_uri(self, engine):
        assert pm.normalize_possible_result_media_url(engine, "files/abc123") == "files/abc123"

    def test_result_media_url_rejects_template_and_relative(self, engine):
        assert pm.normalize_possible_result_media_url(engine, "{{x}}") is None
        assert pm.normalize_possible_result_media_url(engine, "plain/relative") is None
        assert pm.normalize_possible_result_media_url(engine, None) is None


# ===========================================================================
# payload_media: video / audio extraction
# ===========================================================================


class TestVideoAudioExtraction:
    def test_first_video_from_direct_keys(self, engine):
        assert pm.extract_first_video_url(
            engine, {"videoUrl": "https://x.com/v.mp4"}
        ) == "https://x.com/v.mp4"

    def test_first_video_from_url_with_mime(self, engine):
        out = pm.extract_first_video_url(
            engine, {"mimeType": "video/mp4", "url": "https://x.com/c.mp4"}
        )
        assert out == "https://x.com/c.mp4"

    def test_first_video_from_list_key(self, engine):
        out = pm.extract_first_video_url(
            engine, {"videoUrls": ["https://x.com/a.mp4", "https://x.com/b.mp4"]}
        )
        assert out == "https://x.com/a.mp4"

    def test_first_video_from_nested_dict_candidate(self, engine):
        out = pm.extract_first_video_url(
            engine, {"videos": [{"url": "https://x.com/n.mp4"}]}
        )
        assert out == "https://x.com/n.mp4"

    def test_first_video_from_bare_string_payload(self, engine):
        assert pm.extract_first_video_url(engine, "https://x.com/s.mp4") == "https://x.com/s.mp4"

    def test_first_video_none_when_absent(self, engine):
        assert pm.extract_first_video_url(engine, {"foo": "bar"}) is None

    def test_first_audio_from_direct_and_list(self, engine):
        assert pm.extract_first_audio_url(
            engine, {"audioUrl": "https://x.com/a.mp3"}
        ) == "https://x.com/a.mp3"
        assert pm.extract_first_audio_url(
            engine, {"audioUrls": ["https://x.com/list.mp3"]}
        ) == "https://x.com/list.mp3"

    def test_first_audio_from_url_with_mime(self, engine):
        out = pm.extract_first_audio_url(
            engine, {"mime_type": "audio/wav", "url": "https://x.com/c.wav"}
        )
        assert out == "https://x.com/c.wav"

    def test_first_audio_none_when_absent(self, engine):
        assert pm.extract_first_audio_url(engine, {"x": 1}) is None

    def test_first_audio_from_nested_dict_candidate(self, engine):
        out = pm.extract_first_audio_url(
            engine, {"audios": [{"url": "https://x.com/nested.mp3"}]}
        )
        assert out == "https://x.com/nested.mp3"


# ===========================================================================
# payload_media: source-video payload packing
# ===========================================================================


class TestBuildSourceVideoPayload:
    def test_none_and_blank_template(self, engine):
        assert pm.build_source_video_payload(engine, None) is None
        assert pm.build_source_video_payload(engine, "{{x}}") is None
        assert pm.build_source_video_payload(engine, "  ") is None

    def test_plain_url_string(self, engine):
        assert pm.build_source_video_payload(engine, "https://x.com/v.mp4") == "https://x.com/v.mp4"

    def test_bare_text_passthrough_when_no_video_url(self, engine):
        # Non-URL, non-template text is returned verbatim.
        assert pm.build_source_video_payload(engine, "some-reference-token") == "some-reference-token"

    def test_url_only_dict_collapses_to_string(self, engine):
        out = pm.build_source_video_payload(engine, {"videoUrl": "https://x.com/v.mp4"})
        assert out == "https://x.com/v.mp4"

    def test_rich_dict_returns_normalized_payload(self, engine):
        out = pm.build_source_video_payload(
            engine,
            {
                "videoUrl": "https://x.com/v.mp4",
                "provider_file_uri": "files/xyz",
                "gcs_uri": "gs://bucket/v.mp4",
                "mime_type": "video/mp4",
            },
        )
        assert out["url"] == "https://x.com/v.mp4"
        # provider_file_name inferred from a files/ uri.
        assert out["provider_file_name"] == "files/xyz"
        assert out["gcs_uri"] == "gs://bucket/v.mp4"
        assert out["mime_type"] == "video/mp4"

    def test_list_returns_first_resolvable(self, engine):
        out = pm.build_source_video_payload(
            engine, [{"foo": "bar"}, {"videoUrl": "https://x.com/v2.mp4"}]
        )
        assert out == "https://x.com/v2.mp4"

    def test_nested_source_video_key(self, engine):
        out = pm.build_source_video_payload(
            engine, {"source_video": {"videoUrl": "https://x.com/nested.mp4"}}
        )
        assert out == "https://x.com/nested.mp4"

    def test_empty_dict_returns_none(self, engine):
        assert pm.build_source_video_payload(engine, {"unrelated": 1}) is None


# ===========================================================================
# payload_media: mime guessing & provider reference rewrite
# ===========================================================================


class TestMimeGuessAndProviderRewrite:
    def test_guess_from_data_uri(self, engine):
        assert pm.guess_image_mime_type_from_reference(engine, "data:image/jpeg;base64,AAA") == "image/jpeg"

    def test_guess_from_extension(self, engine):
        assert pm.guess_image_mime_type_from_reference(engine, "https://x.com/a.png") == "image/png"

    def test_guess_from_file_uri(self, engine):
        assert pm.guess_image_mime_type_from_reference(engine, "file:///tmp/pic.webp") == "image/webp"

    def test_guess_defaults_to_png(self, engine):
        assert pm.guess_image_mime_type_from_reference(engine, "") == "image/png"
        assert pm.guess_image_mime_type_from_reference(engine, "https://x.com/unknown") == "image/png"

    def test_provider_rewrite_skips_unknown_provider(self, engine):
        url = "https://x.com/a.png"
        assert pm.normalize_reference_image_for_provider(engine, url, "openai") == url

    def test_provider_rewrite_keeps_existing_data_uri(self, engine):
        url = "data:image/png;base64,AAAA"
        assert pm.normalize_reference_image_for_provider(engine, url, "google") == url

    def test_provider_rewrite_tongyi_keeps_http(self, engine):
        url = "https://x.com/a.png"
        assert pm.normalize_reference_image_for_provider(engine, url, "tongyi") == url

    def test_provider_rewrite_google_loads_and_encodes(self, engine, monkeypatch):
        # Mock ONLY the filesystem/network boundary; rest of the rewrite is real.
        def _fake_load(ref):
            return (b"\x89PNG-bytes", "image/png", "ref.png")

        monkeypatch.setattr(engine, "_load_binary_from_reference", _fake_load)
        out = pm.normalize_reference_image_for_provider(
            engine, "https://x.com/ref.png", "google"
        )
        assert out.startswith("data:image/png;base64,")

    def test_provider_rewrite_falls_back_on_load_error(self, engine, monkeypatch):
        def _boom(ref):
            raise OSError("cannot read")

        monkeypatch.setattr(engine, "_load_binary_from_reference", _boom)
        url = "https://x.com/ref.png"
        # On failure the original reference is returned unchanged.
        assert pm.normalize_reference_image_for_provider(engine, url, "google") == url

    def test_provider_rewrite_empty_value(self, engine):
        assert pm.normalize_reference_image_for_provider(engine, "", "google") == ""


# ===========================================================================
# payload_media: agent reference resolution (uses real ExecutionContext)
# ===========================================================================


class TestAgentReferenceResolution:
    def test_reference_image_from_node_data(self, engine):
        ctx = ExecutionContext(initial_input={})
        out = pm.resolve_agent_reference_image_url(
            engine,
            node_data={"agentReferenceImageUrl": "https://x.com/ref.png"},
            context=ctx,
            initial_input={},
            input_packets=[],
        )
        assert out == "https://x.com/ref.png"

    def test_reference_image_template_resolved(self, engine):
        ctx = ExecutionContext(initial_input={"pic": "https://x.com/tmpl.png"})
        out = pm.resolve_agent_reference_image_url(
            engine,
            node_data={"agentReferenceImageUrl": "{{input.pic}}"},
            context=ctx,
            initial_input={},
            input_packets=[],
        )
        assert out == "https://x.com/tmpl.png"

    def test_reference_image_from_input_packets(self, engine):
        ctx = ExecutionContext(initial_input={})
        out = pm.resolve_agent_reference_image_url(
            engine,
            node_data={},
            context=ctx,
            initial_input={},
            input_packets=[{"output": {"imageUrl": "https://x.com/from-packet.png"}}],
        )
        assert out == "https://x.com/from-packet.png"

    def test_reference_image_from_initial_input_fallback(self, engine):
        ctx = ExecutionContext(initial_input={})
        out = pm.resolve_agent_reference_image_url(
            engine,
            node_data={},
            context=ctx,
            initial_input={"imageUrl": "https://x.com/initial.png"},
            input_packets=[],
        )
        assert out == "https://x.com/initial.png"

    def test_reference_image_empty_when_nothing(self, engine):
        ctx = ExecutionContext(initial_input={})
        out = pm.resolve_agent_reference_image_url(
            engine, node_data={}, context=ctx, initial_input={}, input_packets=[]
        )
        assert out == ""

    def test_reference_image_non_normalizable_string_returned_stripped(self, engine):
        ctx = ExecutionContext(initial_input={})
        # A non-URL, non-template ref does not normalize, but the raw (stripped)
        # value is still returned as a last resort.
        out = pm.resolve_agent_reference_image_url(
            engine,
            node_data={"agentReferenceImageUrl": "  some-opaque-ref  "},
            context=ctx,
            initial_input={},
            input_packets=[],
        )
        assert out == "some-opaque-ref"

    def test_source_video_input_from_node_data(self, engine):
        ctx = ExecutionContext(initial_input={})
        out = pm.resolve_agent_source_video_input(
            engine,
            node_data={"agentSourceVideoUrl": "https://x.com/v.mp4"},
            context=ctx,
            initial_input={},
            input_packets=[],
        )
        assert out == "https://x.com/v.mp4"

    def test_source_video_input_continue_from_packets(self, engine):
        ctx = ExecutionContext(initial_input={})
        out = pm.resolve_agent_source_video_input(
            engine,
            node_data={"agentContinueFromPreviousVideo": True},
            context=ctx,
            initial_input={},
            input_packets=[{"output": {"videoUrl": "https://x.com/prev.mp4"}}],
        )
        assert out == "https://x.com/prev.mp4"

    def test_source_video_input_none_when_no_continue(self, engine):
        ctx = ExecutionContext(initial_input={})
        out = pm.resolve_agent_source_video_input(
            engine,
            node_data={},
            context=ctx,
            initial_input={"videoUrl": "https://x.com/i.mp4"},
            input_packets=[],
        )
        assert out is None

    def test_source_video_url_extracts_from_input(self, engine):
        ctx = ExecutionContext(initial_input={})
        out = pm.resolve_agent_source_video_url(
            engine,
            node_data={"agentSourceVideoUrl": "https://x.com/url.mp4"},
            context=ctx,
            initial_input={},
            input_packets=[],
        )
        assert out == "https://x.com/url.mp4"

    def test_source_video_url_empty_when_none(self, engine):
        ctx = ExecutionContext(initial_input={})
        out = pm.resolve_agent_source_video_url(
            engine, node_data={}, context=ctx, initial_input={}, input_packets=[]
        )
        assert out == ""
