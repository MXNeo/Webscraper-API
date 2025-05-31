# Kubernetes Deployment

This directory contains Kubernetes manifests for deploying the WebScraper API in production environments, including K3s, K8s, and other Kubernetes distributions.

## Files

### `quick-deploy.yaml`
Simple, single-file Kubernetes deployment for quick testing:
- 2 replicas for basic load distribution
- Basic resource limits
- ClusterIP service and Ingress
- Minimal configuration

### `k8s-deployment.yaml`
Standard production deployment with:
- 3 replicas for high availability
- Resource requests and limits
- Health checks (readiness and liveness probes)
- Secrets management for API keys
- Pod disruption budget
- Ingress with timeout configurations

### `k8s-persistent-config.yaml`
Advanced deployment with persistent configuration:
- Persistent Volume Claim (PVC) for shared configuration
- Init containers for configuration initialization
- Hot-reload configuration without pod restarts
- ConfigMap templates for default settings
- Multi-pod shared configuration access

### `config-update-scripts.yaml`
Configuration management utilities:
- Shell scripts for updating API keys, models, and proxy settings
- Backup and restore functionality
- Configuration validation tools
- Job templates for running update operations

## Quick Start

### Option 1: Simple Deployment

```bash
# Deploy basic version
kubectl apply -f quick-deploy.yaml

# Check deployment
kubectl get pods -l app=webscraper-api
kubectl get svc webscraper-api-service
```

### Option 2: Production Deployment

```bash
# Create secret for API keys
kubectl create secret generic webscraper-secrets \
  --from-literal=openai-api-key=sk-your-actual-api-key

# Deploy production version
kubectl apply -f k8s-deployment.yaml

# Check status
kubectl get deployment webscraper-api
kubectl get pods -l app=webscraper-api
```

### Option 3: Persistent Configuration Deployment

```bash
# Deploy with persistent config
kubectl apply -f k8s-persistent-config.yaml

# Deploy config management scripts
kubectl apply -f config-update-scripts.yaml

# Verify PVC is bound
kubectl get pvc webscraper-config-pvc
```

## Configuration Management

### Using Persistent Configuration

#### Update API Key
```bash
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: update-openai-key-$(date +%s)
spec:
  template:
    spec:
      containers:
      - name: config-updater
        image: alpine:3.18
        command: ["/bin/sh", "-c"]
        args:
        - |
          apk add --no-cache jq
          /scripts/update-api-key.sh openai sk-your-new-openai-api-key
        volumeMounts:
        - name: config-storage
          mountPath: /shared-config
        - name: update-scripts
          mountPath: /scripts
      restartPolicy: Never
      volumes:
      - name: config-storage
        persistentVolumeClaim:
          claimName: webscraper-config-pvc
      - name: update-scripts
        configMap:
          name: config-update-scripts
          defaultMode: 0755
  backoffLimit: 1
EOF
```

#### View Current Configuration
```bash
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: view-config-$(date +%s)
spec:
  template:
    spec:
      containers:
      - name: config-viewer
        image: alpine:3.18
        command: ["/bin/sh", "-c"]
        args:
        - |
          apk add --no-cache jq
          /scripts/view-config.sh
        volumeMounts:
        - name: config-storage
          mountPath: /shared-config
        - name: update-scripts
          mountPath: /scripts
      restartPolicy: Never
      volumes:
      - name: config-storage
        persistentVolumeClaim:
          claimName: webscraper-config-pvc
      - name: update-scripts
        configMap:
          name: config-update-scripts
          defaultMode: 0755
  backoffLimit: 1
EOF

# View the output
kubectl logs job/view-config-$(date +%s)
```

## Access and Networking

### Ingress Configuration

Update the host in your chosen deployment file:

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

### Port Forwarding (for testing)

```bash
# Forward local port to service
kubectl port-forward svc/webscraper-api-service 8000:80

# Access at http://localhost:8000
```

## Scaling and Performance

### Manual Scaling

```bash
# Scale to 5 replicas
kubectl scale deployment webscraper-api --replicas=5

# Check scaling status
kubectl get deployment webscraper-api
```

### Resource Monitoring

```bash
# Check resource usage
kubectl top pods -l app=webscraper-api
kubectl top nodes

# Check pod status
kubectl describe pods -l app=webscraper-api
```

## Troubleshooting

### Common Issues

#### PVC Not Binding (for persistent config)
```bash
# Check storage class
kubectl get storageclass

# Check PVC status
kubectl describe pvc webscraper-config-pvc

# For K3s, ensure local-path provisioner is running
kubectl get pods -n kube-system | grep local-path
```

#### Pods Not Starting
```bash
# Check pod logs
kubectl logs -l app=webscraper-api

# Check events
kubectl get events --sort-by=.metadata.creationTimestamp

# Describe deployment
kubectl describe deployment webscraper-api
```

#### Configuration Issues
```bash
# Check config initialization (persistent config only)
kubectl logs -l app=webscraper-api -c config-init

# Check secrets
kubectl get secrets webscraper-secrets -o yaml

# Verify config file exists (persistent config only)
kubectl exec deployment/webscraper-api -- ls -la /shared-config/
```

### Recovery Procedures

#### Restart Deployment
```bash
kubectl rollout restart deployment/webscraper-api
```

#### Reset Configuration (persistent config only)
```bash
# Delete config to trigger re-initialization
kubectl exec deployment/webscraper-api -- rm /shared-config/config.json

# Restart pods
kubectl rollout restart deployment/webscraper-api
```

## Performance Tuning

### Resource Limits

Adjust based on your workload:

```yaml
resources:
  requests:
    memory: "512Mi"    # Minimum memory
    cpu: "250m"        # Minimum CPU (0.25 cores)
  limits:
    memory: "2Gi"      # Maximum memory
    cpu: "1000m"       # Maximum CPU (1 core)
```

### Concurrency Settings

Configure via environment variables:

```yaml
env:
- name: UVICORN_WORKERS
  value: "2"           # Workers per pod
- name: MAX_THREAD_POOL_SIZE
  value: "10"          # Threads per worker
```

## Documentation

For detailed guides, see:
- [K3S Deployment Guide](../K3S_DEPLOYMENT_GUIDE.md)
- [Persistent Configuration Guide](../PERSISTENT_CONFIG_GUIDE.md)
- [Main README](../README.md)

## Capacity Planning

| Configuration | Concurrent Requests | Resource Requirements |
|---------------|-------------------|---------------------|
| **Light** | ~10 requests | 1 pod, 512Mi RAM, 0.25 CPU |
| **Medium** | ~20 requests | 2 pods, 1Gi RAM, 0.5 CPU each |
| **High** | ~30+ requests | 3+ pods, 2Gi RAM, 1 CPU each | 