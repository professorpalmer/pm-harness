"""Tests for the open-workspace runtime flow and its REST endpoints."""
import json
import os
import tempfile
import threading
import urllib.request
import urllib.error
import subprocess
from http.server import ThreadingHTTPServer


def _server():
    import harness.server as srv
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port, srv


def _post(port, path, body, headers):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=10)


def _get(port, path, headers=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {}, method="GET")
    return urllib.request.urlopen(req, timeout=10)


def test_open_workspace_endpoints():
    httpd, port, srv = _server()
    try:
        # 1. POST /api/workspace/open without token -> 403
        try:
            _post(port, "/api/workspace/open", {"path": "/tmp"}, {"Content-Type": "application/json"})
            assert False, "should have failed with 403"
        except urllib.error.HTTPError as e:
            assert e.code == 403

        headers = {
            "Content-Type": "application/json",
            "X-Harness-Token": srv._TOKEN
        }

        # 2. POST /api/workspace/open with a non-existent path -> 400
        try:
            _post(port, "/api/workspace/open", {"path": "/nonexistent/path/here/12345"}, headers)
            assert False, "should have failed with 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            resp_body = json.loads(e.read().decode())
            assert "existing directory" in resp_body["error"]

        # 3. Create a temp directory with a git repository
        with tempfile.TemporaryDirectory() as tmpdir:
            real_tmp = os.path.realpath(tmpdir)
            # init git repo
            subprocess.run(["git", "init", "-b", "main", real_tmp], capture_output=True, check=True)
            # configure git dummy user
            subprocess.run(["git", "-C", real_tmp, "config", "user.name", "Test User"], check=True)
            subprocess.run(["git", "-C", real_tmp, "config", "user.email", "test@example.com"], check=True)
            # commit something so HEAD exists and rev-parse branch works
            test_file = os.path.join(real_tmp, "README.md")
            with open(test_file, "w") as f:
                f.write("# Temp Repo")
            subprocess.run(["git", "-C", real_tmp, "add", "README.md"], check=True)
            subprocess.run(["git", "-C", real_tmp, "commit", "-m", "initial commit"], check=True)

            # POST /api/workspace/open with this real git repo path
            res = _post(port, "/api/workspace/open", {"path": real_tmp}, headers)
            assert res.status == 200
            data = json.loads(res.read().decode())
            assert data["ok"] is True
            assert data["repo"] == real_tmp
            assert data["is_git"] is True
            assert data["branch"] == "main"

            # 4. GET /api/workspace -> verify it returns the open workspace info
            res_get = _get(port, f"/api/workspace?token={srv._TOKEN}", {"X-Harness-Token": srv._TOKEN})
            assert res_get.status == 200
            data_get = json.loads(res_get.read().decode())
            assert data_get["repo"] == real_tmp
            assert data_get["is_git"] is True
            assert data_get["branch"] == "main"
            assert "codegraph_status" in data_get

    finally:
        httpd.shutdown()
