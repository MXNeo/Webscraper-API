# WebScraper API - Slim production image (v1.4.0)
# Removed: playwright browser install, scrapegraphai (torch/ML deps) → ~400 MB vs ~17 GB
# Optional heavy deps are documented in requirements-optional.txt
# Multi-platform: AMD64 and ARM64 (Apple Silicon)
FROM python:3.11-slim

WORKDIR /app

# Single layer for ALL system deps - no playwright browser libs needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    ca-certificates \
    sqlite3 \
    gosu \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies (no cache, no compile bytecode for smaller image)
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for persistent storage
RUN mkdir -p /app/data /app/config /app/logs

# Copy application code
COPY . .

# ---------- Runtime environment ----------

ENV PYTHONUNBUFFERED=1
ENV UVICORN_WORKERS=1
ENV MAX_THREAD_POOL_SIZE=10
ENV PYTHONPATH=/app

# Metrics
ENV METRICS_ENABLED=true
ENV PERSIST_METRICS=true
ENV METRICS_DB_PATH=/app/data/metrics.db
ENV MEMORY_RETENTION_HOURS=24
ENV DB_RETENTION_DAYS=30
ENV MAX_MEMORY_ENTRIES=10000

# Proxy pool
ENV PROXY_POOL_SIZE=50
ENV MIN_PROXY_POOL_SIZE=10
ENV PROXY_REFRESH_INTERVAL=300
ENV BATCH_UPDATE_INTERVAL=60

# Proxy auto-enable at startup (set to "true" together with DB_* vars)
ENV PROXY_ENABLED=false

# Zyte API (optional - pass via docker-compose / k8s secret)
ENV ZYTE_API_KEY=""

# ---------- Security ----------
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
RUN chmod 755 /app/data /app/config /app/logs

# ---------- Startup script ----------
RUN printf '#!/bin/bash\n\
echo "=== WebScraper API v1.4.0 ==="\n\
echo "Architecture : $(uname -m)"\n\
echo "Python       : $(python --version)"\n\
echo "Metrics      : $METRICS_ENABLED"\n\
echo "Proxy enabled: $PROXY_ENABLED"\n\
echo "Zyte key set : $([ -n \"$ZYTE_API_KEY\" ] && echo yes || echo no)"\n\
\n\
mkdir -p /app/data /app/config /app/logs\n\
chown -R appuser:appuser /app/data /app/config /app/logs\n\
\n\
if [ "$PERSIST_METRICS" = "true" ] && [ ! -f "/app/data/metrics.db" ]; then\n\
    touch /app/data/metrics.db\n\
    chown appuser:appuser /app/data/metrics.db\n\
fi\n\
\n\
WORKERS=${UVICORN_WORKERS:-1}\n\
if [ "$WORKERS" -gt 1 ]; then\n\
    echo "Starting with $WORKERS workers"\n\
    exec gosu appuser uvicorn main:app --host 0.0.0.0 --port 8000 --workers $WORKERS\n\
else\n\
    echo "Starting with single worker"\n\
    exec gosu appuser uvicorn main:app --host 0.0.0.0 --port 8000\n\
fi\n' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

VOLUME ["/app/data", "/app/config"]

CMD ["/app/start.sh"]
