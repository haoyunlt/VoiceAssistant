-- Conversation Service Schema 迁移脚本
-- 创建时间: 2025-10-26
-- 版本: v2.0.0

-- 创建 conversation schema
CREATE SCHEMA IF NOT EXISTS conversation;

-- 设置搜索路径
SET search_path TO conversation, public;

-- 会话表
CREATE TABLE IF NOT EXISTS conversation.conversations (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,
    title VARCHAR(500),
    mode INTEGER NOT NULL DEFAULT 1, -- 1=Chat, 2=Agent, 3=Workflow, 4=Voice
    status INTEGER NOT NULL DEFAULT 1, -- 1=Active, 2=Archived, 3=Deleted
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP,
    message_count INTEGER NOT NULL DEFAULT 0
);

-- 索引
CREATE INDEX idx_conversations_user_id ON conversation.conversations(user_id) WHERE status != 3;
CREATE INDEX idx_conversations_tenant_id ON conversation.conversations(tenant_id) WHERE status != 3;
CREATE INDEX idx_conversations_status ON conversation.conversations(status);
CREATE INDEX idx_conversations_mode ON conversation.conversations(mode);
CREATE INDEX idx_conversations_created_at ON conversation.conversations(created_at DESC);
CREATE INDEX idx_conversations_last_message_at ON conversation.conversations(last_message_at DESC NULLS LAST) WHERE status = 1;

-- 消息表
CREATE TABLE IF NOT EXISTS conversation.messages (
    id VARCHAR(64) PRIMARY KEY,
    conversation_id VARCHAR(64) NOT NULL,
    role INTEGER NOT NULL, -- 1=User, 2=Assistant, 3=System, 4=Tool
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_messages_conversation_id ON conversation.messages(conversation_id, created_at DESC);
CREATE INDEX idx_messages_created_at ON conversation.messages(created_at DESC);
CREATE INDEX idx_messages_role ON conversation.messages(role);

-- 外键约束
ALTER TABLE conversation.messages 
    ADD CONSTRAINT fk_messages_conversation 
    FOREIGN KEY (conversation_id) 
    REFERENCES conversation.conversations(id) 
    ON DELETE CASCADE;

-- 参与者表（多人对话场景）
CREATE TABLE IF NOT EXISTS conversation.participants (
    conversation_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'member', -- owner, member, viewer
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (conversation_id, user_id)
);

-- 索引
CREATE INDEX idx_participants_user_id ON conversation.participants(user_id);
CREATE INDEX idx_participants_conversation_id ON conversation.participants(conversation_id);

-- 外键约束
ALTER TABLE conversation.participants 
    ADD CONSTRAINT fk_participants_conversation 
    FOREIGN KEY (conversation_id) 
    REFERENCES conversation.conversations(id) 
    ON DELETE CASCADE;

-- 函数：自动更新 updated_at
CREATE OR REPLACE FUNCTION conversation.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 触发器
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversation.conversations
    FOR EACH ROW EXECUTE FUNCTION conversation.update_updated_at_column();

-- 函数：自动更新会话的最后消息时间和消息计数
CREATE OR REPLACE FUNCTION conversation.update_conversation_on_message()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversation.conversations
    SET last_message_at = NEW.created_at,
        message_count = message_count + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 触发器
CREATE TRIGGER update_conversation_after_message AFTER INSERT ON conversation.messages
    FOR EACH ROW EXECUTE FUNCTION conversation.update_conversation_on_message();

-- 注释
COMMENT ON TABLE conversation.conversations IS '会话表';
COMMENT ON TABLE conversation.messages IS '消息表';
COMMENT ON TABLE conversation.participants IS '会话参与者表';

COMMENT ON COLUMN conversation.conversations.mode IS '会话模式：1=Chat, 2=Agent, 3=Workflow, 4=Voice';
COMMENT ON COLUMN conversation.conversations.status IS '会话状态：1=Active, 2=Archived, 3=Deleted';
COMMENT ON COLUMN conversation.messages.role IS '消息角色：1=User, 2=Assistant, 3=System, 4=Tool';

