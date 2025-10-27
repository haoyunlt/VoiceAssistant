-- 创建 model_router schema（如果不存在）
CREATE SCHEMA IF NOT EXISTS model_router;

-- 创建 A/B 测试配置表
CREATE TABLE IF NOT EXISTS model_router.ab_tests (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    variants JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(64)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ab_tests_status ON model_router.ab_tests(status);
CREATE INDEX IF NOT EXISTS idx_ab_tests_start_time ON model_router.ab_tests(start_time);
CREATE INDEX IF NOT EXISTS idx_ab_tests_end_time ON model_router.ab_tests(end_time);
CREATE INDEX IF NOT EXISTS idx_ab_tests_created_at ON model_router.ab_tests(created_at);
CREATE INDEX IF NOT EXISTS idx_ab_tests_created_by ON model_router.ab_tests(created_by);

-- 添加注释
COMMENT ON TABLE model_router.ab_tests IS 'A/B测试配置表';
COMMENT ON COLUMN model_router.ab_tests.id IS '测试ID';
COMMENT ON COLUMN model_router.ab_tests.name IS '测试名称';
COMMENT ON COLUMN model_router.ab_tests.description IS '测试描述';
COMMENT ON COLUMN model_router.ab_tests.start_time IS '开始时间';
COMMENT ON COLUMN model_router.ab_tests.end_time IS '结束时间';
COMMENT ON COLUMN model_router.ab_tests.status IS '状态: draft/running/paused/completed';
COMMENT ON COLUMN model_router.ab_tests.strategy IS '选择策略: consistent_hash/weighted_random';
COMMENT ON COLUMN model_router.ab_tests.variants IS '变体配置(JSON)';
COMMENT ON COLUMN model_router.ab_tests.metadata IS '元数据(JSON)';
COMMENT ON COLUMN model_router.ab_tests.created_at IS '创建时间';
COMMENT ON COLUMN model_router.ab_tests.updated_at IS '更新时间';
COMMENT ON COLUMN model_router.ab_tests.created_by IS '创建人';

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION model_router.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_ab_tests_updated_at
    BEFORE UPDATE ON model_router.ab_tests
    FOR EACH ROW
    EXECUTE FUNCTION model_router.update_updated_at_column();

