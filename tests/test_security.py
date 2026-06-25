"""Security: the local server must reject cross-origin / rebound / unauthenticated
requests on mutating endpoints (the RCE fix)."""
import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

import pytest


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


def test_mcp_add_rejected_without_token():
    httpd, port, srv = _server()
    try:
        try:
            _post(port, "/api/mcp/add", {"name": "evil", "command": "touch", "args": ["/tmp/pwned_pmharness"]},
                  {"Content-Type": "application/json"})
            assert False, "should have been rejected"
        except urllib.error.HTTPError as e:
            assert e.code == 403
    finally:
        httpd.shutdown()


def test_mcp_add_rejected_cross_origin_even_with_token():
    httpd, port, srv = _server()
    try:
        try:
            _post(port, "/api/mcp/add", {"name": "evil", "command": "touch", "args": ["/tmp/x"]},
                  {"Content-Type": "application/json", "X-Harness-Token": srv._TOKEN,
                   "Origin": "https://evil.com"})
            assert False, "cross-origin should be rejected"
        except urllib.error.HTTPError as e:
            assert e.code == 403
    finally:
        httpd.shutdown()


def test_rebind_host_rejected():
    httpd, port, srv = _server()
    try:
        try:
            _post(port, "/api/mcp/add", {"name": "evil", "command": "touch", "args": ["/tmp/x"]},
                  {"Content-Type": "application/json", "X-Harness-Token": srv._TOKEN,
                   "Host": "evil.attacker.com"})
            assert False, "non-loopback Host should be rejected"
        except urllib.error.HTTPError as e:
            assert e.code == 403
    finally:
        httpd.shutdown()


def test_legit_request_with_token_allowed():
    httpd, port, srv = _server()
    try:
        # remove is harmless + idempotent; proves a properly-tokened same-origin call passes the guard
        r = _post(port, "/api/mcp/remove", {"name": "nonexistent"},
                  {"Content-Type": "application/json", "X-Harness-Token": srv._TOKEN})
        assert r.status == 200
    finally:
        httpd.shutdown()
