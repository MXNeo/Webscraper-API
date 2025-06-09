from fastapi import FastAPI, HTTPException, Request, Form, WebSocket, WebSocketDisconnect
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
from newsplease import NewsPlease
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

class ScrapeGraphConfigRequest(BaseModel):
    api_key: str

class DatabaseConfigRequest(BaseModel):
    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    table: str = "proxies"

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

@app.get("/proxy-management", response_class=HTMLResponse)
async def proxy_management_page(request: Request):
    """Serve the proxy management page"""
    return templates.TemplateResponse("proxy-management.html", {
        "request": request
    })

@app.post("/api/scrape", response_class=HTMLResponse)
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
    max_tokens: str = Form(None),  # Accept as string first, then convert
    base_url: str = Form(None),
    api_version: str = Form(None),
    deployment_name: str = Form(None),
    embeddings_deployment: str = Form(None)
):
    """Save ScrapeGraph AI configuration"""
    try:
        # Validate API key format for providers that need it
        if provider in ["openai", "anthropic", "azure"] and api_key:
            # Basic validation - check it's not empty and has reasonable length
            if len(api_key.strip()) < 10:
                raise HTTPException(status_code=400, detail="API key appears to be too short")
            
            # OpenAI API keys usually start with sk- but not always (e.g., organization keys)
            # Anthropic keys start with sk-ant-
            # Azure keys are different format
            # Let's be more lenient with validation
            api_key = api_key.strip()
        
        config = {
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "configured_at": time.time()
        }
        
        if api_key:
            config["api_key"] = api_key
        if max_tokens and max_tokens.strip():
            try:
                config["max_tokens"] = int(max_tokens.strip())
            except ValueError:
                raise HTTPException(status_code=400, detail="Max tokens must be a valid number")
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

