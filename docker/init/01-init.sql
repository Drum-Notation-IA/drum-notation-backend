-- Database initialization script for Drum Notation Backend
-- This script runs automatically when the PostgreSQL container starts for the first time

-- Set client encoding and standards compliance
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

-- Create necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;
COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';

CREATE EXTENSION IF NOT EXISTS "pg_trgm" WITH SCHEMA public;
COMMENT ON EXTENSION "pg_trgm" IS 'text similarity measurement and index searching based on trigrams';

-- Set timezone to UTC
SET timezone = 'UTC';

-- Create application user (if needed for specific permissions)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user WITH LOGIN PASSWORD 'app_password';
    END IF;
END
$$;

-- Grant necessary permissions to application user
GRANT CONNECT ON DATABASE drum_notation TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT CREATE ON SCHEMA public TO app_user;

-- Create function to automatically update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create application configuration table
CREATE TABLE IF NOT EXISTS app_config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value TEXT,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial configuration
INSERT INTO app_config (key, value, description) VALUES
    ('app_name', 'Drum Notation Backend', 'Application name'),
    ('version', '1.0.0', 'Application version'),
    ('database_version', '1.0.0', 'Database schema version'),
    ('initialized_at', CURRENT_TIMESTAMP::TEXT, 'Database initialization timestamp'),
    ('max_file_size_mb', '100', 'Maximum file upload size in MB'),
    ('default_pagination_limit', '50', 'Default pagination limit for API responses')
ON CONFLICT (key) DO NOTHING;

-- Create trigger for app_config updated_at
DROP TRIGGER IF EXISTS update_app_config_updated_at ON app_config;
CREATE TRIGGER update_app_config_updated_at
    BEFORE UPDATE ON app_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions on app_config table
GRANT SELECT, INSERT, UPDATE, DELETE ON app_config TO app_user;
GRANT USAGE, SELECT ON SEQUENCE app_config_id_seq TO app_user;

-- Create indexes for commonly queried fields (these will be created by Alembic too)
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email ON users(email) WHERE deleted_at IS NULL;
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_username ON users(username) WHERE deleted_at IS NULL;
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_user_id ON videos(user_id) WHERE deleted_at IS NULL;
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notations_video_id ON notations(video_id) WHERE deleted_at IS NULL;

-- Performance optimizations
ALTER DATABASE drum_notation SET shared_preload_libraries = 'pg_stat_statements';
ALTER DATABASE drum_notation SET log_statement = 'none';
ALTER DATABASE drum_notation SET log_min_duration_statement = 1000;

-- Connection and memory settings for optimal performance
ALTER DATABASE drum_notation SET max_connections = 200;
ALTER DATABASE drum_notation SET shared_buffers = '256MB';
ALTER DATABASE drum_notation SET effective_cache_size = '1GB';
ALTER DATABASE drum_notation SET work_mem = '4MB';
ALTER DATABASE drum_notation SET maintenance_work_mem = '64MB';
ALTER DATABASE drum_notation SET random_page_cost = 1.1;
ALTER DATABASE drum_notation SET effective_io_concurrency = 200;

-- Set up full-text search configuration
ALTER DATABASE drum_notation SET default_text_search_config = 'pg_catalog.english';

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Drum Notation Backend database initialized successfully at %', CURRENT_TIMESTAMP;
    RAISE NOTICE 'Database: %, User: %', current_database(), current_user;
END
$$;

-- Final status check
SELECT
    'Database initialization completed!' as status,
    current_database() as database_name,
    version() as postgresql_version,
    CURRENT_TIMESTAMP as completed_at;
