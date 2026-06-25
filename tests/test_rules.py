"""Rules store + rules distiller (deterministic, fake pilot)."""
from harness.rule_store import RuleStore, Rule
from harness.skill_distiller import distill_rules


def test_rule_store_crud(tmp_path):
    s = RuleStore(path=str(tmp_path / "rules.json"))
    s.add(Rule(text="Never use emojis in output", state="pending"))
    assert len(s.list()) == 1
    assert len(s.list("pending")) == 1
    s.set_state("never-use-emojis-in-output", "active")
    assert s.list("active")[0].text == "Never use emojis in output"


def test_rule_dedup(tmp_path):
    s = RuleStore(path=str(tmp_path / "rules.json"))
    s.add(Rule(text="Always run the tests before claiming done", state="active"))
    assert s.exists_similar("always run tests before claiming done") is not None
    assert s.exists_similar("use postgres for storage") is None


class _Pilot:
    def __init__(self, text): self._t = text
    def complete(self, prompt, *, system=None):
        class R: text = self._t
        return R()


def test_distill_rules_proposes(tmp_path):
    s = RuleStore(path=str(tmp_path / "rules.json"))
    pilot = _Pilot('{"rules":[{"text":"Never commit secrets","scope":"global"},{"text":"Always use the venv python","scope":"global"}]}')
    findings = [{"type": "finding", "headline": "leaked a key once"}]
    r = distill_rules(pilot, "obj", findings, s)
    assert r["status"] == "proposed"
    assert len(r["proposed"]) == 2
    assert all(rule.state == "pending" for rule in s.list())


def test_distill_rules_empty(tmp_path):
    s = RuleStore(path=str(tmp_path / "rules.json"))
    pilot = _Pilot('{"rules":[]}')
    r = distill_rules(pilot, "obj", [{"type": "finding", "headline": "x"}], s)
    assert r["status"] == "skipped"


def test_distill_rules_dedup(tmp_path):
    s = RuleStore(path=str(tmp_path / "rules.json"))
    s.add(Rule(text="Never use emojis in output", state="active"))
    pilot = _Pilot('{"rules":[{"text":"Never use emojis in output ever","scope":"global"}]}')
    r = distill_rules(pilot, "obj", [{"type": "finding", "headline": "x"}], s)
    assert r["status"] == "duplicate"
    assert len(r["duplicates"]) == 1
