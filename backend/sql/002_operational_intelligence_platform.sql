CREATE TABLE operational_events (
    id BIGINT IDENTITY PRIMARY KEY,
    correlation_id UNIQUEIDENTIFIER NOT NULL,
    event_type NVARCHAR(120) NOT NULL,
    source_name NVARCHAR(160) NOT NULL,
    environment_name NVARCHAR(50) NOT NULL,
    severity NVARCHAR(30) NOT NULL,
    status NVARCHAR(50) NOT NULL,
    score INT NULL,
    payload_json NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE runtime_metrics (
    id BIGINT IDENTITY PRIMARY KEY,
    correlation_id UNIQUEIDENTIFIER NOT NULL,
    metric_name NVARCHAR(160) NOT NULL,
    metric_value DECIMAL(18,4) NOT NULL,
    metric_unit NVARCHAR(40) NOT NULL,
    source_name NVARCHAR(160) NOT NULL,
    environment_name NVARCHAR(50) NOT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE dead_letter_queue (
    id BIGINT IDENTITY PRIMARY KEY,
    correlation_id UNIQUEIDENTIFIER NOT NULL,
    operation_name NVARCHAR(255) NOT NULL,
    payload_json NVARCHAR(MAX) NOT NULL,
    failure_reason NVARCHAR(MAX) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    status NVARCHAR(50) NOT NULL DEFAULT 'OPEN',
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    resolved_at DATETIME2 NULL
);

CREATE INDEX IX_operational_events_correlation_id ON operational_events(correlation_id);
CREATE INDEX IX_runtime_metrics_correlation_id ON runtime_metrics(correlation_id);
CREATE INDEX IX_dead_letter_queue_status ON dead_letter_queue(status);
