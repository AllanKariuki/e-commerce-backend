-- =====================================================================
-- Bootstraps databases that Django expects on first Postgres startup.
-- Runs only when the postgres data volume is empty (first boot).
-- =====================================================================

-- Create the Keycloak database (the main DB is created by POSTGRES_DB).
SELECT 'CREATE DATABASE keycloak_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak_db')\gexec

-- pgvector extension lives per-database; enable it in the main app DB.
\c ecommerce_db
CREATE EXTENSION IF NOT EXISTS vector;
