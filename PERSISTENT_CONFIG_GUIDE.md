# Persistent Configuration Guide for WebScraper API

This guide explains how to deploy the WebScraper API with persistent configuration using Kubernetes Persistent Volume Claims (PVC). This approach allows all workers to share the same configuration and enables hot-reloading without pod restarts.

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Pod 1         │    │   Pod 2         │    │   Pod 3         │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ WebScraper  │ │    │ │ WebScraper  │ │    │ │ WebScraper  │ │
│ │ API         │ │    │ │ API         │ │    │ │ API         │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│       │         │    │       │         │    │       │         │
└───────┼─────────┘    └───────┼─────────┘    └───────┼─────────┘
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               │
                    ┌─────────────────┐
                    │ Persistent      │
                    │ Volume          │
                    │ /shared-config/ │
                    │ ├─config.json   │
                    │ └─backups/      │
                    └─────────────────┘
```

## 🚀 Quick Deployment

### 1. Deploy with Persistent Configuration

```bash
# Deploy the persistent config version
kubectl apply -f k8s-persistent-config.yaml

# Deploy the config management scripts
kubectl apply -f config-update-scripts.yaml
```

### 2. Verify Deployment

```bash
# Check if PVC is bound
kubectl get pvc webscraper-config-pvc

# Check if pods are running
kubectl get pods -l app=webscraper-api

# Check config initialization
kubectl logs -l app=webscraper-api -c config-init
```

## 🔧 Configuration Management

### Method 1: Using Update Scripts (Recommended)

#### Update API Key
```bash
# Start a config update job
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

#### Update Model
```bash
# Update model for a provider
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: update-model-$(date +%s)
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
          /scripts/update-model.sh openai gpt-4o
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

### Method 2: Direct File Editing

#### Access the Config File Directly
```bash
# Start an interactive pod with access to the config
kubectl run config-editor --rm -i --tty \
  --image=alpine:3.18 \
  --overrides='
{
  "spec": {
    "containers": [
      {
        "name": "config-editor",
        "image": "alpine:3.18",
        "command": ["/bin/sh"],
        "volumeMounts": [
          {
            "name": "config-storage",
            "mountPath": "/shared-config"
          }
        ]
      }
    ],
    "volumes": [
      {
        "name": "config-storage",
        "persistentVolumeClaim": {
          "claimName": "webscraper-config-pvc"
        }
      }
    ]
  }
}' -- /bin/sh

# Inside the pod:
apk add --no-cache nano jq
nano /shared-config/config.json
```

#### Example Configuration Update
```json
{
  "llm_providers": {
    "openai": {
      "api_key": "sk-your-new-openai-api-key",
      "model": "gpt-4o",
      "base_url": "https://api.openai.com/v1"
    },
    "anthropic": {
      "api_key": "sk-ant-your-anthropic-key",
      "model": "claude-3-opus-20240229",
      "base_url": "https://api.anthropic.com"
    }
  },
  "proxy_settings": {
    "http_proxy": "http://proxy.company.com:8080",
    "https_proxy": "http://proxy.company.com:8080",
    "no_proxy": "localhost,127.0.0.1"
  },
  "scraping_settings": {
    "timeout": 45,
    "max_retries": 5,
    "user_agent": "WebScraper-API/1.0"
  },
  "last_updated": "2025-01-31T12:00:00Z"
}
```

## 🔄 Configuration Behavior

### Hot-Reload Process
1. **File Change Detection**: Each pod watches `/shared-config/config.json` for changes every 5 seconds
2. **Automatic Reload**: When changes are detected, configuration is reloaded without pod restart
3. **Immediate Effect**: New settings take effect for subsequent requests
4. **No Downtime**: Service continues running during config updates

### Configuration Override Behavior
- **Merge by Default**: New configurations are merged with existing ones
- **Key-Level Override**: Individual keys are replaced, not entire sections
- **Timestamp Update**: `last_updated` field is automatically updated
- **Backup Creation**: Previous config is automatically backed up

### Example Override Scenarios

#### Scenario 1: Update Only API Key
```bash
# Before
{
  "llm_providers": {
    "openai": {
      "api_key": "sk-old-key",
      "model": "gpt-4o-mini"
    }
  }
}

# Update command
./update-api-key.sh openai sk-new-key

# After (model preserved, only api_key changed)
{
  "llm_providers": {
    "openai": {
      "api_key": "sk-new-key",
      "model": "gpt-4o-mini"
    }
  }
}
```

#### Scenario 2: Add New Provider
```bash
# Before: Only OpenAI configured
# After adding Anthropic via direct edit:
{
  "llm_providers": {
    "openai": {
      "api_key": "sk-openai-key",
      "model": "gpt-4o-mini"
    },
    "anthropic": {
      "api_key": "sk-ant-new-key",
      "model": "claude-3-haiku-20240307"
    }
  }
}
```

## 📊 Monitoring Configuration Changes

### Check Configuration Status
```bash
# View current config via API
curl http://webscraper.local/api/config/status

