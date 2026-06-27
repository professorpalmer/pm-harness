import os
import pytest
from harness.config import HarnessConfig
from harness.conversation import ConversationalSession, ConvEvent
from harness.skill_store import SkillStore, Skill
from harness.rule_store import RuleStore, Rule
from harness.skill_distiller import distill_session, distill_rules


class FakePilot:
    def __init__(self, responses):
        self.responses = responses if isinstance(responses, list) else [responses]
        self.call_count = 0

    def complete(self, prompt, *, system=None):
        class R:
            def __init__(self, text):
                self.text = text
        text = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return R(text)


def test_auto_distill_default_on(monkeypatch):
    # Test default when env is empty
    monkeypatch.delenv("HARNESS_AUTO_DISTILL", raising=False)
    config = HarnessConfig()
    session = ConversationalSession(config)
    assert session._auto_distill is True

    # Test falsey env values
    for val in ("0", "false", "no", "FALSE", "No"):
        monkeypatch.setenv("HARNESS_AUTO_DISTILL", val)
        session = ConversationalSession(config)
        assert session._auto_distill is False

    # Test truthy env values
    for val in ("1", "true", "yes", "TRUE", "Yes"):
        monkeypatch.setenv("HARNESS_AUTO_DISTILL", val)
        session = ConversationalSession(config)
        assert session._auto_distill is True


def test_hard_task_trigger(tmp_path):
    config = HarnessConfig()
    config.repo = str(tmp_path)
    session = ConversationalSession(config)
    session._skills = SkillStore(root=str(tmp_path / "skills"))
    session._rules = RuleStore(path=str(tmp_path / "rules.json"))

    # Less than MIN_FINDINGS findings
    session._session_findings = [{"type": "finding", "headline": "Only one finding"}]
    session._first_objective = "Fix critical memory leak"
    
    # Simulate high tool call count
    session._total_tool_calls = 8
    
    # Seed display transcript
    session._display_transcript = [
        {"role": "user", "text": "Fix critical memory leak"},
        {"role": "assistant", "text": "I analyzed memory usage and found a leaking dictionary. I cleared it."}
    ]

    # Pilot returns valid candidate JSON
    session.pilot = FakePilot('{"name":"Clear dict leak","description":"When dictionaries grow unbounded","body":"1. inspect dict usage\\n2. clear dict reference"}')

    res = session.distill()
    assert res["skill"]["status"] == "proposed"
    
    # Ensure it was proposed as PENDING (human gate holds)
    skill = session._skills.get(res["skill"]["slug"])
    assert skill is not None
    assert skill.state == "pending"
    assert "inspect dict usage" in skill.body


def test_duplicate_with_new_info_proposes_patch(tmp_path):
    store = SkillStore(root=str(tmp_path / "skills"))
    
    # Save active skill
    existing = Skill(
        name="SSE Fix",
        description="Fixes SSE issues",
        body="1. check flush",
        state="active"
    )
    store.save(existing)
    
    # 1. Candidate is Jaccard similar to existing skill (Jaccard = 1.0)
    # 2. Pilot merged output is different from existing body
    pilot = FakePilot([
        # Response for distill_session's original complete call
        '{"name":"SSE Fix","description":"Fixes SSE issues","body":"1. check flush\\n2. check content-type"}',
        # Response for merge_prompt complete call
        '{"name":"SSE Fix","description":"Fixes SSE issues","body":"1. check flush\\n2. check content-type"}'
    ])
    
    findings = [
        {"type": "finding", "headline": "SSE needs flush"},
        {"type": "finding", "headline": "content-type must be set"}
    ]
    
    r = distill_session(pilot, "sse task", findings, store)
    assert r["status"] == "patch_proposed"
    assert r["supersedes"] == "sse-fix"
    assert r["slug"] == "sse-fix-patch"
    
    # Ensure the patch skill was stored in PENDING
    patch_skill = store.get("sse-fix-patch")
    assert patch_skill is not None
    assert patch_skill.state == "pending"
    assert "check content-type" in patch_skill.body
    
    # Approve the patch skill and ensure it updates the active skill and unlinks the patch skill
    approved = store.set_state("sse-fix-patch", "active")
    assert approved is not None
    assert approved.slug == "sse-fix"
    assert approved.state == "active"
    assert "check content-type" in approved.body
    
    # Original active skill is updated, patch skill is deleted
    assert store.get("sse-fix-patch") is None
    assert store.get("sse-fix").body == "1. check flush\n2. check content-type"


def test_corrections_feed_distill_rules(tmp_path):
    rule_store = RuleStore(path=str(tmp_path / "rules.json"))
    
    pilot = FakePilot('{"rules": [{"text": "never use emojis in output", "scope": "global"}]}')
    
    # No findings, but we have user corrections
    findings = []
    corrections = ["don't use emojis", "stop using emojis"]
    
    r = distill_rules(pilot, "no emoji task", findings, rule_store, corrections=corrections)
    assert r["status"] == "proposed"
    assert "never-use-emojis-in-output" in r["proposed"]
    
    # Ensure human gate holds (proposed rule is pending)
    rules = rule_store.list()
    rule = next((r for r in rules if r.slug == "never-use-emojis-in-output"), None)
    assert rule is not None
    assert rule.state == "pending"
    assert rule.text == "never use emojis in output"


def test_human_gate_holds_all(tmp_path):
    # Propose skill/rule and confirm they are pending
    skill_store = SkillStore(root=str(tmp_path / "skills"))
    rule_store = RuleStore(path=str(tmp_path / "rules.json"))
    
    pilot = FakePilot([
        '{"name":"New Procedure","description":"New description","body":"New body"}',
        '{"rules": [{"text": "never edit without verifying", "scope": "global"}]}'
    ])
    
    findings = [
        {"type": "finding", "headline": "step one done"},
        {"type": "finding", "headline": "step two done"}
    ]
    
    skill_res = distill_session(pilot, "task", findings, skill_store)
    rule_res = distill_rules(pilot, "task", findings, rule_store)
    
    assert skill_res["status"] == "proposed"
    assert rule_res["status"] == "proposed"
    
    skill = skill_store.get(skill_res["slug"])
    assert skill.state == "pending"
    
    rules = rule_store.list()
    rule = next((r for r in rules if r.slug == rule_res["proposed"][0]), None)
    assert rule is not None
    assert rule.state == "pending"
