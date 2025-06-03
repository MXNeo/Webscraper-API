import logging
import time
import threading
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from queue import Queue, Empty
import random

logger = logging.getLogger(__name__)

@dataclass
class ProxyInfo:
    id: int
    address: str
    port: int
    username: Optional[str]
    password: Optional[str]
    type: str
    error_count: int
    last_used: Optional[float] = None
    proxy_url: str = ""
    
    def __post_init__(self):
        # Build proxy URL
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        self.proxy_url = f"{self.type}://{auth}{self.address}:{self.port}"

class ProxyPool:
    """Enhanced proxy pool manager with batching and caching"""
    
    def __init__(self, db_manager, config_store=None):
        self.db_manager = db_manager
        self.config_store = config_store or {}
        
        # Pool configuration
        self.pool_size = int(self.config_store.get("proxy_pool_size", 50))
        self.min_pool_size = int(self.config_store.get("min_proxy_pool_size", 10))
        self.refresh_interval = int(self.config_store.get("proxy_refresh_interval", 300))  # 5 minutes
        self.batch_update_interval = int(self.config_store.get("batch_update_interval", 60))  # 1 minute
        
        # Pool state
        self.available_proxies: Queue = Queue()
        self.failed_proxies: Set[int] = set()
        self.proxy_stats: Dict[int, Dict] = {}  # Track usage stats
        self.last_refresh = 0
        self.last_batch_update = 0
        
        # Thread safety
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._background_thread = None
        
        # Pending updates for batch processing
        self.pending_error_updates: Dict[int, int] = {}  # proxy_id -> error_increment
        self.pending_success_updates: Set[int] = set()    # proxy_ids that succeeded
        
        # Initialize pool
        self._refresh_pool()
        self._start_background_worker()
    
    def _start_background_worker(self):
        """Start background thread for periodic maintenance"""
        if self._background_thread and self._background_thread.is_alive():
            return
        
        self._background_thread = threading.Thread(target=self._background_worker, daemon=True)
        self._background_thread.start()
        logger.info("Proxy pool background worker started")
    
    def _background_worker(self):
        """Background worker for periodic pool maintenance"""
        while not self._stop_event.is_set():
            try:
                current_time = time.time()
                
                # Check if pool needs refreshing
                if current_time - self.last_refresh > self.refresh_interval:
                    logger.info("Periodic proxy pool refresh triggered")
                    self._refresh_pool()
                
                # Check if we need to process batch updates
                if current_time - self.last_batch_update > self.batch_update_interval:
                    logger.info("Processing batch proxy updates")
                    self._process_batch_updates()
                
                # Check pool health
                self._check_pool_health()
                
                # Sleep for 30 seconds before next check
                self._stop_event.wait(30)
                
            except Exception as e:
                logger.error(f"Error in proxy pool background worker: {str(e)}")
                self._stop_event.wait(60)  # Wait longer on error
    
    def _refresh_pool(self, force=False):
        """Refresh the proxy pool with fresh proxies from database"""
        with self._lock:
            try:
                current_time = time.time()
                
                # Don't refresh too frequently unless forced
                if not force and current_time - self.last_refresh < 60:
                    return
                
                logger.info(f"Refreshing proxy pool (target size: {self.pool_size})")
                
                # Get fresh proxies from database
                fresh_proxies = self.db_manager.get_proxies(count=self.pool_size)
                
                if not fresh_proxies:
                    logger.warning("No proxies retrieved from database")
                    return
                
                # Clear existing pool
                while not self.available_proxies.empty():
                    try:
                        self.available_proxies.get_nowait()
                    except Empty:
                        break
                
                # Add fresh proxies to pool
                added_count = 0
                for proxy_data in fresh_proxies:
                    if proxy_data['id'] not in self.failed_proxies:
                        proxy_info = ProxyInfo(
                            id=proxy_data['id'],
                            address=proxy_data['address'],
                            port=proxy_data['port'],
                            username=proxy_data.get('username'),
                            password=proxy_data.get('password'),
                            type=proxy_data['type'],
                            error_count=proxy_data['error_count']
                        )
                        self.available_proxies.put(proxy_info)
                        added_count += 1
                
                self.last_refresh = current_time
                logger.info(f"Proxy pool refreshed: {added_count} proxies added, {len(self.failed_proxies)} failed proxies excluded")
                
                # Reset failed proxies if pool is getting too small
                if added_count < self.min_pool_size and len(self.failed_proxies) > 0:
                    logger.info(f"Pool size too small ({added_count}), resetting failed proxies")
                    self.failed_proxies.clear()
                    self._refresh_pool(force=True)
                
            except Exception as e:
                logger.error(f"Error refreshing proxy pool: {str(e)}")
    
    def _check_pool_health(self):
        """Check and maintain pool health"""
        with self._lock:
            pool_size = self.available_proxies.qsize()
            
            if pool_size < self.min_pool_size:
                logger.warning(f"Proxy pool below minimum size ({pool_size} < {self.min_pool_size}), triggering refresh")
                self._refresh_pool(force=True)
            
            # Log pool stats
            if pool_size > 0:
                logger.debug(f"Proxy pool health: {pool_size} available, {len(self.failed_proxies)} failed")
    
    def get_proxy(self, exclude_ids: Optional[Set[int]] = None) -> Optional[ProxyInfo]:
        """Get a proxy from the pool with exclusion support"""
        exclude_ids = exclude_ids or set()
        attempts = 0
        max_attempts = min(50, self.available_proxies.qsize() + 10)
        
        with self._lock:
            while attempts < max_attempts:
                try:
                    proxy = self.available_proxies.get_nowait()
                    
                    # Check if proxy should be excluded
                    if proxy.id in exclude_ids or proxy.id in self.failed_proxies:
                        # Put it back at the end of the queue
                        self.available_proxies.put(proxy)
                        attempts += 1
                        continue
                    
                    # Update last used time
                    proxy.last_used = time.time()
                    
                    # Track usage
                    if proxy.id not in self.proxy_stats:
                        self.proxy_stats[proxy.id] = {"uses": 0, "errors": 0, "last_used": proxy.last_used}
                    
                    self.proxy_stats[proxy.id]["uses"] += 1
                    self.proxy_stats[proxy.id]["last_used"] = proxy.last_used
                    
                    logger.debug(f"Retrieved proxy {proxy.id} from pool: {proxy.address}:{proxy.port}")
                    return proxy
                    
                except Empty:
                    # Pool is empty, try to refresh
                    logger.warning("Proxy pool is empty, attempting refresh")
                    self._refresh_pool(force=True)
                    break
                
                attempts += 1
            
            logger.warning(f"Could not get suitable proxy after {attempts} attempts")
            return None
    
    def return_proxy(self, proxy: ProxyInfo, success: bool = True):
        """Return a proxy to the pool after use"""
        with self._lock:
            if success:
                # Mark for success update
                self.pending_success_updates.add(proxy.id)
                
                # Put proxy back in pool if it's still good
                if proxy.id not in self.failed_proxies:
                    self.available_proxies.put(proxy)
                    logger.debug(f"Returned successful proxy {proxy.id} to pool")
            else:
                # Mark proxy as failed
                self.failed_proxies.add(proxy.id)
                
                # Add to pending error updates
                if proxy.id in self.pending_error_updates:
                    self.pending_error_updates[proxy.id] += 1
                else:
                    self.pending_error_updates[proxy.id] = 1
                
                # Update stats
                if proxy.id in self.proxy_stats:
                    self.proxy_stats[proxy.id]["errors"] += 1
                
                logger.warning(f"Marked proxy {proxy.id} as failed, not returning to pool")
    
    def _process_batch_updates(self):
        """Process pending proxy updates in batches"""
        with self._lock:
            try:
                current_time = time.time()
                
                # Process error updates
                if self.pending_error_updates:
                    logger.info(f"Processing {len(self.pending_error_updates)} proxy error updates")
                    
                    for proxy_id, error_count in self.pending_error_updates.items():
                        try:
                            # Increment error count multiple times if needed
                            for _ in range(error_count):
                                self.db_manager.increment_proxy_error(proxy_id)
                        except Exception as e:
                            logger.error(f"Failed to update error count for proxy {proxy_id}: {str(e)}")
                    
                    self.pending_error_updates.clear()
                
                # Process success updates (update last_used timestamps)
                if self.pending_success_updates:
                    logger.info(f"Processing {len(self.pending_success_updates)} proxy success updates")
                    
                    for proxy_id in self.pending_success_updates:
                        try:
                            self.db_manager.update_proxy_last_used(proxy_id)
                        except Exception as e:
                            logger.error(f"Failed to update last_used for proxy {proxy_id}: {str(e)}")
                    
                    self.pending_success_updates.clear()
                
                self.last_batch_update = current_time
                
            except Exception as e:
                logger.error(f"Error processing batch updates: {str(e)}")
    
    def get_pool_stats(self) -> Dict:
        """Get current pool statistics"""
        with self._lock:
            return {
                "available_proxies": self.available_proxies.qsize(),
                "failed_proxies": len(self.failed_proxies),
                "total_tracked": len(self.proxy_stats),
                "last_refresh": self.last_refresh,
                "last_batch_update": self.last_batch_update,
                "pending_error_updates": len(self.pending_error_updates),
                "pending_success_updates": len(self.pending_success_updates),
                "pool_config": {
                    "pool_size": self.pool_size,
                    "min_pool_size": self.min_pool_size,
                    "refresh_interval": self.refresh_interval,
                    "batch_update_interval": self.batch_update_interval
                }
            }
    
    def force_refresh(self):
        """Force an immediate pool refresh"""
        logger.info("Forcing proxy pool refresh")
        self._refresh_pool(force=True)
    
    def reset_failed_proxies(self):
        """Reset failed proxy list"""
        with self._lock:
            cleared_count = len(self.failed_proxies)
            self.failed_proxies.clear()
            logger.info(f"Reset {cleared_count} failed proxies")
            return cleared_count
    
    def stop(self):
        """Stop the proxy pool and background worker"""
        logger.info("Stopping proxy pool")
        self._stop_event.set()
        
        if self._background_thread and self._background_thread.is_alive():
            self._background_thread.join(timeout=10)
        
        # Process any pending updates before stopping
        self._process_batch_updates()


