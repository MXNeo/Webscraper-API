# WebScraper API Metrics & Persistence Guide

## 📊 **Metrics System Overview**

The WebScraper API includes a comprehensive metrics collection system that tracks:

### **Tracked Metrics**
- **Request Performance**: Response times, success rates, error types
- **Proxy Usage**: Which proxies are used, success/failure rates per proxy
- **System Health**: Memory usage, database connectivity, proxy pool status
- **Historical Data**: Daily/hourly breakdowns, trends over time

### **Storage Strategy**
- **In-Memory**: Recent 24 hours (configurable) for fast access
- **SQLite Database**: Historical data with automatic cleanup
- **Memory Efficient**: Only simple counters and aggregates in memory

---

## 🗄️ **Data Storage & Memory Usage**

### **Memory Usage Analysis**
Running for **months continuously**:

| Data Type | Memory Usage | Notes |
|-----------|--------------|--------|
| **Simple Counters** | ~1-10 KB | Total requests, success count, etc. |
| **Response Times** | ~8-80 KB | Last 1000 response times (8 bytes each) |
| **Recent Requests** | ~1-10 MB | 10,000 recent requests (1KB each) |
| **Daily Aggregates** | ~10-100 KB | Compressed daily statistics |
| **Total Estimated** | **~2-15 MB** | Very manageable even after months |

**✅ Conclusion**: Memory usage is minimal and won't cause issues even with months of uptime.

### **Automatic Cleanup**
- **Memory**: Old entries automatically purged after 24 hours
- **Database**: Historical data cleaned up after 30 days (configurable)
- **Daily Rotation**: Statistics reset daily with archival

---

## 🔧 **Configuration Persistence**

### **What Gets Persisted**
With Kubernetes PV or Docker volumes, **ALL configurations survive restarts**:

| Configuration Type | Storage Location | Persistence |
|-------------------|------------------|-------------|
| **OpenAI API Keys** | `config.json` (encrypted) | ✅ **Yes** |
| **Database Connections** | `config.json` (encrypted) | ✅ **Yes** |
| **ScrapeGraph Settings** | `config.json` | ✅ **Yes** |
| **Metrics Database** | `data/metrics.db` | ✅ **Yes** |
| **Proxy Pool State** | Database + memory | ✅ **Yes** |

### **File Structure**
```
/app/
├── data/                     # Persistent data volume
│   ├── metrics.db           # SQLite metrics database
│   └── proxy_cache.json     # Proxy pool cache (optional)
├── config/                   # Persistent config volume
│   ├── config.json          # Encrypted configurations
│   └── secret.key           # Encryption key
└── logs/                     # Optional log persistence
    └── app.log
```

---

## 🐳 **Docker Configuration**

### **Docker Compose with Volumes**
```yaml
services:
  webscraper-api:
    build: .
    volumes:
      # Persistent data storage
      - webscraper_data:/app/data
      # Persistent configuration storage
      - webscraper_config:/app/config
    environment:
      - METRICS_ENABLED=true
      - PERSIST_METRICS=true
      - METRICS_DB_PATH=data/metrics.db

volumes:
  webscraper_data:
    driver: local
  webscraper_config:
    driver: local
```

### **Host Directory Binding**
```yaml
volumes:
  # Bind to host directories for easier access
  - ./data:/app/data
  - ./config:/app/config
```

---

## ☸️ **Kubernetes Configuration**

### **Persistent Volume Claims**
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: webscraper-data-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi  # Enough for years of metrics
```

### **Deployment Volume Mounts**
```yaml
spec:
  containers:
  - name: webscraper-api
    volumeMounts:
    - name: data-storage
      mountPath: /app/data
    - name: config-storage
      mountPath: /app/config
  volumes:
  - name: data-storage
    persistentVolumeClaim:
      claimName: webscraper-data-pvc
```

---

## 📈 **Statistics Dashboard Features**

### **Real-time Metrics**
- **Auto-refresh**: Updates every 30 seconds
- **Live KPIs**: Total requests, success rate, avg response time
- **Memory monitoring**: Current usage vs limits

### **Charts & Visualizations**
- **Response Time Distribution**: Min, median, avg, P95, P99, max
- **Success Rate Trends**: Doughnut chart showing success/failure ratio
- **Historical Data**: Daily and hourly breakdowns
- **Proxy Usage**: Which proxies are most/least used

### **Health Monitoring**
- **System Status**: Memory, success rate, proxy pool health
- **Error Analysis**: Types of errors and frequency
- **Performance Tracking**: Response time trends

### **Data Export**
- **JSON Export**: Complete metrics data
- **CSV Export**: (Coming soon)
- **Automatic Downloads**: With timestamp

---

## ⚙️ **Configuration Options**

### **Environment Variables**
```bash
# Metrics Settings
METRICS_ENABLED=true                 # Enable/disable metrics collection
PERSIST_METRICS=true                 # Store to SQLite database
METRICS_DB_PATH=data/metrics.db      # Database file path
MEMORY_RETENTION_HOURS=24            # Keep in memory for 24 hours
DB_RETENTION_DAYS=30                 # Keep database data for 30 days
MAX_MEMORY_ENTRIES=10000             # Maximum in-memory entries

