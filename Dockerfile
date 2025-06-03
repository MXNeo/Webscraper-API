# WebScraper API with Enhanced Metrics System
# Multi-platform support for AMD64 and ARM64 (Apple Silicon)
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    ca-certificates \
    sqlite3 \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Install platform-specific dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers with cross-platform support
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium

# Create directories for persistent storage
RUN mkdir -p /app/data /app/config /app/logs

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV UVICORN_WORKERS=1
ENV MAX_THREAD_POOL_SIZE=10
ENV PYTHONPATH=/app

# Metrics configuration
ENV METRICS_ENABLED=true
ENV PERSIST_METRICS=true
ENV METRICS_DB_PATH=/app/data/metrics.db
ENV MEMORY_RETENTION_HOURS=24
ENV DB_RETENTION_DAYS=30
ENV MAX_MEMORY_ENTRIES=10000

# Proxy pool configuration
ENV PROXY_POOL_SIZE=50
ENV MIN_PROXY_POOL_SIZE=10
ENV PROXY_REFRESH_INTERVAL=300
ENV BATCH_UPDATE_INTERVAL=60

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set proper permissions for data directories
RUN chown -R appuser:appuser /app /ms-playwright
RUN chmod 755 /app/data /app/config /app/logs

# Create startup script with metrics initialization
RUN echo '#!/bin/bash\n\
echo "=== WebScraper API with Enhanced Metrics ==="\n\
echo "Starting on $(uname -m) architecture"\n\
echo "Platform: $(uname -s)"\n\
echo "Python version: $(python --version)"\n\
echo "Metrics enabled: $METRICS_ENABLED"\n\
echo "Persist metrics: $PERSIST_METRICS"\n\
echo "Data directory: /app/data"\n\
echo "Config directory: /app/config"\n\
\n\
# Initialize data directory structure\n\
mkdir -p /app/data /app/config /app/logs\n\
chown -R appuser:appuser /app/data /app/config /app/logs\n\
\n\
# Check if metrics database exists\n\
if [ "$PERSIST_METRICS" = "true" ] && [ ! -f "/app/data/metrics.db" ]; then\n\
    echo "Initializing metrics database..."\n\
    touch /app/data/metrics.db\n\
    chown appuser:appuser /app/data/metrics.db\n\
fi\n\
\n\
echo "Starting WebScraper API..."\n\
WORKERS=${UVICORN_WORKERS:-1}\n\
if [ "$WORKERS" -gt 1 ]; then\n\
    echo "Starting with $WORKERS workers"\n\
    exec gosu appuser uvicorn main:app --host 0.0.0.0 --port 8000 --workers $WORKERS\n\
else\n\
    echo "Starting with single worker"\n\
    exec gosu appuser uvicorn main:app --host 0.0.0.0 --port 8000\n\
fi' > /app/start.sh && chmod +x /app/start.sh

# Expose the port
EXPOSE 8000

# Health check with metrics endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Volume declarations for persistent storage
VOLUME ["/app/data", "/app/config"]

# Run the application
CMD ["/app/start.sh"] 