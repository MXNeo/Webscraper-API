# WebScraper API - Deployment Guide

## 🚀 Deployment Options

The WebScraper API supports two deployment modes to fit different use cases:

### 1. 🏠 Standalone Deployment
- **Use Case**: Development, testing, or when you have an existing database
- **Features**: API only, configure your own database connection
- **File**: `docker-compose.standalone.yml`

### 2. 🔧 Full Deployment
- **Use Case**: Production, complete setup, or new installations
- **Features**: API + PostgreSQL + Sample Data + pgAdmin (optional)
- **File**: `docker-compose.full.yml`

---

## 🏠 Standalone Deployment

### Quick Start
```bash
# Clone the repository
git clone https://github.com/MXNeo/Webscraper-API.git
cd webscraper-api

# Set your OpenAI API key (optional)
export OPENAI_API_KEY="your-api-key-here"

# Start the standalone service
docker-compose -f docker-compose.standalone.yml up -d
```

### Access Points
- **API**: http://localhost:8000
- **Statistics**: http://localhost:8000/statistics
- **Proxy Management**: http://localhost:8000/proxy-management

### Configuration
The standalone deployment requires manual database configuration through the web interface:

1. Navigate to http://localhost:8000
2. Go to the database configuration section
3. Enter your PostgreSQL connection details
4. Test the connection
5. Create the proxy table if needed

### Environment Variables
```bash
# Optional: Set your OpenAI API key
OPENAI_API_KEY=your-openai-api-key

# Metrics settings (defaults shown)
METRICS_ENABLED=true
PERSIST_METRICS=true
MEMORY_RETENTION_HOURS=24
DB_RETENTION_DAYS=30
```

### Data Persistence
- **Metrics**: Stored in `./data/metrics.db` (SQLite)
- **Configuration**: Stored in `./config/`
- **Logs**: Stored in `./logs/`

---

## 🔧 Full Deployment

### Quick Start
```bash
# Clone the repository
git clone https://github.com/MXNeo/Webscraper-API.git
cd webscraper-api

# Set your OpenAI API key (optional)
export OPENAI_API_KEY="your-api-key-here"

# Start the full stack
docker-compose -f docker-compose.full.yml up -d

# Optional: Include pgAdmin for database management
docker-compose -f docker-compose.full.yml --profile tools up -d
```

### Access Points
- **API**: http://localhost:8000
- **Statistics**: http://localhost:8000/statistics
- **Proxy Management**: http://localhost:8000/proxy-management
- **PostgreSQL**: localhost:5432
- **pgAdmin** (optional): http://localhost:8080

### Pre-configured Database
The full deployment automatically:
- Creates a PostgreSQL database with sample proxy data
- Initializes all required tables and indexes
- Sets up 20+ sample proxies from various providers
- Configures performance tracking and statistics

### Default Credentials
```yaml
# PostgreSQL Database
Host: postgres (internal) / localhost (external)
Port: 5432
Database: webscraper
Username: webscraper_user
Password: webscraper_secure_password_2024

# pgAdmin (if enabled)
Email: admin@webscraper.local
Password: admin_password_2024
```

### Environment Variables
```bash
# API Configuration
OPENAI_API_KEY=your-openai-api-key

# Database (pre-configured)
DB_HOST=postgres
DB_PORT=5432
DB_NAME=webscraper
DB_USER=webscraper_user
DB_PASSWORD=webscraper_secure_password_2024

# Deployment mode
DEPLOYMENT_MODE=full
AUTO_DB_SETUP=true
DB_INIT_SAMPLE_DATA=true
```

### Data Persistence
- **Database**: PostgreSQL volume (`postgres_data`)
- **Metrics**: SQLite + PostgreSQL hybrid
- **Configuration**: Persistent volume (`webscraper_config`)
- **Logs**: Persistent volume (`webscraper_logs`)
- **pgAdmin**: Configuration volume (`pgadmin_data`)

---

## 🛠️ Advanced Configuration

### Custom Environment File
Create a `.env` file for persistent configuration:

