import os
import json
from cryptography.fernet import Fernet
from typing import Dict, Optional, Any
from dotenv import load_dotenv

class Config:
    """Enhanced configuration management with stability settings"""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Stability and Performance Settings
        self.PROXY_RETRY_COUNT = int(os.getenv("PROXY_RETRY_COUNT", "3"))
        self.REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))  # Reduced from 30
        self.CONNECTION_TIMEOUT = int(os.getenv("CONNECTION_TIMEOUT", "5"))  # DB connection timeout
        self.MAX_THREAD_POOL_SIZE = int(os.getenv("MAX_THREAD_POOL_SIZE", "10"))
        
        # Circuit Breaker Settings
        self.CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
        self.CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60"))
        
        # Database Connection Pool Settings
        self.DB_POOL_MIN_CONNECTIONS = int(os.getenv("DB_POOL_MIN_CONNECTIONS", "2"))
        self.DB_POOL_MAX_CONNECTIONS = int(os.getenv("DB_POOL_MAX_CONNECTIONS", "10"))
        
        # Proxy Management Settings
        self.PROXY_ERROR_THRESHOLD = int(os.getenv("PROXY_ERROR_THRESHOLD", "3"))  # Reduced from 5
        self.PROXY_RECOVERY_PROBABILITY = float(os.getenv("PROXY_RECOVERY_PROBABILITY", "0.1"))  # 10% chance on health check
        self.PROXY_FETCH_COUNT = int(os.getenv("PROXY_FETCH_COUNT", "10"))  # Number of proxies to fetch for retries
        
        # Enhanced Proxy Pool Settings
        self.PROXY_POOL_SIZE = int(os.getenv("PROXY_POOL_SIZE", "50"))  # Number of proxies to keep in pool
        self.MIN_PROXY_POOL_SIZE = int(os.getenv("MIN_PROXY_POOL_SIZE", "10"))  # Minimum pool size before refresh
        self.PROXY_REFRESH_INTERVAL = int(os.getenv("PROXY_REFRESH_INTERVAL", "300"))  # Refresh pool every 5 minutes
        self.BATCH_UPDATE_INTERVAL = int(os.getenv("BATCH_UPDATE_INTERVAL", "60"))  # Process batch updates every minute
        
        # Request Settings
        self.USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "10485760"))  # 10MB limit
        self.ENABLE_REQUEST_RETRIES = os.getenv("ENABLE_REQUEST_RETRIES", "true").lower() == "true"
        
        # Monitoring and Health Check Settings
        self.HEALTH_CHECK_PROXY_RESET = os.getenv("HEALTH_CHECK_PROXY_RESET", "true").lower() == "true"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        self.ENABLE_DEBUG_LOGS = os.getenv("ENABLE_DEBUG_LOGS", "false").lower() == "true"
        
        # Rate Limiting (optional)
        self.RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
        self.RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
        self.RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds
        
        self.config_file = "config.json"
        self.key_file = "secret.key"
        self._ensure_encryption_key()
        self._load_config()
    
    def _ensure_encryption_key(self):
        """Ensure encryption key exists"""
        if not os.path.exists(self.key_file):
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
        
        with open(self.key_file, 'rb') as f:
            self.key = f.read()
        
        self.cipher = Fernet(self.key)
    
    def _load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            # Start with completely empty config - no defaults
            self.config = {
                "scrapegraph": {},
                "database": {}
            }
    
    def _save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def _encrypt_value(self, value: str) -> str:
        """Encrypt a sensitive value"""
        return self.cipher.encrypt(value.encode()).decode()
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a sensitive value"""
        return self.cipher.decrypt(encrypted_value.encode()).decode()
    
    def update_scrapegraph_config(self, 
                                 provider: str,
                                 model: str, 
                                 api_key: Optional[str] = None,
                                 base_url: Optional[str] = None, 
                                 temperature: float = 0.0,
                                 max_tokens: Optional[int] = None,
                                 additional_params: Optional[Dict[str, Any]] = None):
        """Update ScrapeGraph AI configuration with flexible provider support"""
        config = {
            "provider": provider,
            "model": model,
            "temperature": temperature
        }
        
        # Encrypt API key if provided
        if api_key:
            config["api_key"] = self._encrypt_value(api_key)
        
        # Add optional parameters
        if base_url:
            config["base_url"] = base_url
        if max_tokens:
            config["max_tokens"] = max_tokens
        if additional_params:
            config["additional_params"] = additional_params
        
        self.config["scrapegraph"] = config
        self._save_config()
    
    def get_scrapegraph_config(self) -> Dict:
        """Get ScrapeGraph AI configuration for use"""
        if not self.config.get("scrapegraph"):
            return {}
        
        config = self.config["scrapegraph"].copy()
        provider = config.get("provider", "openai")
        
        # Build the configuration based on provider
        if provider == "openai":
            return self._build_openai_config(config)
        elif provider == "anthropic":
            return self._build_anthropic_config(config)
        elif provider == "ollama":
            return self._build_ollama_config(config)
        elif provider == "azure":
            return self._build_azure_config(config)
        elif provider == "custom":
            return self._build_custom_config(config)
        else:
            # Fallback to generic configuration
            return self._build_generic_config(config)
    
    def _build_openai_config(self, config: Dict) -> Dict:
        """Build OpenAI-specific configuration"""
        graph_config = {
            "llm": {
                "model": f"openai/{config.get('model', 'gpt-3.5-turbo')}",
                "temperature": config.get("temperature", 0.0)
            },
            "verbose": False,
            "headless": True
        }
        
        # Decrypt API key if present
        if config.get("api_key"):
            graph_config["llm"]["api_key"] = self._decrypt_value(config["api_key"])
        
        # Add optional parameters
        if config.get("max_tokens"):
            graph_config["llm"]["max_tokens"] = config["max_tokens"]
        
        return graph_config
    
    def _build_anthropic_config(self, config: Dict) -> Dict:
        """Build Anthropic Claude-specific configuration"""
        from langchain_anthropic import ChatAnthropic
        
        # Create model instance for Anthropic
        llm_params = {
            "model": config.get("model", "claude-3-opus-20240229"),
            "temperature": config.get("temperature", 0.0)
        }
        
        if config.get("api_key"):
            llm_params["api_key"] = self._decrypt_value(config["api_key"])
        
        if config.get("max_tokens"):
            llm_params["max_tokens"] = config["max_tokens"]
        
        llm = ChatAnthropic(**llm_params)
        
        return {
            "llm": {
                "model_instance": llm
            },
            "verbose": True,
            "headless": True
        }
    
    def _build_ollama_config(self, config: Dict) -> Dict:
        """Build Ollama local model configuration"""
        graph_config = {
            "llm": {
                "model": config.get("model", "ollama/mistral"),
                "temperature": config.get("temperature", 0.0),
                "format": "json",  # Ollama requires explicit format
                "base_url": config.get("base_url", "http://localhost:11434")
            },
            "embeddings": {
                "model": "ollama/nomic-embed-text",
                "temperature": 0,
                "base_url": config.get("base_url", "http://localhost:11434")
            },
            "verbose": True,
            "headless": True
        }
        
        if config.get("max_tokens"):
            graph_config["llm"]["model_tokens"] = config["max_tokens"]
        
        return graph_config
    
    def _build_azure_config(self, config: Dict) -> Dict:
        """Build Azure OpenAI configuration"""
        from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
        
        additional_params = config.get("additional_params", {})
        
        llm_model_instance = AzureChatOpenAI(
            openai_api_version=additional_params.get("api_version", "2023-05-15"),
            azure_deployment=additional_params.get("deployment_name", ""),
            temperature=config.get("temperature", 0.0)
        )
        
        embedder_model_instance = AzureOpenAIEmbeddings(
            azure_deployment=additional_params.get("embeddings_deployment", ""),
            openai_api_version=additional_params.get("api_version", "2023-05-15")
        )
        
        return {
            "llm": {
                "model_instance": llm_model_instance,
                "model_tokens": config.get("max_tokens", 100000)
            },
            "embeddings": {
                "model_instance": embedder_model_instance
            },
            "verbose": True,
            "headless": True
        }
    
    def _build_custom_config(self, config: Dict) -> Dict:
        """Build custom provider configuration"""
        graph_config = {
            "llm": {
                "model": config.get("model"),
                "temperature": config.get("temperature", 0.0)
            },
            "verbose": True,
            "headless": True
        }
        
        # Decrypt API key if present
        if config.get("api_key"):
            graph_config["llm"]["api_key"] = self._decrypt_value(config["api_key"])
        
        # Add base URL for custom endpoints
        if config.get("base_url"):
            graph_config["llm"]["base_url"] = config["base_url"]
        
        # Add optional parameters
        if config.get("max_tokens"):
            graph_config["llm"]["max_tokens"] = config["max_tokens"]
        
        # Add any additional parameters
        if config.get("additional_params"):
            graph_config["llm"].update(config["additional_params"])
        
        return graph_config
    
    def _build_generic_config(self, config: Dict) -> Dict:
        """Build generic configuration for unknown providers"""
        return self._build_custom_config(config)
    
    def get_scrapegraph_config_safe(self) -> Dict:
        """Get ScrapeGraph AI configuration without sensitive data"""
        if not self.config.get("scrapegraph"):
            return {}
        
        config = self.config["scrapegraph"].copy()
        
        return {
            "provider": config.get("provider", ""),
            "model": config.get("model", ""),
            "base_url": config.get("base_url", ""),
            "temperature": config.get("temperature", 0.0),
            "max_tokens": config.get("max_tokens"),
            "has_api_key": bool(config.get("api_key")),
            "additional_params": config.get("additional_params", {})
        }
    
    def delete_scrapegraph_config(self):
        """Delete ScrapeGraph AI configuration"""
        self.config["scrapegraph"] = {}
        self._save_config()
    
    def update_database_config(self, host: str, database: str, table: str, username: str, password: str, port: int = 5432):
        """Update database configuration"""
        self.config["database"] = {
            "host": host,
            "port": port,
            "database": database,
            "table": table,
            "username": username,
            "password": self._encrypt_value(password)
        }
        self._save_config()
    
    def get_database_config(self) -> Dict:
        """Get database configuration"""
        if not self.config.get("database"):
            return {}
        
        config = self.config["database"].copy()
        
        # Decrypt password if present
        if config.get("password"):
            config["password"] = self._decrypt_value(config["password"])
        
        return config
    
    def is_scrapegraph_configured(self) -> bool:
        """Check if ScrapeGraph AI is configured"""
        scrapegraph_config = self.config.get("scrapegraph", {})
        provider = scrapegraph_config.get("provider")
        
        # For Ollama, we don't need an API key
        if provider == "ollama":
            return bool(scrapegraph_config.get("model"))
        
        # For other providers, we need an API key
        return bool(scrapegraph_config.get("api_key") and scrapegraph_config.get("model"))
    
    def is_database_configured(self) -> bool:
        """Check if database is configured"""
        db_config = self.config.get("database", {})
        required_fields = ["host", "database", "table", "username", "password"]
        return all(db_config.get(field) for field in required_fields)
    
    def get_request_headers(self):
        """Get enhanced request headers for better success rate"""
        return {
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
            'DNT': '1'
        }
    
    def get_retry_delays(self):
        """Get exponential backoff delays for retries"""
        return [0.5, 1.0, 2.0, 4.0, 8.0]  # seconds
    
    def is_retryable_error(self, error):
        """Determine if an error should trigger a retry"""
        retryable_errors = [
            'ProxyError',
            'ConnectTimeout',
            'ReadTimeout',
            'ConnectionError',
            'ChunkedEncodingError',
            'ContentDecodingError'
        ]
        
        error_str = str(error)
        return any(err in error_str for err in retryable_errors)
    
    def get_proxy_selection_strategy(self):
        """Get proxy selection strategy"""
        strategy = os.getenv("PROXY_SELECTION_STRATEGY", "round_robin")
        return strategy  # round_robin, random, least_errors
    
    def should_skip_proxy_on_error(self, status_code):
        """Determine if proxy should be skipped based on HTTP status code"""
        # Don't use proxies for client errors (4xx)
        skip_codes = [401, 403, 404, 429]
        return status_code in skip_codes
    
    def get_stability_config(self):
        """Get all stability-related configuration"""
        return {
            "proxy_retry_count": self.PROXY_RETRY_COUNT,
            "request_timeout": self.REQUEST_TIMEOUT,
            "connection_timeout": self.CONNECTION_TIMEOUT,
            "proxy_error_threshold": self.PROXY_ERROR_THRESHOLD,
            "circuit_breaker_failure_threshold": self.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            "circuit_breaker_recovery_timeout": self.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
            "enable_request_retries": self.ENABLE_REQUEST_RETRIES,
            "proxy_recovery_probability": self.PROXY_RECOVERY_PROBABILITY,
            "max_thread_pool_size": self.MAX_THREAD_POOL_SIZE,
            "db_pool_min_connections": self.DB_POOL_MIN_CONNECTIONS,
            "db_pool_max_connections": self.DB_POOL_MAX_CONNECTIONS,
            # Enhanced proxy pool settings
            "proxy_pool_size": self.PROXY_POOL_SIZE,
            "min_proxy_pool_size": self.MIN_PROXY_POOL_SIZE,
            "proxy_refresh_interval": self.PROXY_REFRESH_INTERVAL,
            "batch_update_interval": self.BATCH_UPDATE_INTERVAL
        } 