@app.post("/api/database/config")
async def save_database_config(request: DatabaseConfigRequest):
    """Save database configuration"""
    try:
        # Handle auto-configured password (when empty, use environment if available)
        password = request.password
        if not password and os.getenv("DB_PASSWORD"):
            password = os.getenv("DB_PASSWORD")
            logger.info("Using auto-configured database password from environment")
        
        config_instance.update_database_config(
            host=request.host,
            database=request.database,
            table=request.table,
            username=request.username,
            password=password,
            port=request.port
        )
        
        # Update the config store to reflect the new database configuration
        config_store["database"] = {
            "host": request.host,
            "port": request.port,
            "database": request.database,
            "username": request.username,
            "password": password,
            "table": request.table
        }
        
        # Clear previous test results
        config_store["last_db_test"] = None
        config_store["last_proxy_test"] = None
        
        # Reset database manager connection pool to use new config
        db_manager.disconnect()
        
        logger.info(f"Database configuration saved and config store updated: {request.host}:{request.port}")
        
        return {"success": True, "message": "Database configuration saved successfully"}
        
    except Exception as e:
        logger.error(f"Failed to save database config: {str(e)}")
        return {"error": f"Failed to save database configuration: {str(e)}"}

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
                        'Accept-Encoding': 'gzip, deflate',  # Let requests handle decompression
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
                    logger.debug(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
                    logger.debug(f"Content-Encoding: {response.headers.get('content-encoding', 'none')}")
                    
                    # Ensure we have valid text content
                    try:
                        # response.text handles encoding/decoding automatically
                        html_content = response.text
                        if not html_content or len(html_content.strip()) == 0:
                            raise ValueError("Empty HTML content received")
                        
                        # Check if content looks like HTML
                        if not ('<html' in html_content.lower() or '<div' in html_content.lower() or '<body' in html_content.lower()):
                            logger.warning(f"Content doesn't appear to be HTML. First 200 chars: {repr(html_content[:200])}")
                        
                    except UnicodeDecodeError as e:
                        logger.error(f"Unicode decode error: {e}")
                        # Try with different encoding
                        html_content = response.content.decode('utf-8', errors='ignore')
                    
                    # Create article and set the HTML content
                    article = Article(url)
                    article.download(input_html=html_content)
                    article.parse()
                    
                    # DEBUG: Log detailed article extraction results
                    logger.info(f"[DEBUG] Newspaper4k extraction results for {url}:")
                    logger.info(f"[DEBUG] - Title: {repr(getattr(article, 'title', None))}")
                    logger.info(f"[DEBUG] - Text length: {len(getattr(article, 'text', '') or '')}")
                    article_text = getattr(article, 'text', None)
                    logger.info(f"[DEBUG] - Text preview: {repr(article_text[:200]) if article_text else 'None'}")
                    logger.info(f"[DEBUG] - Top image: {repr(getattr(article, 'top_image', None))}")
                    logger.info(f"[DEBUG] - Publish date: {repr(getattr(article, 'publish_date', None))}")
                    authors = getattr(article, 'authors', None)
                    logger.info(f"[DEBUG] - Authors: {repr(list(authors)) if authors else 'None'}")
                    summary = getattr(article, 'summary', None)
                    logger.info(f"[DEBUG] - Summary length: {len(summary) if summary else 0}")
                    
                    # Check if extraction actually succeeded
                    if not article_text or len(article_text.strip()) == 0:
                        logger.warning(f"[DEBUG] Newspaper4k extracted no content for {url}")
                        logger.warning(f"[DEBUG] HTML response length: {len(html_content)}")
                        logger.warning(f"[DEBUG] HTML preview: {repr(html_content[:500])}")
                        
                        # Try alternative parsing approach
                        try:
                            # Try parsing again with different settings
                            article.config.fetch_images = False
                            article.config.memoize_articles = False
                            article.parse()
                            
                            updated_text = getattr(article, 'text', None)
                            if updated_text and len(updated_text.strip()) > 0:
                                logger.info(f"[DEBUG] Alternative parsing successful, got {len(updated_text)} characters")
                                article_text = updated_text  # Update for final result
                            else:
                                logger.warning(f"[DEBUG] Alternative parsing also failed")
                        except Exception as e:
                            logger.warning(f"[DEBUG] Alternative parsing error: {str(e)}")
                    
                    # Mark proxy as successful if used
                    if selected_proxy:
                        proxy_retry_manager.mark_proxy_success_for_request(request_id, selected_proxy)
                        logger.debug(f"Marked proxy {selected_proxy.id} as successful for request {request_id}")
                    
                    # Standardize output to match ScrapGraph AI format
                    article_title = getattr(article, 'title', None)
                    article_top_image = getattr(article, 'top_image', None)
                    article_publish_date = getattr(article, 'publish_date', None)
                    article_authors = getattr(article, 'authors', None)
                    article_summary = getattr(article, 'summary', None)
                    
                    result = {
                        "content": article_text or "",
                        "top_image": article_top_image if article_top_image else None,
                        "published": article_publish_date.isoformat() if article_publish_date else None,
                        "title": article_title if article_title else None,
                        "authors": list(article_authors) if article_authors else [],
                        "summary": article_summary if article_summary else None
                    }
                    
                    title_for_log = result.get('title') or 'N/A'
                    title_preview = title_for_log[:50] if title_for_log != 'N/A' else 'N/A'
                    logger.info(f"Successfully scraped article: content_length={len(result['content'])}, title='{title_preview}...', attempt={attempt + 1}")
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

@app.post("/api/scrape/newsplease")
async def scrape_with_newsplease(request: ScrapeRequest):
    """Scrape using news-please with enhanced proxy pool support and retry logic"""
    start_time = time.time()
    url = str(request.url)
    request_id = str(uuid.uuid4())  # Unique ID for this request
    selected_proxy = None
    error_type = None
    content_length = 0
    attempt_count = 0
    
    try:
        logger.info(f"Received news-please scrape request for URL: {url} (request_id: {request_id})")
        
        # Check if proxy should be used
        use_proxy = request.use_proxy or config_store.get("proxy_enabled", False)
        max_retries = config_store.get("proxy_retry_count", 3)
        request_timeout = config_store.get("request_timeout", 15)
        
        # Define the scraping function with enhanced retry logic
        def run_newsplease_scraper():
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
                    
                    # Configure proxy settings for news-please if available
                    proxy_config = None
                    if selected_proxy and use_proxy_this_attempt:
                        # news-please uses different proxy configuration
                        proxy_config = {
                            'http': selected_proxy.proxy_url,
                            'https': selected_proxy.proxy_url
                        }
                        logger.debug(f"Using proxy URL: {selected_proxy.address}:{selected_proxy.port}")
                    
                    # Configure news-please parameters
                    # news-please doesn't have direct proxy support in from_urls, so we'll use requests with proxy first
                    if proxy_config:
                        # Manual request with proxy, then parse with news-please
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
                        
                        logger.debug(f"Fetching URL with proxy: {url}")
                        response = requests.get(
                            url,
                            headers=headers,
                            proxies=proxy_config,
                            timeout=request_timeout,
                            allow_redirects=True,
                            verify=True
                        )
                        response.raise_for_status()
                        
                        content_length = len(response.content)
                        logger.debug(f"Successfully fetched content via proxy, status: {response.status_code}, size: {content_length} bytes")
                        
                        # Parse the content with news-please from HTML
                        article = NewsPlease.from_html(response.text, url=url)
                        
                        # DEBUG: Log what we got from news-please via proxy
                        logger.info(f"[DEBUG] news-please (proxy) extraction results for {url}:")
                        logger.info(f"[DEBUG] - Article type: {type(article)}")
                        logger.info(f"[DEBUG] - Article object: {repr(article)}")
                        
                    else:
                        # Direct news-please extraction without proxy
                        logger.debug(f"Fetching URL directly with news-please: {url}")
                        articles = NewsPlease.from_urls([url])
                        article = articles.get(url)
                        
                        # DEBUG: Log what we got from news-please direct
                        logger.info(f"[DEBUG] news-please (direct) extraction results for {url}:")
                        logger.info(f"[DEBUG] - Articles dict: {type(articles)}")
                        logger.info(f"[DEBUG] - Article for URL: {type(article)}")
                        logger.info(f"[DEBUG] - Article object: {repr(article)}")
                        
                        if article is None:
                            raise Exception(f"news-please could not extract article from {url}")
                        
                        # Only try to get maintext if it's an actual article object
                        if hasattr(article, 'maintext'):
                            content_length = len(article.maintext) if article.maintext else 0
                            logger.debug(f"Successfully extracted content, size: {content_length} characters")
                        else:
                            logger.warning(f"[DEBUG] Article object has no maintext attribute: {dir(article)}")
                    
                    # Mark proxy as successful if used
                    if selected_proxy:
                        proxy_retry_manager.mark_proxy_success_for_request(request_id, selected_proxy)
                        logger.debug(f"Marked proxy {selected_proxy.id} as successful for request {request_id}")
                    
                    # Check if article extraction was successful
                    if article is None:
                        raise Exception("news-please could not extract article content")
                    
                    # DEBUG: Log all available attributes
                    logger.info(f"[DEBUG] Available attributes on article: {dir(article)}")
                    
                    # Handle different response types from news-please
                    if hasattr(article, 'maintext'):
                        # It's a proper Article object
                        logger.info(f"[DEBUG] Article object - maintext length: {len(article.maintext) if article.maintext else 0}")
                        result = {
                            "content": article.maintext if article.maintext else "",
                            "title": article.title if hasattr(article, 'title') and article.title else None,
                            "published": article.date_publish.isoformat() if hasattr(article, 'date_publish') and article.date_publish else None,
                            "authors": [article.authors] if hasattr(article, 'authors') and article.authors else [],
                            "description": article.description if hasattr(article, 'description') and article.description else None,
                            "language": article.language if hasattr(article, 'language') and article.language else None,
                            "source_domain": article.source_domain if hasattr(article, 'source_domain') and article.source_domain else None,
                            "top_image": article.image_url if hasattr(article, 'image_url') and article.image_url else None,
                            "url": article.url if hasattr(article, 'url') and article.url else url
                        }
                    elif isinstance(article, dict):
                        # It's a dictionary response
                        logger.info(f"[DEBUG] Dictionary response keys: {list(article.keys())}")
                        result = {
                            "content": article.get('maintext', '') or article.get('text', '') or article.get('content', ''),
                            "title": article.get('title'),
                            "published": article.get('date_publish'),
                            "authors": [article.get('authors')] if article.get('authors') else [],
                            "description": article.get('description'),
                            "language": article.get('language'),
                            "source_domain": article.get('source_domain'),
                            "top_image": article.get('image_url') or article.get('top_image'),
                            "url": article.get('url', url)
                        }
                    else:
                        logger.error(f"[DEBUG] Unexpected article type: {type(article)}")
                        raise Exception(f"Unexpected article type: {type(article)}")
                    
                    logger.info(f"Successfully scraped article with news-please: content_length={len(result['content'])}, title='{result.get('title', 'N/A')[:50]}...', attempt={attempt + 1}")
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
                    if hasattr(e, 'response') and e.response and e.response.status_code >= 400 and e.response.status_code < 500:
                        raise Exception(last_error)
                    
                    if selected_proxy:
                        proxy_retry_manager.mark_proxy_failed_for_request(request_id, selected_proxy)
                    
                    if attempt == max_retries:
                        break
                    
                    time.sleep(1.0 * (attempt + 1))
                    
                except Exception as e:
                    last_error = f"news-please scraping failed: {str(e)}"
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
        result = await loop.run_in_executor(thread_pool, run_newsplease_scraper)
        
        # Record successful metrics
        duration = time.time() - start_time
        proxy_info = f"{selected_proxy.address}:{selected_proxy.port}" if selected_proxy else None
        
        record_request_metric(
            url=url,
            method="newsplease",
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
            method="newsplease",
            success=False,
            duration=duration,
            proxy_used=proxy_info,
            error_type=error_type,
            content_length=content_length,
            attempt_count=attempt_count,
            request_id=request_id
        )
        
        logger.error(f"news-please scraping failed for {url}: {str(e)}")
        
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

# Database Table Management Endpoints
@app.get("/api/database/table-status")
async def get_table_status():
    """Check if the proxies table exists and validate its schema"""
    try:
        if not config_instance.get_database_config():
            return {
                "table_exists": False,
                "schema_valid": False,
                "message": "Database not configured",
                "missing_columns": [],
                "deployment_mode": os.getenv("DEPLOYMENT_MODE", "standalone")
            }
        
        # Test database connection first
        db_test_result, db_test_message = db_manager.test_connection()
        if not db_test_result:
            return {
                "table_exists": False,
                "schema_valid": False,
                "message": f"Database connection failed: {db_test_message}",
                "missing_columns": []
            }
        
        # Check if table exists and validate schema
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if proxies table exists
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_name = 'proxies' AND table_schema = 'public'
            """)
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                cursor.close()
                return {
                    "table_exists": False,
                    "schema_valid": False,
                    "message": "Proxies table does not exist",
                    "missing_columns": []
                }
            
            # Validate required columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'proxies' AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            existing_columns = {row['column_name']: row for row in cursor.fetchall()}
            
            # Required columns for basic functionality
            required_columns = {
                'id': 'integer',
                'address': 'character varying',
                'port': 'integer',
                'type': 'character varying',
                'username': 'character varying',
                'password': 'character varying',
                'status': 'character varying',
                'error_count': 'integer'
            }
            
            # Optional but recommended columns
            recommended_columns = {
                'success_count': 'integer',
                'last_used': 'timestamp without time zone',
                'last_tested': 'timestamp without time zone',
                'response_time_ms': 'integer',
                'country': 'character varying',
                'provider': 'character varying',
                'created_at': 'timestamp without time zone',
                'updated_at': 'timestamp without time zone'
            }
            
            missing_required = []
            missing_recommended = []
            
            for col_name, expected_type in required_columns.items():
                if col_name not in existing_columns:
                    missing_required.append(col_name)
            
            for col_name, expected_type in recommended_columns.items():
                if col_name not in existing_columns:
                    missing_recommended.append(col_name)
            
            # Count existing proxies
            cursor.execute("SELECT COUNT(*) as count FROM proxies")
            proxy_count = cursor.fetchone()['count']
            
            cursor.close()
            
            schema_valid = len(missing_required) == 0
            
            return {
                "table_exists": True,
                "schema_valid": schema_valid,
                "message": f"Table found with {proxy_count} proxies" if schema_valid else "Table exists but schema incomplete",
                "missing_required": missing_required,
                "missing_recommended": missing_recommended,
                "proxy_count": proxy_count,
                "existing_columns": list(existing_columns.keys()),
                "deployment_mode": os.getenv("DEPLOYMENT_MODE", "standalone")
            }
            
    except Exception as e:
        logger.error(f"Table status check failed: {str(e)}")
        return {
            "table_exists": False,
            "schema_valid": False,
            "message": f"Error checking table status: {str(e)}",
            "missing_columns": []
        }

@app.post("/api/database/create-table")
async def create_proxies_table():
    """Create the proxies table with complete schema"""
    try:
        if not config_instance.get_database_config():
            raise HTTPException(status_code=400, detail="Database not configured")
        
        # Test database connection first
        db_test_result, db_test_message = db_manager.test_connection()
        if not db_test_result:
            raise HTTPException(status_code=400, detail=f"Database connection failed: {db_test_message}")
        
        # Read and execute the init script
        init_script_path = Path(__file__).parent / "scripts" / "init-db.sql"
        if not init_script_path.exists():
            raise HTTPException(status_code=500, detail="Database initialization script not found")
        
        with open(init_script_path, 'r', encoding='utf-8') as f:
            init_script = f.read()
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Execute the initialization script
            cursor.execute(init_script)
            conn.commit()
            cursor.close()
        
        # Verify table creation
        table_status = await get_table_status()
        
        return {
            "success": True,
            "message": "Proxies table created successfully",
            "table_status": table_status
        }
        
    except Exception as e:
        logger.error(f"Table creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create table: {str(e)}")

# Proxy Management Endpoints
@app.get("/api/proxies")
async def get_all_proxies(
    page: int = 1,
    limit: int = 50,
    status: str = None,
    country: str = None,
    provider: str = None,
    search: str = None
):
    """Get paginated list of all proxies with filtering and search"""
    try:
        if not config_instance.get_database_config():
            raise HTTPException(status_code=400, detail="Database not configured")
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build WHERE clause based on filters
            where_conditions = []
            params = []
            
            if status:
                where_conditions.append("status = %s")
                params.append(status)
            
            if country:
                where_conditions.append("country = %s")
                params.append(country)
            
            if provider:
                where_conditions.append("provider ILIKE %s")
                params.append(f"%{provider}%")
            
            if search:
                where_conditions.append("(address ILIKE %s OR notes ILIKE %s OR provider ILIKE %s)")
                params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
            
            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Get total count for pagination
            count_query = f"SELECT COUNT(*) as total FROM proxy_stats{where_clause}"
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()['total']
            
            # Get paginated results using the proxy_stats view
            offset = (page - 1) * limit
            query = f"""
                SELECT * FROM proxy_stats 
                {where_clause}
                ORDER BY 
                    CASE 
                        WHEN health_status = 'good' THEN 1
                        WHEN health_status = 'warning' THEN 2
                        ELSE 3
                    END,
                    success_rate_percent DESC NULLS LAST,
                    last_used DESC NULLS LAST
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            proxies = cursor.fetchall()
            
            # Convert to list of dicts and format for frontend
            proxy_list = []
            for proxy in proxies:
                proxy_dict = dict(proxy)
                # Format timestamps for display
                for timestamp_field in ['last_used', 'last_tested', 'created_at', 'updated_at']:
                    if proxy_dict.get(timestamp_field):
                        proxy_dict[timestamp_field] = proxy_dict[timestamp_field].isoformat()
                
                # Parse tags if they exist
                if proxy_dict.get('tags'):
                    try:
                        proxy_dict['tags_parsed'] = json.loads(proxy_dict['tags'])
                    except:
                        proxy_dict['tags_parsed'] = []
                
                proxy_list.append(proxy_dict)
            
            cursor.close()
            
            return {
                "proxies": proxy_list,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "pages": (total_count + limit - 1) // limit
                },
                "filters": {
                    "status": status,
                    "country": country,
                    "provider": provider,
                    "search": search
                }
            }
            
    except Exception as e:
        logger.error(f"Failed to get proxies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/proxies/summary")
