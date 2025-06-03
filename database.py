import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from typing import List, Dict, Optional, Tuple
import logging
import random
import time
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Simple circuit breaker to prevent cascading failures"""
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()
    
    def call(self, func, *args, **kwargs):
        with self._lock:
            if self.state == 'OPEN':
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = 'HALF_OPEN'
                else:
                    raise Exception("Circuit breaker is OPEN - database operations temporarily disabled")
            
            try:
                result = func(*args, **kwargs)
                if self.state == 'HALF_OPEN':
                    self.state = 'CLOSED'
                    self.failure_count = 0
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = 'OPEN'
                    logger.error(f"Circuit breaker opened after {self.failure_count} failures")
                
                raise e

class DatabaseManager:
    def __init__(self, config_store=None):
        self.config_store = config_store
        self.connection_pool = None
        self.circuit_breaker = CircuitBreaker()
        self._lock = threading.Lock()
        self._schema_checked = False
        self._has_last_used_column = False
    
    def _create_connection_pool(self) -> bool:
        """Create connection pool for better performance"""
        try:
            db_config = self.get_database_config()
            if not db_config:
                logger.warning("Database not configured")
                return False
            
            logger.info(f"Creating connection pool for PostgreSQL database...")
            logger.info(f"Host: {db_config['host']}")
            logger.info(f"Port: {db_config.get('port', 5432)}")
            logger.info(f"Database: {db_config['database']}")
            logger.info(f"Username: {db_config['username']}")
            
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                host=db_config["host"],
                port=db_config.get("port", 5432),
                database=db_config["database"],
                user=db_config["username"],
                password=db_config["password"],
                cursor_factory=RealDictCursor,
                connect_timeout=5  # Reduced timeout
            )
            
            logger.info(f"Successfully created connection pool for: {db_config['host']}:{db_config.get('port', 5432)}")
            return True
            
        except psycopg2.OperationalError as e:
            logger.error(f"PostgreSQL connection pool creation failed: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Database connection pool creation failed: {str(e)}", exc_info=True)
            return False
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        if not self.connection_pool:
            with self._lock:
                if not self.connection_pool:
                    if not self._create_connection_pool():
                        raise Exception("Failed to create database connection pool")
        
        connection = None
        try:
            connection = self.connection_pool.getconn()
            yield connection
        finally:
            if connection:
                self.connection_pool.putconn(connection)
    
    def _check_schema(self):
        """Check database schema and cache results"""
        if self._schema_checked:
            return
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if last_used column exists
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'proxies' AND column_name = 'last_used'
                """)
                
                self._has_last_used_column = cursor.fetchone() is not None
                self._schema_checked = True
                
                if self._has_last_used_column:
                    logger.info("Database schema check: last_used column exists")
                else:
                    logger.warning("Database schema check: last_used column missing - some operations will be skipped")
                
                cursor.close()
        except Exception as e:
            logger.error(f"Schema check failed: {str(e)}")
            self._schema_checked = True  # Don't keep trying on every request
    
    def connect(self) -> bool:
        """Legacy method for backward compatibility"""
        try:
            with self.get_connection() as conn:
                return True
        except:
            return False
    
    def get_database_config(self) -> Dict:
        """Get database configuration from config store"""
        if self.config_store:
            # Check if it's a Config object with get_database_config method
            if hasattr(self.config_store, 'get_database_config'):
                return self.config_store.get_database_config()
            # Fallback for dictionary-style config store
            elif hasattr(self.config_store, 'get') and self.config_store.get("database"):
                return self.config_store["database"]
        return {}
    
    def disconnect(self):
        """Close connection pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            self.connection_pool = None
            logger.debug("Database connection pool closed")
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test database connection and return status with message"""
        def _test():
            logger.info("Starting database connection test...")
            
            db_config = self.get_database_config()
            if not db_config:
                logger.error("No database configuration found")
                return False, "Database not configured"
            
            logger.info(f"Testing connection to {db_config['host']}:{db_config.get('port', 5432)}")
            logger.info(f"Database: {db_config['database']}, Username: {db_config['username']}")
            
            with self.get_connection() as conn:
                logger.info("Database connection established successfully")
                cursor = conn.cursor()
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                cursor.close()
                
                if result:
                    logger.info("Database test query successful")
                    return True, "Database connection successful"
                else:
                    logger.error("Database test query returned no results")
                    return False, "Database query returned no results"
        
        try:
            return self.circuit_breaker.call(_test)
        except psycopg2.OperationalError as e:
            db_config = self.get_database_config()
            error_msg = f"Database connection failed: {str(e)}"
            logger.error(error_msg)
            
            # Provide more specific error messages
            if "could not connect to server" in str(e).lower():
                return False, f"Cannot reach database server at {db_config.get('host', 'unknown')}:{db_config.get('port', 5432)}. Check if the server is running and accessible."
            elif "authentication failed" in str(e).lower():
                return False, f"Authentication failed for user '{db_config.get('username', 'unknown')}'. Check username and password."
            elif "database" in str(e).lower() and "does not exist" in str(e).lower():
                return False, f"Database '{db_config.get('database', 'unknown')}' does not exist on the server."
            elif "timeout" in str(e).lower():
                return False, "Connection timeout. The database server may be overloaded or network issues exist."
            else:
                return False, error_msg
        except Exception as e:
            error_msg = f"Database test failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def test_proxy_table(self) -> Tuple[bool, str, int]:
        """Test proxy table access and return status with proxy count"""
        def _test():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if table exists and get structure
                cursor.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'proxies'
                    ORDER BY ordinal_position
                """)
                columns = cursor.fetchall()
                
                if not columns:
                    cursor.close()
                    return False, "Proxies table not found", 0
                
                # Verify required columns exist
                column_names = [col['column_name'] for col in columns]
                required_columns = ['id', 'address', 'port', 'error_count', 'status', 'username', 'password', 'type']
                missing_columns = [col for col in required_columns if col not in column_names]
                
                if missing_columns:
                    cursor.close()
                    return False, f"Missing columns in proxies table: {', '.join(missing_columns)}", 0
                
                # Count total and active proxies
                cursor.execute("SELECT COUNT(*) as total FROM proxies")
                total_count = cursor.fetchone()['total']
                
                cursor.execute("SELECT COUNT(*) as active FROM proxies WHERE status = 'active' AND error_count < 5")
                active_count = cursor.fetchone()['active']
                
                cursor.close()
                
                message = f"Proxy table OK: {active_count}/{total_count} active proxies (error_count < 5)"
                logger.info(message)
                return True, message, active_count
        
        try:
            return self.circuit_breaker.call(_test)
        except Exception as e:
            error_msg = f"Proxy table test failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, 0
    
    def get_proxies(self, count: int = 5) -> List[Dict]:
        """
        Get working proxies from database with retry logic
        """
        def _get_proxies():
            self._check_schema()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get active proxies with low error count, randomize order for load balancing
                cursor.execute("""
                    SELECT id, address, port, username, password, type, error_count
                    FROM proxies 
                    WHERE status = 'active' AND error_count < 3
                    ORDER BY error_count ASC, RANDOM()
                    LIMIT %s
                """, (count * 2,))  # Get more proxies to have fallbacks
                
                proxies = cursor.fetchall()
                cursor.close()
                
                # Convert to list of dicts and format proxy URLs
                proxy_list = []
                for proxy in proxies:
                    proxy_dict = dict(proxy)
                    
                    # Build proxy URL
                    auth = ""
                    if proxy['username'] and proxy['password']:
                        auth = f"{proxy['username']}:{proxy['password']}@"
                    
                    proxy_url = f"{proxy['type']}://{auth}{proxy['address']}:{proxy['port']}"
                    proxy_dict['proxy_url'] = proxy_url
                    
                    proxy_list.append(proxy_dict)
                
                logger.info(f"Retrieved {len(proxy_list)} active proxies from database")
                return proxy_list[:count]  # Return only requested count
        
        try:
            return self.circuit_breaker.call(_get_proxies)
        except Exception as e:
            logger.error(f"Failed to retrieve proxies: {str(e)}")
            return []
    
    def increment_proxy_error(self, proxy_id: int) -> bool:
        """
        Increment error count for a failed proxy with exponential backoff
        """
        def _increment():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Increment error count with exponential backoff logic
                cursor.execute("""
                    UPDATE proxies 
                    SET error_count = error_count + 1,
                        status = CASE 
                            WHEN error_count + 1 >= 3 THEN 'inactive'
                            ELSE status
                        END
                    WHERE id = %s
                    RETURNING error_count, status
                """, (proxy_id,))
                
                result = cursor.fetchone()
                conn.commit()
                cursor.close()
                
                if result:
                    logger.warning(f"Proxy {proxy_id} error count incremented to {result['error_count']}, status: {result['status']}")
                    return True
                else:
                    logger.error(f"Proxy {proxy_id} not found for error increment")
                    return False
        
        try:
            return self.circuit_breaker.call(_increment)
        except Exception as e:
            logger.error(f"Failed to increment proxy error count: {str(e)}")
            return False
    
    def update_proxy_last_used(self, proxy_id: int) -> bool:
        """
        Update last used timestamp for a proxy (only if column exists)
        """
        def _update():
            self._check_schema()
            
            if not self._has_last_used_column:
                logger.debug(f"Skipping last_used update for proxy {proxy_id} - column doesn't exist")
                return True
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Update last_used timestamp
                cursor.execute("""
                    UPDATE proxies 
                    SET last_used = NOW()
                    WHERE id = %s
                """, (proxy_id,))
                
                conn.commit()
                cursor.close()
                
                logger.debug(f"Updated last_used timestamp for proxy {proxy_id}")
                return True
        
        try:
            return self.circuit_breaker.call(_update)
        except Exception as e:
            logger.error(f"Failed to update proxy last_used: {str(e)}")
            return False
    
    def get_proxy_stats(self) -> Dict:
        """Get proxy statistics for monitoring with circuit breaker protection"""
        def _get_stats():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get comprehensive proxy statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_proxies,
                        COUNT(CASE WHEN status = 'active' THEN 1 END) as active_proxies,
                        COUNT(CASE WHEN status = 'active' AND error_count < 3 THEN 1 END) as usable_proxies,
                        COUNT(CASE WHEN error_count >= 3 THEN 1 END) as high_error_proxies,
                        AVG(error_count) as avg_error_count
                    FROM proxies
                """)
                
                stats = cursor.fetchone()
                cursor.close()
                
                return dict(stats) if stats else {"error": "No proxy statistics available"}
        
        try:
            return self.circuit_breaker.call(_get_stats)
        except Exception as e:
            logger.error(f"Failed to get proxy statistics: {str(e)}")
            return {"error": str(e)}
    
    def reset_proxy_errors(self, max_error_count: int = 2) -> int:
        """Reset error counts for proxies that might have recovered"""
        def _reset():
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE proxies 
                    SET error_count = 0, status = 'active'
                    WHERE error_count <= %s AND status = 'inactive'
                    RETURNING id
                """, (max_error_count,))
                
                reset_proxies = cursor.fetchall()
                conn.commit()
                cursor.close()
                
                count = len(reset_proxies)
                if count > 0:
                    logger.info(f"Reset error counts for {count} proxies")
                
                return count
        
        try:
            return self.circuit_breaker.call(_reset)
        except Exception as e:
            logger.error(f"Failed to reset proxy errors: {str(e)}")
            return 0 