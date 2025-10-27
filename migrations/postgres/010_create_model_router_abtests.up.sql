-- A/B测试表
CREATE SCHEMA IF NOT EXISTS model_router;

-- A/B测试配置表
CREATE TABLE IF NOT EXISTS model_router.ab_tests (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    strategy VARCHAR(50) NOT NULL DEFAULT 'consistent_hash',
    variants JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(64),

    CONSTRAINT check_time_range CHECK (end_time > start_time),
    CONSTRAINT check_status CHECK (status IN ('draft', 'running', 'paused', 'completed'))
);

-- 创建索引
CREATE INDEX idx_ab_tests_status ON model_router.ab_tests(status);
CREATE INDEX idx_ab_tests_start_time ON model_router.ab_tests(start_time);
CREATE INDEX idx_ab_tests_end_time ON model_router.ab_tests(end_time);
CREATE INDEX idx_ab_tests_created_by ON model_router.ab_tests(created_by);
CREATE INDEX idx_ab_tests_created_at ON model_router.ab_tests(created_at);

-- A/B测试指标表 (简化版，后续可迁移到ClickHouse)
CREATE TABLE IF NOT EXISTS model_router.ab_test_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id VARCHAR(64) NOT NULL,
    variant_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    success BOOLEAN NOT NULL,
    latency_ms FLOAT,
    tokens_used BIGINT,
    cost_usd FLOAT,
    model_id VARCHAR(100),
    metadata JSONB,

    CONSTRAINT fk_test FOREIGN KEY (test_id) REFERENCES model_router.ab_tests(id) ON DELETE CASCADE
);

-- 创建指标表索引
CREATE INDEX idx_ab_test_metrics_test_id ON model_router.ab_test_metrics(test_id);
CREATE INDEX idx_ab_test_metrics_variant_id ON model_router.ab_test_metrics(variant_id);
CREATE INDEX idx_ab_test_metrics_timestamp ON model_router.ab_test_metrics(timestamp);
CREATE INDEX idx_ab_test_metrics_user_id ON model_router.ab_test_metrics(user_id);

-- 创建物化视图用于快速查询聚合结果
CREATE MATERIALIZED VIEW IF NOT EXISTS model_router.ab_test_results AS
SELECT
    test_id,
    variant_id,
    COUNT(*) AS request_count,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) AS success_count,
    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) AS failure_count,
    AVG(latency_ms) AS avg_latency_ms,
    SUM(tokens_used) AS total_tokens,
    SUM(cost_usd) AS total_cost,
    MAX(timestamp) AS last_updated
FROM model_router.ab_test_metrics
GROUP BY test_id, variant_id;

-- 创建物化视图索引
CREATE UNIQUE INDEX idx_ab_test_results_test_variant
    ON model_router.ab_test_results(test_id, variant_id);

-- 创建触发器函数：自动更新 updated_at
CREATE OR REPLACE FUNCTION model_router.update_ab_test_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器
CREATE TRIGGER trigger_update_ab_test_updated_at
    BEFORE UPDATE ON model_router.ab_tests
    FOR EACH ROW
    EXECUTE FUNCTION model_router.update_ab_test_updated_at();

-- 添加注释
COMMENT ON TABLE model_router.ab_tests IS 'A/B测试配置表';
COMMENT ON TABLE model_router.ab_test_metrics IS 'A/B测试指标记录表';
COMMENT ON MATERIALIZED VIEW model_router.ab_test_results IS 'A/B测试聚合结果物化视图';

COMMENT ON COLUMN model_router.ab_tests.id IS '测试ID';
COMMENT ON COLUMN model_router.ab_tests.name IS '测试名称（唯一）';
COMMENT ON COLUMN model_router.ab_tests.status IS '测试状态: draft/running/paused/completed';
COMMENT ON COLUMN model_router.ab_tests.strategy IS '分流策略: consistent_hash/weighted_random';
COMMENT ON COLUMN model_router.ab_tests.variants IS '变体配置（JSON格式）';

-- 插入示例数据（可选）
INSERT INTO model_router.ab_tests (
    id,
    name,
    description,
    start_time,
    end_time,
    status,
    strategy,
    variants,
    created_by
) VALUES (
    'test_example_001',
    'GPT-4 vs Claude-3 Performance Test',
    '比较GPT-4和Claude-3在客服场景下的性能表现',
    NOW(),
    NOW() + INTERVAL '7 days',
    'draft',
    'consistent_hash',
    '[
        {
            "id": "variant_gpt4",
            "name": "GPT-4 Turbo",
            "model_id": "gpt-4-turbo-preview",
            "weight": 0.5,
            "description": "OpenAI GPT-4 Turbo"
        },
        {
            "id": "variant_claude3",
            "name": "Claude-3 Opus",
            "model_id": "claude-3-opus-20240229",
            "weight": 0.5,
            "description": "Anthropic Claude-3 Opus"
        }
    ]'::jsonb,
    'system'
) ON CONFLICT (name) DO NOTHING;
