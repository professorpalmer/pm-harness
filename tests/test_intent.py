"""Unit tests for the pure intent contract -- no Puppetmaster needed."""
import pytest
from pmharness.intent import (
    validate_intent, parse_intent_text, IntentError, DriverIntent, KNOWN_ROLES,
)


def test_valid_run_swarm():
    i = validate_intent({"action": "run_swarm", "goal": "audit repo"})
    assert i.action == "run_swarm" and i.goal == "audit repo"
    assert i.worker_mode == "subprocess"


def test_run_swarm_requires_goal():
    with pytest.raises(IntentError):
        validate_intent({"action": "run_swarm"})


def test_answer_and_stop_need_no_goal():
    assert validate_intent({"action": "answer"}).action == "answer"
    assert validate_intent({"action": "stop"}).action == "stop"


def test_bad_action():
    with pytest.raises(IntentError):
        validate_intent({"action": "explode"})


def test_bad_worker_mode():
    with pytest.raises(IntentError):
        validate_intent({"action": "run_swarm", "goal": "x", "worker_mode": "rocket"})


def test_unknown_role_rejected():
    with pytest.raises(IntentError):
        validate_intent({"action": "run_swarm", "goal": "x", "roles": ["nope"]})


def test_known_roles_pass():
    i = validate_intent({"action": "run_swarm", "goal": "x", "roles": list(KNOWN_ROLES)})
    assert i.roles == list(KNOWN_ROLES)


def test_parse_fenced_json():
    txt = "Here you go:\n```json\n{\"action\": \"answer\"}\n```\nDone."
    assert parse_intent_text(txt)["action"] == "answer"


def test_parse_bare_json_with_prose():
    txt = 'I think: {"action":"stop","rationale":"done"} ok'
    assert parse_intent_text(txt)["action"] == "stop"


def test_parse_nested_braces():
    txt = '{"action":"run_swarm","goal":"x","raw":{"a":{"b":1}}}'
    assert parse_intent_text(txt)["goal"] == "x"


def test_parse_no_json_raises():
    with pytest.raises(IntentError):
        parse_intent_text("no json here at all")


def test_validate_from_text():
    i = validate_intent('{"action":"answer"}')
    assert i.action == "answer"
