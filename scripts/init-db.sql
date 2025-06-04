-- WebScraper API - Database Initialization Script
-- This script creates the basic schema for the webscraper application

-- Create proxies table with basic schema
CREATE TABLE IF NOT EXISTS proxies (
    id SERIAL PRIMARY KEY,
    address VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL CHECK (port > 0 AND port <= 65535),
    type VARCHAR(10) DEFAULT 'http' CHECK (type IN ('http', 'https', 'socks4', 'socks5')),
    username VARCHAR(255),
    password VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'testing', 'failed')),
    error_count INTEGER DEFAULT 0 CHECK (error_count >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(address, port, username)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_proxies_status ON proxies(status);
CREATE INDEX IF NOT EXISTS idx_proxies_type ON proxies(type);

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'WebScraper API database schema initialized successfully!';
    RAISE NOTICE 'Tables created: proxies';
    RAISE NOTICE 'Database ready for use!';
END $$; 