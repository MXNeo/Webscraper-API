# WebScraper API optimized for news articles 🚀

[![Docker Pulls](https://img.shields.io/docker/pulls/neoexec/webscraper-api)](https://hub.docker.com/r/neoexec/webscraper-api)
[![Docker Image Size](https://img.shields.io/docker/image-size/neoexec/webscraper-api/latest)](https://hub.docker.com/r/neoexec/webscraper-api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-1.3.0-blue.svg)](https://github.com/MXNeo/Webscraper-API)

A powerful, production-ready web scraping API that combines **Newspaper4k**, **News-Please**, and **ScrapGraph AI** for intelligent content extraction. Features a modern web interface, enhanced metrics system, real-time monitoring, and optimized for high-concurrency deployments.

## ✨ Features

### 🔧 Triple Scraping Methods
- **Newspaper4k**: Fast, reliable extraction for news articles and web content
- **News-Please**: Advanced news article extraction with enhanced proxy support
- **ScrapGraph AI**: AI-powered scraping using Large Language Models for complex content

### 🤖 LLM Provider Support
- **OpenAI**: GPT-4o, GPT-3.5-turbo, GPT-4-turbo
- **Anthropic Claude**: Claude-3-opus, Claude-3-sonnet, Claude-3-haiku
- **Ollama**: Local models (llama3, mistral, codellama)
- **Azure OpenAI**: Enterprise integration
- **Custom Endpoints**: Any OpenAI-compatible API

### 📊 Enhanced Metrics & Monitoring
- **Real-time System Monitoring**: Live RAM usage, CPU metrics, and performance stats
- **Request Tracking**: Detailed analytics with hourly/daily breakdowns
- **Interactive Charts**: Visual representation of usage patterns and system health
- **WebSocket Logs**: Real-time log streaming with fallback mechanisms
- **Database Health**: Connection status monitoring and automatic recovery

### 🌐 Production Features
- **High Concurrency**: Optimized for 30+ simultaneous requests
- **Web Interface**: User-friendly configuration and testing dashboard with live statistics
- **Health Checks**: Built-in monitoring endpoints with detailed system information
- **Standardized API**: Consistent response format across all methods
- **Persistent Configuration**: Kubernetes PVC support for web UI settings
- **Hot Configuration Reload**: Update settings without restarts
- **Enhanced Error Handling**: Comprehensive logging and graceful failure recovery

### 🐳 Deployment Options
- **Docker**: Single container deployment with multi-architecture support
- **Docker Compose**: Multi-service orchestration with PostgreSQL integration
- **Kubernetes/K3s**: Production-scale deployment with persistent storage
- **Local Development**: Direct Python execution with hot reload

## 🚀 Quick Start

### Option 1: Docker Hub (Recommended)

```bash
# Run with default settings
docker run -d -p 8000:8000 neoexec/webscraper-api:1.3.0

# Run with OpenAI API key
docker run -d -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-api-key \
  neoexec/webscraper-api:1.3.0

# Run latest version
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
cp env.example docker/.env
# Edit docker/.env with your API keys

# Start the service
cd docker
docker-compose up -d
```

### Option 3: Build from Source

```bash
# Clone the repository
git clone https://github.com/MXNeo/Webscraper-API.git
cd Webscraper-API

# Build the Docker image
docker build -f docker/Dockerfile -t webscraper-api .

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

- **Web Interface**: http://localhost:8000 (Enhanced with real-time metrics)
- **Statistics Dashboard**: http://localhost:8000 (Integrated metrics and system monitoring)
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## 📡 API Usage

### Newspaper4k Method (Fast & Reliable)

```bash
curl -X POST "http://localhost:8000/api/scrape/newspaper" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

### News-Please Method (Advanced News Extraction)

```bash
curl -X POST "http://localhost:8000/api/scrape/newsplease" \
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

All methods return identical JSON structure:

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
  "method": "newspaper4k|newsplease|scrapegraph",
  "processing_time": 2.34
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
| `METRICS_ENABLED` | Enable metrics collection | true | No |
| `PERSIST_METRICS` | Persist metrics to database | true | No |
| `MEMORY_RETENTION_HOURS` | Hours to retain in-memory metrics | 24 | No |
| `DB_RETENTION_DAYS` | Days to retain database metrics | 30 | No |

### Docker Compose Configuration

See [docker/README.md](docker/README.md) for detailed Docker deployment instructions.

## ☸️ Kubernetes Deployment

### Simple Deployment (Testing)

```bash
# Deploy basic version without persistence
kubectl apply -f k8s/quick-deploy.yaml

# Access via port forward
kubectl port-forward svc/webscraper-api-service 8000:80
```

### Production Deployment with Persistent Configuration

```bash
# Deploy with persistent web UI configurations and metrics
kubectl apply -f k8s/k3s-webui-persistent.yaml

# Check deployment status
kubectl get pods,pvc,svc,ingress -l app=webscraper-api

# Access web interface
kubectl port-forward svc/webscraper-api-service 8000:80
```

For detailed Kubernetes deployment instructions, see the `k8s/` directory.

## 📊 Performance & Monitoring

### Real-time Metrics (New in v1.3.0)

The enhanced metrics system provides:

- **System Monitoring**: Real-time RAM usage (RSS, VMS, percentage)
- **Request Analytics**: Success/failure rates, response times, method usage
- **Interactive Charts**: Hourly breakdowns, daily trends, system health
- **Live Logs**: Real-time log streaming via WebSocket
- **Database Health**: Connection status and automatic recovery

### Concurrency Capacity

| Configuration | Concurrent Requests | Response Time | Memory Usage |
|---------------|-------------------|---------------|--------------|
| 1 worker, 10 threads | ~10 requests | 5-15 seconds | ~512MB |
| 2 workers, 10 threads | ~20 requests | 5-15 seconds | ~1GB |
| 3 pods, 2 workers each | ~30 requests | 5-15 seconds | ~2GB |

### Resource Requirements

| Scenario | Memory | CPU | Workers | Capacity |
|----------|--------|-----|---------|----------|
| **Light Usage** | 512Mi | 0.25 cores | 1 | ~5 concurrent |
| **Medium Usage** | 1Gi | 0.5 cores | 2 | ~15 concurrent |
| **High Usage** | 2Gi | 1 core | 2 | ~30 concurrent |

## 🆕 What's New in v1.3.0

### ✨ Major Enhancements

- **🔧 News-Please Integration**: Added as third scraping method with advanced proxy support
- **📊 Enhanced Metrics System**: Real-time system monitoring with psutil integration
- **💾 Memory Monitoring**: Actual RAM usage display (RSS, VMS, percentage)
- **📈 Improved Charts**: Fixed time-axis visualization for hourly breakdowns
- **🔄 Database Connection**: Enhanced status monitoring and automatic recovery
- **📝 WebSocket Logs**: Real-time log streaming with improved error handling

### 🐛 Bug Fixes

- Fixed database connection status not updating in web interface
- Fixed memory usage displaying as counter instead of actual RAM
- Fixed chart visualization with proper x,y coordinates
- Fixed logs not displaying due to WebSocket issues
- Improved error handling and fallback mechanisms

## 🛠️ Development

### Project Structure

```
├── main.py                    # FastAPI application with enhanced WebSocket support
├── config.py                  # Configuration management
├── database.py                # Database utilities with health monitoring
├── metrics.py                 # Enhanced metrics system with real-time monitoring
├── requirements.txt           # Python dependencies (includes psutil, news-please)
├── env.example                # Environment template
├── docker/                    # Docker deployment files
│   ├── Dockerfile            # Multi-architecture container build
│   ├── docker-compose.yml    # Multi-service orchestration
│   └── README.md             # Docker deployment guide
├── k8s/                      # Kubernetes deployment files (updated to v1.3.0)
│   ├── deployment.yaml       # Production deployment
│   ├── quick-deploy.yaml     # Simple K8s deployment
│   └── k3s-webui-persistent.yaml # Persistent storage deployment
├── templates/                 # HTML templates with enhanced UI
│   ├── index.html            # Web interface with live metrics
│   └── statistics.html       # Real-time statistics dashboard
└── static/                    # Static assets
    ├── script.js             # Enhanced frontend with WebSocket support
    └── style.css             # Modern styling
```

### Building Custom Images

```bash
# Build with custom tag
docker build -f docker/Dockerfile -t my-webscraper-api:1.3.0 .

# Build for multiple architectures
docker buildx build --platform linux/amd64,linux/arm64 \
  -f docker/Dockerfile -t my-webscraper-api:1.3.0 .
```

## 🔒 Security

- **No API Keys in Images**: API keys must be provided via environment variables
- **Input Validation**: All inputs are validated and sanitized
- **Error Handling**: No sensitive data exposed in error messages
- **Container Security**: Runs with minimal privileges and non-root user
- **RBAC Support**: Kubernetes role-based access control
- **Secure WebSocket**: Authenticated log streaming

## 📋 Troubleshooting

### Common Issues

**Container Won't Start**:
```bash
# Check logs
docker logs <container-id>

# Common causes:
# - Port 8000 already in use
# - Insufficient memory (increase to 1GB+ for metrics)
```

**Metrics Not Displaying**:
```bash
# Ensure metrics are enabled
docker run -e METRICS_ENABLED=true -e PERSIST_METRICS=true \
  neoexec/webscraper-api:1.3.0
```

**WebSocket Connection Issues**:
- Check firewall settings for WebSocket connections
- Ensure proper proxy configuration if behind load balancer

**API Key Errors**:
- Ensure API key format is correct (OpenAI: `sk-...`, Anthropic: `sk-ant-...`)
- Check environment variable is properly set

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/MXNeo/Webscraper-API/issues)
- **Documentation**: See `/docs` endpoint when running
- **Docker Hub**: [neoexec/webscraper-api](https://hub.docker.com/r/neoexec/webscraper-api)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🙏 Acknowledgments

- [News-Please](https://github.com/fhamborg/news-please) - Advanced news article extraction
- [ScrapGraph AI](https://github.com/VinciGit00/Scrapegraph-ai) - AI-powered web scraping
- [Newspaper4k](https://github.com/AndyTheFactory/newspaper4k) - Article extraction
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Playwright](https://playwright.dev/) - Browser automation
- [psutil](https://github.com/giampaolo/psutil) - System monitoring

## 📈 Roadmap

- [ ] Support for more LLM providers (Gemini, Cohere)
- [ ] Advanced content filtering and processing
- [ ] Webhook support for async processing
- [ ] Rate limiting and quota management
- [ ] Export metrics to Prometheus/Grafana
- [ ] Multi-language content support
- [ ] Batch processing capabilities
- [ ] Advanced proxy rotation strategies

---

**Ready to scrape with enhanced monitoring?** 🚀 Get started with the latest Docker Hub image v1.3.0! 
