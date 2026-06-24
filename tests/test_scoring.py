"""Scoring is deterministic and label-driven."""
from pmharness.battery import TaskCase
from pmharness.scoring import score_attempt


def test_perfect_answer_case():
    case = TaskCase("t", "What is X?", "answer")
    s = score_attempt(case, '{"action":"answer"}', model="m")
    assert s.json_valid and s.schema_valid and s.action_correct
    assert s.score == 1.0


def test_wrong_action_scores_partial():
    case = TaskCase("t", "audit repo", "run_swarm", must_execute=True)
    s = score_attempt(case, '{"action":"answer"}', model="m")
    # valid json+schema but wrong decision and no execution
    assert s.json_valid and s.schema_valid and not s.action_correct
    assert 0.0 < s.score < 0.5


def test_swarm_executed_tops_out():
    case = TaskCase("t", "audit repo", "run_swarm", must_execute=True)
    s = score_attempt(case, '{"action":"run_swarm","goal":"audit"}',
                      model="m", executed_ok=True)
    assert s.score == 1.0


def test_swarm_not_executed_caps_below_one():
    case = TaskCase("t", "audit repo", "run_swarm", must_execute=True)
    s = score_attempt(case, '{"action":"run_swarm","goal":"audit"}',
                      model="m", executed_ok=False)
    assert s.action_correct and s.score < 1.0


def test_garbage_output_scores_zero():
    case = TaskCase("t", "audit repo", "run_swarm", must_execute=True)
    s = score_attempt(case, "I cannot help with that", model="m")
    assert not s.json_valid and s.score == 0.0
