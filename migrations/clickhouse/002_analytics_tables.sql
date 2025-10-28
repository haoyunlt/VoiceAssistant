-- Analytics service tables

-- Usage metrics table
CREATE TABLE IF NOT EXISTS voiceassistant.usage_metrics (
    id String,
    tenant_id String,
    user_id String,
    request_id String,
    model_name String,
    endpoint String,
    method String,
    status String,
    total_tokens UInt32,
    prompt_tokens UInt32,
    completion_tokens UInt32,
    cost Float64,
    response_time_ms Float64,
    timestamp DateTime DEFAULT now(),
    date Date DEFAULT toDate(timestamp)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (tenant_id, user_id, timestamp)
TTL timestamp + INTERVAL 90 DAY;

-- Model usage statistics (hourly aggregation)
CREATE MATERIALIZED VIEW IF NOT EXISTS voiceassistant.model_usage_hourly
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (tenant_id, model_name, hour)
AS SELECT
    tenant_id,
    model_name,
    toStartOfHour(timestamp) as hour,
    count() as request_count,
    sum(total_tokens) as total_tokens,
    sum(cost) as total_cost,
    avg(response_time_ms) as avg_response_time,
    countIf(status = 'error') as error_count
FROM voiceassistant.usage_metrics
GROUP BY tenant_id, model_name, hour;

-- User behavior statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS voiceassistant.user_behavior_daily
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (tenant_id, user_id, day)
AS SELECT
    tenant_id,
    user_id,
    toDate(timestamp) as day,
    count() as request_count,
    sum(total_tokens) as total_tokens,
    sum(cost) as total_cost,
    uniq(model_name) as unique_models_used
FROM voiceassistant.usage_metrics
GROUP BY tenant_id, user_id, day;

-- Cost breakdown by tenant and model
CREATE MATERIALIZED VIEW IF NOT EXISTS voiceassistant.cost_breakdown_daily
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (tenant_id, model_name, day)
AS SELECT
    tenant_id,
    model_name,
    toDate(timestamp) as day,
    sum(cost) as total_cost,
    sum(prompt_tokens) as total_prompt_tokens,
    sum(completion_tokens) as total_completion_tokens,
    count() as request_count
FROM voiceassistant.usage_metrics
GROUP BY tenant_id, model_name, day;
