-- OAuth2 和密码历史功能迁移脚本
-- Phase 2: 认证授权增强
-- 创建时间: 2025-10-27
-- 版本: v2.1.0

-- 设置搜索路径
SET search_path TO identity, public;

-- OAuth2 账号绑定表
CREATE TABLE IF NOT EXISTS identity.oauth2_accounts (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    provider VARCHAR(50) NOT NULL, -- 'google', 'github', 'wechat'
    provider_user_id VARCHAR(200) NOT NULL, -- Provider侧的用户ID
    email VARCHAR(255),
    name VARCHAR(255),
    avatar_url TEXT,
    access_token TEXT, -- 加密存储（应用层加密）
    refresh_token TEXT, -- 加密存储（应用层加密）
    token_expires_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 唯一约束：同一provider的同一user_id只能绑定一次
    CONSTRAINT uq_oauth2_provider_user UNIQUE (provider, provider_user_id),

    -- 外键约束
    CONSTRAINT fk_oauth2_user FOREIGN KEY (user_id)
        REFERENCES identity.users(id) ON DELETE CASCADE
);

-- 索引
CREATE INDEX idx_oauth2_accounts_user_id ON identity.oauth2_accounts(user_id);
CREATE INDEX idx_oauth2_accounts_provider ON identity.oauth2_accounts(provider);
CREATE INDEX idx_oauth2_accounts_email ON identity.oauth2_accounts(email);
CREATE INDEX idx_oauth2_accounts_created_at ON identity.oauth2_accounts(created_at DESC);

-- 密码历史表（防止重复使用最近N次密码）
CREATE TABLE IF NOT EXISTS identity.password_history (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    password_hash VARCHAR(255) NOT NULL, -- bcrypt hash
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    CONSTRAINT fk_password_history_user FOREIGN KEY (user_id)
        REFERENCES identity.users(id) ON DELETE CASCADE
);

-- 索引
CREATE INDEX idx_password_history_user_id ON identity.password_history(user_id);
CREATE INDEX idx_password_history_created_at ON identity.password_history(created_at DESC);

-- 密码策略配置表
CREATE TABLE IF NOT EXISTS identity.password_policies (
    id VARCHAR(64) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    tenant_id VARCHAR(64), -- NULL 表示全局策略
    min_length INTEGER NOT NULL DEFAULT 8,
    require_uppercase BOOLEAN NOT NULL DEFAULT true,
    require_lowercase BOOLEAN NOT NULL DEFAULT true,
    require_digit BOOLEAN NOT NULL DEFAULT true,
    require_special_char BOOLEAN NOT NULL DEFAULT true,
    prevent_reuse_count INTEGER NOT NULL DEFAULT 5, -- 防止重复使用最近N次密码
    max_age_days INTEGER, -- 密码最长使用天数，NULL表示不限制
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 每个租户只能有一个策略
    CONSTRAINT uq_password_policy_tenant UNIQUE (tenant_id)
);

-- 索引
CREATE INDEX idx_password_policies_tenant_id ON identity.password_policies(tenant_id);

-- 插入默认全局密码策略
INSERT INTO identity.password_policies
    (id, tenant_id, min_length, require_uppercase, require_lowercase, require_digit, require_special_char, prevent_reuse_count)
VALUES
    ('policy_default', NULL, 8, true, true, true, true, 5)
ON CONFLICT (tenant_id) DO NOTHING;

-- 触发器：自动更新 updated_at
CREATE TRIGGER update_oauth2_accounts_updated_at
    BEFORE UPDATE ON identity.oauth2_accounts
    FOR EACH ROW EXECUTE FUNCTION identity.update_updated_at_column();

CREATE TRIGGER update_password_policies_updated_at
    BEFORE UPDATE ON identity.password_policies
    FOR EACH ROW EXECUTE FUNCTION identity.update_updated_at_column();

-- 用户表增加字段：标记OAuth用户
ALTER TABLE identity.users
    ADD COLUMN IF NOT EXISTS auth_type VARCHAR(20) DEFAULT 'password',
    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS phone VARCHAR(20),
    ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT false;

-- 索引
CREATE INDEX IF NOT EXISTS idx_users_auth_type ON identity.users(auth_type);
CREATE INDEX IF NOT EXISTS idx_users_email_verified ON identity.users(email_verified);
CREATE INDEX IF NOT EXISTS idx_users_phone ON identity.users(phone) WHERE phone IS NOT NULL;

-- 注释
COMMENT ON TABLE identity.oauth2_accounts IS 'OAuth2账号绑定表';
COMMENT ON TABLE identity.password_history IS '密码历史记录表';
COMMENT ON TABLE identity.password_policies IS '密码策略配置表';

COMMENT ON COLUMN identity.users.auth_type IS '认证类型: password, oauth2, ldap';
COMMENT ON COLUMN identity.users.email_verified IS '邮箱是否已验证';
COMMENT ON COLUMN identity.users.phone IS '手机号';
COMMENT ON COLUMN identity.users.phone_verified IS '手机号是否已验证';

COMMENT ON COLUMN identity.oauth2_accounts.provider IS 'OAuth2提供商: google, github, wechat';
COMMENT ON COLUMN identity.oauth2_accounts.provider_user_id IS 'Provider侧的用户ID';
COMMENT ON COLUMN identity.oauth2_accounts.access_token IS '访问令牌（应用层加密）';
COMMENT ON COLUMN identity.oauth2_accounts.refresh_token IS '刷新令牌（应用层加密）';

COMMENT ON COLUMN identity.password_history.password_hash IS '历史密码的bcrypt哈希';

COMMENT ON COLUMN identity.password_policies.prevent_reuse_count IS '防止重复使用最近N次密码，0表示不限制';
COMMENT ON COLUMN identity.password_policies.max_age_days IS '密码最长使用天数，NULL表示不限制';
