import json
import os
import time
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages persistent configuration with hot-reload capabilities"""
    
    def __init__(self, config_file_path: str = "/shared-config/config.json"):
        self.config_file_path = config_file_path
        self.config: Dict[str, Any] = {}
        self.last_modified = 0
        self.watch_enabled = os.getenv("WATCH_CONFIG_CHANGES", "false").lower() == "true"
        self._lock = threading.Lock()
        
        # Load initial configuration
        self.load_config()
        
        # Start file watcher if enabled
        if self.watch_enabled:
            self.start_file_watcher()
    
    def load_config(self) -> bool:
        """Load configuration from file"""
        try:
            if not os.path.exists(self.config_file_path):
                logger.warning(f"Config file not found: {self.config_file_path}")
                self._load_default_config()
                return False
            
            with open(self.config_file_path, 'r') as f:
                new_config = json.load(f)
            
            with self._lock:
                self.config = new_config
                self.last_modified = os.path.getmtime(self.config_file_path)
            
            logger.info(f"Configuration loaded from {self.config_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self._load_default_config()
            return False
    
    def _load_default_config(self):
        """Load default configuration when file is not available"""
        self.config = {
            "llm_providers": {
                "openai": {
                    "api_key": os.getenv("OPENAI_API_KEY", ""),
                    "model": "gpt-4o-mini",
                    "base_url": "https://api.openai.com/v1"
                }
            },
            "proxy_settings": {
                "http_proxy": os.getenv("HTTP_PROXY", ""),
                "https_proxy": os.getenv("HTTPS_PROXY", ""),
                "no_proxy": "localhost,127.0.0.1"
            },
            "scraping_settings": {
                "timeout": 30,
                "max_retries": 3,
                "user_agent": "WebScraper-API/1.0"
            }
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        with self._lock:
            return self.config.copy()
    
    def get_llm_config(self, provider: str = "openai") -> Dict[str, Any]:
        """Get LLM provider configuration"""
        with self._lock:
            return self.config.get("llm_providers", {}).get(provider, {})
    
    def get_proxy_config(self) -> Dict[str, str]:
        """Get proxy configuration"""
        with self._lock:
            return self.config.get("proxy_settings", {})
    
    def get_scraping_config(self) -> Dict[str, Any]:
        """Get scraping configuration"""
        with self._lock:
            return self.config.get("scraping_settings", {})
    
    def update_config(self, new_config: Dict[str, Any], merge: bool = True) -> bool:
        """Update configuration and save to file"""
        try:
            if merge:
                # Merge with existing config
                with self._lock:
                    updated_config = self.config.copy()
                    self._deep_merge(updated_config, new_config)
            else:
                # Replace entire config
                updated_config = new_config.copy()
            
            # Add timestamp
            updated_config["last_updated"] = datetime.utcnow().isoformat() + "Z"
            
            # Save to file
            os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
            with open(self.config_file_path, 'w') as f:
                json.dump(updated_config, f, indent=2)
            
            # Update in-memory config
            with self._lock:
                self.config = updated_config
                self.last_modified = os.path.getmtime(self.config_file_path)
            
            logger.info("Configuration updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return False
    
    def _deep_merge(self, target: Dict, source: Dict):
        """Deep merge two dictionaries"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
    
    def start_file_watcher(self):
        """Start watching config file for changes"""
        def watch_file():
            while True:
                try:
                    if os.path.exists(self.config_file_path):
                        current_modified = os.path.getmtime(self.config_file_path)
                        if current_modified > self.last_modified:
                            logger.info("Config file changed, reloading...")
                            self.load_config()
                    
                    time.sleep(5)  # Check every 5 seconds
                    
                except Exception as e:
                    logger.error(f"Error in file watcher: {e}")
                    time.sleep(10)
        
        watcher_thread = threading.Thread(target=watch_file, daemon=True)
        watcher_thread.start()
        logger.info("Config file watcher started")
    
    def get_api_key(self, provider: str = "openai") -> str:
        """Get API key for specific provider"""
        llm_config = self.get_llm_config(provider)
        api_key = llm_config.get("api_key", "")
        
        # Fallback to environment variables
        if not api_key:
            env_key_map = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "azure": "AZURE_OPENAI_API_KEY"
            }
            env_key = env_key_map.get(provider)
            if env_key:
                api_key = os.getenv(env_key, "")
        
        return api_key
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate current configuration and return status"""
        status = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        config = self.get_config()
        
        # Check LLM providers
        llm_providers = config.get("llm_providers", {})
        if not llm_providers:
            status["errors"].append("No LLM providers configured")
            status["valid"] = False
        
        for provider, settings in llm_providers.items():
            if not settings.get("api_key") and provider != "ollama":
                status["warnings"].append(f"No API key for {provider}")
            
            if not settings.get("model"):
                status["errors"].append(f"No model specified for {provider}")
                status["valid"] = False
        
        return status

# Global config manager instance
config_manager = ConfigManager(os.getenv("CONFIG_FILE_PATH", "/shared-config/config.json")) 