async def get_proxy_summary():
    """Get summary statistics for proxy dashboard"""
    try:
        if not config_instance.get_database_config():
            raise HTTPException(status_code=400, detail="Database not configured")
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get comprehensive summary statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_proxies,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_proxies,
                    COUNT(CASE WHEN status = 'inactive' THEN 1 END) as inactive_proxies,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_proxies,
                    COUNT(CASE WHEN status = 'testing' THEN 1 END) as testing_proxies,
                    
                    -- Health status distribution
                    COUNT(CASE WHEN status = 'active' AND error_count < 3 THEN 1 END) as healthy_proxies,
                    COUNT(CASE WHEN status = 'active' AND error_count >= 3 AND error_count < 5 THEN 1 END) as warning_proxies,
                    COUNT(CASE WHEN error_count >= 5 OR status = 'failed' THEN 1 END) as error_proxies,
                    
                    -- Performance statistics
                    AVG(CASE WHEN response_time_ms IS NOT NULL THEN response_time_ms END) as avg_response_time,
                    MIN(CASE WHEN response_time_ms IS NOT NULL THEN response_time_ms END) as min_response_time,
                    MAX(CASE WHEN response_time_ms IS NOT NULL THEN response_time_ms END) as max_response_time,
                    
                    -- Usage statistics
                    COUNT(CASE WHEN last_used >= NOW() - INTERVAL '1 hour' THEN 1 END) as used_last_hour,
                    COUNT(CASE WHEN last_used >= NOW() - INTERVAL '24 hours' THEN 1 END) as used_last_24h,
                    COUNT(CASE WHEN last_used >= NOW() - INTERVAL '7 days' THEN 1 END) as used_last_week
                    
                FROM proxies
            """)
            
            summary = dict(cursor.fetchone())
            
            # Get country distribution
            cursor.execute("""
                SELECT country, COUNT(*) as count 
                FROM proxies 
                WHERE country IS NOT NULL AND country != 'XX'
                GROUP BY country 
                ORDER BY count DESC 
                LIMIT 10
            """)
            country_distribution = [dict(row) for row in cursor.fetchall()]
            
            # Get provider distribution
            cursor.execute("""
                SELECT provider, COUNT(*) as count 
                FROM proxies 
                WHERE provider IS NOT NULL 
                GROUP BY provider 
                ORDER BY count DESC 
                LIMIT 10
            """)
            provider_distribution = [dict(row) for row in cursor.fetchall()]
            
            # Get proxy type distribution
            cursor.execute("""
                SELECT type, COUNT(*) as count 
                FROM proxies 
                GROUP BY type 
                ORDER BY count DESC
            """)
            type_distribution = [dict(row) for row in cursor.fetchall()]
            
            cursor.close()
            
            return {
                "summary": summary,
                "distributions": {
                    "countries": country_distribution,
                    "providers": provider_distribution,
                    "types": type_distribution
                },
                "timestamp": time.time()
            }
            
    except Exception as e:
        logger.error(f"Failed to get proxy summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket Log Management
class LogManager:
    def __init__(self):
        self.connections: List[WebSocket] = []
        self.log_buffer: List[Dict] = []
        self.max_buffer_size = 1000
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        
        # Send recent logs to new connection
        for log_entry in self.log_buffer[-50:]:  # Last 50 logs
            await websocket.send_json(log_entry)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
    
    async def broadcast_log(self, log_entry: Dict):
        """Broadcast log entry to all connected clients"""
        # Add to buffer
        self.log_buffer.append(log_entry)
        if len(self.log_buffer) > self.max_buffer_size:
            self.log_buffer = self.log_buffer[-self.max_buffer_size:]
        
        # Broadcast to all connections
        disconnected = []
        for connection in self.connections:
            try:
                await connection.send_json(log_entry)
            except:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

# Initialize log manager
log_manager = LogManager()

# Custom log handler for WebSocket streaming
class WebSocketLogHandler(logging.Handler):
    def __init__(self, log_manager):
        super().__init__()
        self.log_manager = log_manager
    
    def emit(self, record):
        try:
            log_entry = {
                "timestamp": record.created,
                "level": record.levelname,
                "module": record.name,
                "message": record.getMessage(),
                "timestamp_iso": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(record.created))
            }
            
            # Add extra fields if available
            if hasattr(record, 'request_id'):
                log_entry['request_id'] = record.request_id
            
            # Send to WebSocket clients (non-blocking)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in an async context, schedule the task
            asyncio.create_task(self.log_manager.broadcast_log(log_entry))
                else:
                    # If not in async context, run it directly
                    loop.run_until_complete(self.log_manager.broadcast_log(log_entry))
            except Exception:
                # Fallback: add to log manager buffer directly
                self.log_manager.log_buffer.append(log_entry)
                if len(self.log_manager.log_buffer) > self.log_manager.max_buffer_size:
                    self.log_manager.log_buffer = self.log_manager.log_buffer[-self.log_manager.max_buffer_size:]
                
        except Exception as e:
            # Don't let logging errors break the application, but try to capture them
            print(f"WebSocket log handler error: {e}")
            pass

# Add WebSocket handler to root logger
websocket_handler = WebSocketLogHandler(log_manager)
websocket_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(websocket_handler)

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket endpoint for live log streaming"""
    await log_manager.connect(websocket)
    logger.info(f"New WebSocket client connected for logs. Total connections: {len(log_manager.connections)}")
    
    try:
        while True:
            # Keep connection alive and listen for client messages
            message = await websocket.receive_text()
            
            # Handle client commands (like filtering)
            try:
                command = json.loads(message)
                if command.get("type") == "filter":
                    # TODO: Implement log filtering
                    pass
                elif command.get("type") == "test":
                    # Generate test logs
                    logger.info("Test log message from WebSocket client")
                    logger.warning("Test warning message")
                    logger.error("Test error message")
            except json.JSONDecodeError:
                # If not JSON, treat as a test message request
                if message == "test":
                    logger.info("Test log message requested via WebSocket")
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from logs. Remaining connections: {len(log_manager.connections) - 1}")
        log_manager.disconnect(websocket)

