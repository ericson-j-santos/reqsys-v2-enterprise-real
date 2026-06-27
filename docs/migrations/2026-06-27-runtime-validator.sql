-- Runtime Validator & Auto-Remediation Engine - schema proposal
-- Apply in SQL Server/PostgreSQL adaptation scripts when durable storage is enabled.

CREATE TABLE runtime_timeline_events (
    id VARCHAR(80) PRIMARY KEY,
    event_type VARCHAR(120) NOT NULL,
    title VARCHAR(240) NOT NULL,
    correlation_id VARCHAR(120) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE runtime_remediation_audit (
    id VARCHAR(80) PRIMARY KEY,
    incident_id VARCHAR(80),
    target VARCHAR(240) NOT NULL,
    action VARCHAR(80) NOT NULL,
    mode VARCHAR(40) NOT NULL,
    accepted BOOLEAN NOT NULL,
    attempts INTEGER NOT NULL,
    circuit_breaker_open BOOLEAN NOT NULL,
    correlation_id VARCHAR(120) NOT NULL,
    created_at TIMESTAMP NOT NULL
);
