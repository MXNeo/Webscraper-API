-- WebScraper API - Sample Proxy Data
-- This script inserts sample proxy data for testing and development

-- Insert diverse sample proxy data
INSERT INTO proxies (
    address, port, type, username, password, status, error_count, success_count,
    country, region, provider, notes, tags, response_time_ms
) VALUES
    -- High-quality residential proxies
    ('proxy-us-east-1.example.com', 8080, 'http', 'user_premium_001', 'secure_pass_001', 'active', 0, 156, 
     'US', 'Virginia', 'PremiumProxies Inc', 'High-speed residential proxy', '["residential", "premium", "fast"]', 250),
    
    ('proxy-us-west-1.example.com', 8080, 'http', 'user_premium_002', 'secure_pass_002', 'active', 1, 134, 
     'US', 'California', 'PremiumProxies Inc', 'West coast residential', '["residential", "premium"]', 180),
    
    -- European proxies
    ('proxy-eu-london.example.com', 3128, 'http', 'user_eu_001', 'eu_pass_001', 'active', 0, 89, 
     'GB', 'London', 'EuroProxy Solutions', 'London datacenter proxy', '["datacenter", "europe"]', 320),
    
    ('proxy-eu-frankfurt.example.com', 8080, 'https', 'user_eu_002', 'eu_pass_002', 'active', 2, 67, 
     'DE', 'Frankfurt', 'EuroProxy Solutions', 'Frankfurt HTTPS proxy', '["datacenter", "europe", "https"]', 280),
    
    -- Asian proxies
    ('proxy-asia-tokyo.example.com', 8080, 'http', 'user_asia_001', 'asia_pass_001', 'active', 1, 45, 
     'JP', 'Tokyo', 'AsiaProxy Network', 'Tokyo residential proxy', '["residential", "asia"]', 420),
    
    ('proxy-asia-singapore.example.com', 3128, 'http', NULL, NULL, 'active', 0, 23, 
     'SG', 'Singapore', 'AsiaProxy Network', 'No-auth Singapore proxy', '["datacenter", "asia", "no-auth"]', 380),
    
    -- SOCKS proxies
    ('socks-proxy-1.example.com', 1080, 'socks5', 'socks_user_001', 'socks_pass_001', 'active', 0, 78, 
     'US', 'Texas', 'SOCKS Proxy Pro', 'High-speed SOCKS5 proxy', '["socks5", "premium"]', 200),
    
    ('socks-proxy-2.example.com', 1080, 'socks4', NULL, NULL, 'active', 3, 34, 
     'CA', 'Toronto', 'Free SOCKS Network', 'Free SOCKS4 proxy', '["socks4", "free"]', 650),
    
    -- Medium performance proxies
    ('proxy-medium-1.example.com', 8080, 'http', 'medium_user_001', 'medium_pass_001', 'active', 2, 89, 
     'US', 'Oregon', 'MidTier Proxies', 'Standard performance proxy', '["standard"]', 450),
    
    ('proxy-medium-2.example.com', 3128, 'http', 'medium_user_002', 'medium_pass_002', 'active', 4, 67, 
     'FR', 'Paris', 'MidTier Proxies', 'European standard proxy', '["standard", "europe"]', 520),
    
    -- Slower/problematic proxies for testing error handling
    ('proxy-slow-1.example.com', 8080, 'http', 'slow_user_001', 'slow_pass_001', 'inactive', 3, 12, 
     'BR', 'São Paulo', 'Slow Proxy Network', 'Slower proxy for testing', '["slow", "testing"]', 1200),
    
    ('proxy-problematic.example.com', 8080, 'http', 'problem_user', 'problem_pass', 'inactive', 6, 5, 
     'IN', 'Mumbai', 'Unreliable Proxies', 'High error rate proxy', '["testing", "unreliable"]', 2500),
    
    -- Testing and development proxies
    ('proxy-test-1.example.com', 8080, 'http', 'test_user_001', 'test_pass_001', 'testing', 0, 0, 
     'US', 'Nevada', 'Testing Network', 'Proxy under testing', '["testing", "development"]', NULL),
    
    ('proxy-dev.example.com', 3128, 'http', NULL, NULL, 'active', 1, 156, 
     'US', 'Utah', 'Development Network', 'Development proxy - no auth', '["development", "no-auth"]', 300),
    
    -- International diversity
    ('proxy-au-sydney.example.com', 8080, 'http', 'au_user_001', 'au_pass_001', 'active', 1, 67, 
     'AU', 'Sydney', 'Oceania Proxy Solutions', 'Australian proxy', '["oceania", "residential"]', 380),
    
    ('proxy-mx-cancun.example.com', 8080, 'http', 'mx_user_001', 'mx_pass_001', 'active', 2, 89, 
     'MX', 'Cancún', 'Latin America Proxies', 'Mexican proxy server', '["latin-america"]', 480),
    
    -- Premium tier with very low latency
    ('premium-proxy-1.example.com', 8080, 'https', 'premium_001', 'ultra_secure_pass_001', 'active', 0, 234, 
     'US', 'New York', 'UltraProxy Premium', 'Ultra-premium low-latency', '["premium", "ultra-fast", "https"]', 95),
    
    ('premium-proxy-2.example.com', 8080, 'https', 'premium_002', 'ultra_secure_pass_002', 'active', 0, 198, 
     'US', 'California', 'UltraProxy Premium', 'West coast premium', '["premium", "ultra-fast", "https"]', 110),
    
    -- Failed proxies for realistic testing
    ('proxy-failed-1.example.com', 8080, 'http', 'failed_user', 'failed_pass', 'failed', 10, 3, 
     'XX', 'Unknown', 'Failed Network', 'Consistently failing proxy', '["failed", "testing"]', NULL),
    
    ('proxy-failed-2.example.com', 3128, 'http', NULL, NULL, 'failed', 8, 1, 
     'XX', 'Unknown', 'Dead Network', 'Dead proxy for testing', '["failed", "dead"]', NULL)