# Test endpoint to generate logs
@app.get("/api/logs/test")
async def test_logs():
    """Generate test log messages for debugging"""
    logger.info("Test INFO log message generated")
    logger.warning("Test WARNING log message generated") 
    logger.error("Test ERROR log message generated")
    logger.debug("Test DEBUG log message generated")
    
    return {
        "message": "Test logs generated",
        "active_connections": len(log_manager.connections),
        "buffer_size": len(log_manager.log_buffer)
    }

@app.get("/api/deployment/info")
async def get_deployment_info():
    """Get deployment mode and configuration information"""
    return {
        "deployment_mode": os.getenv("DEPLOYMENT_MODE", "standalone"),
        "auto_db_setup": os.getenv("AUTO_DB_SETUP", "false").lower() == "true",
        "db_init_sample_data": os.getenv("DB_INIT_SAMPLE_DATA", "false").lower() == "true",
        "metrics_enabled": config_store.get("metrics_enabled", True),
        "proxy_enabled": config_store.get("proxy_enabled", False),
        "platform": platform.system(),
        "container_id": os.getenv("HOSTNAME", "unknown"),
        "version": "1.0.0"
    }

@app.get("/api/config/auto-detect")
async def auto_detect_configuration():
    """Auto-detect configuration for compose setup"""
    try:
        config = {
            "database_auto_configured": False,
            "table_exists": False,
            "deployment_mode": os.getenv("DEPLOYMENT_MODE", "standalone"),
            "auto_db_setup": os.getenv("AUTO_DB_SETUP", "false").lower() == "true"
        }
        
        # Check if database is auto-configured from environment
        if all(os.getenv(var) for var in ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]):
            config["database_auto_configured"] = True
            config["db_host"] = os.getenv("DB_HOST")
            config["db_name"] = os.getenv("DB_NAME")
            config["db_user"] = os.getenv("DB_USER")
            config["db_port"] = int(os.getenv("DB_PORT", "5432"))
            
            # Test connection and check table existence
            try:
                # Temporarily configure database for testing
                config_instance.update_database_config(
                    host=os.getenv("DB_HOST"),
                    database=os.getenv("DB_NAME"),
                    table=os.getenv("DB_TABLE", "proxies"),
                    username=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    port=int(os.getenv("DB_PORT", "5432"))
                )
                
                # Test connection
                db_test_result, db_test_message = db_manager.test_connection()
                if db_test_result:
                    config["database_connected"] = True
                    config["connection_message"] = db_test_message
                    
                    # Check if proxies table exists
                    table_status = await get_table_status()
                    config["table_exists"] = table_status.get("table_exists", False)
                    config["table_status"] = table_status
                else:
                    config["database_connected"] = False
                    config["connection_message"] = db_test_message
                    
            except Exception as e:
                config["database_connected"] = False
                config["connection_message"] = f"Connection test failed: {str(e)}"
        
        return config
        
    except Exception as e:
        logger.error(f"Auto-detect configuration failed: {str(e)}")
        return {
            "database_auto_configured": False,
            "table_exists": False,
            "deployment_mode": "standalone",
            "error": str(e)
        }

