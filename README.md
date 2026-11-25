# WebScraper API

[![Docker Pulls](https://img.shields.io/docker/pulls/neoexec/webscraper-api)](https://hub.docker.com/r/neoexec/webscraper-api)
[![Docker Image Size](https://img.shields.io/docker/image-size/neoexec/webscraper-api/latest)](https://hub.docker.com/r/neoexec/webscraper-api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.4.0-blue.svg)](https://github.com/MXNeo/Webscraper-API)

A self-hosted REST API for extracting article content from news and security websites. It combines **Newspaper4k**, **news-please** and the **Zyte API** behind a single, consistent interface, with built-in proxy rotation, threat-intelligence (IOC) table detection, metrics and a web dashboard.

The service is designed to run standalone or as the scraping backend of [Security-News-Analyzer](https://github.com/MXNeo/Security-News-Analyzer).

---

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [API](#api)
- [Configuration](#configuration)
- [Security](#security)
- [Deployment](#deployment)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

**Extraction engines**

| Engine | Endpoint | Best suited for |
|--------|----------|-----------------|
| Newspaper4k | `POST /api/scrape/newspaper` | Fast extraction of standard article pages; optional Playwright fallback for JavaScript-rendered pages |
| news-please | `POST /api/scrape/newsplease` | Rich metadata (language, description, source domain) |
| Zyte API | `POST /api/scrape/zyte` | Sites with bot protection or heavy JavaScript; rendering happens in the Zyte cloud |
| ScrapeGraphAI | `POST /api/scrape/scrapegraph` | LLM-based extraction (optional, not part of the default image) |

**Platform**

- **Proxy pool** – rotates proxies stored in PostgreSQL, tracks errors per proxy and falls back to a direct connection automatically.
- **IOC detection** – recognises indicator tables (hashes, IPs, domains) in security reports and returns them as structured data.
- **Metrics** – success rates, response times and resource usage per engine, persisted in SQLite.
- **Web interface** – configuration, proxy management, statistics dashboard and live log streaming via WebSocket.
- **Hardened by default** – SSRF protection, response size limits, optional authentication, non-root container.
- **Lean image** – about 400 MB, multi-arch (`linux/amd64`, `linux/arm64`).

---

## Quick start

### Docker

```bash
docker run -d --name webscraper-api -p 8000:8000 \
  -e AUTH_PASSWORD=change-me \
  -v "$(pwd)/config:/app/config" \
  -v "$(pwd)/data:/app/data" \
  neoexec/webscraper-api:1.4.0
```

Open <http://localhost:8000> and sign in as `admin` with the password you set.

### Docker Compose (with PostgreSQL)

```bash
git clone https://github.com/MXNeo/Webscraper-API.git
cd Webscraper-API
cp env.example docker/.env      # set at least DB_PASSWORD, ideally AUTH_PASSWORD
cd docker
docker compose up -d
```

The compose file starts the API and a PostgreSQL instance, initialises the proxy schema and persists configuration in `./config` and metrics in `./data`.

### Local

Requires Python 3.11 or later.

```bash
git clone https://github.com/MXNeo/Webscraper-API.git
cd Webscraper-API
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
uvicorn main:app --reload
```

Optional engines (adds roughly 8 GB):

```bash
pip install -r requirements-optional.txt
playwright install chromium
```

### Endpoints at a glance

| URL | Purpose |
|-----|---------|
| `http://localhost:8000/` | Web interface |
| `http://localhost:8000/statistics` | Metrics dashboard |
| `http://localhost:8000/proxy-management` | Proxy management |
| `http://localhost:8000/docs` | Interactive OpenAPI documentation |
| `http://localhost:8000/api/health` | Health check (no authentication) |

---

## API

All scrape endpoints accept the same request body:

```json
{
  "url": "https://example.com/article",
  "use_proxy": false,
  "api_key": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `url` | string, required | Public `http`/`https` URL to scrape |
| `use_proxy` | boolean | Route the request through the proxy pool (default: pool setting) |
| `api_key` | string | Per-request key for Zyte or ScrapeGraphAI; overrides the configured key |

### Example

```bash
curl -X POST http://localhost:8000/api/scrape/newspaper \
  -u admin:$AUTH_PASSWORD \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

### Response

```json
{
  "url": "https://example.com/article",
  "status": "success",
  "error": null,
  "proxy_used": null,
  "content": {
    "title": "Article title",
    "content": "Full article text ...",
    "authors": ["Jane Doe"],
    "published": "2025-05-31T10:00:00",
    "top_image": "https://example.com/image.jpg"
  }
}
```

`status` is either `success` or `error`; on error, `error` contains the reason. Depending on the engine, `content` contains additional fields:

| Engine | Additional fields |
|--------|-------------------|
| Newspaper4k | `summary`, `tables_found`, `iocs_found`, `structured_iocs`, `structured_domain_iocs` |
| news-please | `description`, `language`, `source_domain`, `url` |

URLs that point to private or internal addresses are rejected with `422 Unprocessable Entity` (see [Security](#security)).

### Zyte API

The Zyte key is resolved in this order: `api_key` in the request → `ZYTE_API_KEY` environment variable → key stored via the web interface.

---

## Configuration

Settings are read from environment variables (or a `.env` file). Values entered in the web interface are stored encrypted in `CONFIG_DIR`. [`env.example`](env.example) lists every option.

### General

| Variable | Default | Description |
|----------|---------|-------------|
| `ZYTE_API_KEY` | – | Zyte API key |
| `OPENAI_API_KEY` | – | OpenAI key for ScrapeGraphAI |
| `CONFIG_DIR` | `./config` (`/app/config` in Docker) | Location of `config.json` and `secret.key` |
| `UVICORN_WORKERS` | `1` | Number of worker processes (Docker image) |
| `MAX_THREAD_POOL_SIZE` | `10` | Concurrent scrape jobs per worker |
| `REQUEST_TIMEOUT` | `15` | Upstream request timeout in seconds |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_PASSWORD` | – | Enables authentication for UI, API and WebSocket |
| `AUTH_USERNAME` | `admin` | Username for HTTP Basic authentication |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed origins |
| `ALLOW_PRIVATE_URLS` | `false` | Allow scraping of private and internal addresses |
| `MAX_CONTENT_LENGTH` | `10485760` | Maximum response size in bytes |
| `MAX_REDIRECTS` | `5` | Maximum redirects per request |

### Proxy pool

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | – | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | – | Database name |
| `DB_USER` | – | Database user |
| `DB_PASSWORD` | – | Database password |
| `DB_TABLE` | `proxies` | Proxy table name |
| `PROXY_ENABLED` | `false` | Activate the proxy pool on startup |
| `PROXY_POOL_SIZE` | `50` | Maximum proxies held in memory |
| `MIN_PROXY_POOL_SIZE` | `10` | Threshold that triggers a refill |
| `PROXY_REFRESH_INTERVAL` | `300` | Pool refresh interval in seconds |

With `PROXY_ENABLED=true` and all `DB_*` variables set, the pool is activated at startup without any manual step in the web interface.

### Metrics

| Variable | Default | Description |
|----------|---------|-------------|
| `METRICS_ENABLED` | `true` | Collect request metrics |
| `PERSIST_METRICS` | `true` | Persist metrics to SQLite |
| `METRICS_DB_PATH` | `data/metrics.db` | SQLite database path |
| `MEMORY_RETENTION_HOURS` | `24` | In-memory retention |
| `DB_RETENTION_DAYS` | `30` | Persistent retention |

---

## Security

| Measure | Details |
|---------|---------|
| SSRF protection | Requests to loopback, private, link-local (including cloud metadata such as `169.254.169.254`), CGNAT and reserved addresses are blocked. Redirect targets are validated as well. |
| Resource limits | Responses are capped at `MAX_CONTENT_LENGTH`, redirects at `MAX_REDIRECTS`. |
| Authentication | When `AUTH_PASSWORD` is set, every request except `/api/health` requires credentials via HTTP Basic, `Authorization: Bearer <password>` or `X-API-Key: <password>`. |
| CORS | Credentials are only accepted for explicitly listed origins, never for the `*` wildcard. |
| Secret storage | Credentials entered in the UI are encrypted (Fernet) and stored with owner-only permissions. Proxy passwords are never returned by the API. |
| Container | Runs as an unprivileged user; local `.env`, `config/` and `data/` are excluded from the build context. |

> **Recommendation:** Set `AUTH_PASSWORD` whenever the service is reachable by anyone other than yourself. Without it, any client on the network can use the API and change its configuration.

To scrape intranet hosts deliberately, set `ALLOW_PRIVATE_URLS=true` and restrict access to the service accordingly.

---

## Deployment

### Integration with Security-News-Analyzer

The API can share the PostgreSQL `proxies` table of the main pipeline:

```yaml
webscraper-api:
  image: neoexec/webscraper-api:1.4.0
  environment:
    DB_HOST: postgres
    DB_NAME: ${POSTGRES_DB}
    DB_USER: ${POSTGRES_USER}
    DB_PASSWORD: ${POSTGRES_PASSWORD}
    PROXY_ENABLED: "true"
    ZYTE_API_KEY: ${ZYTE_API_KEY}
    AUTH_PASSWORD: ${WEBSCRAPER_PASSWORD}
  volumes:
    - ./webscraper/config:/app/config
    - ./webscraper/data:/app/data
```

### Compose variants

| File | Purpose |
|------|---------|
| `docker/docker-compose.yml` | API + PostgreSQL, built from source |
| `docker/docker-compose.full.yml` | API + PostgreSQL + optional pgAdmin (`--profile tools`) |
| `docker/docker-compose.standalone.yml` | API only, no database |
| `docker/docker-compose.test.yml` | Test environment with sample proxies |

### Kubernetes

Manifests for Kubernetes and K3s, including persistent volumes, are available in [`k8s/`](k8s). See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for details.

### Sizing

| Setup | Concurrent requests | Memory |
|-------|---------------------|--------|
| 1 worker, 10 threads | ~10 | ~256 MB |
| 2 workers, 10 threads | ~20 | ~512 MB |
| 3 replicas × 2 workers | ~60 | ~1.5 GB |

Typical response times are 5–15 seconds per article, depending on the target site and proxy.

---

## Development

### Project structure

```
├── main.py                    FastAPI application and endpoints
├── security.py                URL validation, safe fetching, authentication
├── config.py                  Configuration and encrypted secret storage
├── database.py                PostgreSQL access
├── proxy_pool.py              Proxy pool and retry handling
├── table_extraction.py        IOC and table detection
├── metrics.py                 Metrics collection
├── templates/, static/        Web interface
├── tests/                     Test suite
├── docker/                    Dockerfile and compose files
├── k8s/                       Kubernetes manifests
└── docs/                      Additional documentation
```

### Tests

```bash
pip install pytest
pytest tests
```

The suite runs without network access or database.

### Building the image

```bash
docker build -f docker/Dockerfile -t neoexec/webscraper-api:latest .

# Multi-arch
docker buildx build --platform linux/amd64,linux/arm64 \
  -f docker/Dockerfile -t neoexec/webscraper-api:latest --push .
```

---

## Troubleshooting

| Symptom | Cause and solution |
|---------|--------------------|
| `failed to mount local volume ... /config: no such file or directory` | Outdated compose file. Update the repository, or create the directories with `mkdir -p config data`. |
| `required variable DB_PASSWORD is missing a value` | Set `DB_PASSWORD` in `docker/.env`. |
| `422` with "Access to non-public address ... is blocked" | The URL resolves to an internal address. Set `ALLOW_PRIVATE_URLS=true` if this is intended. |
| `401 Authentication required` | `AUTH_PASSWORD` is set; provide credentials. |
| Proxy pool does not activate | Check that `PROXY_ENABLED=true` and all `DB_*` variables are set, then look for `Proxy pool auto-enabled` in the logs. |
| Zyte returns an empty body | Some pages require a Zyte plan with browser rendering. |
| ScrapeGraphAI or Playwright not available | Not included in the default image; install `requirements-optional.txt`. |

---

## License

Released under the [MIT License](LICENSE).

Built on [FastAPI](https://fastapi.tiangolo.com/), [Newspaper4k](https://github.com/AndyTheFactory/newspaper4k), [news-please](https://github.com/fhamborg/news-please), [Zyte API](https://www.zyte.com/), [ScrapeGraphAI](https://github.com/ScrapeGraphAI/Scrapegraph-ai) and [psutil](https://github.com/giampaolo/psutil).