# Enhanced retry manager that uses the proxy pool
class EnhancedProxyRetryManager:
    """Enhanced proxy retry manager using proxy pool"""
    
    def __init__(self, proxy_pool: ProxyPool, max_retries=3):
        self.proxy_pool = proxy_pool
        self.max_retries = max_retries
        self.request_failed_proxies: Dict[str, Set[int]] = {}  # request_id -> failed_proxy_ids
    
    def get_proxy_for_request(self, request_id: str) -> Optional[ProxyInfo]:
        """Get a proxy for a specific request, excluding previously failed ones"""
        failed_for_request = self.request_failed_proxies.get(request_id, set())
        return self.proxy_pool.get_proxy(exclude_ids=failed_for_request)
    
    def mark_proxy_failed_for_request(self, request_id: str, proxy: ProxyInfo):
        """Mark a proxy as failed for a specific request"""
        if request_id not in self.request_failed_proxies:
            self.request_failed_proxies[request_id] = set()
        
        self.request_failed_proxies[request_id].add(proxy.id)
        self.proxy_pool.return_proxy(proxy, success=False)
    
    def mark_proxy_success_for_request(self, request_id: str, proxy: ProxyInfo):
        """Mark a proxy as successful for a specific request"""
        self.proxy_pool.return_proxy(proxy, success=True)
        
        # Clean up request tracking
        if request_id in self.request_failed_proxies:
            del self.request_failed_proxies[request_id]
    
    def get_retry_count_for_request(self, request_id: str) -> int:
        """Get number of failed proxies for a request"""
        return len(self.request_failed_proxies.get(request_id, set()))
    
    def cleanup_old_requests(self, max_age_hours: int = 1):
        """Clean up old request tracking data"""
        # In a real implementation, you'd track request timestamps
        # For now, just limit the size
        if len(self.request_failed_proxies) > 1000:
            # Keep only the most recent 100 requests
            recent_requests = dict(list(self.request_failed_proxies.items())[-100:])
            self.request_failed_proxies = recent_requests 