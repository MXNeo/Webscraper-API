import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional, Tuple
import logging
import random

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, config_store=None):
        self.config_store = config_store
        self.connection = None
    
    def connect(self) -> bool:
        """Establish database connection"""
        try:
            db_config = self.get_database_config()
            if not db_config:
                logger.warning("Database not configured")
                return False
            
            logger.info(f"Attempting to connect to PostgreSQL database...")
            logger.info(f"Host: {db_config['host']}")
            logger.info(f"Port: {db_config.get('port', 5432)}")
            logger.info(f"Database: {db_config['database']}")
            logger.info(f"Username: {db_config['username']}")
            
            self.connection = psycopg2.connect(
                host=db_config["host"],
                port=db_config.get("port", 5432),
                database=db_config["database"],
                user=db_config["username"],
                password=db_config["password"],
                cursor_factory=RealDictCursor,
                connect_timeout=10
            )
            logger.info(f"Successfully connected to database: {db_config['host']}:{db_config.get('port', 5432)}")
            return True
        except psycopg2.OperationalError as e:
            logger.error(f"PostgreSQL connection failed: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}", exc_info=True)
            return False
    
    def get_database_config(self) -> Dict:
        """Get database configuration from config store"""
        if self.config_store and self.config_store.get("database"):
            return self.config_store["database"]
        return {}
    
    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.debug("Database connection closed")
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test database connection and return status with message"""
        try:
            logger.info("Starting database connection test...")
            
            db_config = self.get_database_config()
            if not db_config:
                logger.error("No database configuration found")
                return False, "Database not configured"
            
            logger.info(f"Testing connection to {db_config['host']}:{db_config.get('port', 5432)}")
            logger.info(f"Database: {db_config['database']}, Username: {db_config['username']}")
            
            if self.connect():
                logger.info("Database connection established successfully")
                cursor = self.connection.cursor()
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                cursor.close()
                self.disconnect()
                
                if result:
                    logger.info("Database test query successful")
                    return True, "Database connection successful"
                else:
                    logger.error("Database test query returned no results")
                    return False, "Database query returned no results"
            else:
                logger.error("Failed to establish database connection")
                return False, "Failed to establish database connection"
                
        except psycopg2.OperationalError as e:
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
        
        return False, "Unknown database connection error"
    
    def test_proxy_table(self) -> Tuple[bool, str, int]:
        """Test proxy table access and return status with proxy count"""
        try:
            if not self.connect():
                return False, "Cannot connect to database", 0
            
            cursor = self.connection.cursor()
            
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
                self.disconnect()
                return False, "Proxies table not found", 0
            
            # Verify required columns exist
            column_names = [col['column_name'] for col in columns]
            required_columns = ['id', 'address', 'port', 'error_count', 'status', 'username', 'password', 'type']
            missing_columns = [col for col in required_columns if col not in column_names]
            
            if missing_columns:
                cursor.close()
                self.disconnect()
                return False, f"Missing columns in proxies table: {', '.join(missing_columns)}", 0
            
            # Count total and active proxies
            cursor.execute("SELECT COUNT(*) as total FROM proxies")
            total_count = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as active FROM proxies WHERE status = 'active' AND error_count < 5")
            active_count = cursor.fetchone()['active']
            
            cursor.close()
            self.disconnect()
            
            message = f"Proxy table OK: {active_count}/{total_count} active proxies (error_count < 5)"
            logger.info(message)
            return True, message, active_count
            
        except Exception as e:
            error_msg = f"Proxy table test failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, 0
    
    def get_proxies(self, count: int = 5) -> List[Dict]:
        """
        Get working proxies from database
        
        Proxy table structure:
        - id: primary key
        - address: proxy IP address
        - port: proxy port
        - error_count: number of failed attempts
        - status: 'active' or 'inactive'
        - username: proxy username (optional)
        - password: proxy password (optional)
        - type: 'http' or 'https'
        
        Returns only proxies with status='active' and error_count < 5
        """
        try:
            if not self.connect():
                logger.error("Cannot connect to database for proxy retrieval")
                return []
            
            cursor = self.connection.cursor()
            
            # Get active proxies with low error count, randomize order for load balancing
            cursor.execute("""
                SELECT id, address, port, username, password, type, error_count
                FROM proxies 
                WHERE status = 'active' AND error_count < 5
                ORDER BY RANDOM()
                LIMIT %s
            """, (count,))
            
            proxies = cursor.fetchall()
            cursor.close()
            self.disconnect()
            
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
            return proxy_list
            
        except Exception as e:
            logger.error(f"Failed to retrieve proxies: {str(e)}")
            return []
    
    def increment_proxy_error(self, proxy_id: int) -> bool:
        """
        Increment error count for a failed proxy
        If error_count reaches 5 or more, deactivate the proxy
        """
        try:
            if not self.connect():
                logger.error("Cannot connect to database for proxy error increment")
                return False
            
            cursor = self.connection.cursor()
            
            # Increment error count
            cursor.execute("""
                UPDATE proxies 
                SET error_count = error_count + 1,
                    status = CASE 
                        WHEN error_count + 1 >= 5 THEN 'inactive'
                        ELSE status
                    END
                WHERE id = %s
                RETURNING error_count, status
            """, (proxy_id,))
            
            result = cursor.fetchone()
            self.connection.commit()
            cursor.close()
            self.disconnect()
            
            if result:
                logger.warning(f"Proxy {proxy_id} error count incremented to {result['error_count']}, status: {result['status']}")
                return True
            else:
                logger.error(f"Proxy {proxy_id} not found for error increment")
                return False
                
        except Exception as e:
            logger.error(f"Failed to increment proxy error count: {str(e)}")
            return False
    
    def update_proxy_last_used(self, proxy_id: int) -> bool:
        """
        Update last used timestamp for a proxy
        """
        try:
            if not self.connect():
                logger.error("Cannot connect to database for proxy last_used update")
                return False
            
            cursor = self.connection.cursor()
            
            # Update last_used timestamp
            cursor.execute("""
                UPDATE proxies 
                SET last_used = NOW()
                WHERE id = %s
            """, (proxy_id,))
            
            self.connection.commit()
            cursor.close()
            self.disconnect()
            
            logger.debug(f"Updated last_used timestamp for proxy {proxy_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update proxy last_used: {str(e)}")
            return False
    
    def get_proxy_stats(self) -> Dict:
        """Get proxy statistics for monitoring"""
        try:
            if not self.connect():
                return {"error": "Cannot connect to database"}
            
            cursor = self.connection.cursor()
            
            # Get comprehensive proxy statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_proxies,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_proxies,
                    COUNT(CASE WHEN status = 'active' AND error_count < 5 THEN 1 END) as usable_proxies,
                    COUNT(CASE WHEN error_count >= 5 THEN 1 END) as high_error_proxies,
                    AVG(error_count) as avg_error_count
                FROM proxies
            """)
            
            stats = cursor.fetchone()
            cursor.close()
            self.disconnect()
            
            return dict(stats) if stats else {"error": "No proxy statistics available"}
            
        except Exception as e:
            logger.error(f"Failed to get proxy statistics: {str(e)}")
            return {"error": str(e)} 