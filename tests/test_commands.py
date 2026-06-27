import os
import pytest
from pathlib import Path
from harness.command_store import CommandStore, CommandTemplate, sanitize_name


def test_sanitize_name():
    assert sanitize_name("My_Example-Command 123") == "my-example-command-123"
    assert sanitize_name("/foo/bar") == "foo-bar"
    assert sanitize_name("---abc---") == "abc"


def test_command_store_list_parsed(tmp_path):
    global_dir = tmp_path / "global_commands"
    global_dir.mkdir()
    
    # Write command 1 with description
    cmd1_path = global_dir / "cmd-one.md"
    cmd1_path.write_text(
        "description: First custom command\n"
        "This is the body of first custom command with $ARGUMENTS"
    )
    
    # Write command 2 with fallback description
    cmd2_path = global_dir / "cmd-two.md"
    cmd2_path.write_text(
        "First line of cmd two which is rather long so we will test truncation at eighty characters limit to see if it works as specified.\n"
        "This is the body of cmd two."
    )
    
    store = CommandStore(global_dir=str(global_dir))
    cmds = store.list()
    
    assert len(cmds) == 2  # cmd-one and cmd-two (not seeded because dir was not empty on store init)
    
    # Find cmd-one and cmd-two
    one = next(c for c in cmds if c.name == "cmd-one")
    two = next(c for c in cmds if c.name == "cmd-two")
    
    assert one.description == "First custom command"
    assert one.body == "This is the body of first custom command with $ARGUMENTS"
    assert one.scope == "global"
    
    assert len(two.description) <= 80
    assert two.description == "First line of cmd two which is rather long so we will test truncation at eighty"
    assert "This is the body of cmd two" in two.body


def test_command_store_shadowing(tmp_path):
    global_dir = tmp_path / "global_commands"
    project_dir = tmp_path / "project"
    project_commands_dir = project_dir / ".pmharness" / "commands"
    project_commands_dir.mkdir(parents=True)
    
    # Global command
    cmd_path = global_dir / "test-cmd.md"
    global_dir.mkdir(exist_ok=True)
    cmd_path.write_text(
        "description: Global description\n"
        "Global body"
    )
    
    # Project command (shadows global)
    p_cmd_path = project_commands_dir / "test-cmd.md"
    p_cmd_path.write_text(
        "description: Project description\n"
        "Project body"
    )
    
    store = CommandStore(global_dir=str(global_dir))
    cmds = store.list(repo=str(project_dir))
    
    # test-cmd should be shadowed by project
    target = next(c for c in cmds if c.name == "test-cmd")
    assert target.description == "Project description"
    assert target.body == "Project body"
    assert target.scope == "project"


def test_command_store_render(tmp_path):
    global_dir = tmp_path / "global_commands"
    global_dir.mkdir()
    
    store = CommandStore(global_dir=str(global_dir))
    
    # 1. Test $ARGUMENTS substitution
    (global_dir / "args.md").write_text(
        "description: Args cmd\n"
        "Prefix: $ARGUMENTS"
    )
    
    # 2. Test positional substitution $1 $2
    (global_dir / "pos.md").write_text(
        "description: Positional cmd\n"
        "First: $1, Second: $2, Third: $3"
    )
    
    # 3. Test fallback append
    (global_dir / "fallback.md").write_text(
        "description: Fallback cmd\n"
        "Static body text with no placeholders"
    )
    
    # Test $ARGUMENTS replacement
    res = store.render("args", "hello world")
    assert res == "Prefix: hello world"
    
    # Test positional replacement
    res = store.render("pos", "foo bar")
    assert res == "First: foo, Second: bar, Third: "
    
    # Test fallback append
    res = store.render("fallback", "extra arguments")
    assert res == "Static body text with no placeholders\n\nextra arguments"
    
    # Test fallback append when args are empty
    res = store.render("fallback", "")
    assert res == "Static body text with no placeholders"
    
    # Test unknown command
    res = store.render("unknown", "args")
    assert res is None


def test_command_store_ensure_dirs_seeding(tmp_path):
    global_dir = tmp_path / "global_commands"
    
    # First creation should seed example.md
    store = CommandStore(global_dir=str(global_dir))
    example_path = global_dir / "example.md"
    assert example_path.exists()
    assert "Example custom command" in example_path.read_text()
    
    # Overwrite example.md with something custom
    example_path.write_text("custom content")
    
    # Re-initialize or call ensure_dirs, it should not overwrite
    store2 = CommandStore(global_dir=str(global_dir))
    assert example_path.read_text() == "custom content"
