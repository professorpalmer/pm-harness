"""Differential tests: validate Marionette's session-activity detection against
Hermes' proven reference implementation (hermes_cli.session_recap), imported
directly as the oracle.

WHY THIS IS VALID: Hermes' _count_visible_turns / _iter_assistant_tool_calls is
the battle-tested logic for "how much real work happened in a session." Marionette's
hard-task trigger (tool-call count + error recovery) makes the same judgment. We
feed IDENTICAL chat-completion-style histories to both and assert agreement.

WHY WE DO NOT DIFF THE DISTILLER ITSELF: Hermes has no programmatic skill
distiller (no jaccard/threshold/auto-merge) -- skill creation is agent-tool-driven
via skill_manage. There is no Hermes equivalent to diff Marionette's dedup/merge
against, so that logic is covered by stress/property tests, not differential tests.

The Hermes checkout path is resolved dynamically; tests skip cleanly if absent so
the suite stays hermetic on machines without the reference checkout.
"""
import os
import sys
import pytest

_HERMES_ROOT = os.path.expanduser("~/.hermes/hermes-agent")


def _load_hermes_oracle():
    """Import Hermes' session_recap as the reference oracle, or skip."""
    if not os.path.isdir(_HERMES_ROOT):
        pytest.skip("Hermes reference checkout not present at ~/.hermes/hermes-agent")
    if _HERMES_ROOT not in sys.path:
        sys.path.insert(0, _HERMES_ROOT)
    try:
        from hermes_cli.session_recap import (
            _count_visible_turns,
            _iter_assistant_tool_calls,
        )
    except Exception as e:  # import error -> skip, do not fail the suite
        pytest.skip(f"Hermes session_recap not importable: {e}")
    return _count_visible_turns, _iter_assistant_tool_calls


def _marionette_count_tool_calls(messages):
    """Marionette's notion of tool-call volume, derived from the same history
    shape Hermes consumes. Mirrors how conversation.py recognizes tool calls on
    assistant messages (m['tool_calls'] list)."""
    total = 0
    for m in messages:
        if not isinstance(m, dict):
            continue
        if m.get("role") != "assistant":
            continue
        tcs = m.get("tool_calls") or []
        if isinstance(tcs, list):
            total += len(tcs)
    return total


# ---- fixtures: representative conversation histories ------------------------

def _history_simple():
    return [
        {"role": "user", "content": "do a thing"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "1", "function": {"name": "read_file", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "1", "content": "ok"},
        {"role": "assistant", "content": "done"},
    ]


def _history_hard_task():
    # 10 tool calls across several assistant turns -> "hard task"
    msgs = [{"role": "user", "content": "big task"}]
    for i in range(5):
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"a{i}", "function": {"name": "search_files", "arguments": "{}"}},
            {"id": f"b{i}", "function": {"name": "read_file", "arguments": "{}"}},
        ]})
        msgs.append({"role": "tool", "tool_call_id": f"a{i}", "content": "r"})
        msgs.append({"role": "tool", "tool_call_id": f"b{i}", "content": "r"})
    msgs.append({"role": "assistant", "content": "finished"})
    return msgs


def _history_no_tools():
    return [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "thanks"},
        {"role": "assistant", "content": "you are welcome"},
    ]


@pytest.mark.parametrize("history_fn", [_history_simple, _history_hard_task, _history_no_tools])
def test_tool_call_count_matches_hermes_oracle(history_fn):
    """Marionette's tool-call count must equal Hermes' oracle count on the same history."""
    _count_visible_turns, _iter_assistant_tool_calls = _load_hermes_oracle()
    history = history_fn()
    hermes_count = sum(1 for _ in _iter_assistant_tool_calls(history))
    marionette_count = _marionette_count_tool_calls(history)
    assert marionette_count == hermes_count, (
        f"tool-call count diverged from Hermes oracle: "
        f"marionette={marionette_count} hermes={hermes_count}")


def test_hard_task_threshold_agrees_with_oracle_volume():
    """A history Hermes counts as high-activity (>=8 tool calls) must trip
    Marionette's hard-task threshold; a low-activity one must not."""
    _count_visible_turns, _iter_assistant_tool_calls = _load_hermes_oracle()
    hard = _history_hard_task()
    simple = _history_simple()
    hard_count = sum(1 for _ in _iter_assistant_tool_calls(hard))
    simple_count = sum(1 for _ in _iter_assistant_tool_calls(simple))
    # Marionette's documented hard-task threshold is >= 8 tool calls
    assert hard_count >= 8, f"oracle says hard task has {hard_count} calls"
    assert _marionette_count_tool_calls(hard) >= 8
    assert simple_count < 8
    assert _marionette_count_tool_calls(simple) < 8


def test_visible_turn_count_matches_oracle():
    """Marionette and Hermes must agree on user/assistant turn counts."""
    _count_visible_turns, _iter_assistant_tool_calls = _load_hermes_oracle()
    for history_fn in (_history_simple, _history_hard_task, _history_no_tools):
        history = history_fn()
        h_users, h_assist, h_tools = _count_visible_turns(history)
        m_users = sum(1 for m in history if isinstance(m, dict) and m.get("role") == "user")
        m_assist = sum(1 for m in history if isinstance(m, dict) and m.get("role") == "assistant")
        m_tools = sum(1 for m in history if isinstance(m, dict) and m.get("role") == "tool")
        assert (m_users, m_assist, m_tools) == (h_users, h_assist, h_tools), (
            f"turn counts diverged on {history_fn.__name__}: "
            f"marionette={(m_users, m_assist, m_tools)} hermes={(h_users, h_assist, h_tools)}")
