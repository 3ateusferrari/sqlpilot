-- Database Roles & Internal Audit Schema

-- 1. Create Read-Only User for Agent Execution
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sqlpilot_readonly') THEN
        CREATE ROLE sqlpilot_readonly WITH LOGIN PASSWORD 'readonly_pass';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE chinook TO sqlpilot_readonly;
GRANT USAGE ON SCHEMA public TO sqlpilot_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sqlpilot_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sqlpilot_readonly;
ALTER ROLE sqlpilot_readonly SET default_transaction_read_only = on;
ALTER ROLE sqlpilot_readonly SET statement_timeout = '5000ms';

-- 2. Create Internal Schema and Audit Logs Table
CREATE SCHEMA IF NOT EXISTS internal;

CREATE TABLE IF NOT EXISTS internal.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id TEXT NOT NULL,
    pergunta TEXT NOT NULL,
    sql_original TEXT NOT NULL,
    nivel_risco TEXT NOT NULL,
    motivos_risco JSONB NOT NULL,
    acao_humana TEXT NOT NULL,
    sql_final TEXT,
    feedback TEXT,
    revisor TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for searching audit logs by thread_id
CREATE INDEX IF NOT EXISTS idx_audit_logs_thread_id ON internal.audit_logs(thread_id);
