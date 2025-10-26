-- 创建 conversation schema
CREATE SCHEMA IF NOT EXISTS conversation;

-- 对话表
CREATE TABLE IF NOT EXISTS conversation.conversations (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    mode VARCHAR(20) NOT NULL,  -- text, voice, video
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, paused, archived, deleted
    context_json JSONB,
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_conversations_tenant_user ON conversation.conversations(tenant_id, user_id);
CREATE INDEX idx_conversations_status ON conversation.conversations(status);
CREATE INDEX idx_conversations_last_active ON conversation.conversations(last_active_at DESC);

-- 消息表
CREATE TABLE IF NOT EXISTS conversation.messages (
    id VARCHAR(64) PRIMARY KEY,
    conversation_id VARCHAR(64) NOT NULL REFERENCES conversation.conversations(id),
    tenant_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- user, assistant, system, tool
    content TEXT NOT NULL,
    content_type VARCHAR(20) NOT NULL DEFAULT 'text',  -- text, audio, image, video
    tokens INTEGER DEFAULT 0,
    model VARCHAR(100),
    provider VARCHAR(50),
    metadata_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_messages_conversation ON conversation.messages(conversation_id, created_at);
CREATE INDEX idx_messages_user ON conversation.messages(user_id);
CREATE INDEX idx_messages_tenant ON conversation.messages(tenant_id);

-- 添加注释
COMMENT ON TABLE conversation.conversations IS '对话表';
COMMENT ON TABLE conversation.messages IS '消息表';

COMMENT ON COLUMN conversation.conversations.id IS '对话ID';
COMMENT ON COLUMN conversation.conversations.tenant_id IS '租户ID';
COMMENT ON COLUMN conversation.conversations.user_id IS '用户ID';
COMMENT ON COLUMN conversation.conversations.title IS '对话标题';
COMMENT ON COLUMN conversation.conversations.mode IS '对话模式';
COMMENT ON COLUMN conversation.conversations.status IS '对话状态';
COMMENT ON COLUMN conversation.conversations.context_json IS '上下文配置';
COMMENT ON COLUMN conversation.conversations.last_active_at IS '最后活跃时间';

COMMENT ON COLUMN conversation.messages.id IS '消息ID';
COMMENT ON COLUMN conversation.messages.conversation_id IS '对话ID';
COMMENT ON COLUMN conversation.messages.role IS '消息角色';
COMMENT ON COLUMN conversation.messages.content IS '消息内容';
COMMENT ON COLUMN conversation.messages.tokens IS 'Token数量';
