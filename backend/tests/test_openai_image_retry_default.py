from app.services.openai._shared import coerce_openai_image_max_retries


def test_openai_image_request_default_keeps_transient_retry_resilience() -> None:
    """Regression guard: image requests need non-zero SDK retries for transient upstream 5xx/empty responses.

    sub2api/codex-pro can intermittently return 5xx or empty image output before recovery. If the default
    is changed back to 0, this test should fail before that regression reaches users again.
    """
    assert coerce_openai_image_max_retries(None) == 2


def test_openai_image_request_max_retries_respects_explicit_values() -> None:
    assert coerce_openai_image_max_retries(5) == 5
    assert coerce_openai_image_max_retries("3") == 3


def test_openai_image_request_max_retries_clamps_invalid_values() -> None:
    assert coerce_openai_image_max_retries(-1) == 0
    assert coerce_openai_image_max_retries("abc") == 2
