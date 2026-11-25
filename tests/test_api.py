"""API-level tests (no network access required)."""
import pytest


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_pages_render(client):
    for path in ("/", "/statistics", "/proxy-management"):
        assert client.get(path).status_code == 200, path


def test_json_scrape_endpoint_is_reachable(client):
    # Used to be shadowed by a Form-based handler on the same path -> always 422
    r = client.post("/api/scrape", json={"url": "http://93.184.215.14/"})
    assert r.status_code == 400
    assert "API key" in r.json()["detail"]


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/api/health",
    "http://localhost/",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.1/",
    "http://192.168.1.1/",
    "http://[::1]/",
    "http://0.0.0.0/",
    "file:///etc/passwd",
    "ftp://93.184.215.14/",
])
@pytest.mark.parametrize("endpoint", [
    "/api/scrape/newspaper", "/api/scrape/newsplease", "/api/scrape/zyte",
    "/api/scrape/scrapegraph", "/api/scrape",
])
def test_ssrf_targets_rejected(client, endpoint, url):
    r = client.post(endpoint, json={"url": url})
    assert r.status_code == 422, (endpoint, url, r.text)


def test_proxies_requires_database_returns_400(client):
    r = client.get("/api/proxies?limit=0")
    assert r.status_code == 400


def test_cors_wildcard_does_not_allow_credentials(client):
    r = client.options("/api/health", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "GET",
    })
    assert r.headers.get("access-control-allow-credentials") != "true"
    assert r.headers.get("access-control-allow-origin") == "*"


def test_config_status(client):
    r = client.get("/api/config/status")
    assert r.status_code == 200
    assert r.json()["database"]["configured"] is False
