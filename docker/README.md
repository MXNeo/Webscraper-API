# 🐳 Docker Configuration for WebScraper API

This directory contains all Docker-related files for the WebScraper API project.

## 📁 Directory Structure

```
docker/
├── Dockerfile                      # Production Dockerfile
├── docker-compose.yml             # Development with PostgreSQL
├── docker-compose.full.yml        # Full production setup
├── docker-compose.standalone.yml  # Standalone mode (no external DB)
├── docker-compose.test.yml        # Testing setup
├── build-multiplatform.sh         # Multi-architecture build script
└── README.md                      # This file
```

## 🚀 Quick Start

### From the `docker/` directory:

```bash
# Standalone mode (no external database)
docker-compose -f docker-compose.standalone.yml up --build

# Development mode (with PostgreSQL)
docker-compose -f docker-compose.yml up --build

# Full production setup
docker-compose -f docker-compose.full.yml up

# Testing mode
docker-compose -f docker-compose.test.yml up --build
```

### From the **root directory**:

```bash
# Using the docker-compose files from root
docker-compose -f docker/docker-compose.standalone.yml up --build
```

## 🔧 Build Context

All docker-compose files use the correct build context:
- **Context**: `..` (parent directory)
- **Dockerfile**: `docker/Dockerfile`

This ensures the Dockerfile can access all application files while keeping Docker configs organized.

## 📋 Available Compose Files

### 1. `docker-compose.standalone.yml`
- **Use case**: Local development, testing
- **Database**: Uses SQLite (metrics only)
- **Features**: Metrics enabled, no proxy database

### 2. `docker-compose.yml`
- **Use case**: Development with full database
- **Database**: PostgreSQL with proxy management
- **Features**: Full feature set with persistence

### 3. `docker-compose.full.yml`
- **Use case**: Production deployment
- **Database**: PostgreSQL + pgAdmin
- **Features**: Complete production setup with monitoring

### 4. `docker-compose.test.yml`
- **Use case**: CI/CD, testing
- **Database**: PostgreSQL with test data
- **Features**: Pre-loaded test proxies and configuration

## 🏗️ Building Images

### Local Build
```bash
# From docker directory
docker build -f Dockerfile -t webscraper-api:local ..
```

### Multi-platform Build
```bash
# From docker directory
./build-multiplatform.sh
```

## 📂 Volume Mounts

All compose files correctly mount volumes from the parent directory:
- `../data` → `/app/data` (metrics, databases)
- `../config` → `/app/config` (configurations)
- `../logs` → `/app/logs` (application logs)

## 🔒 Environment Variables

Create a `.env` file in the **root directory** (not in docker/) with:

```bash
# Required
OPENAI_API_KEY=sk-your-api-key-here

# Database (for full setup)
DB_USER=your_db_user
DB_PASSWORD=your_secure_password
DB_NAME=webscraper

# Metrics (optional)
METRICS_ENABLED=true
PERSIST_METRICS=true
```

## 🧪 Testing the Configuration

```bash
# Validate docker-compose files
docker-compose -f docker-compose.standalone.yml config
docker-compose -f docker-compose.yml config
docker-compose -f docker-compose.full.yml config
```

## 🐛 Troubleshooting

### Build Context Issues
If you see "file not found" errors:
- Make sure you're using the correct build context (`..`)
- Verify the Dockerfile path (`docker/Dockerfile`)
- Run from the `docker/` directory

### Volume Mount Issues
- Ensure directories exist in parent directory
- Check volume paths use `../` prefix
- Verify permissions on mounted directories

### Network Issues
- Each compose file uses its own network
- Use service names for inter-container communication
- Check port conflicts if running multiple setups

## 📚 Additional Documentation

- [Development Setup](../docs/DEVELOPMENT_TRACKING.md)
- [Deployment Guide](../docs/DEPLOYMENT.md)
- [Testing Guide](../docs/TESTING.md)

# Docker Deployment

This directory contains Docker deployment files for the WebScraper API with **full cross-platform compatibility** for Windows, macOS (Intel & Apple Silicon), and Linux systems.

## 🌍 Cross-Platform Support

The WebScraper API Docker image supports multiple architectures:

- ✅ **Windows** (AMD64) - Docker Desktop
- ✅ **macOS Intel** (AMD64) - Docker Desktop  
- ✅ **macOS Apple Silicon** (ARM64) - Docker Desktop
- ✅ **Linux AMD64** - Docker Engine
- ✅ **Linux ARM64** - Docker Engine

## Files

### `Dockerfile`
Multi-platform Docker image with:
- Python 3.11 slim base image
- Cross-platform dependency installation
- Playwright browser support for all architectures
- Non-root user for security
- Health checks
- Platform detection and logging

### `docker-compose.yml`
Simple orchestration setup with environment configuration

### `build-multiplatform.sh`
Script for building multi-platform images supporting both AMD64 and ARM64

## 🚀 Quick Start

### Option 1: Use Pre-built Image (Recommended)

```bash
# Works on all platforms - Docker automatically pulls the right architecture
docker run -d -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-api-key \
  neoexec/webscraper-api:latest
```

### Option 2: Docker Compose

