import pytest
import tempfile
import shutil
import os
import subprocess
import json
from harness.config import HarnessConfig
from harness.conversation import ConversationalSession

@pytest.fixture
def temp_git_repo():
    dirpath = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init"], cwd=dirpath, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=dirpath, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=dirpath, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Write base file
        base_file = os.path.join(dirpath, "base.txt")
        with open(base_file, "w") as f:
            f.write("Line 1\nLine 2\nLine 3\n")
            
        subprocess.run(["git", "add", "base.txt"], cwd=dirpath, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=dirpath, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        yield dirpath
    finally:
        shutil.rmtree(dirpath, ignore_errors=True)

def test_apply_worker_patch_create_file(temp_git_repo):
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=tempfile.mkdtemp())
    cfg.repo = temp_git_repo
    session = ConversationalSession(cfg)
    
    artifacts = [
        {
            "type": "patch",
            "payload": {
                "files": ["new_file.txt"],
                "unified_diff": "diff --git a/new_file.txt b/new_file.txt\nnew file mode 100644\n--- /dev/null\n+++ b/new_file.txt\n@@ -0,0 +1 @@\n+hello world from worker\n"
            }
        }
    ]
    
    applied, files, msg = session._apply_worker_patch(artifacts)
    assert applied is True
    assert files == ["new_file.txt"]
    assert "applied cleanly" in msg or "applied with 3way merge" in msg
    
    # Assert file exists with exact contents
    new_filepath = os.path.join(temp_git_repo, "new_file.txt")
    assert os.path.exists(new_filepath)
    with open(new_filepath, "r") as f:
        assert f.read() == "hello world from worker\n"

def test_apply_worker_patch_idempotency(temp_git_repo):
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=tempfile.mkdtemp())
    cfg.repo = temp_git_repo
    session = ConversationalSession(cfg)
    
    artifacts = [
        {
            "type": "patch",
            "payload": {
                "files": ["new_file.txt"],
                "unified_diff": "diff --git a/new_file.txt b/new_file.txt\nnew file mode 100644\n--- /dev/null\n+++ b/new_file.txt\n@@ -0,0 +1 @@\n+hello world from worker\n"
            }
        }
    ]
    
    # 1st apply
    applied, files, msg = session._apply_worker_patch(artifacts)
    assert applied is True
    
    # 2nd apply (idempotency check)
    applied_2, files_2, msg_2 = session._apply_worker_patch(artifacts)
    assert applied_2 is True
    assert files_2 == ["new_file.txt"]
    assert "already applied" in msg_2
    
    # Assert file is still correct
    new_filepath = os.path.join(temp_git_repo, "new_file.txt")
    assert os.path.exists(new_filepath)
    with open(new_filepath, "r") as f:
        assert f.read() == "hello world from worker\n"

def test_apply_worker_patch_modify_file(temp_git_repo):
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=tempfile.mkdtemp())
    cfg.repo = temp_git_repo
    session = ConversationalSession(cfg)
    
    artifacts = [
        {
            "type": "patch",
            "payload": {
                "files": ["base.txt"],
                "unified_diff": "diff --git a/base.txt b/base.txt\n--- a/base.txt\n+++ b/base.txt\n@@ -1,3 +1,4 @@\n Line 1\n+Line 1.5\n Line 2\n Line 3\n"
            }
        }
    ]
    
    applied, files, msg = session._apply_worker_patch(artifacts)
    assert applied is True
    assert files == ["base.txt"]
    assert "applied cleanly" in msg or "applied with 3way merge" in msg
    
    base_filepath = os.path.join(temp_git_repo, "base.txt")
    with open(base_filepath, "r") as f:
        assert f.read() == "Line 1\nLine 1.5\nLine 2\nLine 3\n"

def test_apply_worker_patch_not_cleanly(temp_git_repo):
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=tempfile.mkdtemp())
    cfg.repo = temp_git_repo
    session = ConversationalSession(cfg)
    
    # Context mismatch on base.txt
    artifacts = [
        {
            "type": "patch",
            "payload": {
                "files": ["base.txt"],
                "unified_diff": "diff --git a/base.txt b/base.txt\n--- a/base.txt\n+++ b/base.txt\n@@ -1,3 +1,3 @@\n Nonexistent Line\n-Line 2\n+Line 2 Modified\n Line 3\n"
            }
        }
    ]
    
    applied, files, msg = session._apply_worker_patch(artifacts)
    assert applied is False
    assert "patch did not apply cleanly" in msg
    
    # Assert base.txt remains unchanged
    base_filepath = os.path.join(temp_git_repo, "base.txt")
    with open(base_filepath, "r") as f:
        assert f.read() == "Line 1\nLine 2\nLine 3\n"

def test_apply_worker_patch_no_patch_artifact(temp_git_repo):
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=tempfile.mkdtemp())
    cfg.repo = temp_git_repo
    session = ConversationalSession(cfg)
    
    artifacts = [
        {
            "type": "finding",
            "payload": {
                "report": "Some other finding"
            }
        }
    ]
    
    applied, files, msg = session._apply_worker_patch(artifacts)
    assert applied is False
    assert files == []
    assert msg == "no patch to apply"
