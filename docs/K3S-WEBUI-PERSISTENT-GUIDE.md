# K3s WebUI Persistent Configuration Deployment Guide

This guide explains how to deploy the WebScraper API on K3s with persistent storage for all web interface configurations, including API keys, proxy settings, and database connections.

## 🎯 What This Deployment Does

### **Persistent Storage for Web UI Settings**
- **API Keys**: OpenAI, Anthropic, Azure, Ollama keys configured via web interface
- **Proxy Settings**: HTTP proxy and database proxy table connections
- **Database Connections**: PostgreSQL connection settings for proxy rotation
- **Application Settings**: Web UI preferences and configurations
- **Automatic Backups**: Configuration backups and versioning

### **K3s Optimized Features**
- Uses K3s `local-path` storage class (default)
- Traefik ingress controller integration
- ReadWriteOnce PVCs (K3s limitation)
- Optimized for single-node or small cluster deployments

## 🚀 Quick Deployment

### 1. Deploy to K3s

```bash
# Apply the complete manifest
kubectl apply -f k3s-webui-persistent.yaml

# Check deployment status
kubectl get pods -l app=webscraper-api
kubectl get pvc
kubectl get ingress
```

### 2. Verify Storage Initialization

```bash
# Check if storage initialization completed
kubectl logs job/webscraper-storage-init

# Verify PVCs are bound
kubectl get pvc
# Should show:
# webscraper-webui-config-pvc   Bound
# webscraper-database-pvc       Bound
```

### 3. Access the Web Interface

```bash
# Option 1: Port forward (for testing)
kubectl port-forward svc/webscraper-api-service 8000:80

# Access at: http://localhost:8000

# Option 2: Configure ingress host
# Edit the ingress in k3s-webui-persistent.yaml:
# Change 'webscraper.local' to your domain
# Then access at: http://your-domain.com
```

## 📁 Persistent Storage Structure

The deployment creates this storage structure:

```
/app/persistent-config/
├── api-keys/
│   └── keys.json              # API keys from web UI
├── llm-configs/
│   └── provider-settings.json # LLM model configurations
├── proxy-settings/
│   └── proxy.json             # Proxy and database settings
├── app-settings/
│   └── config.json            # Web UI preferences
└── backups/                   # Automatic configuration backups

/app/persistent-database/
├── sqlite/                    # Local database files
├── proxy-tables/              # Proxy rotation data
└── logs/                      # Application logs
```

## ⚙️ Configuration via Web Interface

### 1. Configure API Keys

1. **Access Web Interface**: http://localhost:8000 (or your domain)
2. **Navigate to Configuration**: Click on "Configuration" tab
3. **Add API Keys**:
   - **OpenAI**: Enter your `sk-...` key
   - **Anthropic**: Enter your `sk-ant-...` key
   - **Azure**: Configure endpoint and key
   - **Ollama**: Set local endpoint URL

4. **Save Configuration**: Click "Save" - settings persist in PV

### 2. Configure Proxy Settings

1. **Database Proxy Table**:
   ```
   Host: your-postgres-host.com
   Port: 5432
   Database: proxy_db
   Username: proxy_user
   Password: your-password
   Table: proxies
   ```

2. **HTTP Proxy**:
   ```
   Proxy Host: proxy.company.com
   Proxy Port: 8080
   Username: (optional)
   Password: (optional)
   ```

3. **Save Settings**: All proxy configurations persist across pod restarts

### 3. Test Configuration Persistence

```bash
# Restart deployment to test persistence
kubectl rollout restart deployment/webscraper-api

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=webscraper-api --timeout=120s

# Access web interface - your settings should still be there!
kubectl port-forward svc/webscraper-api-service 8000:80
```

## 🔧 Advanced Configuration

### Scaling the Deployment

```bash
# Scale to more replicas (shares same config)
kubectl scale deployment webscraper-api --replicas=3

# Check status
kubectl get pods -l app=webscraper-api
```

### Backup Configuration

```bash
# Create manual backup of configurations
kubectl exec deployment/webscraper-api -- tar -czf /tmp/config-backup.tar.gz /app/persistent-config

# Copy backup to local machine
kubectl cp webscraper-api-<pod-name>:/tmp/config-backup.tar.gz ./config-backup.tar.gz
```

### View Current Configuration

```bash
# Check API keys configuration
kubectl exec deployment/webscraper-api -- cat /app/persistent-config/api-keys/keys.json

# Check proxy settings
kubectl exec deployment/webscraper-api -- cat /app/persistent-config/proxy-settings/proxy.json

# Check application settings
kubectl exec deployment/webscraper-api -- cat /app/persistent-config/app-settings/config.json
```

## 🌐 Ingress Configuration

### Option 1: Local Development (Default)

```yaml
spec:
  rules:
  - host: webscraper.local
```

Add to your `/etc/hosts`:
```
127.0.0.1 webscraper.local
```

