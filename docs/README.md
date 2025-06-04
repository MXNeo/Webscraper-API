# Kubernetes Deployment

This directory contains streamlined Kubernetes manifests for deploying the WebScraper API in production environments, optimized for K3s and other Kubernetes distributions.

## Files

### `quick-deploy.yaml`
Simple, single-file Kubernetes deployment for quick testing and basic production use:
- 2 replicas for basic load distribution
- Basic resource limits and health checks
- ClusterIP service and Ingress
- Minimal configuration - no persistent storage
- Perfect for testing and lightweight deployments

### `k3s-webui-persistent.yaml`
**Recommended for production** - Advanced K3s deployment with persistent storage:
- **Persistent Volume Claims** for web UI configurations and database storage
- **Web UI Configuration Persistence**: API keys, proxy settings, database connections
- **Automatic Storage Initialization** with proper directory structure
- **K3s Optimized**: Uses local-path storage class and Traefik ingress
- **High Availability**: 2 replicas with shared configuration
- **Production Ready**: Resource limits, health checks, graceful shutdown

### `K3S-WEBUI-PERSISTENT-GUIDE.md`
Comprehensive deployment guide for the persistent configuration setup.

## 🚀 Quick Start

### Option 1: Simple Deployment (Testing)

```bash
# Deploy basic version without persistence
kubectl apply -f quick-deploy.yaml

# Check deployment
kubectl get pods -l app=webscraper-api
kubectl get svc webscraper-api-service

# Access via port forward
kubectl port-forward svc/webscraper-api-service 8000:80
```

### Option 2: Production Deployment with Persistent Storage (Recommended)

```bash
# Deploy with persistent web UI configurations
kubectl apply -f k3s-webui-persistent.yaml

# Check deployment status
kubectl get pods,pvc,svc,ingress -l app=webscraper-api

# Verify storage initialization
kubectl logs job/webscraper-storage-init

# Access web interface
kubectl port-forward svc/webscraper-api-service 8000:80
```

## 🎯 Which Deployment to Choose?

### Use `quick-deploy.yaml` when:
- ✅ **Testing** the application quickly
- ✅ **Temporary deployments** that don't need persistence
- ✅ **CI/CD pipelines** for testing
- ✅ **Minimal resource** environments
- ❌ You don't mind reconfiguring API keys after restarts

### Use `k3s-webui-persistent.yaml` when:
- ✅ **Production deployments** where configuration persistence is critical
- ✅ **Web UI configuration** via the interface (API keys, proxy settings)
- ✅ **Database connections** for proxy rotation
- ✅ **Long-term deployments** that need to survive restarts
- ✅ **Team environments** where multiple users configure the system

## 📁 Persistent Storage Features (k3s-webui-persistent.yaml)

### What Gets Persisted:
- **API Keys**: OpenAI, Anthropic, Azure, Ollama keys configured via web interface
- **Proxy Settings**: HTTP proxy and PostgreSQL database connections
- **Database Connections**: Proxy table rotation settings
- **Application Settings**: Web UI preferences and configurations
- **Logs and Data**: Application logs and runtime data

### Storage Structure:
```
/app/persistent-config/
├── api-keys/keys.json         # API keys from web UI
├── proxy-settings/proxy.json  # Proxy and database settings
├── app-settings/config.json   # Web UI preferences
└── backups/                   # Automatic backups

/app/persistent-database/
├── sqlite/                    # Local database files
├── proxy-tables/              # Proxy rotation data
└── logs/                      # Application logs
```

## 🌐 Access and Networking

### Local Development
```bash
# Port forward to access locally
kubectl port-forward svc/webscraper-api-service 8000:80

# Access at: http://localhost:8000
```

### Production Access
Edit the ingress host in your chosen deployment file:

```yaml
spec:
  rules:
  - host: webscraper.yourdomain.com  # Change this
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

## 🔧 Common Operations

### Scaling
```bash
# Scale to more replicas
kubectl scale deployment webscraper-api --replicas=3

# Check status
kubectl get pods -l app=webscraper-api
```

### Monitoring
```bash
# View logs
kubectl logs -l app=webscraper-api -f

# Check resource usage
kubectl top pods -l app=webscraper-api

# Check storage (persistent deployment only)
kubectl get pvc
kubectl exec deployment/webscraper-api -- df -h /app/persistent-config
```

### Configuration Management (Persistent Deployment Only)
```bash
# View current API keys
kubectl exec deployment/webscraper-api -- cat /app/persistent-config/api-keys/keys.json

# View proxy settings
kubectl exec deployment/webscraper-api -- cat /app/persistent-config/proxy-settings/proxy.json

# Create configuration backup
kubectl exec deployment/webscraper-api -- tar -czf /tmp/config-backup.tar.gz /app/persistent-config
kubectl cp webscraper-api-<pod-name>:/tmp/config-backup.tar.gz ./config-backup.tar.gz
```

## 🛠️ Troubleshooting

### Common Issues

#### Pods Not Starting
```bash
# Check pod logs
kubectl logs -l app=webscraper-api

# Check events
kubectl get events --sort-by=.metadata.creationTimestamp

# Describe deployment
kubectl describe deployment webscraper-api
```

#### PVC Not Binding (Persistent Deployment)
```bash
# Check if local-path provisioner is running (K3s)
kubectl get pods -n kube-system | grep local-path

# Check storage class
kubectl get storageclass

# Install local-path provisioner if missing:
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.24/deploy/local-path-storage.yaml
```

#### Web Interface Not Accessible
```bash
# Check service endpoints
kubectl get endpoints webscraper-api-service

# Test internal connectivity
kubectl exec deployment/webscraper-api -- curl -f http://localhost:8000/api/health

# Check ingress status
kubectl describe ingress webscraper-api-ingress
```

## 📋 Quick Reference

### Essential Commands
```bash
# Deploy (choose one)
kubectl apply -f quick-deploy.yaml                    # Simple
kubectl apply -f k3s-webui-persistent.yaml           # Production

# Check status
kubectl get pods,svc,ingress -l app=webscraper-api

# Access web interface
kubectl port-forward svc/webscraper-api-service 8000:80

# View logs
kubectl logs -l app=webscraper-api -f

# Scale
kubectl scale deployment webscraper-api --replicas=3

# Restart
kubectl rollout restart deployment/webscraper-api

# Delete
kubectl delete -f <deployment-file>
```

### Configuration Paths (Persistent Deployment)
- **API Keys**: `/app/persistent-config/api-keys/keys.json`
- **Proxy Settings**: `/app/persistent-config/proxy-settings/proxy.json`
- **App Settings**: `/app/persistent-config/app-settings/config.json`
- **Database**: `/app/persistent-database/`

## 📚 Documentation

For detailed setup instructions for the persistent deployment, see:
- [K3S WebUI Persistent Guide](K3S-WEBUI-PERSISTENT-GUIDE.md)
- [Main README](../README.md)

Choose the deployment that best fits your needs - simple for testing, persistent for production! 🚀 