# Performance Tuning
PROXY_POOL_SIZE=50                   # Number of proxies in pool
BATCH_UPDATE_INTERVAL=60             # Batch database updates (seconds)
```

### **Dynamic Configuration**
```python
# Via config_store in main.py
config_store.update({
    "metrics_enabled": True,
    "persist_metrics": True,
    "memory_retention_hours": 24,
    "max_memory_entries": 10000
})
```

---

## 🚀 **Getting Started**

### **1. Enable Metrics**
```bash
# Set environment variables
export METRICS_ENABLED=true
export PERSIST_METRICS=true
```

### **2. Setup Persistent Storage**

#### **Docker**
```bash
docker run -v webscraper_data:/app/data \
           -v webscraper_config:/app/config \
           webscraper-api
```

#### **Kubernetes**
```bash
kubectl apply -f k8s/persistent-volume.yaml
kubectl apply -f k8s/deployment.yaml
```

### **3. Access Statistics**
- Navigate to `/statistics` in your browser
- View real-time metrics and charts
- Export data as needed

---

## 🔍 **API Endpoints**

### **Metrics Endpoints**
```bash
# Current real-time metrics
GET /api/metrics/current

# Historical data (last N days)
GET /api/metrics/historical?days=7

# Export all metrics
GET /api/metrics/export

# Proxy pool statistics
GET /api/proxy/pool/stats
```

### **Example Response**
```json
{
  "counters": {
    "total_requests": 1234,
    "successful_requests": 1100,
    "failed_requests": 134
  },
  "response_times": {
    "avg": 2.34,
    "p95": 5.67,
    "p99": 8.90
  },
  "recent_hour": {
    "requests": 45,
    "success_rate": 91.2,
    "proxy_usage": 67.8
  }
}
```

---

## 🛡️ **Security & Privacy**

### **Sensitive Data Handling**
- **API Keys**: Encrypted using Fernet encryption
- **Database Passwords**: Stored encrypted in config files
- **Metrics**: No sensitive URL content stored, only domains
- **Proxy URLs**: IP addresses anonymized in logs

### **Data Retention**
- **Automatic Cleanup**: Old data purged automatically
- **Configurable Retention**: Adjust retention periods as needed
- **GDPR Compliant**: No personal data stored in metrics

---

## 📋 **Troubleshooting**

### **Common Issues**

#### **Metrics Not Appearing**
```bash
# Check if metrics are enabled
curl http://localhost:8000/api/metrics/current

# Verify environment variables
echo $METRICS_ENABLED
```

#### **Configuration Not Persisting**
```bash
# Check volume mounts
docker inspect <container_id> | grep Mounts

# Verify file permissions
ls -la /app/data/
ls -la /app/config/
```

#### **High Memory Usage**
```bash
# Reduce memory retention
export MEMORY_RETENTION_HOURS=6
export MAX_MEMORY_ENTRIES=1000
```

### **Performance Optimization**

#### **For High-Volume Usage**
- Reduce `MEMORY_RETENTION_HOURS` to 6-12 hours
- Increase `BATCH_UPDATE_INTERVAL` to 120 seconds
- Set `MAX_MEMORY_ENTRIES` to 5000

#### **For Long-Term Storage**
- Increase `DB_RETENTION_DAYS` to 90 or 365
- Enable database compression (SQLite VACUUM)
- Consider external time-series database for enterprise use

---

## 🔮 **Future Enhancements**

### **Planned Features**
- **CSV Export**: Direct CSV download functionality
- **Alerting**: Email/webhook alerts for high error rates
- **Custom Dashboards**: User-configurable metric views
- **Integration**: Prometheus/Grafana support
- **Real-time Streaming**: WebSocket-based live updates

### **Advanced Metrics**
- **Geographic Analysis**: Proxy location success rates
- **Content Analysis**: Success rates by content type/size
- **User Agent Analysis**: Performance by browser type
- **Time-based Patterns**: Success rates by time of day

This comprehensive metrics system provides production-ready monitoring with minimal resource usage and complete configuration persistence across restarts. 