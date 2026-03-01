# WebScraper API optimized for news articles 🚀

[![Docker Pulls](https://img.shields.io/docker/pulls/neoexec/webscraper-api)](https://hub.docker.com/r/neoexec/webscraper-api)
[![Docker Image Size](https://img.shields.io/docker/image-size/neoexec/webscraper-api/latest)](https://hub.docker.com/r/neoexec/webscraper-api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-1.4.0-blue.svg)](https://github.com/MXNeo/Webscraper-API)

A production-ready web scraping API combining **Newspaper4k**, **News-Please**, and **Zyte API** for intelligent content extraction with full proxy-pool support. Features a modern web interface, real-time metrics, and plug-and-play integration with [Security-News-Analyzer](https://github.com/MXNeo/Security-News-Analyzer).

## ✨ Features

### 🔧 Scraping Methods

| Method | Endpoint | Description |
|--------|----------|-------------|
| **Newspaper4k** | `POST /api/scrape/newspaper` | Fast extraction; Playwright JS-render fallback (if installed) |
| **News-Please** | `POST /api/scrape/newsplease` | Advanced news extraction with proxy support |
| **Zyte API** | `POST /api/scrape/zyte` | Premium anti-bot / JS-render via Zyte cloud — no local browser needed |
| **ScrapGraph AI** | `POST /api/scrape/scrapegraph` | LLM-powered scraping (optional, not in default image) |

> **ScrapGraph AI** and **Playwright** are **not included** in the default Docker image to keep it lean (~400 MB).
> Install them locally via `pip install -r requirements-optional.txt`.

### 🌐 Proxy Pool (Plug-and-play with Security-News-Analyzer)

The container can automatically connect to the shared PostgreSQL `proxies` table used by the main pipeline:

```yaml
# docker-compose snippet (Security-News-Analyzer)
webscraper-api:
  image: neoexec/webscraper-api:1.4.0
  environment:
    # Point to the shared Postgres instance
    DB_HOST: postgres
    DB_PORT: 5432
    DB_NAME: ${POSTGRES_DB}
    DB_USER: ${POSTGRES_USER}
    DB_PASSWORD: ${POSTGRES_PASSWORD}
    DB_TABLE: proxies          # default - matches main project schema
    PROXY_ENABLED: "true"      # auto-enable on startup (no UI click needed)
    # Optional: pass your Zyte key for anti-bot scraping
    ZYTE_API_KEY: ${ZYTE_API_KEY}
```

Setting `PROXY_ENABLED=true` together with valid `DB_*` variables is all that is needed — the container reads the proxy list from PostgreSQL at startup and begins rotating them automatically.

### 📊 Enhanced Metrics & Monitoring
- Real-time RAM / CPU usage via psutil
- Per-method request success/failure rates and response times
- Interactive charts (hourly/daily breakdowns)
- WebSocket real-time log streaming
- Database health monitoring and automatic recovery

### 🐳 Deployment Options
- **Docker** — single container, multi-arch (amd64 + arm64)
- **Docker Compose** — multi-service with PostgreSQL
- **Kubernetes/K3s** — persistent storage, RBAC

---

## 🚀 Quick Start

### Option 1: Docker Hub

```bash
# Minimal - no AI features
docker run -d -p 8000:8000 neoexec/webscraper-api:1.4.0

# With Zyte API
docker run -d -p 8000:8000 \
  -e ZYTE_API_KEY=your-zyte-key \
  neoexec/webscraper-api:1.4.0

# With proxy pool from Postgres
docker run -d -p 8000:8000 \
  -e DB_HOST=your-postgres-host \
  -e DB_NAME=your-db \
  -e DB_USER=your-user \
  -e DB_PASSWORD=your-password \
  -e PROXY_ENABLED=true \
  neoexec/webscraper-api:1.4.0
```

### Option 2: Docker Compose

```bash
git clone https://github.com/MXNeo/Webscraper-API.git
cd Webscraper-API
cp env.example docker/.env
# Edit docker/.env
cd docker
docker-compose up -d
```

### Option 3: Local Development

```bash
git clone https://github.com/MXNeo/Webscraper-API.git
cd Webscraper-API
pip install -r requirements.txt

# Optional: add Playwright + ScrapGraphAI
pip install -r requirements-optional.txt
playwright install chromium

cp env.example .env
# Edit .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🌐 Access Points

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | Web interface + metrics dashboard |
| `http://localhost:8000/docs` | Interactive API documentation |
| `http://localhost:8000/api/health` | Health check + version info |

---

## 📡 API Usage

### Newspaper4k (fast)

```bash
curl -X POST "http://localhost:8000/api/scrape/newspaper" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

### News-Please (advanced)

```bash
curl -X POST "http://localhost:8000/api/scrape/newsplease" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

### Zyte API (anti-bot / JS-heavy sites)

```bash
# API key via env var ZYTE_API_KEY  -OR-  pass inline:
curl -X POST "http://localhost:8000/api/scrape/zyte" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "api_key": "your-zyte-key"}'
```

API key resolution order: `request.api_key` → `ZYTE_API_KEY` env var → Web UI config

### ScrapGraph AI (optional — not in default image)

```bash
curl -X POST "http://localhost:8000/api/scrape/scrapegraph" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "api_key": "sk-your-openai-key"}'
```

### Unified Response Format

All methods return the same JSON schema:

```json
{
  "url": "https://example.com/article",
  "content": {
    "content": "Full article text...",
    "top_image": "https://example.com/image.jpg",
    "published": "2025-05-31T10:00:00"
  },
  "status": "success",
  "error": null,
  "method": "newspaper4k|newsplease|zyte|scrapegraph",
  "processing_time": 2.34
}
```

---

## ⚙️ Configuration

### Environment Variables

#### Core API

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ZYTE_API_KEY` | Zyte API key for premium scraping | — | For Zyte method |
| `OPENAI_API_KEY` | OpenAI key for ScrapGraph AI | — | For AI method |
| `ANTHROPIC_API_KEY` | Anthropic key for Claude | — | For AI method |
| `UVICORN_WORKERS` | Uvicorn worker count | `1` | No |
| `MAX_THREAD_POOL_SIZE` | Thread pool per worker | `10` | No |

#### Proxy Pool (Security-News-Analyzer integration)

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_HOST` | PostgreSQL host | — |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | — |
| `DB_USER` | Database user | — |
| `DB_PASSWORD` | Database password | — |
| `DB_TABLE` | Proxy table name | `proxies` |
| `PROXY_ENABLED` | Auto-enable proxy pool at startup | `false` |
| `PROXY_POOL_SIZE` | Max proxies in pool | `50` |
| `MIN_PROXY_POOL_SIZE` | Refill threshold | `10` |
| `PROXY_REFRESH_INTERVAL` | Pool refresh interval (s) | `300` |

#### Metrics

| Variable | Description | Default |
|----------|-------------|---------|
| `METRICS_ENABLED` | Enable metrics collection | `true` |
| `PERSIST_METRICS` | Persist metrics to SQLite | `true` |
| `MEMORY_RETENTION_HOURS` | In-memory metric retention | `24` |
| `DB_RETENTION_DAYS` | SQLite metric retention | `30` |

---

## 📊 Performance

### Concurrency

| Config | Concurrent | Response time | RAM |
|--------|-----------|---------------|-----|
| 1 worker, 10 threads | ~10 | 5-15 s | ~256 MB |
| 2 workers, 10 threads | ~20 | 5-15 s | ~512 MB |
| 3 pods × 2 workers | ~60 | 5-15 s | ~1.5 GB |

### Image Sizes (v1.4.0 vs previous)

| | v1.3.x | v1.4.0 |
|--|--------|--------|
| Compressed (Docker Hub) | ~3 GB | ~200 MB |
| Uncompressed | ~17 GB | ~400 MB |

Savings come from removing Playwright browser binaries (~1.5 GB) and ScrapGraphAI / PyTorch / Transformers (~8 GB). Both remain available as optional installs.

---

## 🆕 What's New in v1.4.0

### ✨ New Features
- **🕸️ Zyte API Integration**: New `/api/scrape/zyte` endpoint — handles anti-bot protection, JS rendering, and proxy rotation in the cloud. API key resolves from `ZYTE_API_KEY` env var → request body → Web UI.
- **🔌 Proxy Auto-Pickup**: Set `PROXY_ENABLED=true` with `DB_*` env vars and the proxy pool activates automatically at container startup — no Web UI click required.
- **⚡ 97% smaller Docker image**: Playwright and ScrapGraphAI moved to `requirements-optional.txt`. Default image is now ~400 MB (was ~17 GB).

### 🐛 Bug Fixes
- Fixed: DB config loaded from env vars was not propagated into `config_store`, so proxy pool was never activated even when `DB_*` vars were set correctly.

---

## 🛠️ Development

### Project Structure

```
├── main.py                    # FastAPI application
├── config.py                  # Configuration management
├── database.py                # Database + proxy pool utilities
├── metrics.py                 # Real-time metrics system
├── requirements.txt           # Core dependencies (~400 MB image)
├── requirements-optional.txt  # playwright + scrapegraphai (+8 GB)
├── env.example                # Environment variable template
├── docker/
│   ├── Dockerfile            # Slim multi-arch build (no Playwright)
│   ├── docker-compose.yml    # Multi-service orchestration
│   └── README.md
├── k8s/                      # Kubernetes deployment files
├── templates/                 # Jinja2 HTML templates
└── static/                    # CSS + JS assets
```

### Building the Image

```bash
# Standard build
docker build -f docker/Dockerfile -t neoexec/webscraper-api:1.4.0 .

# Multi-arch (requires buildx)
docker buildx build --platform linux/amd64,linux/arm64 \
  -f docker/Dockerfile \
  -t neoexec/webscraper-api:1.4.0 \
  --push .
```

---

## 🔒 Security

- API keys are never baked into the image — always pass via environment variables
- Container runs as non-root (`appuser`)
- Input validation on all endpoints
- No sensitive data exposed in error responses

---

## 📋 Troubleshooting

**Proxy pool not activating**  
→ Ensure `PROXY_ENABLED=true` AND all `DB_*` variables are set. Check startup logs for `"Proxy pool auto-enabled"`.

**Zyte returns empty body**  
→ Some paywalled / dynamic pages require a paid Zyte plan with JavaScript rendering enabled.

**ScrapGraph / Playwright not found**  
→ These are not in the default image. Run `pip install -r requirements-optional.txt` and `playwright install chromium` for local use.

**Container won't start**  
→ Check `docker logs <container>`. Common causes: port 8000 in use, insufficient memory.

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

## 🙏 Acknowledgments

- [News-Please](https://github.com/fhamborg/news-please)
- [Newspaper4k](https://github.com/AndyTheFactory/newspaper4k)
- [ScrapGraph AI](https://github.com/VinciGit00/Scrapegraph-ai)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Zyte](https://www.zyte.com/)
- [psutil](https://github.com/giampaolo/psutil)

---

**Ready to scrape?** 🚀 Pull the latest slim image: `docker pull neoexec/webscraper-api:1.4.0`
