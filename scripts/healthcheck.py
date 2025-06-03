#!/usr/bin/env python3
"""
Health check script for webscraper-api service
Can be used with Docker HEALTHCHECK or Kubernetes probes
"""

import requests
import sys
import json
import os
from datetime import datetime

def check_service_health():
    """Check if the webscraper service is healthy"""
    
    # Get service URL from environment or use default
    service_url = os.getenv("HEALTHCHECK_URL", "http://localhost:8000")
    timeout = int(os.getenv("HEALTHCHECK_TIMEOUT", "10"))
    
    try:
        # Check basic health endpoint
        health_response = requests.get(
            f"{service_url}/api/health",
            timeout=timeout
        )
        
        if health_response.status_code != 200:
            print(f"Health endpoint returned status {health_response.status_code}")
            return False
        
        health_data = health_response.json()
        
        # Check if service reports healthy status
        if health_data.get("status") != "healthy":
            print(f"Service reports unhealthy status: {health_data.get('status')}")
            return False
        
        # Check circuit breaker state
        circuit_breaker_state = health_data.get("circuit_breaker_state", "UNKNOWN")
        if circuit_breaker_state == "OPEN":
            print("Circuit breaker is OPEN - service may be experiencing issues")
            # Don't fail health check immediately, but log it
        
        print(f"Service is healthy - Circuit breaker: {circuit_breaker_state}")
        
        # Optional: Check service stats for additional monitoring
        try:
            stats_response = requests.get(
                f"{service_url}/api/service/stats",
                timeout=5
            )
            
            if stats_response.status_code == 200:
                stats_data = stats_response.json()
                
                # Log some useful statistics
                proxy_stats = stats_data.get("proxy_stats", {})
                usable_proxies = proxy_stats.get("usable_proxies", 0)
                failed_proxies = stats_data.get("failed_proxies_count", 0)
                
                print(f"Proxy status: {usable_proxies} usable, {failed_proxies} temporarily failed")
                
                # Warn if too many proxies are failing
                if failed_proxies > 10:
                    print("WARNING: High number of failed proxies detected")
        
        except Exception as e:
            print(f"Could not fetch service stats (non-critical): {str(e)}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("Could not connect to service")
        return False
    
    except requests.exceptions.Timeout:
        print(f"Health check timed out after {timeout} seconds")
        return False
    
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {str(e)}")
        return False
    
    except Exception as e:
        print(f"Unexpected error during health check: {str(e)}")
        return False

def check_database_connectivity():
    """Check if database is accessible"""
    service_url = os.getenv("HEALTHCHECK_URL", "http://localhost:8000")
    
    try:
        # Test database connection through the service
        db_test_response = requests.post(
            f"{service_url}/api/config/database/test",
            data={
                "host": os.getenv("DB_HOST", "localhost"),
                "port": int(os.getenv("DB_PORT", "5432")),
                "database": os.getenv("DB_NAME", "webscraper"),
                "username": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", "")
            },
            timeout=10
        )
        
        if db_test_response.status_code == 200:
            result = db_test_response.json()
            if result.get("success"):
                print("Database connectivity: OK")
                return True
            else:
                print(f"Database connectivity: FAILED - {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"Database test endpoint returned status {db_test_response.status_code}")
            return False
    
    except Exception as e:
        print(f"Database connectivity check failed: {str(e)}")
        return False

def main():
    """Main health check function"""
    print(f"Health check started at {datetime.now().isoformat()}")
    
    # Check service health
    service_healthy = check_service_health()
    
    # Check database connectivity (optional)
    db_check_enabled = os.getenv("HEALTHCHECK_DB_ENABLED", "false").lower() == "true"
    db_healthy = True
    
    if db_check_enabled:
        db_healthy = check_database_connectivity()
    
    # Determine overall health
    overall_healthy = service_healthy and db_healthy
    
    if overall_healthy:
        print("Overall health check: PASSED")
        sys.exit(0)
    else:
        print("Overall health check: FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main() 