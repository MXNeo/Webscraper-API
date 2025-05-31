FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
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
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install -r requirements.txt

# Install Playwright browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV UVICORN_WORKERS=1
ENV MAX_THREAD_POOL_SIZE=10

# Expose the port
EXPOSE 8000

# Create startup script for flexible worker configuration
RUN echo '#!/bin/bash\n\
WORKERS=${UVICORN_WORKERS:-1}\n\
if [ "$WORKERS" -gt 1 ]; then\n\
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers $WORKERS\n\
else\n\
    exec uvicorn main:app --host 0.0.0.0 --port 8000\n\
fi' > /app/start.sh && chmod +x /app/start.sh

# Run the application
CMD ["/app/start.sh"] 