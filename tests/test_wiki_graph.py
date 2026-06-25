"""Tests for Portable-LLM-Wiki Graph View integration."""
import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

import pytest
from harness.wiki import WikiClient, parse_graph_from_response


def _server():
    import harness.server as srv
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port, srv


def _get(port, path, headers=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {}, method="GET")
    return urllib.request.urlopen(req, timeout=10)


def test_wiki_graph_endpoint_rejected_without_token():
    httpd, port, srv = _server()
    try:
        try:
            _get(port, "/api/wiki/graph")
            assert False, "should have been rejected with 403"
        except urllib.error.HTTPError as e:
            assert e.code == 403
    finally:
        httpd.shutdown()


def test_wiki_graph_endpoint_graceful_not_configured():
    httpd, port, srv = _server()
    orig_url = srv._cfg.wiki_url
    srv._cfg.wiki_url = ""  # simulate not configured
    try:
        resp = _get(port, "/api/wiki/graph", {"X-Harness-Token": srv._TOKEN})
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["configured"] is False
        assert data["status"] == "not_configured"
        assert data["nodes"] == []
        assert data["edges"] == []
    finally:
        srv._cfg.wiki_url = orig_url
        httpd.shutdown()


def test_wiki_client_parse_already_normalized():
    data = {
        "nodes": [
            {"id": "index", "title": "Index Page", "section": "main"},
            {"id": "about", "title": "About Us"}
        ],
        "edges": [
            {"source": "index", "target": "about"}
        ]
    }
    parsed = parse_graph_from_response(data)
    assert parsed["nodes"] == [
        {"id": "index", "title": "Index Page", "section": "main", "tags": None},
        {"id": "about", "title": "About Us", "section": None, "tags": None}
    ]
    assert parsed["edges"] == [
        {"source": "index", "target": "about"}
    ]


def test_wiki_client_parse_manifest_pages():
    data = [
        {
            "slug": "page-one",
            "title": "Page One",
            "section": "docs",
            "tags": ["guide"],
            "links": ["page-two"]
        },
        {
            "slug": "page-two",
            "title": "Page Two",
            "content": "Referencing [[page-one]] and [[non-existent-page|Cool Page]]."
        }
    ]
    parsed = parse_graph_from_response(data)
    assert len(parsed["nodes"]) == 2
    assert parsed["nodes"][0]["id"] == "page-one"
    assert parsed["nodes"][0]["section"] == "docs"
    assert parsed["nodes"][0]["tags"] == ["guide"]
    
    # page-one has explicit link to page-two
    # page-two has content referencing page-one and non-existent-page (which is slugified to non-existent-page)
    # So we should have edges from page-one -> page-two and page-two -> page-one, and page-two -> non-existent-page
    edges = parsed["edges"]
    assert {"source": "page-one", "target": "page-two"} in edges
    assert {"source": "page-two", "target": "page-one"} in edges
    assert {"source": "page-two", "target": "non-existent-page"} in edges


def test_wiki_client_graph_live_mocked(monkeypatch):
    class FakeResp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self):
            return json.dumps([
                {"slug": "a", "title": "A", "links": ["b"]}
            ]).encode()

    def fake_urlopen(req, timeout=0):
        assert req.full_url == "http://mywiki/api/graph"
        assert req.headers.get("Authorization") == "Bearer mysecret"
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = WikiClient(base_url="http://mywiki", token="mysecret")
    res = client.graph()
    assert res["error"] is None
    assert len(res["nodes"]) == 1
    assert res["nodes"][0]["id"] == "a"
    assert res["edges"] == [{"source": "a", "target": "b"}]
