-- Create schema for AI Orchestrator
CREATE SCHEMA IF NOT EXISTS ai_orchestrator;

-- Create tasks table
CREATE TABLE IF NOT EXISTS ai_orchestrator.tasks (
    id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 5,
    conversation_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,
    input JSONB NOT NULL,
    output JSONB,
    steps JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for better query performance
CREATE INDEX idx_tasks_type ON ai_orchestrator.tasks(type);
CREATE INDEX idx_tasks_status ON ai_orchestrator.tasks(status);
CREATE INDEX idx_tasks_priority ON ai_orchestrator.tasks(priority);
CREATE INDEX idx_tasks_conversation ON ai_orchestrator.tasks(conversation_id);
CREATE INDEX idx_tasks_user ON ai_orchestrator.tasks(user_id);
CREATE INDEX idx_tasks_tenant ON ai_orchestrator.tasks(tenant_id);
CREATE INDEX idx_tasks_created_at ON ai_orchestrator.tasks(created_at);
CREATE INDEX idx_tasks_completed_at ON ai_orchestrator.tasks(completed_at);

-- Create composite index for pending tasks query
CREATE INDEX idx_tasks_pending_priority ON ai_orchestrator.tasks(status, priority DESC, created_at ASC)
    WHERE status = 'pending';

-- Create composite index for tenant + status queries
CREATE INDEX idx_tasks_tenant_status ON ai_orchestrator.tasks(tenant_id, status, created_at DESC);

-- Add comments
COMMENT ON TABLE ai_orchestrator.tasks IS 'AI任务表，记录各类AI处理任务（RAG、Agent、Voice等）';
COMMENT ON COLUMN ai_orchestrator.tasks.id IS '任务ID，格式: task_{uuid}';
COMMENT ON COLUMN ai_orchestrator.tasks.type IS '任务类型: rag, agent, chat, voice, multimodal';
COMMENT ON COLUMN ai_orchestrator.tasks.status IS '任务状态: pending, running, completed, failed, cancelled';
COMMENT ON COLUMN ai_orchestrator.tasks.priority IS '任务优先级: 0=低, 5=普通, 10=高';
COMMENT ON COLUMN ai_orchestrator.tasks.conversation_id IS '关联的对话ID';
COMMENT ON COLUMN ai_orchestrator.tasks.user_id IS '用户ID';
COMMENT ON COLUMN ai_orchestrator.tasks.tenant_id IS '租户ID';
COMMENT ON COLUMN ai_orchestrator.tasks.input IS '任务输入数据（JSON）';
COMMENT ON COLUMN ai_orchestrator.tasks.output IS '任务输出结果（JSON）';
COMMENT ON COLUMN ai_orchestrator.tasks.steps IS '任务执行步骤（JSON数组）';
COMMENT ON COLUMN ai_orchestrator.tasks.metadata IS '任务元数据（JSON）';

-- Create trigger to automatically update updated_at
CREATE OR REPLACE FUNCTION ai_orchestrator.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON ai_orchestrator.tasks
    FOR EACH ROW EXECUTE FUNCTION ai_orchestrator.update_updated_at_column();

-- Grant permissions (adjust as needed)
-- GRANT USAGE ON SCHEMA ai_orchestrator TO app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ai_orchestrator.tasks TO app_user;
