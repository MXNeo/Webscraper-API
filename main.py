from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl
from typing import Dict, Any, Optional, List
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from scrapegraphai.graphs import SmartScraperGraph
from newspaper import Article
import asyncio
import concurrent.futures
import json
import platform
import random
import time
from database import DatabaseManager
import requests
from urllib.parse import quote
from proxy_pool import ProxyPool, EnhancedProxyRetryManager, ProxyInfo
import uuid
from metrics import init_metrics, record_request_metric
from config import Config

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get the current directory using pathlib for cross-platform compatibility
BASE_DIR = Path(__file__).parent.absolute()
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Log platform information for debugging
logger.info(f"Running on {platform.system()} {platform.release()}")
logger.info(f"Python version: {platform.python_version()}")
logger.info(f"Base directory: {BASE_DIR}")

# Configure thread pool for better concurrency
MAX_THREAD_POOL_SIZE = int(os.getenv("MAX_THREAD_POOL_SIZE", "10"))
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREAD_POOL_SIZE)

# Initialize FastAPI app
app = FastAPI(
    title="WebScraper API",
    description="API for scraping content from websites using ScrapeGraphAI",
    version="1.0.0"
)

# Setup templates and static files with cross-platform paths
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get OpenAI API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment variables")

# Initialize Config instance
config_instance = Config()

# Enhanced configuration store with status tracking
config_store = {
    "scrapegraph": None,
    "database": None,
    "proxy_enabled": False,
    "last_db_test": None,
    "last_proxy_test": None,
    "proxy_retry_count": 3,  # Number of proxy retries
    "request_timeout": 15,   # Reduced timeout
    "proxy_rotation_enabled": True,
    # New proxy pool settings
    "proxy_pool_size": 50,           # Number of proxies to keep in pool
    "min_proxy_pool_size": 10,       # Minimum pool size before refresh
    "proxy_refresh_interval": 300,   # Refresh pool every 5 minutes
    "batch_update_interval": 60,     # Process batch updates every minute
    # Metrics settings
    "metrics_enabled": True,         # Enable metrics collection
    "persist_metrics": True,         # Persist metrics to SQLite
    "metrics_db_path": "data/metrics.db",  # Path to metrics database
    "memory_retention_hours": 24,    # Keep metrics in memory for 24 hours
    "db_retention_days": 30,         # Keep database metrics for 30 days
    "max_memory_entries": 10000      # Maximum in-memory metric entries
}

# Initialize database manager with config instance
db_manager = DatabaseManager(config_instance)

# Initialize database configuration from environment variables if available
if all(os.getenv(var) for var in ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]):
    logger.info("Initializing database configuration from environment variables")
    config_instance.update_database_config(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        table=os.getenv("DB_TABLE", "proxies"),  # Default table name
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    # Add port if specified
    if os.getenv("DB_PORT"):
        config_instance.config["database"]["port"] = int(os.getenv("DB_PORT"))
    logger.info(f"Database configuration set: {os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '5432')}")

# Initialize enhanced proxy pool and retry manager
proxy_pool = ProxyPool(db_manager, config_store)
proxy_retry_manager = EnhancedProxyRetryManager(proxy_pool)

# Initialize metrics collection
metrics_collector = init_metrics(config_store)

# Models
class ScrapeRequest(BaseModel):
    url: HttpUrl
    api_key: Optional[str] = None
    use_proxy: Optional[bool] = False

class ScrapeResponse(BaseModel):
    url: str
    content: Dict[str, Any]
    status: str
    error: Optional[str] = None
    proxy_used: Optional[str] = None

# Default LLM configuration
def get_llm_config(api_key: str = None):
    return {
        "llm": {
            "api_key": api_key or OPENAI_API_KEY,
            "model": "openai/gpt-4o-mini",
        },
        "verbose": False,
        "headless": True,
    }

# Web Interface Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main web interface"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "has_api_key": bool(OPENAI_API_KEY)
    })

@app.get("/statistics", response_class=HTMLResponse)
async def statistics_page(request: Request):
    """Serve the statistics dashboard page"""
    return templates.TemplateResponse("statistics.html", {
        "request": request
    })

@app.post("/web/scrape", response_class=HTMLResponse)
async def web_scrape(
    request: Request,
    url: str = Form(...),
    api_key: str = Form(None)
):
    """Web interface for scraping"""
    try:
        # Use the API key from form or environment
        effective_api_key = api_key.strip() if api_key and api_key.strip() else OPENAI_API_KEY
        
        if not effective_api_key:
            raise HTTPException(status_code=400, detail="API key is required")
        
        # Validate API key format
        if not effective_api_key.startswith("sk-") or len(effective_api_key) < 20:
            raise HTTPException(status_code=400, detail="Invalid API key format")
        
        # Get LLM configuration
        llm_config = get_llm_config(effective_api_key)
        
        # Define the scraping function to run in thread pool
        def run_scraper():
            scraper = SmartScraperGraph(
                prompt="""Extract the following information from this webpage and return it as a JSON object:
                {
                    "content": "The complete article content/text without HTML markup - include the full text without truncating",
                    "top_image": "URL of the main article image if available",
                    "published": "Publication date if available"
                }
                
                Please extract the complete article text without truncating. If any field is not available, use null.""",
                source=url,
                config=llm_config
            )
            result = scraper.run()
            
            # Handle nested content structure that sometimes occurs
            if isinstance(result, dict) and 'content' in result:
                # If the result has nested content, flatten it
                if isinstance(result['content'], dict) and 'content' in result['content']:
                    return {
                        'content': result['content']['content'],
                        'top_image': result['content'].get('top_image'),
                        'published': result['content'].get('published')
                    }
            
            return result
        
        # Run the scraper in a thread pool to avoid asyncio.run() conflict
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(thread_pool, run_scraper)
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "has_api_key": bool(OPENAI_API_KEY),
            "result": result,
            "url": url,
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error scraping URL {url}: {str(e)}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "has_api_key": bool(OPENAI_API_KEY),
            "error": str(e),
            "url": url,
            "success": False
        })

