#!/bin/bash

echo "🚀 WebScraper API - Docker Compose Example"
echo "=========================================="

# Start the application
echo "📦 Starting application with Docker Compose..."
docker-compose up -d

# Wait for the application to be ready
echo "⏳ Waiting for application to be ready..."
sleep 5

# Check health
echo "🏥 Checking application health..."
curl -s http://localhost:8000/api/health | jq .

# Test newspaper4k method
echo ""
echo "📰 Testing Newspaper4k method..."
curl -s -X POST "http://localhost:8000/api/scrape/newspaper" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' | jq '.content | keys'

# Show logs
echo ""
echo "📋 Recent application logs:"
docker-compose logs --tail=5 webscraper-api

echo ""
echo "✅ Setup complete!"
echo "🌐 Web interface: http://localhost:8000"
echo "📚 API docs: http://localhost:8000/docs"
echo ""
echo "To stop the application:"
echo "docker-compose down" 