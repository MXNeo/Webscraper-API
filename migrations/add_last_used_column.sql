-- Migration script to add last_used column to proxies table
-- This fixes the "column 'last_used' of relation 'proxies' does not exist" error

-- Check if the column already exists before adding it
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'proxies' 
        AND column_name = 'last_used'
    ) THEN
        ALTER TABLE proxies ADD COLUMN last_used TIMESTAMP WITH TIME ZONE DEFAULT NULL;
        RAISE NOTICE 'Added last_used column to proxies table';
    ELSE
        RAISE NOTICE 'last_used column already exists in proxies table';
    END IF;
END
$$;

-- Create an index on last_used for better query performance
CREATE INDEX IF NOT EXISTS idx_proxies_last_used ON proxies(last_used);

-- Update existing records to have a reasonable last_used value (optional)
-- UPDATE proxies SET last_used = NOW() - INTERVAL '1 day' WHERE last_used IS NULL;

-- Verify the change
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'proxies' 
AND column_name = 'last_used'; 