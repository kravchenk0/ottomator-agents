-- Migration: 001_initial_schema
-- Description: Initial schema setup for agentic RAG with pgvector

-- Check if migration has already been applied
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'schema_migrations') THEN
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    END IF;
    
    IF EXISTS (SELECT 1 FROM schema_migrations WHERE version = 1) THEN
        RAISE NOTICE 'Migration 001 has already been applied';
        RETURN;
    END IF;
END $$;

-- Apply migration
\i ../schema.sql

-- Record migration
INSERT INTO schema_migrations (version) VALUES (1);