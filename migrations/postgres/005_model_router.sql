-- Model Router Schema
CREATE SCHEMA IF NOT EXISTS model_router;

-- 模型表
CREATE TABLE IF NOT EXISTS model_router.models (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    endpoint VARCHAR(500) NOT NULL,
    api_key VARCHAR(500),
    max_tokens INT NOT NULL,
    context_window INT NOT NULL,
    input_price_per_k DECIMAL(10,6) NOT NULL DEFAULT 0,
    output_price_per_k DECIMAL(10,6) NOT NULL DEFAULT 0,
    priority INT NOT NULL DEFAULT 50,
    weight INT NOT NULL DEFAULT 100,
    timeout INT NOT NULL DEFAULT 30,
    retry_count INT NOT NULL DEFAULT 3,
    rate_limit INT NOT NULL DEFAULT 60,
    capabilities TEXT[],
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 模型指标表
CREATE TABLE IF NOT EXISTS model_router.model_metrics (
    model_id VARCHAR(64) PRIMARY KEY REFERENCES model_router.models(id) ON DELETE CASCADE,
    total_requests BIGINT NOT NULL DEFAULT 0,
    success_requests BIGINT NOT NULL DEFAULT 0,
    failed_requests BIGINT NOT NULL DEFAULT 0,
    avg_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
    p95_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
    p99_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_tokens BIGINT NOT NULL DEFAULT 0,
    total_cost DECIMAL(12,4) NOT NULL DEFAULT 0,
    error_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    last_request_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_models_name ON model_router.models(name);
CREATE INDEX idx_models_provider ON model_router.models(provider);
CREATE INDEX idx_models_type ON model_router.models(type);
CREATE INDEX idx_models_status ON model_router.models(status);
CREATE INDEX idx_models_priority ON model_router.models(priority DESC);
CREATE INDEX idx_models_type_status ON model_router.models(type, status);

-- 更新时间触发器
CREATE OR REPLACE FUNCTION model_router.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_models_updated_at BEFORE UPDATE ON model_router.models
FOR EACH ROW EXECUTE FUNCTION model_router.update_updated_at_column();

CREATE TRIGGER update_model_metrics_updated_at BEFORE UPDATE ON model_router.model_metrics
FOR EACH ROW EXECUTE FUNCTION model_router.update_updated_at_column();

-- 注释
COMMENT ON TABLE model_router.models IS '模型配置表';
COMMENT ON TABLE model_router.model_metrics IS '模型指标表';
