-- Notification Service Schema
CREATE SCHEMA IF NOT EXISTS notification;

-- 通知表
CREATE TABLE IF NOT EXISTS notification.notifications (
    id VARCHAR(64) PRIMARY KEY,
    channel VARCHAR(20) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    template_id VARCHAR(64),
    subject VARCHAR(500),
    content TEXT,
    recipient VARCHAR(255) NOT NULL,
    metadata JSONB,
    scheduled_at TIMESTAMP,
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    error_msg TEXT,
    retry_count INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 3,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 模板表
CREATE TABLE IF NOT EXISTS notification.templates (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(20) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,
    subject VARCHAR(500),
    content TEXT NOT NULL,
    variables TEXT[],
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_notifications_channel ON notification.notifications(channel);
CREATE INDEX idx_notifications_status ON notification.notifications(status);
CREATE INDEX idx_notifications_user ON notification.notifications(user_id);
CREATE INDEX idx_notifications_tenant ON notification.notifications(tenant_id);
CREATE INDEX idx_notifications_scheduled ON notification.notifications(scheduled_at);
CREATE INDEX idx_notifications_created_at ON notification.notifications(created_at DESC);

CREATE INDEX idx_templates_name ON notification.templates(name);
CREATE INDEX idx_templates_type ON notification.templates(type);
CREATE INDEX idx_templates_tenant ON notification.templates(tenant_id);
CREATE INDEX idx_templates_is_active ON notification.templates(is_active);

-- 更新时间触发器
CREATE OR REPLACE FUNCTION notification.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_notifications_updated_at BEFORE UPDATE ON notification.notifications
FOR EACH ROW EXECUTE FUNCTION notification.update_updated_at_column();

CREATE TRIGGER update_templates_updated_at BEFORE UPDATE ON notification.templates
FOR EACH ROW EXECUTE FUNCTION notification.update_updated_at_column();

-- 注释
COMMENT ON TABLE notification.notifications IS '通知表';
COMMENT ON TABLE notification.templates IS '通知模板表';