### Option 2: Production Domain

Edit the ingress section in `k3s-webui-persistent.yaml`:

```yaml
spec:
  rules:
  - host: webscraper.yourdomain.com  # Your actual domain
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: webscraper-api-service
            port:
              number: 80
```

### Option 3: IP-based Access

```yaml
spec:
  rules:
  - host: ""  # Empty host for IP access
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: webscraper-api-service
            port:
              number: 80
```

## 📊 Monitoring and Troubleshooting

### Check Pod Status

```bash
# View pod logs
kubectl logs -l app=webscraper-api -f

# Check pod details
kubectl describe pods -l app=webscraper-api

# Check resource usage
kubectl top pods -l app=webscraper-api
```

### Storage Troubleshooting

```bash
# Check PVC status
kubectl describe pvc webscraper-webui-config-pvc
kubectl describe pvc webscraper-database-pvc

# Check storage usage
kubectl exec deployment/webscraper-api -- df -h /app/persistent-config
kubectl exec deployment/webscraper-api -- df -h /app/persistent-database

# List configuration files
kubectl exec deployment/webscraper-api -- find /app/persistent-config -type f
```

### Common Issues

#### PVC Not Binding

```bash
# Check if local-path provisioner is running
kubectl get pods -n kube-system | grep local-path

# Check storage class
kubectl get storageclass

# If local-path doesn't exist, install it:
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.24/deploy/local-path-storage.yaml
```

#### Configuration Not Persisting

```bash
# Check if volumes are mounted correctly
kubectl exec deployment/webscraper-api -- mount | grep persistent

# Check file permissions
kubectl exec deployment/webscraper-api -- ls -la /app/persistent-config/

# Verify environment variables
kubectl exec deployment/webscraper-api -- env | grep WEBSCRAPER
```

#### Web Interface Not Loading

```bash
# Check service endpoints
kubectl get endpoints webscraper-api-service

# Test internal connectivity
kubectl exec deployment/webscraper-api -- curl -f http://localhost:8000/api/health

# Check ingress status
kubectl describe ingress webscraper-api-ingress
```

## 🔄 Configuration Migration

### From Docker Compose to K3s

If you have existing configurations from Docker Compose:

```bash
# 1. Export configurations from Docker container
docker exec <container-id> tar -czf /tmp/config.tar.gz /app/config

# 2. Copy to local machine
docker cp <container-id>:/tmp/config.tar.gz ./

# 3. Extract and copy to K3s pod
kubectl cp ./config.tar.gz webscraper-api-<pod-name>:/tmp/

# 4. Extract in pod
kubectl exec webscraper-api-<pod-name> -- tar -xzf /tmp/config.tar.gz -C /app/persistent-config/
```

### Backup and Restore

```bash
# Create backup
kubectl exec deployment/webscraper-api -- tar -czf /tmp/full-backup.tar.gz /app/persistent-config /app/persistent-database

# Restore from backup
kubectl cp ./full-backup.tar.gz webscraper-api-<pod-name>:/tmp/
kubectl exec webscraper-api-<pod-name> -- tar -xzf /tmp/full-backup.tar.gz -C /app/
```

## 🎯 Production Considerations

### Resource Limits

For production, adjust resources based on your needs:

```yaml
resources:
  requests:
    memory: "1Gi"      # Increase for heavy usage
    cpu: "500m"        # 0.5 CPU cores
  limits:
    memory: "4Gi"      # Maximum memory
    cpu: "2000m"       # 2 CPU cores
```

### Storage Size

Adjust PVC sizes based on your data:

```yaml
# For large proxy tables and extensive configurations
resources:
  requests:
    storage: 10Gi  # Increase as needed
```

### High Availability

```yaml
# Increase replicas for HA
replicas: 3

# Add pod anti-affinity to spread across nodes
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - webscraper-api
        topologyKey: kubernetes.io/hostname
```

## 📋 Quick Reference

### Essential Commands

```bash
# Deploy
kubectl apply -f k3s-webui-persistent.yaml

# Check status
kubectl get pods,pvc,svc,ingress -l app=webscraper-api

# Access web interface
kubectl port-forward svc/webscraper-api-service 8000:80

# View logs
kubectl logs -l app=webscraper-api -f

# Scale deployment
kubectl scale deployment webscraper-api --replicas=3

# Restart deployment
kubectl rollout restart deployment/webscraper-api

# Delete deployment
kubectl delete -f k3s-webui-persistent.yaml
```

### Configuration Files

- **API Keys**: `/app/persistent-config/api-keys/keys.json`
- **Proxy Settings**: `/app/persistent-config/proxy-settings/proxy.json`
- **App Settings**: `/app/persistent-config/app-settings/config.json`
- **Database**: `/app/persistent-database/`

This deployment ensures all your web interface configurations persist across pod restarts, scaling, and cluster maintenance! 🚀 