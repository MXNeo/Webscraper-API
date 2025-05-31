# WebScraper API - Docker Image

[![Docker Pulls](https://img.shields.io/docker/pulls/neoexec/webscraper-api)](https://hub.docker.com/r/neoexec/webscraper-api)
[![Docker Image Size](https://img.shields.io/docker/image-size/neoexec/webscraper-api/latest)](https://hub.docker.com/r/neoexec/webscraper-api)

A powerful, production-ready web scraping API that combines **Newspaper4k** and **ScrapGraph AI** for intelligent content extraction. Features a modern web interface, configurable LLM providers, and optimized for concurrent requests.

## 🚀 Quick Start

### Basic Usage

```bash
# Run with default settings
docker run -d -p 8000:8000 neoexec/webscraper-api:latest

# Run with OpenAI API key
docker run -d -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-api-key \
  neoexec/webscraper-api:latest

# Run with multiple workers for high concurrency
docker run -d -p 8000:8000 \
  -e UVICORN_WORKERS=2 \
  -e MAX_THREAD_POOL_SIZE=10 \
  -e OPENAI_API_KEY=sk-your-api-key \
  neoexec/webscraper-api:latest
```

### Access the Application

- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for ScrapGraph AI | None | For AI scraping |
| `UVICORN_WORKERS` | Number of worker processes | 1 | No |
| `MAX_THREAD_POOL_SIZE` | Thread pool size per worker | 10 | No |
| `PYTHONUNBUFFERED` | Python output buffering | 1 | No |

### Resource Requirements

| Scenario | Memory | CPU | Workers | Capacity |
|----------|--------|-----|---------|----------|
| **Light Usage** | 512Mi | 0.25 cores | 1 | ~5 concurrent |
| **Medium Usage** | 1Gi | 0.5 cores | 2 | ~15 concurrent |
| **High Usage** | 2Gi | 1 core | 2 | ~30 concurrent |

## 📡 API Usage

### Newspaper4k Method (Fast & Reliable)

```bash
curl -X POST "http://localhost:8000/api/scrape/newspaper" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

### ScrapGraph AI Method (AI-Powered)

```bash
curl -X POST "http://localhost:8000/api/scrape" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/article",
    "api_key": "sk-your-openai-api-key"
  }'
```

### Response Format

Both methods return identical JSON structure:

```json
{
  "url": "https://example.com/article",
  "content": {
    "content": "Full article text...",
    "top_image": "https://example.com/image.jpg",
    "published": "2025-05-31T10:00:00"
  },
  "status": "success",
  "error": null
}
```

## 🐳 Docker Compose

```yaml
version: '3.8'
services:
  webscraper-api:
    image: neoexec/webscraper-api:latest
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - UVICORN_WORKERS=2
      - MAX_THREAD_POOL_SIZE=10
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## ☸️ Kubernetes Deployment

### Simple Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webscraper-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: webscraper-api
  template:
    metadata:
      labels:
        app: webscraper-api
    spec:
      containers:
      - name: webscraper-api
        image: neoexec/webscraper-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: UVICORN_WORKERS
          value: "2"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: webscraper-secrets
              key: openai-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: webscraper-api-service
spec:
  selector:
    app: webscraper-api
  ports:
  - port: 80
    targetPort: 8000
```

### Create Secret

```bash
kubectl create secret generic webscraper-secrets \
  --from-literal=openai-api-key=sk-your-actual-api-key
```

## 🎯 Features

### Dual Scraping Methods
- **Newspaper4k**: Fast, reliable extraction for news articles
- **ScrapGraph AI**: AI-powered scraping using Large Language Models

### LLM Provider Support
- **OpenAI**: GPT-4o, GPT-3.5-turbo, GPT-4-turbo
- **Anthropic Claude**: Claude-3-opus, Claude-3-sonnet, Claude-3-haiku
- **Ollama**: Local models (llama3, mistral, codellama)
- **Azure OpenAI**: Enterprise integration
- **Custom Endpoints**: Any OpenAI-compatible API

### Production Features
- **High Concurrency**: Optimized for multiple simultaneous requests
- **Web Interface**: User-friendly configuration and testing
- **Health Checks**: Built-in monitoring endpoints
- **Standardized API**: Consistent response format
- **Error Handling**: Comprehensive error management

## 📊 Performance

### Concurrency Capacity

| Configuration | Concurrent Requests | Response Time |
|---------------|-------------------|---------------|
| 1 worker, 10 threads | ~10 requests | 5-15 seconds |
| 2 workers, 10 threads | ~20 requests | 5-15 seconds |
| 3 pods, 2 workers each | ~30 requests | 5-15 seconds |

### Load Testing

```bash
# Install hey for load testing
go install github.com/rakyll/hey@latest

# Test 10 concurrent requests
hey -n 50 -c 10 -m POST \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' \
  http://localhost:8000/api/scrape/newspaper
```

## 🔍 Monitoring

### Health Check

```bash
curl http://localhost:8000/api/health
# Response: {"status": "healthy"}
```

### Logs

```bash
# View container logs
docker logs -f <container-id>

# In Kubernetes
kubectl logs -f deployment/webscraper-api
```

## 🛠️ Development

### Local Development

```bash
# Clone the repository
git clone https://github.com/your-repo/webscraper-api
cd webscraper-api

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install --with-deps chromium

# Run locally
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Building Custom Image

```bash
# Build from source
docker build -t my-webscraper-api .

# Run custom build
docker run -d -p 8000:8000 my-webscraper-api
```

## 🔒 Security

- **No API Keys in Image**: API keys must be provided via environment variables
- **Input Validation**: All inputs are validated and sanitized
- **Error Handling**: No sensitive data exposed in error messages
- **Container Security**: Runs with minimal privileges

## 📋 Troubleshooting

### Common Issues

**Container Won't Start**:
```bash
# Check logs
docker logs <container-id>

# Common causes:
# - Port 8000 already in use
# - Insufficient memory
```

**API Key Errors**:
```bash
# Ensure API key format is correct
# OpenAI: sk-...
# Anthropic: sk-ant-...
```

**High Memory Usage**:
```bash
# Reduce workers or increase memory limit
docker run -m 2g neoexec/webscraper-api:latest
```

### Support

- **Issues**: Report bugs and feature requests
- **Documentation**: Full API documentation at `/docs`
- **Examples**: See repository for more examples

## 📄 License

MIT License - see repository for details.

## 🏷️ Tags

- `latest` - Latest stable version
- `v1.0.0` - Specific version
- `v1.x.x` - Version-specific tags

---

**Ready to scrape?** 🚀 Pull the image and start extracting content in minutes! 