# API Routes
@app.get("/api/health")
async def health_check():
    # Periodically reset proxy errors for recovery
    if random.random() < 0.1:  # 10% chance on each health check
        try:
            reset_count = db_manager.reset_proxy_errors(max_error_count=2)
            proxy_pool.reset_failed_proxies()  # Also reset pool's failed proxies
            logger.info(f"Health check: Reset {reset_count} proxy error counts for recovery")
        except Exception as e:
            logger.error(f"Failed to reset proxy errors during health check: {str(e)}")
    
    return {
        "status": "healthy",
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "timestamp": int(time.time()),
        "circuit_breaker_state": db_manager.circuit_breaker.state,
        "proxy_pool_size": proxy_pool.available_proxies.qsize()
    }

@app.post("/api/scrape", response_model=ScrapeResponse)
async def scrape_url(request: ScrapeRequest):
    try:
        url = str(request.url)
        logger.info(f"Received scrape request for URL: {url}")
        
        # Get API key from request or environment
        api_key = request.api_key or OPENAI_API_KEY
        if not api_key:
            raise HTTPException(status_code=400, detail="API key is required")
        
        # Validate API key format
        if not api_key.startswith("sk-") or len(api_key) < 20:
            raise HTTPException(status_code=400, detail="Invalid API key format")
        
        # Get LLM configuration
        llm_config = get_llm_config(api_key)
        
        # Define the scraping function to run in thread pool
        def run_scraper():
            scraper = SmartScraperGraph(
                prompt="""Extract the following information from this webpage and return it as a JSON object:
                {
                    "content": "The complete article content/text without HTML markup - include the full text without truncating",
                    "top_image": "URL of the main article image if available",
                    "published": "Publication date if available"
                }
                
                Please extract the complete article text without truncating. If any field is not available, use null.""",
                source=url,
                config=llm_config
            )
            result = scraper.run()
            
            # Handle nested content structure that sometimes occurs
            if isinstance(result, dict) and 'content' in result:
                # If the result has nested content, flatten it
                if isinstance(result['content'], dict) and 'content' in result['content']:
                    return {
                        'content': result['content']['content'],
                        'top_image': result['content'].get('top_image'),
                        'published': result['content'].get('published')
                    }
            
            return result
        
        # Run the scraper in a thread pool to avoid asyncio.run() conflict
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(thread_pool, run_scraper)
        
        return ScrapeResponse(
            url=url,
            content=result,
            status="success"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error scraping URL {request.url}: {str(e)}")
        return ScrapeResponse(
            url=str(request.url),
            content={},
            status="error",
            error=str(e)
        )

# Configuration API Routes
@app.get("/api/config/status")
async def get_config_status():
    """Get configuration status with detailed testing"""
    # Test database connection if configured
    db_status = "not_configured"
    db_message = "Database not configured"
    proxy_count = 0
    
    if config_store["database"]:
        try:
            db_test_result, db_test_message = db_manager.test_connection()
            if db_test_result:
                db_status = "connected"
                db_message = db_test_message
                
                # Test proxy table if database is connected
                proxy_test_result, proxy_test_message, proxy_count = db_manager.test_proxy_table()
                config_store["last_proxy_test"] = {
                    "success": proxy_test_result,
                    "message": proxy_test_message,
                    "proxy_count": proxy_count,
                    "timestamp": time.time()
                }
            else:
                db_status = "error"
                db_message = db_test_message
        except Exception as e:
            db_status = "error"
            db_message = f"Database test failed: {str(e)}"
            logger.error(f"Database status check failed: {str(e)}")
    
    config_store["last_db_test"] = {
        "status": db_status,
        "message": db_message,
        "timestamp": time.time()
    }
    
    return {
        "scrapegraph": {
            "configured": config_store["scrapegraph"] is not None,
            "provider": config_store["scrapegraph"].get("provider") if config_store["scrapegraph"] else None,
            "status": "configured" if config_store["scrapegraph"] else "not_configured"
        },
        "database": {
            "configured": config_store["database"] is not None,
            "status": db_status,
            "message": db_message,
            "last_test": config_store["last_db_test"]
        },
        "proxy": {
            "enabled": config_store["proxy_enabled"],
            "available_proxies": proxy_count,
            "status": "ready" if proxy_count > 0 and config_store["proxy_enabled"] else "disabled",
            "last_test": config_store["last_proxy_test"]
        }
    }

@app.post("/api/config/scrapegraph")
async def save_scrapegraph_config(
    provider: str = Form(...),
    model: str = Form(...),
    api_key: str = Form(None),
    temperature: float = Form(0.0),
    max_tokens: int = Form(None),
    base_url: str = Form(None),
    api_version: str = Form(None),
    deployment_name: str = Form(None),
    embeddings_deployment: str = Form(None)
):
    """Save ScrapeGraph AI configuration"""
    try:
        # Validate API key format for providers that need it
        if provider in ["openai", "anthropic", "azure"] and api_key:
            if not api_key.startswith("sk-") or len(api_key) < 20:
                raise HTTPException(status_code=400, detail="Invalid API key format")
        
        config = {
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "configured_at": time.time()
        }
        
        if api_key:
            config["api_key"] = api_key
        if max_tokens:
            config["max_tokens"] = max_tokens
        if base_url:
            config["base_url"] = base_url
        if api_version:
            config["api_version"] = api_version
        if deployment_name:
            config["deployment_name"] = deployment_name
        if embeddings_deployment:
            config["embeddings_deployment"] = embeddings_deployment
            
        config_store["scrapegraph"] = config
        logger.info(f"ScrapeGraph AI configuration saved: provider={provider}, model={model}")
        
        return {"message": "ScrapeGraph AI configuration saved successfully", "status": "configured"}
        
    except Exception as e:
        logger.error(f"Error saving ScrapeGraph AI configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/config/scrapegraph")
async def delete_scrapegraph_config():
    """Delete ScrapeGraph AI configuration"""
    config_store["scrapegraph"] = None
    logger.info("ScrapeGraph AI configuration deleted")
    return {"message": "ScrapeGraph AI configuration deleted", "status": "not_configured"}

@app.post("/api/config/database/test")
async def test_database_config(
    host: str = Form(...),
    port: int = Form(5432),
    database: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    """Test database configuration without saving it"""
    try:
        logger.info(f"Testing database configuration (without saving):")
        logger.info(f"  Host: {host}")
        logger.info(f"  Port: {port}")
        logger.info(f"  Database: {database}")
        logger.info(f"  Username: {username}")
        logger.info(f"  Password: {'*' * len(password) if password else 'None'}")
        
        # Validate input parameters
        if not host or not host.strip():
            logger.error("Database host is empty or invalid")
            raise HTTPException(status_code=400, detail="Database host is required and cannot be empty")
        
        if not database or not database.strip():
            logger.error("Database name is empty or invalid")
            raise HTTPException(status_code=400, detail="Database name is required and cannot be empty")
        
        if not username or not username.strip():
            logger.error("Database username is empty or invalid")
            raise HTTPException(status_code=400, detail="Database username is required and cannot be empty")
        
        if not password or not password.strip():
            logger.error("Database password is empty or invalid")
            raise HTTPException(status_code=400, detail="Database password is required and cannot be empty")
        
        if not isinstance(port, int) or port <= 0 or port > 65535:
            logger.error(f"Invalid port number: {port}")
            raise HTTPException(status_code=400, detail="Port must be a valid number between 1 and 65535")
        
        # Create temporary configuration for testing
        temp_config = {
            "host": host.strip(),
            "port": port,
            "database": database.strip(),
            "username": username.strip(),
            "password": password.strip()
        }
        
        logger.info("Testing database connection with provided credentials...")
        
        # Temporarily store config for testing
        original_config = config_store.get("database")
        config_store["database"] = temp_config
        
        try:
            # Test the connection
            db_test_result, db_test_message = db_manager.test_connection()
            
            if not db_test_result:
                logger.error(f"Database connection test failed: {db_test_message}")
                return {
                    "success": False,
                    "message": db_test_message,
                    "proxy_table_status": "Not tested - connection failed",
                    "available_proxies": 0
                }
            
            logger.info("Database connection successful, testing proxy table...")
            
            # Test proxy table
            proxy_test_result, proxy_test_message, proxy_count = db_manager.test_proxy_table()
            
            logger.info(f"Database test completed: {host}:{port}/{database}")
            logger.info(f"Proxy table test: {proxy_test_message}")
            
            return {
                "success": True,
                "message": "Database connection test successful",
                "proxy_table_status": proxy_test_message,
                "available_proxies": proxy_count,
                "proxy_table_ok": proxy_test_result
            }
            
        finally:
            # Restore original configuration
            config_store["database"] = original_config
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error testing database configuration: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/api/config/database")
async def save_database_config(
    host: str = Form(...),
    port: int = Form(5432),
    database: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    """Save database configuration and test connection"""
    try:
        logger.info(f"Received database configuration request:")
        logger.info(f"  Host: {host}")
        logger.info(f"  Port: {port}")
        logger.info(f"  Database: {database}")
        logger.info(f"  Username: {username}")
        logger.info(f"  Password: {'*' * len(password) if password else 'None'}")
        
        # Validate input parameters
        if not host or not host.strip():
            logger.error("Database host is empty or invalid")
            raise HTTPException(status_code=400, detail="Database host is required and cannot be empty")
        
        if not database or not database.strip():
            logger.error("Database name is empty or invalid")
            raise HTTPException(status_code=400, detail="Database name is required and cannot be empty")
        
        if not username or not username.strip():
            logger.error("Database username is empty or invalid")
            raise HTTPException(status_code=400, detail="Database username is required and cannot be empty")
        
        if not password or not password.strip():
            logger.error("Database password is empty or invalid")
            raise HTTPException(status_code=400, detail="Database password is required and cannot be empty")
        
        if not isinstance(port, int) or port <= 0 or port > 65535:
            logger.error(f"Invalid port number: {port}")
            raise HTTPException(status_code=400, detail="Port must be a valid number between 1 and 65535")
        
        config = {
            "host": host.strip(),
            "port": port,
            "database": database.strip(),
            "username": username.strip(),
            "password": password.strip(),
            "configured_at": time.time()
        }
        
        logger.info("Database configuration validated, testing connection...")
        
        # Test the connection before saving
        config_store["database"] = config
        logger.info("Testing database connection...")
        db_test_result, db_test_message = db_manager.test_connection()
        
        if not db_test_result:
            # Remove the config if test failed
            config_store["database"] = None
            logger.error(f"Database connection test failed: {db_test_message}")
            raise HTTPException(status_code=400, detail=f"Database connection test failed: {db_test_message}")
        
        logger.info("Database connection successful, testing proxy table...")
        
        # Test proxy table
        proxy_test_result, proxy_test_message, proxy_count = db_manager.test_proxy_table()
        
        logger.info(f"Database configuration saved and tested: {host}:{port}/{database}")
        logger.info(f"Proxy table test: {proxy_test_message}")
        
        return {
            "message": "Database configuration saved and tested successfully",
            "status": "connected",
            "proxy_table_status": proxy_test_message,
            "available_proxies": proxy_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        config_store["database"] = None
        logger.error(f"Unexpected error saving database configuration: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/api/config/database")
async def delete_database_config():
    """Delete database configuration"""
    config_store["database"] = None
    config_store["proxy_enabled"] = False
    config_store["last_db_test"] = None
    config_store["last_proxy_test"] = None
    logger.info("Database configuration deleted")
    return {"message": "Database configuration deleted", "status": "not_configured"}

@app.post("/api/config/proxy/toggle")
async def toggle_proxy_usage(
    enabled: bool = Form(...)
):
    """Enable or disable proxy usage"""
    try:
        if enabled and not config_store["database"]:
            raise HTTPException(status_code=400, detail="Database must be configured before enabling proxy usage")
        
        if enabled:
            # Test proxy availability
            proxy_test_result, proxy_test_message, proxy_count = db_manager.test_proxy_table()
            if not proxy_test_result or proxy_count == 0:
                raise HTTPException(status_code=400, detail=f"No usable proxies available: {proxy_test_message}")
        
        config_store["proxy_enabled"] = enabled
        status = "enabled" if enabled else "disabled"
        logger.info(f"Proxy usage {status}")
        
        return {
            "message": f"Proxy usage {status}",
            "enabled": enabled,
            "available_proxies": proxy_count if enabled else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling proxy usage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/proxy/test")
async def test_proxy_connection():
    """Test proxy database connection and retrieve sample proxies"""
    try:
        if not config_store["database"]:
            raise HTTPException(status_code=400, detail="Database not configured")
        
        # Test database connection
        db_test_result, db_test_message = db_manager.test_connection()
        if not db_test_result:
            return {
                "success": False,
                "message": f"Database connection failed: {db_test_message}",
                "proxies": []
            }
        
        # Test proxy table
        proxy_test_result, proxy_test_message, proxy_count = db_manager.test_proxy_table()
        if not proxy_test_result:
            return {
                "success": False,
                "message": proxy_test_message,
                "proxies": []
            }
        
        # Get sample proxies (limit to 3 for testing)
        sample_proxies = db_manager.get_proxies(count=3)
        
        # Remove sensitive information for display
        safe_proxies = []
        for proxy in sample_proxies:
            safe_proxy = {
                "id": proxy["id"],
                "address": proxy["address"],
                "port": proxy["port"],
                "type": proxy["type"],
                "error_count": proxy["error_count"],
                "has_auth": bool(proxy.get("username") and proxy.get("password"))
            }
            safe_proxies.append(safe_proxy)
        
        logger.info(f"Proxy test successful: {len(sample_proxies)} proxies retrieved")
        
        return {
            "success": True,
            "message": f"Proxy test successful: {proxy_count} total proxies available",
            "total_proxies": proxy_count,
            "sample_proxies": safe_proxies
        }
        
    except Exception as e:
        logger.error(f"Proxy test failed: {str(e)}")
        return {
            "success": False,
            "message": f"Proxy test failed: {str(e)}",
            "proxies": []
        }

@app.get("/api/proxy/stats")
async def get_proxy_stats():
    """Get detailed proxy statistics"""
    try:
        if not config_store["database"]:
            raise HTTPException(status_code=400, detail="Database not configured")
        
        stats = db_manager.get_proxy_stats()
        logger.info(f"Proxy statistics retrieved: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get proxy statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/proxy/debug")
async def debug_proxy_data():
    """Debug endpoint to show proxy data structure (with masked credentials)"""
    try:
        if not config_store["database"]:
            return {"error": "Database not configured"}
        
        # Get one proxy for debugging
        proxies = db_manager.get_proxies(count=1)
        if not proxies:
            return {"error": "No proxies available"}
        
        proxy = proxies[0]
        
        # Mask sensitive data for debugging
        debug_proxy = {
            "id": proxy.get("id"),
            "address": proxy.get("address"),
            "port": proxy.get("port"),
            "type": proxy.get("type"),
            "error_count": proxy.get("error_count"),
            "status": proxy.get("status", "unknown"),
            "username": "***" if proxy.get("username") else None,
            "password": "***" if proxy.get("password") else None,
            "has_auth": bool(proxy.get("username") and proxy.get("password")),
            "proxy_url_sample": proxy.get("proxy_url", "").replace(
                proxy.get("username", ""), "***").replace(
                proxy.get("password", ""), "***") if proxy.get("proxy_url") else None
        }
        
        return {
            "proxy_data": debug_proxy,
            "expected_format": "http://username:password@ip:port or https://username:password@ip:port"
        }
        
    except Exception as e:
        logger.error(f"Debug proxy data failed: {str(e)}")
        return {"error": str(e)}

# Update the scraping endpoints to use stored configuration
@app.post("/api/scrape/scrapegraph")
async def scrape_with_scrapegraph_config(request: ScrapeRequest):
    """Scrape using stored ScrapeGraph AI configuration"""
    try:
        url = str(request.url)
        logger.info(f"Received ScrapeGraph scrape request for URL: {url}")
        
        # Get stored configuration
        stored_config = config_store.get("scrapegraph")
        if not stored_config:
            raise HTTPException(status_code=400, detail="ScrapeGraph AI not configured. Please configure it first.")
        
        # Use API key from request or stored config
        api_key = request.api_key or stored_config.get("api_key")
        if not api_key:
            raise HTTPException(status_code=400, detail="API key is required")
        
        # Validate API key format
        if not api_key.startswith("sk-") or len(api_key) < 20:
            raise HTTPException(status_code=400, detail="Invalid API key format. Please provide a valid OpenAI API key starting with 'sk-'")
        
        # Check if proxy should be used
        use_proxy = request.use_proxy or config_store.get("proxy_enabled", False)
        selected_proxy = None
        proxy_id = None
        
        if use_proxy and config_store["database"]:
            # Get a proxy from the database
            proxies = db_manager.get_proxies(count=1)
            if proxies:
                selected_proxy = proxies[0]
                proxy_id = selected_proxy["id"]
                logger.info(f"Using proxy {proxy_id} for ScrapGraph AI: {selected_proxy['address']}:{selected_proxy['port']}")
            else:
                logger.warning("Proxy requested but no proxies available, proceeding without proxy")
        
        # Build configuration for ScrapeGraph AI
        llm_config = {
            "llm": {
                "api_key": api_key,
                "model": f"openai/{stored_config.get('model', 'gpt-4o-mini')}",
                "temperature": stored_config.get("temperature", 0.0)
            },
            "verbose": False,
            "headless": True
        }
        
        if stored_config.get("max_tokens"):
            llm_config["llm"]["max_tokens"] = stored_config["max_tokens"]
        
        # Define the scraping function to run in thread pool
        def run_scraper():
            try:
                # If using proxy, fetch content manually first
                if selected_proxy:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                    }
                    
                    # Build proxy URL with authentication embedded
                    if selected_proxy.get('username') and selected_proxy.get('password'):
                        # URL-encode credentials to handle special characters
                        username = quote(selected_proxy['username'], safe='')
                        password = quote(selected_proxy['password'], safe='')
                        proxy_address = f"{selected_proxy['type']}://{username}:{password}@{selected_proxy['address']}:{selected_proxy['port']}"
                        logger.info(f"Using authenticated proxy for ScrapGraph AI: {selected_proxy['username']}:***@{selected_proxy['address']}:{selected_proxy['port']}")
                    else:
                        # No authentication
                        proxy_address = f"{selected_proxy['type']}://{selected_proxy['address']}:{selected_proxy['port']}"
                        logger.info(f"Using proxy for ScrapGraph AI (no auth): {selected_proxy['address']}:{selected_proxy['port']}")
                    
                    proxies = {
                        'http': proxy_address,
                        'https': proxy_address
                    }
                    
                    logger.debug(f"Fetching URL with proxy for ScrapGraph AI: {url}")
                    response = requests.get(
                        url,
                        headers=headers,
                        proxies=proxies,
                        timeout=30,
                        allow_redirects=True,
                        verify=True
                    )
                    response.raise_for_status()
                    
                    logger.debug(f"Successfully fetched content via proxy, status: {response.status_code}")
                    
                    # Use the fetched HTML as source for ScrapGraph AI
                    scraper = SmartScraperGraph(
                        prompt="""Extract the following information from this webpage and return it as a JSON object:
                        {
                            "content": "The complete article content/text without HTML markup - include the full text without truncating",
                            "top_image": "URL of the main article image if available",
                            "published": "Publication date if available"
                        }
                        
                        Please extract the complete article text without truncating. If any field is not available, use null.""",
                        source=response.text,  # Use fetched HTML instead of URL
                        config=llm_config
                    )
                    
                    # Update proxy success
                    if proxy_id:
                        db_manager.update_proxy_last_used(proxy_id)
                        logger.debug(f"Updated last_used for proxy {proxy_id}")
                        
                else:
                    # Use URL directly without proxy
                    scraper = SmartScraperGraph(
                        prompt="""Extract the following information from this webpage and return it as a JSON object:
                        {
                            "content": "The complete article content/text without HTML markup - include the full text without truncating",
                            "top_image": "URL of the main article image if available",
                            "published": "Publication date if available"
                        }
                        
                        Please extract the complete article text without truncating. If any field is not available, use null.""",
                        source=url,
                        config=llm_config
                    )
                
                result = scraper.run()
                
                # Handle nested content structure that sometimes occurs
                if isinstance(result, dict) and 'content' in result:
                    # If the result has nested content, flatten it
                    if isinstance(result['content'], dict) and 'content' in result['content']:
                        return {
                            'content': result['content']['content'],
                            'top_image': result['content'].get('top_image'),
                            'published': result['content'].get('published')
                        }
                
                return result
                
            except requests.exceptions.ProxyError as e:
                error_msg = f"Proxy error: {str(e)}"
                logger.error(error_msg)
                if proxy_id and selected_proxy:
                    logger.warning(f"Proxy {proxy_id} failed, incrementing error count")
                    db_manager.increment_proxy_error(proxy_id)
                raise Exception(error_msg)
                
            except requests.exceptions.RequestException as e:
                error_msg = f"Request failed: {str(e)}"
                logger.error(error_msg)
                if proxy_id and selected_proxy:
                    logger.warning(f"Request failed with proxy {proxy_id}, incrementing error count")
                    db_manager.increment_proxy_error(proxy_id)
                raise Exception(error_msg)
                
            except Exception as e:
                if proxy_id and selected_proxy:
                    logger.warning(f"ScrapGraph AI failed with proxy {proxy_id}, incrementing error count")
                    db_manager.increment_proxy_error(proxy_id)
                raise e
        
        # Run the scraper in a thread pool to avoid asyncio.run() conflict
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(thread_pool, run_scraper)
        
        proxy_info = None
        if selected_proxy:
            proxy_info = f"{selected_proxy['address']}:{selected_proxy['port']}"
        
        return ScrapeResponse(
            url=url,
            content=result,
            status="success",
            proxy_used=proxy_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ScrapeGraph scraping failed: {str(e)}")
        error_msg = str(e)
        if "Model not supported" in error_msg:
            error_msg = f"Model not supported. Please check your API key is valid and the model '{stored_config.get('model', 'gpt-4o-mini')}' is available with your OpenAI account."
        
        proxy_info = None
        if selected_proxy:
            proxy_info = f"{selected_proxy['address']}:{selected_proxy['port']}"
        
        return ScrapeResponse(
            url=str(request.url),
            content={},
            status="error",
            error=error_msg,
            proxy_used=proxy_info
        )

@app.post("/api/scrape/newspaper")
async def scrape_with_newspaper(request: ScrapeRequest):
    """Scrape using Newspaper4k with enhanced proxy pool support and retry logic"""
    start_time = time.time()
    url = str(request.url)
    request_id = str(uuid.uuid4())  # Unique ID for this request
    selected_proxy = None
    error_type = None
    content_length = 0
    attempt_count = 0
    
    try:
        logger.info(f"Received Newspaper scrape request for URL: {url} (request_id: {request_id})")
        
        # Check if proxy should be used
        use_proxy = request.use_proxy or config_store.get("proxy_enabled", False)
        max_retries = config_store.get("proxy_retry_count", 3)
        request_timeout = config_store.get("request_timeout", 15)
        
        # Define the scraping function with enhanced retry logic
        def run_newspaper_scraper():
            nonlocal selected_proxy, error_type, content_length, attempt_count
            
            last_error = None
            
            for attempt in range(max_retries + 1):  # +1 for no-proxy fallback
                attempt_count = attempt + 1
                try:
                    # Determine if we should use proxy on this attempt
                    use_proxy_this_attempt = use_proxy and attempt < max_retries
                    
                    if use_proxy_this_attempt and config_store["database"]:
                        # Get a proxy from the pool for this specific request
                        selected_proxy = proxy_retry_manager.get_proxy_for_request(request_id)
                        if selected_proxy:
                            logger.info(f"Attempt {attempt + 1}: Using proxy {selected_proxy.id}: {selected_proxy.address}:{selected_proxy.port}")
                        else:
                            logger.warning(f"Attempt {attempt + 1}: No proxies available, proceeding without proxy")
                            use_proxy_this_attempt = False
                    else:
                        if attempt == max_retries:
                            logger.info(f"Attempt {attempt + 1}: Fallback to direct connection (no proxy)")
                        selected_proxy = None
                    
                    # Prepare request configuration
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Cache-Control': 'max-age=0'
                    }
                    
                    # Configure proxy if available
                    proxies = None
                    if selected_proxy and use_proxy_this_attempt:
                        proxies = {
                            'http': selected_proxy.proxy_url,
                            'https': selected_proxy.proxy_url
                        }
                        logger.debug(f"Using proxy URL: {selected_proxy.address}:{selected_proxy.port}")
                    
                    # Make the request with timeout and retries
                    logger.debug(f"Fetching URL: {url}")
                    
                    # Session for connection reuse
                    session = requests.Session()
                    session.headers.update(headers)
                    
                    response = session.get(
                        url,
                        proxies=proxies,
                        timeout=request_timeout,
                        allow_redirects=True,
                        verify=True
                    )
                    response.raise_for_status()
                    
                    content_length = len(response.content)
                    logger.debug(f"Successfully fetched content, status: {response.status_code}, size: {content_length} bytes")
                    
                    # Create article and set the HTML content
                    article = Article(url)
                    article.download(input_html=response.text)
                    article.parse()
                    
                    # Mark proxy as successful if used
                    if selected_proxy:
                        proxy_retry_manager.mark_proxy_success_for_request(request_id, selected_proxy)
                        logger.debug(f"Marked proxy {selected_proxy.id} as successful for request {request_id}")
                    
                    # Standardize output to match ScrapGraph AI format
                    result = {
                        "content": article.text if article.text else "",
                        "top_image": article.top_image,
                        "published": article.publish_date.isoformat() if article.publish_date else None,
                        "title": article.title if hasattr(article, 'title') else None,
                        "authors": list(article.authors) if hasattr(article, 'authors') else [],
                        "summary": article.summary if hasattr(article, 'summary') else None
                    }
                    
                    logger.info(f"Successfully scraped article: content_length={len(result['content'])}, title='{result.get('title', 'N/A')[:50]}...', attempt={attempt + 1}")
                    return result
                    
                except requests.exceptions.ProxyError as e:
                    last_error = f"Proxy error: {str(e)}"
                    error_type = "ProxyError"
                    logger.warning(f"Attempt {attempt + 1} - Proxy error: {str(e)}")
                    
                    if selected_proxy:
                        proxy_retry_manager.mark_proxy_failed_for_request(request_id, selected_proxy)
                        logger.warning(f"Marked proxy {selected_proxy.id} as failed for request {request_id}")
                    
                    if attempt == max_retries:
                        break
                    
                    # Short delay before retry
                    time.sleep(0.5 * (attempt + 1))
                    
                except requests.exceptions.Timeout as e:
                    last_error = f"Request timeout after {request_timeout}s: {str(e)}"
                    error_type = "Timeout"
                    logger.warning(f"Attempt {attempt + 1} - Timeout: {str(e)}")
                    
                    if selected_proxy:
                        proxy_retry_manager.mark_proxy_failed_for_request(request_id, selected_proxy)
                    
                    if attempt == max_retries:
                        break
                    
                    time.sleep(1.0 * (attempt + 1))
                    
                except requests.exceptions.ConnectionError as e:
                    last_error = f"Connection error: {str(e)}"
                    error_type = "ConnectionError"
                    logger.warning(f"Attempt {attempt + 1} - Connection error: {str(e)}")
                    
                    if selected_proxy:
                        proxy_retry_manager.mark_proxy_failed_for_request(request_id, selected_proxy)
                    
                    if attempt == max_retries:
                        break
                    
                    time.sleep(1.0 * (attempt + 1))
                    
                except requests.exceptions.HTTPError as e:
                    last_error = f"HTTP error: {str(e)}"
                    error_type = "HTTPError"
                    logger.warning(f"Attempt {attempt + 1} - HTTP error: {str(e)}")
                    
                    # Don't retry on 4xx errors (client errors)
                    if response.status_code >= 400 and response.status_code < 500:
                        raise Exception(last_error)
                    
                    if selected_proxy:
                        proxy_retry_manager.mark_proxy_failed_for_request(request_id, selected_proxy)
                    
                    if attempt == max_retries:
                        break
                    
                    time.sleep(1.0 * (attempt + 1))
                    
                except Exception as e:
                    last_error = f"Scraping failed: {str(e)}"
                    error_type = "UnknownError"
                    logger.warning(f"Attempt {attempt + 1} - Unexpected error: {str(e)}")
                    
                    if selected_proxy:
                        proxy_retry_manager.mark_proxy_failed_for_request(request_id, selected_proxy)
                    
                    if attempt == max_retries:
                        break
                    
                    time.sleep(1.0 * (attempt + 1))
            
            # If we get here, all attempts failed
            raise Exception(f"All {max_retries + 1} attempts failed. Last error: {last_error}")
        
        # Run the scraper in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(thread_pool, run_newspaper_scraper)
        
        # Record successful metrics
        duration = time.time() - start_time
        proxy_info = f"{selected_proxy.address}:{selected_proxy.port}" if selected_proxy else None
        
        record_request_metric(
            url=url,
            method="newspaper",
            success=True,
            duration=duration,
            proxy_used=proxy_info,
            content_length=len(result.get('content', '')),
            attempt_count=attempt_count,
            request_id=request_id
        )
        
        return ScrapeResponse(
            url=url,
            content=result,
            status="success",
            proxy_used=proxy_info
        )
        
    except Exception as e:
        # Record failed metrics
        duration = time.time() - start_time
        proxy_info = f"{selected_proxy.address}:{selected_proxy.port}" if selected_proxy else None
        
        record_request_metric(
            url=url,
            method="newspaper",
            success=False,
            duration=duration,
            proxy_used=proxy_info,
            error_type=error_type or "UnknownError",
            content_length=content_length,
            attempt_count=attempt_count,
            request_id=request_id
        )
        
        logger.error(f"Newspaper scraping failed completely: {str(e)}")
        return ScrapeResponse(
            url=str(request.url),
            content={},
            status="error",
            error=str(e),
            proxy_used=proxy_info
        )

# Add metrics endpoints
@app.get("/api/metrics/current")
async def get_current_metrics():
    """Get current real-time metrics"""
    try:
        if metrics_collector:
            return metrics_collector.get_current_stats()
        else:
            return {"error": "Metrics not initialized"}
    except Exception as e:
        logger.error(f"Failed to get current metrics: {str(e)}")
        return {"error": str(e)}

@app.get("/api/metrics/historical")
async def get_historical_metrics(days: int = 7):
    """Get historical metrics for specified number of days"""
    try:
        if metrics_collector:
            return metrics_collector.get_historical_stats(days=days)
        else:
            return {"error": "Metrics not initialized"}
    except Exception as e:
        logger.error(f"Failed to get historical metrics: {str(e)}")
        return {"error": str(e)}

@app.get("/api/metrics/export")
async def export_metrics():
    """Export all metrics data"""
    try:
        if metrics_collector:
            return {
                "data": metrics_collector.export_metrics(),
                "timestamp": time.time()
            }
        else:
            return {"error": "Metrics not initialized"}
    except Exception as e:
        logger.error(f"Failed to export metrics: {str(e)}")
        return {"error": str(e)}

# Enhanced service stats endpoint with proxy pool information
@app.get("/api/service/stats")
async def get_service_stats():
    """Get comprehensive service statistics including proxy pool"""
    try:
        # Get proxy stats from database
        proxy_stats = db_manager.get_proxy_stats()
        
        # Get proxy pool stats
        pool_stats = proxy_pool.get_pool_stats()
        
        # Get circuit breaker status
        circuit_breaker_status = {
            "state": db_manager.circuit_breaker.state,
            "failure_count": db_manager.circuit_breaker.failure_count,
            "last_failure_time": db_manager.circuit_breaker.last_failure_time
        }
        
        return {
            "timestamp": int(time.time()),
            "proxy_stats": proxy_stats,
            "proxy_pool_stats": pool_stats,
            "circuit_breaker": circuit_breaker_status,
            "config": {
                "proxy_enabled": config_store.get("proxy_enabled", False),
                "proxy_retry_count": config_store.get("proxy_retry_count", 3),
                "request_timeout": config_store.get("request_timeout", 15),
                "proxy_pool_size": config_store.get("proxy_pool_size", 50),
                "min_proxy_pool_size": config_store.get("min_proxy_pool_size", 10)
            },
            "active_requests": len(proxy_retry_manager.request_failed_proxies)
        }
    except Exception as e:
        logger.error(f"Failed to get service stats: {str(e)}")
        return {"error": str(e), "timestamp": int(time.time())}

# Enhanced proxy reset endpoint
@app.post("/api/service/reset-proxies")
async def reset_proxy_errors():
    """Manually reset proxy error counts and refresh pool"""
    try:
        # Reset database proxy errors
        reset_count = db_manager.reset_proxy_errors(max_error_count=2)
        
        # Reset proxy pool failed proxies
        pool_reset_count = proxy_pool.reset_failed_proxies()
        
        # Force refresh the proxy pool
        proxy_pool.force_refresh()
        
        # Clean up request tracking
        proxy_retry_manager.cleanup_old_requests()
        
        return {
            "status": "success",
            "db_reset_count": reset_count,
            "pool_reset_count": pool_reset_count,
            "message": f"Reset {reset_count} proxy error counts and {pool_reset_count} pool failures"
        }
    except Exception as e:
        logger.error(f"Failed to reset proxy errors: {str(e)}")
        return {"status": "error", "message": str(e)}

# New endpoint for proxy pool management
@app.get("/api/proxy/pool/stats")
async def get_proxy_pool_stats():
    """Get detailed proxy pool statistics"""
    try:
        return proxy_pool.get_pool_stats()
    except Exception as e:
        logger.error(f"Failed to get proxy pool stats: {str(e)}")
        return {"error": str(e)}

@app.post("/api/proxy/pool/refresh")
async def refresh_proxy_pool():
    """Force refresh the proxy pool"""
    try:
        proxy_pool.force_refresh()
        return {"status": "success", "message": "Proxy pool refresh triggered"}
    except Exception as e:
        logger.error(f"Failed to refresh proxy pool: {str(e)}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 