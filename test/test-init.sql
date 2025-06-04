-- Test database initialization for WebScraper API
-- This creates the proxy table and adds sample data for testing

-- Create proxies table
CREATE TABLE IF NOT EXISTS proxies (
    id SERIAL PRIMARY KEY,
    address VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL,
    type VARCHAR(10) DEFAULT 'http',
    username VARCHAR(255),
    password VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active',
    error_count INTEGER DEFAULT 0,
    last_used TIMESTAMP DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_proxies_status_errors ON proxies(status, error_count);
CREATE INDEX IF NOT EXISTS idx_proxies_last_used ON proxies(last_used);

-- Insert sample proxy data for testing
-- Note: These are dummy/test proxies - replace with real ones for actual use
INSERT INTO proxies (address, port, type, username, password, status, error_count) VALUES
    ('proxy1.example.com', 8080, 'http', 'user1', 'pass1', 'active', 0),
    ('proxy2.example.com', 8080, 'http', 'user2', 'pass2', 'active', 0),
    ('proxy3.example.com', 3128, 'http', NULL, NULL, 'active', 1),
    ('proxy4.example.com', 8080, 'https', 'user4', 'pass4', 'active', 0),
    ('proxy5.example.com', 8080, 'http', 'user5', 'pass5', 'active', 2),
    -- Some inactive proxies for testing
    ('proxy6.example.com', 8080, 'http', 'user6', 'pass6', 'inactive', 0),
    ('proxy7.example.com', 8080, 'http', 'user7', 'pass7', 'active', 5), -- High error count
    -- Some proxies without authentication
    ('proxy8.example.com', 3128, 'http', NULL, NULL, 'active', 0),
    ('proxy9.example.com', 8080, 'http', NULL, NULL, 'active', 1),
    ('proxy10.example.com', 8080, 'https', 'user10', 'pass10', 'active', 0)
ON CONFLICT DO NOTHING;

-- Create a function to update the updated_at timestamp
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

-- Display initialization results
DO $$
DECLARE
    proxy_count INTEGER;
    active_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO proxy_count FROM proxies;
    SELECT COUNT(*) INTO active_count FROM proxies WHERE status = 'active' AND error_count < 5;
    
    RAISE NOTICE 'Database initialization complete!';
    RAISE NOTICE 'Total proxies: %', proxy_count;
    RAISE NOTICE 'Active usable proxies: %', active_count;
END $$; 