@app.get("/api/config/initialize-setup")
async def initialize_full_setup():
    """Initialize the full setup with database and proxy table"""
    try:
        if not all(os.getenv(var) for var in ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]):
            raise HTTPException(status_code=400, detail="Database environment variables not configured")
        
        # Configure database
        config_instance.update_database_config(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            table=os.getenv("DB_TABLE", "proxies"),
            username=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=int(os.getenv("DB_PORT", "5432"))
        )
        
        # Test connection
        db_test_result, db_test_message = db_manager.test_connection()
        if not db_test_result:
            raise HTTPException(status_code=500, detail=f"Database connection failed: {db_test_message}")
        
        # Create proxies table if it doesn't exist
        table_result = await create_proxies_table()
        
        # Enable proxy usage if table was created successfully
        if table_result.get("success"):
            config_store["proxy_enabled"] = True
        
        return {
            "success": True,
            "message": "Full setup initialized successfully",
            "database_configured": True,
            "table_status": table_result,
            "proxy_enabled": config_store["proxy_enabled"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Initialize full setup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/database/initialize")
async def initialize_database():
    """Initialize database table with complete structure"""
    try:
        # Check if we have database configuration
        db_config = config_instance.get_database_config()
        
        # For auto-configured setups, use environment variables
        if not db_config and os.getenv("DB_HOST"):
            logger.info("Using environment variables for database initialization")
            config_instance.update_database_config(
                host=os.getenv("DB_HOST"),
                database=os.getenv("DB_NAME"),
                table=os.getenv("DB_TABLE", "proxies"),
                username=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                port=int(os.getenv("DB_PORT", "5432"))
            )
            db_config = config_instance.get_database_config()
        
        if not db_config:
            return {"success": False, "error": "Database not configured. Please configure database connection first."}
        
        # Test connection first
        db_test_result, db_test_message = db_manager.test_connection()
        if not db_test_result:
            return {"success": False, "error": f"Database connection failed: {db_test_message}"}
        
        # Use the existing database manager to create the table
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create the complete table structure with all columns
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS proxies (
                id SERIAL PRIMARY KEY,
                
                -- Basic proxy information
                address VARCHAR(255) NOT NULL,
                port INTEGER NOT NULL CHECK (port > 0 AND port <= 65535),
                type VARCHAR(10) DEFAULT 'http' CHECK (type IN ('http', 'https', 'socks4', 'socks5')),
                
                -- Authentication
                username VARCHAR(255),
                password VARCHAR(255),
                
                -- Status and performance tracking
                status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'testing', 'failed')),
                error_count INTEGER DEFAULT 0 CHECK (error_count >= 0),
                success_count INTEGER DEFAULT 0 CHECK (success_count >= 0),
                
                -- Usage tracking
                last_used TIMESTAMP DEFAULT NULL,
                last_tested TIMESTAMP DEFAULT NULL,
                response_time_ms INTEGER DEFAULT NULL,
                
                -- Geographic and provider information
                country VARCHAR(2),  -- ISO country code
                region VARCHAR(100),
                provider VARCHAR(100),
                
                -- Metadata
                notes TEXT,
                tags VARCHAR(500),  -- JSON array as string
                
                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- Ensure uniqueness
                UNIQUE(address, port, username)
            )
            """
            
            # Execute table creation
            cursor.execute(create_table_sql)
            
            # Add missing columns to existing table if needed
            alter_statements = [
                "ALTER TABLE proxies ADD COLUMN IF NOT EXISTS success_count INTEGER DEFAULT 0",
                "ALTER TABLE proxies ADD COLUMN IF NOT EXISTS last_used TIMESTAMP DEFAULT NULL",
                "ALTER TABLE proxies ADD COLUMN IF NOT EXISTS last_tested TIMESTAMP DEFAULT NULL", 
                "ALTER TABLE proxies ADD COLUMN IF NOT EXISTS response_time_ms INTEGER DEFAULT NULL",
                "ALTER TABLE proxies ADD COLUMN IF NOT EXISTS country VARCHAR(2)",
                "ALTER TABLE proxies ADD COLUMN IF NOT EXISTS region VARCHAR(100)",
                "ALTER TABLE proxies ADD COLUMN IF NOT EXISTS provider VARCHAR(100)",
                "ALTER TABLE proxies ADD COLUMN IF NOT EXISTS notes TEXT",
                "ALTER TABLE proxies ADD COLUMN IF NOT EXISTS tags VARCHAR(500)"
            ]
            
            for statement in alter_statements:
                try:
                    cursor.execute(statement)
                except Exception as e:
                    # Column might already exist, that's okay
                    logger.debug(f"Alter statement skipped (column might exist): {statement} - {str(e)}")
            
            # Create indexes for better performance
            index_statements = [
                "CREATE INDEX IF NOT EXISTS idx_proxies_status_errors ON proxies(status, error_count)",
                "CREATE INDEX IF NOT EXISTS idx_proxies_last_used ON proxies(last_used)",
                "CREATE INDEX IF NOT EXISTS idx_proxies_last_tested ON proxies(last_tested)",
                "CREATE INDEX IF NOT EXISTS idx_proxies_type ON proxies(type)",
                "CREATE INDEX IF NOT EXISTS idx_proxies_country ON proxies(country)",
                "CREATE INDEX IF NOT EXISTS idx_proxies_provider ON proxies(provider)",
                "CREATE INDEX IF NOT EXISTS idx_proxies_response_time ON proxies(response_time_ms)"
            ]
            
            for statement in index_statements:
                try:
                    cursor.execute(statement)
                except Exception as e:
                    logger.debug(f"Index creation skipped: {statement} - {str(e)}")
            
            conn.commit()
            
            # Get updated table info
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'proxies' 
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            
            # Get row count
            cursor.execute("SELECT COUNT(*) as count FROM proxies;")
            row_count = cursor.fetchone()['count']
            
            cursor.close()
            
        return {
            "success": True,
            "message": f"Database initialized successfully! Table created/updated with {len(columns)} columns and {row_count} rows.",
            "table_info": {
                "columns": [dict(col) for col in columns],
                "row_count": row_count
            }
        }
            
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Database initialization failed: {str(e)}"}

@app.post("/api/database/test")
async def test_database_connection(request: DatabaseConfigRequest):
    """Test database connection"""
    try:
        import psycopg2
        
        # Test connection
        conn = psycopg2.connect(
            host=request.host,
            port=request.port,
            database=request.database,
            user=request.username,
            password=request.password
        )
        
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    
            return {"success": True, "message": "Database connection successful"}
            
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return {"error": f"Database connection failed: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 