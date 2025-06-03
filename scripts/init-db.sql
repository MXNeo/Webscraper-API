-- WebScraper API - Database Initialization Script
-- This script creates the complete schema for the webscraper application

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create proxies table with comprehensive schema
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
    tags VARCHAR(500),  -- JSON array as string: ["residential", "fast", "premium"]
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure uniqueness
    UNIQUE(address, port, username)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_proxies_status_errors ON proxies(status, error_count);
CREATE INDEX IF NOT EXISTS idx_proxies_last_used ON proxies(last_used);
CREATE INDEX IF NOT EXISTS idx_proxies_last_tested ON proxies(last_tested);
CREATE INDEX IF NOT EXISTS idx_proxies_type ON proxies(type);
CREATE INDEX IF NOT EXISTS idx_proxies_country ON proxies(country);
CREATE INDEX IF NOT EXISTS idx_proxies_provider ON proxies(provider);
CREATE INDEX IF NOT EXISTS idx_proxies_response_time ON proxies(response_time_ms);

-- Create proxy_usage_logs table for detailed tracking
CREATE TABLE IF NOT EXISTS proxy_usage_logs (
    id SERIAL PRIMARY KEY,
    proxy_id INTEGER REFERENCES proxies(id) ON DELETE CASCADE,
    
    -- Request information
    request_url VARCHAR(1000),
    request_method VARCHAR(10) DEFAULT 'GET',
    request_id VARCHAR(100),  -- UUID for request tracking
    
    -- Response information
    success BOOLEAN NOT NULL,
    response_code INTEGER,
    response_time_ms INTEGER,
    error_message TEXT,
    
    -- Metadata
    user_agent VARCHAR(500),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX ON (proxy_id),
    INDEX ON (timestamp),
    INDEX ON (success),
    INDEX ON (request_id)
);

-- Create function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
DROP TRIGGER IF EXISTS update_proxies_updated_at ON proxies;
CREATE TRIGGER update_proxies_updated_at
    BEFORE UPDATE ON proxies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create function to automatically update proxy statistics
CREATE OR REPLACE FUNCTION update_proxy_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.success THEN
        UPDATE proxies 
        SET success_count = success_count + 1,
            last_used = NEW.timestamp,
            response_time_ms = COALESCE(
                (response_time_ms * success_count + NEW.response_time_ms) / (success_count + 1),
                NEW.response_time_ms
            )
        WHERE id = NEW.proxy_id;
    ELSE
        UPDATE proxies 
        SET error_count = error_count + 1,
            status = CASE 
                WHEN error_count + 1 >= 5 THEN 'failed'
                WHEN error_count + 1 >= 3 THEN 'inactive'
                ELSE status
            END
        WHERE id = NEW.proxy_id;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for automatic stats updates
DROP TRIGGER IF EXISTS update_proxy_stats_trigger ON proxy_usage_logs;
CREATE TRIGGER update_proxy_stats_trigger
    AFTER INSERT ON proxy_usage_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_proxy_stats();

-- Create view for proxy statistics
CREATE OR REPLACE VIEW proxy_stats AS
SELECT 
    p.id,
    p.address,
    p.port,
    p.type,
    p.status,
    p.error_count,
    p.success_count,
    p.last_used,
    p.last_tested,
    p.response_time_ms,
    p.country,
    p.provider,
    
    -- Calculated statistics
    CASE 
        WHEN (p.success_count + p.error_count) > 0 
        THEN ROUND((p.success_count::FLOAT / (p.success_count + p.error_count)) * 100, 2)
        ELSE NULL 
    END as success_rate_percent,
    
    (p.success_count + p.error_count) as total_requests,
    
    -- Last 24 hours statistics
    COALESCE(recent_stats.recent_requests, 0) as recent_24h_requests,
    COALESCE(recent_stats.recent_successes, 0) as recent_24h_successes,
    COALESCE(recent_stats.avg_recent_response_time, 0) as avg_recent_response_time_ms,
    
    -- Status indicators
    CASE 
        WHEN p.status = 'active' AND p.error_count < 3 THEN 'good'
        WHEN p.status = 'active' AND p.error_count < 5 THEN 'warning'
        ELSE 'error'
    END as health_status,
    
    p.created_at,
    p.updated_at

FROM proxies p
LEFT JOIN (
    SELECT 
        proxy_id,
        COUNT(*) as recent_requests,
        SUM(CASE WHEN success THEN 1 ELSE 0 END) as recent_successes,
        AVG(CASE WHEN success THEN response_time_ms END) as avg_recent_response_time
    FROM proxy_usage_logs 
    WHERE timestamp >= NOW() - INTERVAL '24 hours'
    GROUP BY proxy_id
) recent_stats ON p.id = recent_stats.proxy_id;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'WebScraper API database schema initialized successfully!';
    RAISE NOTICE 'Tables created: proxies, proxy_usage_logs';
    RAISE NOTICE 'Views created: proxy_stats';
    RAISE NOTICE 'Functions created: update_updated_at_column, update_proxy_stats';
    RAISE NOTICE 'Triggers created: update_proxies_updated_at, update_proxy_stats_trigger';
END $$; 