```bash
# .env file
OPENAI_API_KEY=your-actual-api-key-here

# Proxy Pool Settings
PROXY_POOL_SIZE=100
MIN_PROXY_POOL_SIZE=20
PROXY_REFRESH_INTERVAL=300

# Metrics Settings
METRICS_ENABLED=true
MEMORY_RETENTION_HOURS=48
DB_RETENTION_DAYS=60
MAX_MEMORY_ENTRIES=20000

# Database Settings (standalone mode)
DB_HOST=your-postgres-host
DB_PORT=5432
DB_NAME=your-database
DB_USER=your-username
DB_PASSWORD=your-password
```

### Resource Limits
Add resource limits to your docker-compose files:

```yaml
services:
  webscraper-api:
    # ... existing configuration ...
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
```

### Health Checks
Both deployments include health checks:
- **API**: HTTP check on `/api/health`
- **PostgreSQL**: Connection check with `pg_isready`

---

## 🚀 Production Deployment

### Docker Swarm
```bash
# Deploy to Docker Swarm
docker stack deploy -c docker-compose.full.yml webscraper-stack
```

### Kubernetes
Convert docker-compose to Kubernetes manifests:
```bash
# Using kompose
kompose convert -f docker-compose.full.yml

# Or use existing k8s manifests
kubectl apply -f k8s/
```

### Reverse Proxy (Nginx)
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket support for live logs
    location /ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

---

## 🔍 Monitoring & Troubleshooting

### Health Checks
```bash
# Check API health
curl http://localhost:8000/api/health

# Check deployment info
curl http://localhost:8000/api/deployment/info

# Check database status
curl http://localhost:8000/api/database/table-status
```

### Logs
```bash
# View API logs
docker-compose logs webscraper-api

# View PostgreSQL logs (full deployment)
docker-compose logs postgres

# Follow logs in real-time
docker-compose logs -f webscraper-api
```

### Performance Metrics
Access real-time metrics at:
- **Statistics Dashboard**: http://localhost:8000/statistics
- **API Endpoint**: http://localhost:8000/api/metrics/current

---

## 🔧 Database Management

### Manual Database Setup (Standalone)
If you need to manually set up the database:

```sql
-- Connect to your PostgreSQL instance
psql -h localhost -U your_user -d your_database

-- Run the initialization script
\i scripts/init-db.sql

-- Optional: Load sample data
\i scripts/sample-data.sql
```

### Backup & Restore
```bash
# Backup (full deployment)
docker exec postgres pg_dump -U webscraper_user webscraper > backup.sql

# Restore
docker exec -i postgres psql -U webscraper_user webscraper < backup.sql
```

---

## 🚨 Security Considerations

### Production Checklist
- [ ] Change default database passwords
- [ ] Use environment variables for secrets
- [ ] Enable HTTPS with proper certificates
- [ ] Implement firewall rules
- [ ] Regular security updates
- [ ] Monitor access logs

### Environment Variables Security
```bash
# Use Docker secrets in production
echo "your-secure-password" | docker secret create db_password -

# Reference in docker-compose
services:
  webscraper-api:
    secrets:
      - db_password
    environment:
      - DB_PASSWORD_FILE=/run/secrets/db_password
```

---

## 📊 Scaling & Performance

### Horizontal Scaling
For high-traffic deployments:

1. **Load Balancer**: Use nginx or cloud load balancer
2. **Multiple API Instances**: Scale API containers
3. **Database**: Use read replicas for query performance
4. **Shared Storage**: Implement Redis for shared metrics

### Performance Tuning
```yaml
# PostgreSQL tuning
postgres:
  environment:
    - POSTGRES_SHARED_PRELOAD_LIBRARIES=pg_stat_statements
    - POSTGRES_MAX_CONNECTIONS=200
    - POSTGRES_SHARED_BUFFERS=256MB
    - POSTGRES_EFFECTIVE_CACHE_SIZE=1GB
```

---

## 🆘 Support & Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check database credentials
   - Verify network connectivity
   - Check PostgreSQL logs

2. **Import Not Working**
   - Verify file format
   - Check file permissions
   - Review browser console for errors

3. **Live Logs Not Connecting**
   - Check WebSocket support
   - Verify no proxy blocking WebSocket
   - Check browser developer tools

### Getting Help
- **GitHub Issues**: https://github.com/MXNeo/Webscraper-API/issues
- **Documentation**: Check DEVELOPMENT_TRACKING.md
- **Logs**: Enable debug logging for detailed information

---

## 📝 License & Contributing

This project is open-source. Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

For detailed development information, see `DEVELOPMENT_TRACKING.md`. 