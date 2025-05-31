# Docker Deployment

This directory contains Docker-related files for containerized deployment of the WebScraper API.

## Files

### `Dockerfile`
Multi-stage Docker build file that creates an optimized production image with:
- Python 3.11-slim base image
- Playwright browser dependencies
- Application code and dependencies
- Health checks and proper startup configuration

### `docker-compose.yml`
Docker Compose configuration for easy multi-service deployment with:
- WebScraper API service
- Environment variable configuration
- Health checks
- Restart policies
- Volume mounting support

## Quick Start

### Option 1: Use Pre-built Image from Docker Hub

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
# Copy environment template
cp ../env.example .env
# Edit .env with your API keys

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

### Option 3: Build from Source

```bash
# Build the image
docker build -t webscraper-api .

# Run the container
docker run -d -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-api-key \
  webscraper-api
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for ScrapGraph AI | None | For AI scraping |
| `ANTHROPIC_API_KEY` | Anthropic API key | None | For Claude models |
| `UVICORN_WORKERS` | Number of worker processes | 1 | No |
| `MAX_THREAD_POOL_SIZE` | Thread pool size per worker | 10 | No |

### Docker Compose Environment

Create a `.env` file in this directory:

```env
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
UVICORN_WORKERS=2
MAX_THREAD_POOL_SIZE=10
```

## Access Points

After deployment:
- **Web Interface**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## Troubleshooting

### Common Issues

**Port Already in Use**:
```bash
# Use different port
docker run -d -p 8080:8000 neoexec/webscraper-api:latest
```

**Container Won't Start**:
```bash
# Check logs
docker logs <container-id>
docker-compose logs webscraper-api
```

**Memory Issues**:
```bash
# Increase memory limit
docker run -m 2g neoexec/webscraper-api:latest
```

For more detailed information, see the main [README.md](../README.md). 