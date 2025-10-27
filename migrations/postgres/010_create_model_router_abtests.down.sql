-- 删除触发器
DROP TRIGGER IF EXISTS trigger_update_ab_test_updated_at ON model_router.ab_tests;

-- 删除触发器函数
DROP FUNCTION IF EXISTS model_router.update_ab_test_updated_at();

-- 删除物化视图
DROP MATERIALIZED VIEW IF EXISTS model_router.ab_test_results;

-- 删除表（级联删除外键约束）
DROP TABLE IF EXISTS model_router.ab_test_metrics CASCADE;
DROP TABLE IF EXISTS model_router.ab_tests CASCADE;

-- 可选：删除schema（如果不再需要）
-- DROP SCHEMA IF EXISTS model_router CASCADE;
