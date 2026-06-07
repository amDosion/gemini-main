"""Workflow DoS guard: a client-supplied loop ``max_iterations`` must be clamped
to a sane upper bound so it cannot blow up the per-node visit ceiling (unbounded
loop execution).
"""

from app.services.agent.workflow_engine.flow_control import (
    MAX_LOOP_ITERATIONS,
    resolve_max_visits,
)


class _Engine:
    DEFAULT_MAX_NODE_VISITS = 40


def test_loop_max_iterations_is_clamped_to_upper_bound():
    visits = resolve_max_visits(_Engine(), "loop", {"max_iterations": 10_000_000})
    assert visits <= MAX_LOOP_ITERATIONS + 2


def test_loop_camelcase_max_iterations_is_clamped():
    visits = resolve_max_visits(_Engine(), "loop", {"maxIterations": 5_000_000})
    assert visits <= MAX_LOOP_ITERATIONS + 2


def test_loop_normal_iterations_preserved():
    assert resolve_max_visits(_Engine(), "loop", {"max_iterations": 5}) == 7


def test_loop_negative_iterations_floored():
    assert resolve_max_visits(_Engine(), "loop", {"max_iterations": -100}) >= 2


def test_loop_garbage_iterations_falls_back():
    assert resolve_max_visits(_Engine(), "loop", {"max_iterations": "not-a-number"}) >= 2


def test_non_loop_node_uses_engine_default():
    assert resolve_max_visits(_Engine(), "agent", {}) == 40
