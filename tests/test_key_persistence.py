"""Tests for persistent provider disconnect + per-workspace model memory."""
import os
import tempfile


def test_disconnect_persists_over_shell_env(monkeypatch):
    """A deliberately disconnected provider stays disconnected on restart even
    when the user's shell exports its key (login-shell env re-injects it)."""
    monkeypatch.setenv("HARNESS_STATE_DIR", tempfile.mkdtemp())
    import importlib
    from harness import keys as K
    importlib.reload(K)

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret-1234")
    K.clear_api_key("openrouter")
    assert "openrouter" in K.get_disconnected()
    assert "OPENROUTER_API_KEY" not in os.environ

    # Restart: shell re-exports the key, startup scrub must remove it again.
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret-1234")
    K.scrub_disconnected_env()
    assert "OPENROUTER_API_KEY" not in os.environ


def test_reconnect_clears_disconnect(monkeypatch):
    monkeypatch.setenv("HARNESS_STATE_DIR", tempfile.mkdtemp())
    import importlib
    from harness import keys as K
    importlib.reload(K)

    K.clear_api_key("openrouter")
    assert "openrouter" in K.get_disconnected()
    K.set_api_key("openrouter", "sk-or-new-key-5678")
    assert "openrouter" not in K.get_disconnected()
    assert os.environ.get("OPENROUTER_API_KEY") == "sk-or-new-key-5678"


def test_available_providers_excludes_disconnected(monkeypatch):
    monkeypatch.setenv("HARNESS_STATE_DIR", tempfile.mkdtemp())
    import importlib
    from harness import keys as K
    importlib.reload(K)
    from harness import providers as prov

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xyz")
    K.mark_disconnected("anthropic")
    names = {p.name for p in prov.available_providers()}
    assert "anthropic" not in names


def test_workspace_driver_memory(monkeypatch):
    monkeypatch.setenv("HARNESS_STATE_DIR", tempfile.mkdtemp())
    import importlib
    import harness.server as srv
    importlib.reload(srv)

    repoA = "/Users/test/repoA"
    repoB = "/Users/test/repoB"
    srv._save_workspace_driver(repoA, "anthropic:claude-opus-4-8")
    srv._save_workspace_driver(repoB, "openrouter:openai/gpt-5.5")
    assert srv._get_workspace_driver(repoA) == "anthropic:claude-opus-4-8"
    assert srv._get_workspace_driver(repoB) == "openrouter:openai/gpt-5.5"
    # Overwrite preserves the other.
    srv._save_workspace_driver(repoA, "openai:gpt-5.4")
    assert srv._get_workspace_driver(repoA) == "openai:gpt-5.4"
    assert srv._get_workspace_driver(repoB) == "openrouter:openai/gpt-5.5"


def test_workspace_driver_skips_temp_dirs(monkeypatch):
    monkeypatch.setenv("HARNESS_STATE_DIR", tempfile.mkdtemp())
    import importlib
    import harness.server as srv
    importlib.reload(srv)
    tmp = tempfile.mkdtemp()  # under /tmp -> must NOT be persisted
    srv._save_workspace_driver(tmp, "x:y")
    assert srv._get_workspace_driver(tmp) is None
