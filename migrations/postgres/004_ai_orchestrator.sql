-- AI Orchestrator Schema
CREATE SCHEMA IF NOT EXISTS ai_orchestrator;

-- 任务表
CREATE TABLE IF NOT EXISTS ai_orchestrator.tasks (
    id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    priority INT NOT NULL DEFAULT 5,
    conversation_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,
    input JSONB,
    output JSONB,
    steps JSONB,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- 索引
CREATE INDEX idx_tasks_type ON ai_orchestrator.tasks(type);
CREATE INDEX idx_tasks_status ON ai_orchestrator.tasks(status);
CREATE INDEX idx_tasks_priority ON ai_orchestrator.tasks(priority DESC);
CREATE INDEX idx_tasks_conversation ON ai_orchestrator.tasks(conversation_id);
CREATE INDEX idx_tasks_user ON ai_orchestrator.tasks(user_id);
CREATE INDEX idx_tasks_tenant ON ai_orchestrator.tasks(tenant_id);
CREATE INDEX idx_tasks_created_at ON ai_orchestrator.tasks(created_at DESC);

-- 复合索引：租户 + 状态
CREATE INDEX idx_tasks_tenant_status ON ai_orchestrator.tasks(tenant_id, status);

-- 复合索引：状态 + 优先级（用于任务队列）
CREATE INDEX idx_tasks_status_priority ON ai_orchestrator.tasks(status, priority DESC, created_at ASC);

-- 更新时间触发器
CREATE OR REPLACE FUNCTION ai_orchestrator.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON ai_orchestrator.tasks
FOR EACH ROW EXECUTE FUNCTION ai_orchestrator.update_updated_at_column();

-- 任务执行日志表（可选，用于审计）
CREATE TABLE IF NOT EXISTS ai_orchestrator.task_execution_logs (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL REFERENCES ai_orchestrator.tasks(id),
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_logs_task_id ON ai_orchestrator.task_execution_logs(task_id);
CREATE INDEX idx_task_logs_created_at ON ai_orchestrator.task_execution_logs(created_at DESC);

-- 注释
COMMENT ON TABLE ai_orchestrator.tasks IS 'AI任务表';
COMMENT ON COLUMN ai_orchestrator.tasks.id IS '任务ID';
COMMENT ON COLUMN ai_orchestrator.tasks.type IS '任务类型：rag/agent/chat/voice/multimodal';
COMMENT ON COLUMN ai_orchestrator.tasks.status IS '任务状态：pending/running/completed/failed/cancelled';
COMMENT ON COLUMN ai_orchestrator.tasks.priority IS '任务优先级：0-10';
COMMENT ON COLUMN ai_orchestrator.tasks.conversation_id IS '对话ID';
COMMENT ON COLUMN ai_orchestrator.tasks.user_id IS '用户ID';
COMMENT ON COLUMN ai_orchestrator.tasks.tenant_id IS '租户ID';
COMMENT ON COLUMN ai_orchestrator.tasks.input IS '任务输入（JSON）';
COMMENT ON COLUMN ai_orchestrator.tasks.output IS '任务输出（JSON）';
COMMENT ON COLUMN ai_orchestrator.tasks.steps IS '执行步骤（JSON数组）';
COMMENT ON COLUMN ai_orchestrator.tasks.metadata IS '元数据（JSON）';
