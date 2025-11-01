-- =====================================================
-- Conversation Service - Index Optimization
-- =====================================================
-- Purpose: 优化查询性能，添加必要索引
-- Author: System
-- Date: 2024-11-01
-- =====================================================

-- ========================================
-- conversations 表索引优化
-- ========================================

-- 1. 租户+用户+状态组合索引（最常用的查询模式）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_tenant_user_status
    ON conversation.conversations(tenant_id, user_id, status)
    WHERE status != 'deleted';

COMMENT ON INDEX conversation.idx_conversations_tenant_user_status IS
    '租户+用户+状态组合索引，用于列表查询，排除已删除记录';

-- 2. 最近活跃时间索引（按活跃度排序）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_last_active
    ON conversation.conversations(last_active_at DESC)
    WHERE status = 'active';

COMMENT ON INDEX conversation.idx_conversations_last_active IS
    '最近活跃时间倒序索引，用于获取活跃对话';

-- 3. 创建时间索引（按创建时间排序）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_created_at
    ON conversation.conversations(created_at DESC);

COMMENT ON INDEX conversation.idx_conversations_created_at IS
    '创建时间倒序索引，用于时间范围查询';

-- 4. 用户+状态索引（用户维度查询）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_user_status
    ON conversation.conversations(user_id, status, last_active_at DESC)
    WHERE status != 'deleted';

COMMENT ON INDEX conversation.idx_conversations_user_status IS
    '用户+状态索引，用于用户对话列表查询';

-- 5. 设备 ID 索引（多设备同步）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_device_id
    ON conversation.conversations(device_id)
    WHERE device_id IS NOT NULL;

COMMENT ON INDEX conversation.idx_conversations_device_id IS
    '设备 ID 索引，用于多设备同步查询';

-- ========================================
-- messages 表索引优化
-- ========================================

-- 1. 对话+创建时间组合索引（最常用）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_conversation_created
    ON conversation.messages(conversation_id, created_at DESC)
    WHERE status != 'deleted';

COMMENT ON INDEX conversation.idx_messages_conversation_created IS
    '对话+创建时间倒序索引，用于获取对话消息列表';

-- 2. 用户+创建时间索引（用户消息历史）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_user_created
    ON conversation.messages(user_id, created_at DESC);

COMMENT ON INDEX conversation.idx_messages_user_created IS
    '用户+创建时间索引，用于用户消息历史查询';

-- 3. 对话+角色索引（按角色筛选）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_conversation_role
    ON conversation.messages(conversation_id, role, created_at DESC);

COMMENT ON INDEX conversation.idx_messages_conversation_role IS
    '对话+角色索引，用于按角色筛选消息';

-- 4. 全文搜索索引（PostgreSQL GIN）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_content_gin
    ON conversation.messages USING gin(to_tsvector('english', content));

COMMENT ON INDEX conversation.idx_messages_content_gin IS
    '消息内容全文搜索索引（英文）';

-- 5. 租户+创建时间索引（租户级查询）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_tenant_created
    ON conversation.messages(tenant_id, created_at DESC);

COMMENT ON INDEX conversation.idx_messages_tenant_created IS
    '租户+创建时间索引，用于租户级别统计';

-- 6. 父消息 ID 索引（回复线程）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_parent_id
    ON conversation.messages(parent_id)
    WHERE parent_id IS NOT NULL;

COMMENT ON INDEX conversation.idx_messages_parent_id IS
    '父消息 ID 索引，用于查询消息回复线程';

-- ========================================
-- 性能优化建议
-- ========================================

-- 1. 更新表统计信息
ANALYZE conversation.conversations;
ANALYZE conversation.messages;

-- 2. 设置合适的 work_mem（用于排序和哈希）
-- 在会话级别设置：SET work_mem = '64MB';

-- 3. 启用自动 VACUUM（确保表统计信息及时更新）
-- 在 postgresql.conf 中设置：
-- autovacuum = on
-- autovacuum_naptime = 1min

-- ========================================
-- 分区策略建议（可选，用于超大表）
-- ========================================

-- 按月分区 messages 表（示例，需要修改表结构）
/*
-- 创建分区表
CREATE TABLE conversation.messages_partitioned (
    LIKE conversation.messages INCLUDING ALL
) PARTITION BY RANGE (created_at);

-- 创建分区
CREATE TABLE conversation.messages_2024_11 PARTITION OF conversation.messages_partitioned
    FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');

CREATE TABLE conversation.messages_2024_12 PARTITION OF conversation.messages_partitioned
    FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');

-- 迁移数据
INSERT INTO conversation.messages_partitioned SELECT * FROM conversation.messages;

-- 重命名表
ALTER TABLE conversation.messages RENAME TO messages_old;
ALTER TABLE conversation.messages_partitioned RENAME TO messages;
*/

-- ========================================
-- 慢查询监控
-- ========================================

-- 启用慢查询日志（postgresql.conf）
-- log_min_duration_statement = 500ms  # 记录超过 500ms 的查询

-- 查询慢查询统计（需要 pg_stat_statements 扩展）
/*
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

SELECT
    query,
    calls,
    mean_exec_time,
    max_exec_time,
    stddev_exec_time
FROM pg_stat_statements
WHERE query LIKE '%conversation%' OR query LIKE '%message%'
ORDER BY mean_exec_time DESC
LIMIT 20;
*/

-- ========================================
-- 回滚脚本（如需移除索引）
-- ========================================

/*
-- 移除 conversations 表索引
DROP INDEX CONCURRENTLY IF EXISTS conversation.idx_conversations_tenant_user_status;
DROP INDEX CONCURRENTLY IF EXISTS conversation.idx_conversations_last_active;
DROP INDEX CONCURRENTLY IF EXISTS conversation.idx_conversations_created_at;
DROP INDEX CONCURRENTLY IF EXISTS conversation.idx_conversations_user_status;
DROP INDEX CONCURRENTLY IF EXISTS conversation.idx_conversations_device_id;

-- 移除 messages 表索引
DROP INDEX CONCURRENTLY IF EXISTS conversation.idx_messages_conversation_created;
DROP INDEX CONCURRENTLY IF EXISTS conversation.idx_messages_user_created;
DROP INDEX CONCURRENTLY IF EXISTS conversation.idx_messages_conversation_role;
DROP INDEX CONCURRENTLY IF EXISTS conversation.idx_messages_content_gin;
DROP INDEX CONCURRENTLY IF EXISTS conversation.idx_messages_tenant_created;
DROP INDEX CONCURRENTLY IF EXISTS conversation.idx_messages_parent_id;
*/
