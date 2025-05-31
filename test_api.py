#!/usr/bin/env python3
"""
Test script for the WebScraper API
"""
import requests
import json
import os

# API endpoint
API_URL = "http://localhost:8000"

def test_health():
    """Test the health endpoint"""
    response = requests.get(f"{API_URL}/health")
    print(f"Health check: {response.json()}")

def test_scrape(url, api_key):
    """Test scraping a URL"""
    payload = {
        "url": url,
        "api_key": api_key
    }
    
    response = requests.post(f"{API_URL}/scrape", json=payload)
    result = response.json()
    
    print(f"Scraping {url}:")
    print(f"Status: {result['status']}")
    
    if result['status'] == 'success':
        print(f"Content preview: {str(result['content'])[:200]}...")
    else:
        print(f"Error: {result['error']}")
    
    return result

if __name__ == "__main__":
    # Test health
    test_health()
    
    # Get API key from environment or prompt
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\nNo OPENAI_API_KEY found in environment.")
        print("Please set your OpenAI API key:")
        print("export OPENAI_API_KEY='your-api-key-here'")
        print("\nOr test with a fake key to see validation:")
        api_key = "sk-fake-key-for-testing"
    
    # Test scraping
    print(f"\nTesting scrape with API key: {api_key[:10]}...")
    test_scrape("https://example.com", api_key) 