import os
import shutil
import tempfile
import subprocess
import pytest

from harness.worker import ProviderWorker, WorkerResult, is_obviously_destructive
from harness.conversation import ConversationalSession, ConvEvent
from harness.autobudget import AutoBudget
from harness.worktrees import _is_repo


def create_temp_git_repo():
    repo_dir = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, capture_output=True)
    
    with open(os.path.join(repo_dir, "test.txt"), "w") as f:
        f.write("hello\n")
    subprocess.run(["git", "add", "test.txt"], cwd=repo_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_dir, capture_output=True)
    return repo_dir


def test_is_obviously_destructive():
    # Destructive patterns
    assert is_obviously_destructive("rm -rf /") is True
    assert is_obviously_destructive("rm -rf ~") is True
    assert is_obviously_destructive(":(){:|:&};:") is True
    assert is_obviously_destructive("mkfs.ext4 /dev/sdb1") is True
    assert is_obviously_destructive("dd if=/dev/zero of=/dev/sd") is True
    assert is_obviously_destructive("git push origin --force") is True
    assert is_obviously_destructive("RM -RF /") is True  # Case insensitive
    assert is_obviously_destructive("  rm   -rf   ~  ") is True  # Whitespace robust
    
    # Safe patterns
    assert is_obviously_destructive("pytest -q") is False
    assert is_obviously_destructive("git diff") is False
    assert is_obviously_destructive("rm -rf temp_folder_name") is False
    assert is_obviously_destructive("echo hello") is False


def test_worker_not_git_repo():
    temp_dir = tempfile.mkdtemp()
    try:
        worker = ProviderWorker(repo=temp_dir, goal="add something")
        res = worker.run()
        assert res.ok is False
        assert "not a git repo" in res.error
    finally:
        shutil.rmtree(temp_dir)


def test_worker_success(monkeypatch):
    repo_dir = create_temp_git_repo()
    try:
        # We monkeypatch ConversationalSession.run_auto to simulate writing a file and yielding some events.
        def mock_run_auto(self, objective, budget=None, require_codegraph=True):
            # self is the ConversationalSession instance
            assert self.config.repo != repo_dir  # Must be a separate worktree path
            assert os.path.exists(self.config.repo)
            
            # Write a real file in the worktree
            filepath = os.path.join(self.config.repo, "added_by_worker.txt")
            with open(filepath, "w") as f:
                f.write("this is a new file created by the worker\n")
                
            yield ConvEvent("message", {"text": "I have created the added_by_worker.txt file."})
            yield ConvEvent("auto_halt", {"reason": "pilot reports objective met"})

        monkeypatch.setattr(ConversationalSession, "run_auto", mock_run_auto)

        # Let's run the worker
        worker = ProviderWorker(
            repo=repo_dir,
            goal="Create a file added_by_worker.txt with custom text",
            run_tests="echo 'tests passed'",
            keep_worktree_on_failure=True
        )
        
        # Verify the setup
        assert worker.repo == os.path.abspath(repo_dir)
        assert worker.goal == "Create a file added_by_worker.txt with custom text"
        
        res = worker.run()
        
        # Verify result
        assert res.ok is True
        assert res.patch != ""
        assert "added_by_worker.txt" in res.files_changed
        assert "added_by_worker.txt" in res.patch
        assert "this is a new file created by the worker" in res.patch
        assert "tests passed" in res.test_output
        assert "pilot reports objective met" in res.summary
        assert "I have created the added_by_worker.txt file." in res.summary
        
        # Verify worktree is cleaned up on success
        assert not os.path.exists(res.worktree)
        
        # Verify the patch applies cleanly to the original repo
        patch_file = os.path.join(repo_dir, "change.patch")
        with open(patch_file, "w") as f:
            f.write(res.patch)
            
        p_apply = subprocess.run(
            ["git", "apply", "change.patch"],
            cwd=repo_dir,
            capture_output=True,
            text=True
        )
        assert p_apply.returncode == 0
        
        # Verify original repo now has the file
        created_file_path = os.path.join(repo_dir, "added_by_worker.txt")
        assert os.path.exists(created_file_path)
        with open(created_file_path, "r") as f:
            assert f.read() == "this is a new file created by the worker\n"
            
    finally:
        shutil.rmtree(repo_dir)


def test_worker_empty_change(monkeypatch):
    repo_dir = create_temp_git_repo()
    try:
        def mock_run_auto_empty(self, objective, budget=None, require_codegraph=True):
            yield ConvEvent("message", {"text": "I looked around but made no changes."})
            yield ConvEvent("auto_halt", {"reason": "pilot reports objective met"})

        monkeypatch.setattr(ConversationalSession, "run_auto", mock_run_auto_empty)

        worker = ProviderWorker(
            repo=repo_dir,
            goal="Inspect the repository",
            keep_worktree_on_failure=True
        )
        
        res = worker.run()
        
        assert res.ok is False
        assert res.patch == ""
        assert res.files_changed == []
        assert res.summary == "no changes produced"
        
        # Worktree should still be cleaned up because success of the run itself is False but keep_worktree_on_failure only retains on execution failure (exceptions), not on empty diff.
        # Wait, if patch is empty, is it a success or a failure of the execution?
        # In our ProviderWorker, success = True when it finishes without exception. So it is cleaned up successfully!
        assert not os.path.exists(res.worktree)
        
    finally:
        shutil.rmtree(repo_dir)


def test_worker_destructive_guards(monkeypatch):
    repo_dir = create_temp_git_repo()
    try:
        commands_run = []
        
        # We monkeypatch run_auto to run a destructive command, and a safe command
        def mock_run_auto_destructive(self, objective, budget=None, require_codegraph=True):
            # Try running a destructive command
            p_dest = subprocess.run("rm -rf /", shell=True)
            commands_run.append(("rm -rf /", p_dest.returncode, p_dest.stdout))
            
            # Try running a safe command
            p_safe = subprocess.run("echo hello_safe", shell=True, capture_output=True, text=True)
            commands_run.append(("echo hello_safe", p_safe.returncode, p_safe.stdout.strip()))
            
            yield ConvEvent("auto_halt", {"reason": "done"})

        monkeypatch.setattr(ConversationalSession, "run_auto", mock_run_auto_destructive)

        worker = ProviderWorker(repo=repo_dir, goal="test guards")
        res = worker.run()
        
        # Check that rm -rf / was intercepted and mocked
        assert len(commands_run) == 2
        
        cmd1, code1, out1 = commands_run[0]
        assert cmd1 == "rm -rf /"
        assert code1 == 1
        assert "rejected by safety guardrails" in out1
        
        cmd2, code2, out2 = commands_run[1]
        assert cmd2 == "echo hello_safe"
        assert code2 == 0
        assert out2 == "hello_safe"
        
    finally:
        shutil.rmtree(repo_dir)
