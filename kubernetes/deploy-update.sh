#!/bin/bash

echo "🚀 Deploying WebScraper API with latest updates..."

# Apply the updated deployment
kubectl apply -f k3s-webui-persistent.yaml

# Force a rollout restart to ensure new image is pulled
echo "🔄 Forcing rollout restart to pull latest image..."
kubectl rollout restart deployment/webscraper-api

# Wait for rollout to complete
echo "⏳ Waiting for rollout to complete..."
kubectl rollout status deployment/webscraper-api --timeout=300s

# Check pod status
echo "📊 Current pod status:"
kubectl get pods -l app=webscraper-api

# Show service status
echo "🌐 Service status:"
kubectl get svc webscraper-api-service

echo "✅ Deployment complete! Check the logs with:"
echo "   kubectl logs -l app=webscraper-api --tail=20" 