import logging
import time
import threading
import sqlite3
import json
import os
import psutil
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from datetime import datetime, timedelta
import statistics

logger = logging.getLogger(__name__)

@dataclass
class RequestMetric:
    timestamp: float
    url: str
    method: str  # 'scrapegraph', 'newspaper'
    success: bool
    duration: float  # seconds
    proxy_used: Optional[str]
    error_type: Optional[str]
    content_length: int
    attempt_count: int
    request_id: str

class MetricsCollector:
    """Comprehensive metrics collection with memory and SQLite storage"""
    
    def __init__(self, config_store=None):
        self.config_store = config_store or {}
        
        # Configuration
        self.metrics_enabled = self.config_store.get("metrics_enabled", True)
        self.persist_metrics = self.config_store.get("persist_metrics", True)
        self.metrics_db_path = self.config_store.get("metrics_db_path", "data/metrics.db")
        self.memory_retention_hours = int(self.config_store.get("memory_retention_hours", 24))
        self.db_retention_days = int(self.config_store.get("db_retention_days", 30))
        self.max_memory_entries = int(self.config_store.get("max_memory_entries", 10000))
        
        # Thread safety
        self._lock = threading.RLock()
        
        # In-memory storage (recent data for fast access)
        self.recent_requests: deque = deque(maxlen=self.max_memory_entries)
        self.counters = defaultdict(int)
        self.timers = defaultdict(list)
        
        # Aggregated stats (reset daily)
        self.daily_stats = {
            "date": datetime.now().date().isoformat(),
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0.0,
            "proxy_usage": defaultdict(int),
            "error_types": defaultdict(int),
            "methods_used": defaultdict(int)
        }
        
        # Initialize database if persistence is enabled
        if self.persist_metrics:
            self._init_database()
        
        # Start background cleanup worker
        self._start_cleanup_worker()
    
    def _init_database(self):
        """Initialize SQLite database for metrics persistence"""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.metrics_db_path), exist_ok=True)
            
            conn = sqlite3.connect(self.metrics_db_path)
            cursor = conn.cursor()
            
            # Create metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS request_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    url TEXT NOT NULL,
                    method TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    duration REAL NOT NULL,
                    proxy_used TEXT,
                    error_type TEXT,
                    content_length INTEGER,
                    attempt_count INTEGER,
                    request_id TEXT,
                    created_date DATE DEFAULT CURRENT_DATE
                )
            """)
            
            # Create indexes for better query performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON request_metrics(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_method ON request_metrics(method)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_success ON request_metrics(success)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_date ON request_metrics(created_date)")
            
            # Create daily statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date DATE PRIMARY KEY,
                    total_requests INTEGER,
                    successful_requests INTEGER,
                    failed_requests INTEGER,
                    avg_response_time REAL,
                    data JSON
                )
            """)
            
            conn.commit()
            conn.close()
            
            logger.info(f"Metrics database initialized: {self.metrics_db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize metrics database: {str(e)}")
            self.persist_metrics = False
    
    def record_request(self, metric: RequestMetric):
        """Record a request metric"""
        if not self.metrics_enabled:
            return
        
        with self._lock:
            # Add to memory
            self.recent_requests.append(metric)
            
            # Update counters
            self.counters["total_requests"] += 1
            if metric.success:
                self.counters["successful_requests"] += 1
            else:
                self.counters["failed_requests"] += 1
            
            self.counters[f"method_{metric.method}"] += 1
            
            if metric.proxy_used:
                self.counters["proxy_requests"] += 1
            else:
                self.counters["direct_requests"] += 1
            
            # Update timers
            self.timers["response_times"].append(metric.duration)
            if len(self.timers["response_times"]) > 1000:  # Keep only recent 1000
                self.timers["response_times"] = self.timers["response_times"][-1000:]
            
            # Update daily stats
            self._update_daily_stats(metric)
            
            # Persist to database if enabled
            if self.persist_metrics:
                self._persist_metric(metric)
    
    def _update_daily_stats(self, metric: RequestMetric):
        """Update daily aggregated statistics"""
        current_date = datetime.now().date().isoformat()
        
        # Reset daily stats if date changed
        if self.daily_stats["date"] != current_date:
            self._save_daily_stats()
            self._reset_daily_stats(current_date)
        
        # Update current day stats
        self.daily_stats["total_requests"] += 1
        if metric.success:
            self.daily_stats["successful_requests"] += 1
        else:
            self.daily_stats["failed_requests"] += 1
            if metric.error_type:
                self.daily_stats["error_types"][metric.error_type] += 1
        
        self.daily_stats["methods_used"][metric.method] += 1
        
        if metric.proxy_used:
            self.daily_stats["proxy_usage"][metric.proxy_used] += 1
        
        # Update average response time
        total = self.daily_stats["total_requests"]
        current_avg = self.daily_stats["avg_response_time"]
        self.daily_stats["avg_response_time"] = ((current_avg * (total - 1)) + metric.duration) / total
    
    def _persist_metric(self, metric: RequestMetric):
        """Persist metric to SQLite database"""
        try:
            conn = sqlite3.connect(self.metrics_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO request_metrics 
                (timestamp, url, method, success, duration, proxy_used, error_type, 
                 content_length, attempt_count, request_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.timestamp, metric.url, metric.method, metric.success,
                metric.duration, metric.proxy_used, metric.error_type,
                metric.content_length, metric.attempt_count, metric.request_id
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to persist metric: {str(e)}")
    
    def _save_daily_stats(self):
        """Save daily statistics to database"""
        if not self.persist_metrics:
            return
        
        try:
            conn = sqlite3.connect(self.metrics_db_path)
            cursor = conn.cursor()
            
            # Convert defaultdicts to regular dicts for JSON serialization
            data = {
                "proxy_usage": dict(self.daily_stats["proxy_usage"]),
                "error_types": dict(self.daily_stats["error_types"]),
                "methods_used": dict(self.daily_stats["methods_used"])
            }
            
            cursor.execute("""
                INSERT OR REPLACE INTO daily_stats 
                (date, total_requests, successful_requests, failed_requests, avg_response_time, data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                self.daily_stats["date"],
                self.daily_stats["total_requests"],
                self.daily_stats["successful_requests"],
                self.daily_stats["failed_requests"],
                self.daily_stats["avg_response_time"],
                json.dumps(data)
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Saved daily stats for {self.daily_stats['date']}")
            
        except Exception as e:
            logger.error(f"Failed to save daily stats: {str(e)}")
    
    def _reset_daily_stats(self, new_date: str):
        """Reset daily statistics for new day"""
        self.daily_stats = {
            "date": new_date,
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0.0,
            "proxy_usage": defaultdict(int),
            "error_types": defaultdict(int),
            "methods_used": defaultdict(int)
        }
    
    def get_current_stats(self) -> Dict:
        """Get current real-time statistics"""
        with self._lock:
            # Calculate recent performance (last hour)
            cutoff_time = time.time() - 3600  # 1 hour ago
            recent_requests = [r for r in self.recent_requests if r.timestamp > cutoff_time]
            
            recent_success_rate = 0
            recent_avg_time = 0
            recent_proxy_usage = 0
            
            if recent_requests:
                successful = sum(1 for r in recent_requests if r.success)
                recent_success_rate = (successful / len(recent_requests)) * 100
                recent_avg_time = sum(r.duration for r in recent_requests) / len(recent_requests)
                proxy_requests = sum(1 for r in recent_requests if r.proxy_used)
                recent_proxy_usage = (proxy_requests / len(recent_requests)) * 100
            
            # Overall response times
            response_times = self.timers.get("response_times", [])
            response_time_stats = {}
            if response_times:
                response_time_stats = {
                    "min": min(response_times),
                    "max": max(response_times),
                    "avg": statistics.mean(response_times),
                    "median": statistics.median(response_times),
                    "p95": self._percentile(response_times, 95),
                    "p99": self._percentile(response_times, 99)
                }
            
            # Get actual system memory usage
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            return {
                "timestamp": time.time(),
                "counters": dict(self.counters),
                "recent_hour": {
                    "requests": len(recent_requests),
                    "success_rate": round(recent_success_rate, 2),
                    "avg_response_time": round(recent_avg_time, 3),
                    "proxy_usage": round(recent_proxy_usage, 2)
                },
                "response_times": response_time_stats,
                "daily_stats": {
                    **self.daily_stats,
                    "proxy_usage": dict(self.daily_stats["proxy_usage"]),
                    "error_types": dict(self.daily_stats["error_types"]),
                    "methods_used": dict(self.daily_stats["methods_used"])
                },
                "memory_usage": {
                    "rss_mb": round(memory_info.rss / 1024 / 1024, 2),  # Resident Set Size in MB
                    "vms_mb": round(memory_info.vms / 1024 / 1024, 2),  # Virtual Memory Size in MB
                    "percent": round(memory_percent, 2),  # Percentage of system memory
                    "recent_requests_count": len(self.recent_requests),
                    "max_memory_entries": self.max_memory_entries,
                    "buffer_usage_percent": round((len(self.recent_requests) / self.max_memory_entries) * 100, 2)
                }
            }
    
    def get_historical_stats(self, days: int = 7) -> Dict:
        """Get historical statistics from database"""
        if not self.persist_metrics:
            return {"error": "Persistence not enabled"}
        
        try:
            conn = sqlite3.connect(self.metrics_db_path)
            cursor = conn.cursor()
            
            # Get daily stats for the last N days
            cursor.execute("""
                SELECT date, total_requests, successful_requests, failed_requests, 
                       avg_response_time, data
                FROM daily_stats 
                WHERE date >= date('now', '-{} days')
                ORDER BY date DESC
            """.format(days))
            
            daily_data = []
            for row in cursor.fetchall():
                data = json.loads(row[5]) if row[5] else {}
                daily_data.append({
                    "date": row[0],
                    "total_requests": row[1],
                    "successful_requests": row[2],
                    "failed_requests": row[3],
                    "avg_response_time": row[4],
                    "success_rate": (row[2] / row[1] * 100) if row[1] > 0 else 0,
                    **data
                })
            
            # Get hourly breakdown for today
            today = datetime.now().date().isoformat()
            cursor.execute("""
                SELECT strftime('%H', datetime(timestamp, 'unixepoch')) as hour,
                       COUNT(*) as requests,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                       AVG(duration) as avg_duration
                FROM request_metrics 
                WHERE date(datetime(timestamp, 'unixepoch')) = ?
                GROUP BY hour
                ORDER BY hour
            """, (today,))
            
            hourly_data = [
                {
                    "hour": int(row[0]),
                    "requests": row[1],
                    "successful": row[2],
                    "avg_duration": round(row[3] or 0, 3),
                    "success_rate": round((row[2] / row[1] * 100) if row[1] > 0 else 0, 2)
                }
                for row in cursor.fetchall()
            ]
            
            conn.close()
            
            return {
                "daily_stats": daily_data,
                "hourly_today": hourly_data,
                "period_days": days
            }
            
        except Exception as e:
            logger.error(f"Failed to get historical stats: {str(e)}")
            return {"error": str(e)}
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of a list"""
        if not data:
            return 0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * (percentile / 100)
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])
    
    def _start_cleanup_worker(self):
        """Start background worker for cleanup tasks"""
        def cleanup_worker():
            while True:
                try:
                    # Clean up old in-memory data
                    cutoff_time = time.time() - (self.memory_retention_hours * 3600)
                    with self._lock:
                        # Remove old entries from recent_requests
                        while self.recent_requests and self.recent_requests[0].timestamp < cutoff_time:
                            self.recent_requests.popleft()
                    
                    # Clean up old database entries
                    if self.persist_metrics:
                        self._cleanup_old_db_entries()
                    
                    # Sleep for 1 hour
                    time.sleep(3600)
                    
                except Exception as e:
                    logger.error(f"Error in metrics cleanup worker: {str(e)}")
                    time.sleep(300)  # Sleep 5 minutes on error
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("Metrics cleanup worker started")
    
    def _cleanup_old_db_entries(self):
        """Clean up old database entries"""
        try:
            conn = sqlite3.connect(self.metrics_db_path)
            cursor = conn.cursor()
            
            # Delete old request metrics
            cutoff_date = (datetime.now() - timedelta(days=self.db_retention_days)).isoformat()
            cursor.execute("DELETE FROM request_metrics WHERE created_date < ?", (cutoff_date,))
            deleted_requests = cursor.rowcount
            
            # Delete old daily stats
            cursor.execute("DELETE FROM daily_stats WHERE date < ?", (cutoff_date,))
            deleted_daily = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if deleted_requests > 0 or deleted_daily > 0:
                logger.info(f"Cleaned up {deleted_requests} old request metrics and {deleted_daily} old daily stats")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old database entries: {str(e)}")
    
    def export_metrics(self, format: str = "json") -> str:
        """Export metrics data"""
        if format == "json":
            return json.dumps({
                "current_stats": self.get_current_stats(),
                "historical_stats": self.get_historical_stats(30)
            }, indent=2)
        else:
            return "Unsupported format"

# Global metrics instance
metrics_collector = None

def init_metrics(config_store):
    """Initialize global metrics collector"""
    global metrics_collector
    metrics_collector = MetricsCollector(config_store)
    return metrics_collector

def record_request_metric(url: str, method: str, success: bool, duration: float,
                         proxy_used: Optional[str] = None, error_type: Optional[str] = None,
                         content_length: int = 0, attempt_count: int = 1, request_id: str = ""):
    """Convenience function to record request metrics"""
    if metrics_collector:
        metric = RequestMetric(
            timestamp=time.time(),
            url=url,
            method=method,
            success=success,
            duration=duration,
            proxy_used=proxy_used,
            error_type=error_type,
            content_length=content_length,
            attempt_count=attempt_count,
            request_id=request_id
        )
        metrics_collector.record_request(metric) 