# Check file modification time
kubectl exec -it deployment/webscraper-api -- stat /shared-config/config.json

# View recent config changes in logs
kubectl logs -l app=webscraper-api | grep -i "config"
```

### Configuration Validation
```bash
# Validate config via API
curl http://webscraper.local/api/config/validate

# Manual validation
kubectl run config-validator --rm -i --tty \
  --image=alpine:3.18 \
  --overrides='...' -- /bin/sh

# Inside pod:
apk add --no-cache jq
jq . /shared-config/config.json  # Check JSON syntax
```

## 🔒 Security Considerations

### API Key Protection
- **No Plain Text in YAML**: API keys are stored in the persistent volume, not in Kubernetes manifests
- **File Permissions**: Config file has restricted permissions (666)
- **Backup Encryption**: Consider encrypting backup files for sensitive environments

### Access Control
```bash
# Restrict PVC access with RBAC
kubectl apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: config-manager
rules:
- apiGroups: [""]
  resources: ["persistentvolumeclaims"]
  verbs: ["get", "list"]
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["create", "get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: config-manager-binding
subjects:
- kind: User
  name: config-admin
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: config-manager
  apiGroup: rbac.authorization.k8s.io
EOF
```

## 🛠️ Troubleshooting

### Common Issues

#### PVC Not Binding
```bash
# Check storage class
kubectl get storageclass

# Check PVC status
kubectl describe pvc webscraper-config-pvc

# For K3s, ensure local-path provisioner is running
kubectl get pods -n kube-system | grep local-path
```

#### Config Not Loading
```bash
# Check init container logs
kubectl logs -l app=webscraper-api -c config-init

# Check main container logs
kubectl logs -l app=webscraper-api -c webscraper-api | grep -i config

# Verify file exists
kubectl exec deployment/webscraper-api -- ls -la /shared-config/
```

#### Hot-Reload Not Working
```bash
# Check if file watcher is enabled
kubectl exec deployment/webscraper-api -- env | grep WATCH_CONFIG

# Check file modification time
kubectl exec deployment/webscraper-api -- stat /shared-config/config.json

# Force reload by restarting pods
kubectl rollout restart deployment/webscraper-api
```

### Recovery Procedures

#### Restore from Backup
```bash
# List available backups
kubectl exec deployment/webscraper-api -- ls -la /shared-config/backups/

# Restore specific backup
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: restore-config-$(date +%s)
spec:
  template:
    spec:
      containers:
      - name: config-restorer
        image: alpine:3.18
        command: ["/bin/sh", "-c"]
        args:
        - |
          apk add --no-cache jq
          /scripts/restore-config.sh /shared-config/backups/config-backup-20250131-120000.json
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

#### Reset to Default Configuration
```bash
# Delete current config to trigger re-initialization
kubectl exec deployment/webscraper-api -- rm /shared-config/config.json

# Restart pods to trigger init container
kubectl rollout restart deployment/webscraper-api
```

## 📈 Performance Impact

### Resource Usage
- **Storage**: ~1MB for config file + backups
- **Memory**: Minimal impact (~1-2MB per pod for file watching)
- **CPU**: Negligible (file check every 5 seconds)
- **Network**: No additional network traffic

### Scaling Considerations
- **Multi-Pod**: All pods share the same configuration instantly
- **Multi-Node**: Works across different nodes (ReadWriteMany PVC)
- **High Availability**: Configuration survives pod restarts and node failures

## 🎯 Best Practices

1. **Always Backup**: Use the backup script before major changes
2. **Validate Changes**: Test configuration changes in staging first
3. **Monitor Logs**: Watch application logs after config changes
4. **Use Scripts**: Prefer update scripts over manual JSON editing
5. **Version Control**: Keep configuration templates in version control
6. **Security**: Rotate API keys regularly using the update scripts

## 📋 Quick Reference

### Common Commands
```bash
# Deploy persistent config
kubectl apply -f k8s-persistent-config.yaml
kubectl apply -f config-update-scripts.yaml

# Update OpenAI API key
./update-api-key.sh openai sk-new-key

# Update model
./update-model.sh openai gpt-4o

# View current config
./view-config.sh

# Create backup
./backup-config.sh

# Check API status
curl http://webscraper.local/api/health
curl http://webscraper.local/api/config/status
```

### File Locations
- **Config File**: `/shared-config/config.json`
- **Backups**: `/shared-config/backups/`
- **Scripts**: `/scripts/` (in update jobs)
- **Logs**: `kubectl logs -l app=webscraper-api`

This persistent configuration approach provides a robust, scalable solution for managing WebScraper API settings across multiple pods with zero-downtime updates! 🚀 