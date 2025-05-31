from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl
from typing import Dict, Any, Optional
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

# Configure logging
logging.basicConfig(level=logging.INFO)
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

# Add a simple in-memory configuration store
config_store = {
    "scrapegraph": None,
    "database": None
}

# Models
class ScrapeRequest(BaseModel):
    url: HttpUrl
    api_key: Optional[str] = None

class ScrapeResponse(BaseModel):
    url: str
    content: Dict[str, Any]
    status: str
    error: Optional[str] = None

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
    return {
        "status": "healthy",
        "platform": platform.system(),
        "python_version": platform.python_version()
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
    """Get configuration status"""
    return {
        "scrapegraph": {
            "configured": config_store["scrapegraph"] is not None,
            "provider": config_store["scrapegraph"].get("provider") if config_store["scrapegraph"] else None
        },
        "database": {
            "configured": config_store["database"] is not None
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
            "temperature": temperature
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
        
        return {"message": "ScrapeGraph AI configuration saved successfully"}
        
    except Exception as e:
        logger.error(f"Error saving ScrapeGraph AI configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/config/scrapegraph")
async def delete_scrapegraph_config():
    """Delete ScrapeGraph AI configuration"""
    config_store["scrapegraph"] = None
    return {"message": "ScrapeGraph AI configuration deleted"}

@app.post("/api/config/database")
async def save_database_config(
    host: str = Form(...),
    port: int = Form(5432),
    database: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    """Save database configuration"""
    config_store["database"] = {
        "host": host,
        "port": port,
        "database": database,
        "username": username,
        "password": password
    }
    return {"message": "Database configuration saved successfully"}

@app.delete("/api/config/database")
async def delete_database_config():
    """Delete database configuration"""
    config_store["database"] = None
    return {"message": "Database configuration deleted"}

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
        raise
    except Exception as e:
        logger.error(f"ScrapeGraph scraping failed: {str(e)}")
        error_msg = str(e)
        if "Model not supported" in error_msg:
            error_msg = f"Model not supported. Please check your API key is valid and the model '{stored_config.get('model', 'gpt-4o-mini')}' is available with your OpenAI account."
        
        return ScrapeResponse(
            url=str(request.url),
            content={},
            status="error",
            error=error_msg
        )

@app.post("/api/scrape/newspaper")
async def scrape_with_newspaper(request: ScrapeRequest):
    """Scrape using Newspaper4k"""
    try:
        url = str(request.url)
        logger.info(f"Received Newspaper scrape request for URL: {url}")
        
        # Define the scraping function to run in thread pool
        def run_newspaper_scraper():
            article = Article(url)
            article.download()
            article.parse()
            
            # Standardize output to match ScrapGraph AI format
            return {
                "content": article.text,
                "top_image": article.top_image,
                "published": article.publish_date.isoformat() if article.publish_date else None
            }
        
        # Run the scraper in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(thread_pool, run_newspaper_scraper)
        
        return ScrapeResponse(
            url=url,
            content=result,
            status="success"
        )
        
    except Exception as e:
        logger.error(f"Newspaper scraping failed: {str(e)}")
        return ScrapeResponse(
            url=str(request.url),
            content={},
            status="error",
            error=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 