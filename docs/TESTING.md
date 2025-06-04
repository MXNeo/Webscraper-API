# WebScraper API Testing Guide

## 🚀 Quick Start with Docker

### 1. Build the Image
```bash
docker build -t webscraper-api:latest .
```

### 2. Run with Basic Metrics (No Database)
```bash
docker run -d --name webscraper-test \
  -p 8000:8000 \
  -v ./test-data:/app/data \
  -v ./test-config:/app/config \
  webscraper-api:latest
```

### 3. Run Full Test Environment (With PostgreSQL + Sample Proxies)
```bash
docker-compose -f docker-compose.test.yml up -d
```

## 🔍 Testing Endpoints

### Health Check
```bash
curl http://localhost:8000/api/health
```

### Current Metrics
```bash
curl http://localhost:8000/api/metrics/current
```

### Configuration Status
```bash
curl http://localhost:8000/api/config/status
```

### Historical Metrics (7 days)
```bash
curl http://localhost:8000/api/metrics/historical?days=7
```

### Export All Metrics
```bash
curl http://localhost:8000/api/metrics/export
```

## 🌐 Web Interfaces

- **Main Interface**: http://localhost:8000
- **Statistics Dashboard**: http://localhost:8000/statistics
- **API Documentation**: http://localhost:8000/docs

## 📊 What to Test

### 1. Metrics Collection
- The metrics system automatically tracks all requests
- Check `/statistics` page for real-time dashboard
- Memory usage should be minimal (< 15MB for months of data)

### 2. Database Integration
- With `docker-compose.test.yml`, you get 10 sample proxies
- Database configuration persists across restarts
- Proxy pool automatically refreshes every 5 minutes

### 3. Persistent Storage
- Metrics database: `./test-data/metrics.db`
- Configuration: `./test-config/config.json`
- Both survive container restarts

### 4. API Testing
Try scraping with the newspaper endpoint:
```bash
curl -X POST "http://localhost:8000/api/scrape/newspaper" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

## 🔧 Environment Variables

Key variables for testing:

```bash
# Metrics Configuration
METRICS_ENABLED=true
PERSIST_METRICS=true
METRICS_DB_PATH=/app/data/metrics.db
MEMORY_RETENTION_HOURS=24
DB_RETENTION_DAYS=30

# Database Configuration (for proxy support)
DB_HOST=postgres
DB_PORT=5432
DB_NAME=webscraper
DB_USER=postgres
DB_PASSWORD=testpassword123

# Proxy Pool Settings
PROXY_POOL_SIZE=50
MIN_PROXY_POOL_SIZE=10
PROXY_REFRESH_INTERVAL=300
```

## 📈 Expected Results

### Metrics Dashboard Should Show:
- ✅ Total requests counter
- ✅ Success rate percentage
- ✅ Average response time
- ✅ Proxy usage statistics
- ✅ Memory usage (very low)
- ✅ Interactive charts with Chart.js
- ✅ Auto-refresh every 30 seconds

### Database Integration Should Show:
- ✅ 9 active proxies from sample data
- ✅ Proxy pool refreshing every 5 minutes
- ✅ Connection pool working properly
- ✅ Circuit breaker protection active

### Persistence Should Show:
- ✅ `test-data/metrics.db` file created
- ✅ Configuration saved in `test-config/`
- ✅ Data survives container restarts

## 🛠️ Troubleshooting

### Container Won't Start
```bash
docker logs webscraper-test
```

### Database Connection Issues
```bash
docker-compose -f docker-compose.test.yml logs postgres
docker-compose -f docker-compose.test.yml logs webscraper-api
```

### Check Metrics Database
```bash
docker exec webscraper-test ls -la /app/data/
docker exec webscraper-test sqlite3 /app/data/metrics.db ".tables"
```

### Reset Everything
```bash
docker-compose -f docker-compose.test.yml down -v
docker rmi webscraper-api:latest
# Then rebuild and restart
```

## 🎯 Success Criteria

✅ **Container builds successfully**  
✅ **Application starts without errors**  
✅ **Metrics system initializes**  
✅ **Database connects (with test compose)**  
✅ **Web interfaces load properly**  
✅ **API endpoints respond correctly**  
✅ **Data persists across restarts**  
✅ **Memory usage remains low**  
✅ **Proxy pool functions correctly**  

## 📝 Notes

- The test environment uses dummy proxy data - replace with real proxies for production
- OpenAI API key is optional for basic testing (required for actual scraping)
- Metrics collection works even without database connection
- All configurations are encrypted when saved to files 