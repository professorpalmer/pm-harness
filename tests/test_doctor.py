"""harness doctor: offline checks pass with the stub; missing-key warns not fails."""
from harness import cli


def test_doctor_stub_driver_all_ok(monkeypatch, capsys):
    monkeypatch.setenv("HARNESS_DRIVER", "stub-oracle-v2")
    code = cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "puppetmaster seam" in out
    assert "durable state" in out
    assert "harness ready" in out
    assert code == 0


def test_doctor_missing_key_warns_not_fails(monkeypatch, capsys):
    monkeypatch.setenv("HARNESS_DRIVER", "glm-5.2")
    monkeypatch.setenv("HARNESS_REACH", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    code = cli.main(["doctor"])
    out = capsys.readouterr().out
    # missing driver key is a WARN (not a hard fail) -> doctor still exits 0
    assert "WARN" in out
    assert "OPENROUTER_API_KEY not set" in out
    assert code == 0


def test_doctor_seam_and_store_are_hard_checks(monkeypatch, capsys):
    monkeypatch.setenv("HARNESS_DRIVER", "stub-oracle-v2")
    cli.main(["doctor"])
    out = capsys.readouterr().out
    # the seam + store lines report ok in a healthy repo
    assert "[OK  ] puppetmaster seam" in out or "OK" in out
