"""Unit tests for security.py and config.py hardening."""
import base64
import json
import os

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

import security
from security import AuthMiddleware, ContentTooLargeError, UnsafeURLError, safe_get, validate_url


# ---------------------------------------------------------------- validate_url

def test_public_ip_allowed():
    assert validate_url("https://93.184.215.14/path") == "https://93.184.215.14/path"


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://10.1.2.3/", "http://172.16.0.1/", "http://192.168.0.1/",
    "http://169.254.169.254/", "http://100.64.0.1/", "http://[::1]/", "http://[::ffff:127.0.0.1]/",
    "http://0.0.0.0/", "gopher://93.184.215.14/", "http:///nohost", "",
])
def test_private_or_invalid_rejected(url):
    with pytest.raises(UnsafeURLError):
        validate_url(url)


def test_hostname_resolving_to_private_rejected(monkeypatch):
    monkeypatch.setattr(security.socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("10.0.0.5", 80))])
    with pytest.raises(UnsafeURLError):
        validate_url("http://innocent-looking.example/")


def test_allow_private_urls_override(monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_URLS", "true")
    assert validate_url("http://127.0.0.1/")
    with pytest.raises(UnsafeURLError):  # scheme is still enforced
        validate_url("file:///etc/passwd")


# ---------------------------------------------------------------- safe_get

class FakeResponse:
    def __init__(self, status=200, headers=None, body=b"<html></html>"):
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self.encoding = "utf-8"

    @property
    def is_redirect(self):
        return self.status_code in (301, 302, 303, 307, 308) and "location" in self.headers

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        assert kwargs["allow_redirects"] is False
        self.calls.append(url)
        return self.responses.pop(0)


def test_safe_get_follows_public_redirect():
    s = FakeSession([FakeResponse(302, {"location": "https://93.184.215.15/b"}), FakeResponse()])
    r = safe_get("https://93.184.215.14/a", session=s)
    assert r._content == b"<html></html>"
    assert s.calls == ["https://93.184.215.14/a", "https://93.184.215.15/b"]


def test_safe_get_blocks_redirect_to_internal():
    s = FakeSession([FakeResponse(302, {"location": "http://169.254.169.254/latest/meta-data"})])
    with pytest.raises(UnsafeURLError):
        safe_get("https://93.184.215.14/a", session=s)
    assert len(s.calls) == 1


def test_safe_get_redirect_limit():
    import requests
    s = FakeSession([FakeResponse(302, {"location": "/loop"}) for _ in range(10)])
    with pytest.raises(requests.TooManyRedirects):
        safe_get("https://93.184.215.14/loop", session=s, max_redirects=3)


def test_safe_get_size_limit_declared_and_streamed():
    s = FakeSession([FakeResponse(headers={"content-length": "999999"})])
    with pytest.raises(ContentTooLargeError):
        safe_get("https://93.184.215.14/", session=s, max_bytes=1000)

    s = FakeSession([FakeResponse(body=b"x" * 5000)])
    with pytest.raises(ContentTooLargeError):
        safe_get("https://93.184.215.14/", session=s, max_bytes=1000)


# ---------------------------------------------------------------- auth middleware

def _auth_app():
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/secret")
    def secret():
        return {"secret": 42}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("hi")
        await websocket.close()

    app.add_middleware(AuthMiddleware, username="admin", password="s3cret")
    return TestClient(app)


def _basic(user, pwd):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode()}


def test_auth_required_and_health_public():
    c = _auth_app()
    assert c.get("/api/health").status_code == 200
    r = c.get("/api/secret")
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith("Basic")


@pytest.mark.parametrize("headers,ok", [
    (_basic("admin", "s3cret"), True),
    (_basic("admin", "wrong"), False),
    (_basic("other", "s3cret"), False),
    ({"Authorization": "Bearer s3cret"}, True),
    ({"Authorization": "Bearer nope"}, False),
    ({"X-API-Key": "s3cret"}, True),
    ({"X-API-Key": "nope"}, False),
    ({"Authorization": "Basic !!!notbase64"}, False),
])
def test_auth_credentials(headers, ok):
    r = _auth_app().get("/api/secret", headers=headers)
    assert (r.status_code == 200) is ok


def test_auth_websocket():
    c = _auth_app()
    with c.websocket_connect("/ws", headers={"X-API-Key": "s3cret"}) as ws:
        assert ws.receive_text() == "hi"
    with pytest.raises(Exception):
        with c.websocket_connect("/ws") as ws:
            ws.receive_text()


# ---------------------------------------------------------------- config storage

def test_config_uses_config_dir_and_migrates_legacy(tmp_path, monkeypatch):
    from config import Config

    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"scrapegraph": {}, "database": {}}))
    from cryptography.fernet import Fernet
    (tmp_path / "secret.key").write_bytes(Fernet.generate_key())
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path / "cfg"))

    cfg = Config()
    assert not (tmp_path / "config.json").exists()
    assert (tmp_path / "cfg" / "config.json").exists()
    assert (tmp_path / "cfg" / "secret.key").exists()

    cfg.update_database_config("db", "name", "proxies", "user", "pw")
    raw = json.loads((tmp_path / "cfg" / "config.json").read_text())
    assert raw["database"]["password"] != "pw"  # stored encrypted
    assert Config().get_database_config()["password"] == "pw"


def test_corrupt_config_does_not_crash(tmp_path, monkeypatch):
    from config import Config

    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    (tmp_path / "config.json").write_text("{not json")
    cfg = Config()
    assert cfg.config["database"] == {}


def test_wrong_key_does_not_crash(tmp_path, monkeypatch):
    from config import Config

    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    Config().update_database_config("db", "name", "proxies", "user", "pw")
    os.remove(tmp_path / "secret.key")  # key lost -> new key generated
    assert Config().get_database_config()["password"] == ""
