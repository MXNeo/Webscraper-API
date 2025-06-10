#!/bin/bash

# Multi-platform Docker build script for WebScraper API
# Supports AMD64 (Intel/AMD) and ARM64 (Apple Silicon) architectures

set -e

# Configuration
IMAGE_NAME="neoexec/webscraper-api"
VERSION="1.4.0"
PLATFORMS="linux/amd64,linux/arm64"

echo "🚀 Building multi-platform WebScraper API Docker image"
echo "📦 Image: $IMAGE_NAME:$VERSION"
echo "🏗️  Platforms: $PLATFORMS"
echo ""

# Check if Docker buildx is available
if ! docker buildx version > /dev/null 2>&1; then
    echo "❌ Docker buildx is not available. Please install Docker Desktop or enable buildx."
    exit 1
fi

# Create and use a new builder instance if it doesn't exist
BUILDER_NAME="webscraper-builder"
if ! docker buildx inspect $BUILDER_NAME > /dev/null 2>&1; then
    echo "🔧 Creating new buildx builder: $BUILDER_NAME"
    docker buildx create --name $BUILDER_NAME --use
else
    echo "🔧 Using existing buildx builder: $BUILDER_NAME"
    docker buildx use $BUILDER_NAME
fi

# Bootstrap the builder
echo "🔧 Bootstrapping builder..."
docker buildx inspect --bootstrap

# Build and push multi-platform image
echo "🏗️  Building multi-platform image..."
docker buildx build \
    --platform $PLATFORMS \
    --tag $IMAGE_NAME:$VERSION \
    --tag $IMAGE_NAME:latest \
    --push \
    --file Dockerfile \
    ..

echo ""
echo "✅ Multi-platform build completed successfully!"
echo "📋 Image details:"
echo "   - Name: $IMAGE_NAME:$VERSION"
echo "   - Platforms: $PLATFORMS"
echo "   - Registry: Docker Hub"
echo ""
echo "🧪 Test the image on your platform:"
echo "   docker run -d -p 8000:8000 $IMAGE_NAME:$VERSION"
echo ""
echo "🌍 The image now supports:"
echo "   ✅ Intel/AMD Macs (x86_64)"
echo "   ✅ Apple Silicon Macs (ARM64)"
echo "   ✅ Windows with Docker Desktop"
echo "   ✅ Linux AMD64 systems"
echo "   ✅ Linux ARM64 systems" 