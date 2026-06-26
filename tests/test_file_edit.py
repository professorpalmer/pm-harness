import os
import json
import threading
import urllib.request
import urllib.error
import tempfile
import shutil
from http.server import ThreadingHTTPServer
import subprocess

def _start_server(repo_path):
    os.environ["HARNESS_DRIVER"] = "stub-oracle-v2"
    os.environ["HARNESS_BUDGET"] = "2"
    os.environ["HARNESS_REPO"] = repo_path
    
    import importlib
    import harness.server as srv
    importlib.reload(srv)
    
    srv._cfg.repo = repo_path
    
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port

def test_file_edit_endpoints():
    temp_dir = tempfile.mkdtemp()
    
    # Initialize ephemeral git repo for checkpoints to work
    subprocess.run(["git", "init", "-b", "main"], cwd=temp_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, capture_output=True)
    
    # Create an initial file and commit it so snapshot has a baseline
    init_file = os.path.join(temp_dir, "init.txt")
    with open(init_file, "w") as f:
        f.write("Initial content")
    subprocess.run(["git", "add", "init.txt"], cwd=temp_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=temp_dir, capture_output=True)
    
    httpd, port = _start_server(temp_dir)
    try:
        base = f"http://127.0.0.1:{port}"
        import harness.server as srv
        token = srv._TOKEN
        
        # Test 1: Endpoint 403 without token (GET)
        try:
            urllib.request.urlopen(base + "/api/file/read?path=init.txt", timeout=10)
            assert False, "Should have raised 403"
        except urllib.error.HTTPError as e:
            assert e.code == 403
            
        # Test 2: Endpoint 403 without token (POST)
        try:
            req = urllib.request.Request(
                base + "/api/file/write",
                data=json.dumps({"path": "init.txt", "content": "hack"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=10)
            assert False, "Should have raised 403"
        except urllib.error.HTTPError as e:
            assert e.code == 403
            
        # Test 3: Read returns confined file content
        req = urllib.request.Request(
            base + f"/api/file/read?path=init.txt",
            headers={"X-Harness-Token": token}
        )
        res = json.load(urllib.request.urlopen(req, timeout=10))
        assert res["ok"] is True
        assert res["path"] == "init.txt"
        assert res["content"] == "Initial content"
        assert res["truncated"] is False
        
        # Test 4: Traverse escapes (realpath check) should be rejected
        req = urllib.request.Request(
            base + f"/api/file/read?path=../something.txt",
            headers={"X-Harness-Token": token}
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            assert False, "Should have blocked traversal"
        except urllib.error.HTTPError as e:
            assert e.code in (403, 400)
            
        # Test 5: Rejects writes with traversal or inside .git
        req = urllib.request.Request(
            base + "/api/file/write",
            data=json.dumps({"path": "../traversal.txt", "content": "hack"}).encode(),
            headers={"Content-Type": "application/json", "X-Harness-Token": token},
            method="POST"
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            assert False, "Should have blocked traversal"
        except urllib.error.HTTPError as e:
            assert e.code in (403, 400)
            
        req = urllib.request.Request(
            base + "/api/file/write",
            data=json.dumps({"path": ".git/config", "content": "hack"}).encode(),
            headers={"Content-Type": "application/json", "X-Harness-Token": token},
            method="POST"
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            assert False, "Should have blocked .git write"
        except urllib.error.HTTPError as e:
            assert e.code in (403, 400)
            
        # Test 6: Write writes file atomically + takes a checkpoint first
        req = urllib.request.Request(
            base + "/api/file/write",
            data=json.dumps({"path": "new_file.txt", "content": "New edited content"}).encode(),
            headers={"Content-Type": "application/json", "X-Harness-Token": token},
            method="POST"
        )
        write_res = json.load(urllib.request.urlopen(req, timeout=10))
        assert write_res["ok"] is True
        assert write_res["bytes"] == len("New edited content")
        
        # Check file was written
        new_file_abs = os.path.join(temp_dir, "new_file.txt")
        assert os.path.exists(new_file_abs)
        with open(new_file_abs, "r") as f:
            assert f.read() == "New edited content"
            
        # Check checkpoint was created!
        from harness.checkpoints import CheckpointStore
        store = CheckpointStore(temp_dir)
        checkpoints = store.list()
        assert len(checkpoints) > 0
        assert checkpoints[0]["trigger"] == "manual_edit"
        assert "before manual edit new_file.txt" in checkpoints[0]["label"]
        
    finally:
        httpd.shutdown()
        shutil.rmtree(temp_dir)