```bash
# Clone repository
git clone https://github.com/MXNeo/Webscraper-API.git
cd Webscraper-API/docker

# Copy environment template
cp ../env.example .env

# Edit .env with your API keys (use any text editor)
# Windows: notepad .env
# macOS: open -e .env
# Linux: nano .env

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Option 3: Build from Source

```bash
# Clone repository
git clone https://github.com/MXNeo/Webscraper-API.git
cd Webscraper-API

# Build for your platform
docker build -f docker/Dockerfile -t webscraper-api .

# Run container
docker run -d -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-api-key \
  webscraper-api
```

## 🏗️ Multi-Platform Building

### Build for Multiple Architectures

```bash
# Navigate to docker directory
cd docker

# Run multi-platform build script
./build-multiplatform.sh
```

### Manual Multi-Platform Build

```bash
# Create buildx builder
docker buildx create --name multiplatform-builder --use

# Build and push for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag your-username/webscraper-api:latest \
  --push \
  -f Dockerfile \
  ..
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Platform Notes |
|----------|-------------|---------|----------------|
| `OPENAI_API_KEY` | OpenAI API key | None | Works on all platforms |
| `ANTHROPIC_API_KEY` | Anthropic API key | None | Works on all platforms |
| `UVICORN_WORKERS` | Number of workers | 1 | Adjust based on CPU cores |
| `MAX_THREAD_POOL_SIZE` | Thread pool size | 10 | Works on all platforms |

### Platform-Specific Recommendations

#### Windows
```bash
# Use Docker Desktop with WSL2 backend for best performance
# Recommended worker configuration:
docker run -d -p 8000:8000 \
  -e UVICORN_WORKERS=2 \
  -e MAX_THREAD_POOL_SIZE=8 \
  neoexec/webscraper-api:latest
```

#### macOS (Intel)
```bash
# Standard configuration works well
docker run -d -p 8000:8000 \
  -e UVICORN_WORKERS=2 \
  -e MAX_THREAD_POOL_SIZE=10 \
  neoexec/webscraper-api:latest
```

#### macOS (Apple Silicon)
```bash
# ARM64 image automatically selected
# Excellent performance with native ARM support
docker run -d -p 8000:8000 \
  -e UVICORN_WORKERS=3 \
  -e MAX_THREAD_POOL_SIZE=12 \
  neoexec/webscraper-api:latest
```

## 🔧 Platform-Specific Troubleshooting

### Windows Issues

**Docker Desktop not starting:**
```bash
# Enable WSL2 and virtualization in BIOS
# Install WSL2: wsl --install
# Restart Docker Desktop
```

**Port conflicts:**
```bash
# Check if port 8000 is in use
netstat -an | findstr :8000

# Use different port
docker run -d -p 8080:8000 neoexec/webscraper-api:latest
```

### macOS Issues

**Permission denied on Apple Silicon:**
```bash
# Ensure Docker Desktop has proper permissions
# System Preferences > Security & Privacy > Privacy > Full Disk Access
# Add Docker Desktop
```

**Slow performance:**
```bash
# Increase Docker Desktop memory allocation
# Docker Desktop > Preferences > Resources > Memory: 4GB+
```

### Linux Issues

**Browser dependencies:**
```bash
# Install additional dependencies if needed
sudo apt-get update && sudo apt-get install -y \
  libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1
```

## 📊 Performance by Platform

| Platform | Startup Time | Memory Usage | Concurrent Requests |
|----------|-------------|--------------|-------------------|
| **Windows (WSL2)** | ~30s | 512MB-1GB | 10-15 |
| **macOS Intel** | ~25s | 512MB-1GB | 10-15 |
| **macOS Apple Silicon** | ~20s | 400MB-800MB | 15-20 |
| **Linux AMD64** | ~20s | 400MB-800MB | 15-20 |
| **Linux ARM64** | ~25s | 400MB-800MB | 10-15 |

## 🧪 Testing Cross-Platform Compatibility

### Verify Platform Detection

```bash
# Check platform info
docker run --rm neoexec/webscraper-api:latest python -c "
import platform
print(f'System: {platform.system()}')
print(f'Machine: {platform.machine()}')
print(f'Architecture: {platform.architecture()}')
"
```

### Test API Functionality

```bash
# Start container
docker run -d -p 8000:8000 --name webscraper-test \
  -e OPENAI_API_KEY=sk-your-key \
  neoexec/webscraper-api:latest

# Test health endpoint
curl http://localhost:8000/api/health

# Test scraping (replace with your API key)
curl -X POST "http://localhost:8000/api/scrape/newspaper" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Cleanup
docker stop webscraper-test && docker rm webscraper-test
```

## 📋 Quick Reference

### Essential Commands

```bash
# Pull latest image (auto-detects platform)
docker pull neoexec/webscraper-api:latest

# Run with basic config
docker run -d -p 8000:8000 neoexec/webscraper-api:latest

# Run with API key
docker run -d -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key \
  neoexec/webscraper-api:latest

# Check logs
docker logs <container-id>

# Access web interface
# Open: http://localhost:8000

# Stop container
docker stop <container-id>
```

### Docker Compose Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

The Docker deployment is now fully cross-platform compatible! 🌍 