ON CONFLICT (address, port, username) DO NOTHING;

-- Update last_used timestamps for some proxies to simulate recent activity
UPDATE proxies 
SET last_used = NOW() - INTERVAL '5 minutes'
WHERE address IN (
    'proxy-us-east-1.example.com',
    'premium-proxy-1.example.com',
    'proxy-eu-london.example.com'
);

UPDATE proxies 
SET last_used = NOW() - INTERVAL '2 hours'
WHERE address IN (
    'proxy-us-west-1.example.com',
    'socks-proxy-1.example.com'
);

UPDATE proxies 
SET last_used = NOW() - INTERVAL '1 day'
WHERE address IN (
    'proxy-asia-tokyo.example.com',
    'proxy-medium-1.example.com'
);

-- Update last_tested timestamps
UPDATE proxies 
SET last_tested = NOW() - INTERVAL '30 minutes'
WHERE status = 'active';

UPDATE proxies 
SET last_tested = NOW() - INTERVAL '6 hours'
WHERE status = 'inactive';

UPDATE proxies 
SET last_tested = NOW() - INTERVAL '5 minutes'
WHERE status = 'testing';

-- Insert some sample usage logs for realistic data
INSERT INTO proxy_usage_logs (
    proxy_id, request_url, request_method, request_id, success, 
    response_code, response_time_ms, error_message, user_agent
) 
SELECT 
    p.id,
    'https://example.com/api/test',
    'GET',
    'test-request-' || generate_random_uuid()::text,
    (random() > 0.1)::boolean,  -- 90% success rate
    CASE WHEN (random() > 0.1) THEN 200 ELSE (ARRAY[404, 500, 502, 503])[floor(random() * 4 + 1)] END,
    p.response_time_ms + floor(random() * 100 - 50),  -- Add some variance
    CASE WHEN (random() <= 0.1) THEN 'Connection timeout' ELSE NULL END,
    'WebScraper-API/1.0'
FROM proxies p
WHERE p.status != 'failed'
AND random() > 0.3  -- Only 70% of proxies have recent logs
;

-- Display summary
DO $$
DECLARE
    total_proxies INTEGER;
    active_proxies INTEGER;
    premium_proxies INTEGER;
    countries_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_proxies FROM proxies;
    SELECT COUNT(*) INTO active_proxies FROM proxies WHERE status = 'active';
    SELECT COUNT(*) INTO premium_proxies FROM proxies WHERE tags LIKE '%premium%';
    SELECT COUNT(DISTINCT country) INTO countries_count FROM proxies WHERE country != 'XX';
    
    RAISE NOTICE '=== Sample Data Loaded Successfully ===';
    RAISE NOTICE 'Total proxies inserted: %', total_proxies;
    RAISE NOTICE 'Active proxies: %', active_proxies;
    RAISE NOTICE 'Premium proxies: %', premium_proxies;
    RAISE NOTICE 'Countries represented: %', countries_count;
    RAISE NOTICE 'Usage logs created: % entries', (SELECT COUNT(*) FROM proxy_usage_logs);
    RAISE NOTICE '======================================';
END $$; 