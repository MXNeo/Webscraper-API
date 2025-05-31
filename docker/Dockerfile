# Multi-platform support for AMD64 and ARM64 (Apple Silicon)
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright with platform detection
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install platform-specific dependencies
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

# Copy application code
COPY . .

# Set environment variables for cross-platform compatibility
ENV PYTHONUNBUFFERED=1
ENV UVICORN_WORKERS=1
ENV MAX_THREAD_POOL_SIZE=10
ENV PYTHONPATH=/app

# Create non-root user for security (works on all platforms)
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app /ms-playwright
USER appuser

# Expose the port
EXPOSE 8000

# Create startup script for flexible worker configuration
USER root
RUN echo '#!/bin/bash\n\
echo "Starting WebScraper API on $(uname -m) architecture"\n\
echo "Platform: $(uname -s)"\n\
echo "Python version: $(python --version)"\n\
WORKERS=${UVICORN_WORKERS:-1}\n\
if [ "$WORKERS" -gt 1 ]; then\n\
    echo "Starting with $WORKERS workers"\n\
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers $WORKERS\n\
else\n\
    echo "Starting with single worker"\n\
    exec uvicorn main:app --host 0.0.0.0 --port 8000\n\
fi' > /app/start.sh && chmod +x /app/start.sh

# Switch back to non-root user
USER appuser

# Health check that works on all platforms
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run the application
CMD ["/app/start.sh"] 