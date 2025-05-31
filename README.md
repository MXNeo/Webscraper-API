# WebScraper API 🚀

[![Docker Pulls](https://img.shields.io/docker/pulls/neoexec/webscraper-api)](https://hub.docker.com/r/neoexec/webscraper-api)
[![Docker Image Size](https://img.shields.io/docker/image-size/neoexec/webscraper-api/latest)](https://hub.docker.com/r/neoexec/webscraper-api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A powerful, production-ready web scraping API that combines **Newspaper4k** and **ScrapGraph AI** for intelligent content extraction. Features a modern web interface, configurable LLM providers, and optimized for high-concurrency deployments.

## ✨ Features

### 🔧 Dual Scraping Methods
- **Newspaper4k**: Fast, reliable extraction for news articles and web content
- **ScrapGraph AI**: AI-powered scraping using Large Language Models for complex content

### 🤖 LLM Provider Support
- **OpenAI**: GPT-4o, GPT-3.5-turbo, GPT-4-turbo
- **Anthropic Claude**: Claude-3-opus, Claude-3-sonnet, Claude-3-haiku
- **Ollama**: Local models (llama3, mistral, codellama)
- **Azure OpenAI**: Enterprise integration
- **Custom Endpoints**: Any OpenAI-compatible API

### 🌐 Production Features
- **High Concurrency**: Optimized for 30+ simultaneous requests
- **Web Interface**: User-friendly configuration and testing dashboard
- **Health Checks**: Built-in monitoring endpoints
- **Standardized API**: Consistent response format across all methods
- **Hot Configuration Reload**: Update settings without restarts
- **Persistent Configuration**: Kubernetes PVC support for shared config

### 🐳 Deployment Options
- **Docker**: Single container deployment
- **Docker Compose**: Multi-service orchestration
- **Kubernetes/K3s**: Production-scale deployment with persistent storage
- **Local Development**: Direct Python execution

## 🚀 Quick Start

### Option 1: Docker Hub (Recommended)

```bash
# Run with default settings
docker run -d -p 8000:8000 neoexec/webscraper-api:latest

# Run with OpenAI API key
docker run -d -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-api-key \
  neoexec/webscraper-api:latest
```

### Option 2: Docker Compose

```bash
# Clone the repository
git clone https://github.com/MXNeo/Webscraper-API.git
cd Webscraper-API

# Copy environment template
cp env.example .env
# Edit .env with your API keys

# Start the service
docker-compose up -d
```

### Option 3: Build from Source

```bash
# Clone the repository
git clone https://github.com/MXNeo/Webscraper-API.git
cd Webscraper-API

# Build the Docker image
docker build -t webscraper-api .

# Run the container
docker run -d -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-api-key \
  webscraper-api
```

### Option 4: Local Development

```bash
# Clone the repository
git clone https://github.com/MXNeo/Webscraper-API.git
cd Webscraper-API

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install --with-deps chromium

# Set environment variables
export OPENAI_API_KEY=sk-your-api-key

# Run the application
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 🌐 Access Points

After deployment, access the application at:

- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

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

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for ScrapGraph AI | None | For AI scraping |
| `ANTHROPIC_API_KEY` | Anthropic API key | None | For Claude models |
| `UVICORN_WORKERS` | Number of worker processes | 1 | No |
| `MAX_THREAD_POOL_SIZE` | Thread pool size per worker | 10 | No |

### Docker Compose Configuration

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
```

## ☸️ Kubernetes Deployment

### Simple Deployment

```bash
# Deploy basic version
kubectl apply -f quick-deploy.yaml
```

### Production Deployment with Persistent Configuration

```bash
# Deploy with persistent config and hot-reload
kubectl apply -f k8s-persistent-config.yaml
kubectl apply -f config-update-scripts.yaml
```

For detailed Kubernetes deployment instructions, see:
- [K3S Deployment Guide](K3S_DEPLOYMENT_GUIDE.md)
- [Persistent Configuration Guide](PERSISTENT_CONFIG_GUIDE.md)

## 📊 Performance

### Concurrency Capacity

| Configuration | Concurrent Requests | Response Time |
|---------------|-------------------|---------------|
| 1 worker, 10 threads | ~10 requests | 5-15 seconds |
| 2 workers, 10 threads | ~20 requests | 5-15 seconds |
| 3 pods, 2 workers each | ~30 requests | 5-15 seconds |

### Resource Requirements

| Scenario | Memory | CPU | Workers | Capacity |
|----------|--------|-----|---------|----------|
| **Light Usage** | 512Mi | 0.25 cores | 1 | ~5 concurrent |
| **Medium Usage** | 1Gi | 0.5 cores | 2 | ~15 concurrent |
| **High Usage** | 2Gi | 1 core | 2 | ~30 concurrent |

## 🛠️ Development

### Project Structure

```
├── main.py                    # FastAPI application
├── config.py                  # Configuration management
├── config_manager.py          # Persistent config with hot-reload
├── queue_manager.py           # Redis queue for high-load scenarios
├── database.py                # Database utilities
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container build instructions
├── docker-compose.yml         # Multi-service orchestration
├── templates/                 # HTML templates
│   └── index.html            # Web interface
├── static/                    # Static assets
│   ├── script.js             # Frontend JavaScript
│   └── style.css             # Styling
├── k8s-deployment.yaml        # Basic Kubernetes deployment
├── k8s-persistent-config.yaml # Advanced K8s with persistent config
├── config-update-scripts.yaml # Configuration management scripts
└── docs/                      # Documentation
    ├── K3S_DEPLOYMENT_GUIDE.md
    └── PERSISTENT_CONFIG_GUIDE.md
```

### Running Tests

```bash
# Install test dependencies
pip install pytest requests

# Run API tests
python test_api.py
```

### Building Custom Images

```bash
# Build with custom tag
docker build -t my-webscraper-api:latest .

# Build for multiple architectures
docker buildx build --platform linux/amd64,linux/arm64 \
  -t my-webscraper-api:latest .
```

## 🔒 Security

- **No API Keys in Images**: API keys must be provided via environment variables
- **Input Validation**: All inputs are validated and sanitized
- **Error Handling**: No sensitive data exposed in error messages
- **Container Security**: Runs with minimal privileges
- **RBAC Support**: Kubernetes role-based access control

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
- Ensure API key format is correct (OpenAI: `sk-...`, Anthropic: `sk-ant-...`)
- Check environment variable is properly set

**High Memory Usage**:
```bash
# Reduce workers or increase memory limit
docker run -m 2g neoexec/webscraper-api:latest
```

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/MXNeo/Webscraper-API/issues)
- **Documentation**: See `/docs` endpoint when running
- **Examples**: Check `example_usage.sh` for usage examples

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🙏 Acknowledgments

- [ScrapGraph AI](https://github.com/VinciGit00/Scrapegraph-ai) - AI-powered web scraping
- [Newspaper4k](https://github.com/AndyTheFactory/newspaper4k) - Article extraction
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Playwright](https://playwright.dev/) - Browser automation

## 📈 Roadmap

- [ ] Support for more LLM providers (Gemini, Cohere)
- [ ] Advanced content filtering and processing
- [ ] Webhook support for async processing
- [ ] Rate limiting and quota management
- [ ] Monitoring and metrics dashboard
- [ ] Multi-language content support

---

**Ready to scrape?** 🚀 Get started with the Docker Hub image or build from source! 