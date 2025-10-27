-- ClickHouse schema for message events (OLAP)

CREATE DATABASE IF NOT EXISTS voiceassistant;

-- Message events table (local)
CREATE TABLE IF NOT EXISTS voiceassistant.message_events_local ON CLUSTER '{cluster}' (
    event_id String,
    message_id String,
    conversation_id String,
    user_id String,
    tenant_id String,
    role String,
    content String,
    tokens_used UInt32,
    model String,
    cost_usd Float64,
    latency_ms UInt32,
    created_at DateTime,
    date Date DEFAULT toDate(created_at)
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/message_events_local', '{replica}')
PARTITION BY toYYYYMM(created_at)
ORDER BY (tenant_id, user_id, created_at)
TTL created_at + INTERVAL 90 DAY;

-- Message events distributed table
CREATE TABLE IF NOT EXISTS voiceassistant.message_events ON CLUSTER '{cluster}' AS voiceassistant.message_events_local
ENGINE = Distributed('{cluster}', voiceassistant, message_events_local, rand());

-- Materialized view for hourly aggregation
CREATE MATERIALIZED VIEW IF NOT EXISTS voiceassistant.message_stats_hourly ON CLUSTER '{cluster}'
ENGINE = ReplicatedSummingMergeTree('/clickhouse/tables/{shard}/message_stats_hourly', '{replica}')
PARTITION BY toYYYYMM(hour)
ORDER BY (tenant_id, model, hour)
AS SELECT
    tenant_id,
    model,
    toStartOfHour(created_at) as hour,
    count() as message_count,
    sum(tokens_used) as total_tokens,
    sum(cost_usd) as total_cost,
    avg(latency_ms) as avg_latency
FROM voiceassistant.message_events_local
GROUP BY tenant_id, model, hour;

-- User activity table
CREATE TABLE IF NOT EXISTS voiceassistant.user_activity_local ON CLUSTER '{cluster}' (
    user_id String,
    tenant_id String,
    action String,
    resource_type String,
    resource_id String,
    metadata String,
    created_at DateTime,
    date Date DEFAULT toDate(created_at)
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/user_activity_local', '{replica}')
PARTITION BY toYYYYMM(created_at)
ORDER BY (tenant_id, user_id, created_at)
TTL created_at + INTERVAL 90 DAY;

CREATE TABLE IF NOT EXISTS voiceassistant.user_activity ON CLUSTER '{cluster}' AS voiceassistant.user_activity_local
ENGINE = Distributed('{cluster}', voiceassistant, user_activity_local, rand());

