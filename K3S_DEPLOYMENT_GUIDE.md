# K3s Deployment Guide for WebScraper API

## Concurrency Analysis & Recommendations

### Current Capacity Assessment

**✅ Your FastAPI app can handle 10 concurrent requests well with these optimizations:**

| Component | Current | Optimized | Capacity |
|-----------|---------|-----------|----------|
| **FastAPI Workers** | 1 | 2 per pod | 6 total workers |
| **Thread Pool** | Default (~5) | 10 per worker | 60 total threads |
| **K3s Pods** | 1 | 3 replicas | Load distributed |
| **Memory per Pod** | 512Mi-2Gi | Optimized | Handles Playwright |

### Deployment Architecture

```
Internet → Ingress → Service → 3 Pods (2 workers each) → 6 FastAPI workers → 60 threads
```

**Total Capacity**: ~30-50 concurrent requests (well above your 10 requirement)

## Quick Deployment

### 1. Prepare Your Environment

```bash
# Build and tag the image
docker build -t webscraper-api:latest .

# If using a registry, push it
# docker tag webscraper-api:latest your-registry/webscraper-api:latest
# docker push your-registry/webscraper-api:latest
```

### 2. Configure Secrets

```bash
# Create the secret with your OpenAI API key
echo -n "sk-your-actual-openai-api-key" | base64
# Copy the output and replace in k8s-deployment.yaml
```

### 3. Deploy to K3s

```bash
# Apply the deployment
kubectl apply -f k8s-deployment.yaml

# Check deployment status
kubectl get pods -l app=webscraper-api
kubectl get svc webscraper-api-service
kubectl get ingress webscraper-api-ingress
```

### 4. Test the Deployment

```bash
# Port forward for testing
kubectl port-forward svc/webscraper-api-service 8080:80

# Test health endpoint
curl http://localhost:8080/api/health

# Test scraping
curl -X POST "http://localhost:8080/api/scrape/newspaper" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

## Performance Optimizations

### Resource Configuration

```yaml
resources:
  requests:
    memory: "512Mi"    # Minimum for Playwright
    cpu: "250m"        # 0.25 CPU cores
  limits:
    memory: "2Gi"      # Maximum for heavy scraping
    cpu: "1000m"       # 1 CPU core max
```

### Scaling Configuration

```yaml
replicas: 3              # 3 pods for load distribution
UVICORN_WORKERS: 2       # 2 workers per pod
MAX_THREAD_POOL_SIZE: 10 # 10 threads per worker
```

**Total Capacity**: 3 pods × 2 workers × 10 threads = 60 concurrent operations

### Auto-scaling (Optional)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: webscraper-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: webscraper-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Queue System (For High Load)

### When to Use Queuing

**Use immediate processing (current setup) when**:
- ≤ 10 concurrent requests
- Response time is critical
- Simple deployment preferred

**Use Redis queue when**:
- > 20 concurrent requests
- Can accept async responses
- Need job tracking/retry logic

### Redis Queue Setup

```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

### Queue-based API Endpoints

```python
# Add to requirements.txt
redis>=4.5.0

# New endpoints for queue-based processing
@app.post("/api/scrape/async")
async def scrape_async(request: ScrapeRequest):
    job_id = await queue_manager.enqueue_job(
        url=str(request.url),
        method="scrapegraph",
        api_key=request.api_key
    )
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    status = await queue_manager.get_job_status(job_id)
    result = await queue_manager.get_job_result(job_id)
    return {"job_id": job_id, "status": status, "result": result}
```

## Monitoring & Observability

### Health Checks

```yaml
readinessProbe:
  httpGet:
    path: /api/health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

livenessProbe:
  httpGet:
    path: /api/health
    port: 8000
  initialDelaySeconds: 60
  periodSeconds: 30
```

### Metrics Endpoint

```python
# Add to main.py
@app.get("/api/metrics")
async def get_metrics():
    return {
        "active_threads": threading.active_count(),
        "queue_size": await queue_manager.get_queue_size() if queue_manager.redis_client else 0,
        "memory_usage": psutil.Process().memory_info().rss / 1024 / 1024,  # MB
        "uptime": time.time() - start_time
    }
```

### Logging Configuration

```yaml
env:
- name: LOG_LEVEL
  value: "INFO"
- name: LOG_FORMAT
  value: "json"  # For structured logging
```

## Load Testing

### Test Concurrent Requests

```bash
# Install hey for load testing
go install github.com/rakyll/hey@latest

# Test 10 concurrent requests
hey -n 50 -c 10 -m POST \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' \
  http://your-domain/api/scrape/newspaper

# Expected results:
# - All requests should complete successfully
# - Average response time < 10 seconds
# - No 5xx errors
```

### Stress Test

```bash
# Test higher load to find limits
hey -n 100 -c 20 -m POST \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' \
  http://your-domain/api/scrape/newspaper
```

## Troubleshooting

### Common Issues

**Pods OOMKilled**:
```bash
# Increase memory limits
resources:
  limits:
    memory: "3Gi"  # Increase from 2Gi
```

**High CPU Usage**:
```bash
# Reduce workers or threads
env:
- name: UVICORN_WORKERS
  value: "1"  # Reduce from 2
- name: MAX_THREAD_POOL_SIZE
  value: "5"  # Reduce from 10
```

**Slow Response Times**:
```bash
# Check resource constraints
kubectl top pods
kubectl describe pod <pod-name>

# Check logs
kubectl logs -f deployment/webscraper-api
```

### Debugging Commands

```bash
# Check pod status
kubectl get pods -l app=webscraper-api -o wide

# Check resource usage
kubectl top pods -l app=webscraper-api

# Check logs
kubectl logs -f deployment/webscraper-api --all-containers

# Check service endpoints
kubectl get endpoints webscraper-api-service

# Test internal connectivity
kubectl run test-pod --image=curlimages/curl -it --rm -- sh
# curl http://webscraper-api-service/api/health
```

## Conclusion

**For 10 concurrent requests, your optimized setup provides**:

✅ **3x over-capacity** (can handle ~30 concurrent requests)  
✅ **High availability** (3 pod replicas)  
✅ **Auto-recovery** (health checks + restart policies)  
✅ **Resource efficiency** (optimized thread pools)  
✅ **Monitoring ready** (health/metrics endpoints)  

**No queuing system needed** for your current requirements, but the Redis queue option is available for future scaling. 