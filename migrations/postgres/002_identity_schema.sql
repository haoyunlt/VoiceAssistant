-- Identity Service Schema 迁移脚本
-- 创建时间: 2025-10-26
-- 版本: v2.0.0

-- 创建 identity schema
CREATE SCHEMA IF NOT EXISTS identity;

-- 设置搜索路径
SET search_path TO identity, public;

-- 用户表
CREATE TABLE IF NOT EXISTS identity.users (
    id VARCHAR(64) PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL,
    display_name VARCHAR(100),
    password_hash VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    tenant_id VARCHAR(64),
    roles TEXT[] DEFAULT ARRAY['user']::TEXT[],
    status INTEGER NOT NULL DEFAULT 1, -- 1=Active, 2=Inactive, 3=Suspended, 4=Deleted
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

-- 索引
CREATE INDEX idx_users_email ON identity.users(email) WHERE status != 4;
CREATE INDEX idx_users_tenant_id ON identity.users(tenant_id) WHERE status != 4;
CREATE INDEX idx_users_created_at ON identity.users(created_at DESC);
CREATE INDEX idx_users_status ON identity.users(status);

-- 租户表
CREATE TABLE IF NOT EXISTS identity.tenants (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    status INTEGER NOT NULL DEFAULT 1, -- 1=Trial, 2=Active, 3=Suspended, 4=Expired
    
    -- 配额
    quota_max_users BIGINT NOT NULL DEFAULT 10,
    quota_max_documents BIGINT NOT NULL DEFAULT 100,
    quota_max_storage_bytes BIGINT NOT NULL DEFAULT 10737418240, -- 10GB
    quota_max_api_calls_per_day BIGINT NOT NULL DEFAULT 10000,
    quota_max_tokens_per_month BIGINT NOT NULL DEFAULT 1000000,
    
    -- 用量
    usage_user_count BIGINT NOT NULL DEFAULT 0,
    usage_document_count BIGINT NOT NULL DEFAULT 0,
    usage_storage_bytes BIGINT NOT NULL DEFAULT 0,
    usage_api_calls_today BIGINT NOT NULL DEFAULT 0,
    usage_tokens_this_month BIGINT NOT NULL DEFAULT 0,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_tenants_name ON identity.tenants(name);
CREATE INDEX idx_tenants_status ON identity.tenants(status);

-- 角色表
CREATE TABLE IF NOT EXISTS identity.roles (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    permissions TEXT[] DEFAULT ARRAY[]::TEXT[],
    tenant_id VARCHAR(64), -- NULL 表示系统级角色
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_roles_name ON identity.roles(name);
CREATE INDEX idx_roles_tenant_id ON identity.roles(tenant_id);

-- 用户角色关联表（多对多）
CREATE TABLE IF NOT EXISTS identity.user_roles (
    user_id VARCHAR(64) NOT NULL,
    role_id VARCHAR(64) NOT NULL,
    granted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

-- 索引
CREATE INDEX idx_user_roles_user_id ON identity.user_roles(user_id);
CREATE INDEX idx_user_roles_role_id ON identity.user_roles(role_id);

-- Token 黑名单表（用于登出）
CREATE TABLE IF NOT EXISTS identity.token_blacklist (
    token_hash VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_token_blacklist_expires_at ON identity.token_blacklist(expires_at);
CREATE INDEX idx_token_blacklist_user_id ON identity.token_blacklist(user_id);

-- 审计日志表
CREATE TABLE IF NOT EXISTS identity.audit_logs (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64),
    tenant_id VARCHAR(64),
    action VARCHAR(100) NOT NULL, -- 操作类型，如 "login", "logout", "create_user"
    resource_type VARCHAR(100),   -- 资源类型，如 "user", "tenant"
    resource_id VARCHAR(64),      -- 资源ID
    ip_address INET,
    user_agent TEXT,
    status VARCHAR(50) NOT NULL,  -- "success" 或 "failure"
    details JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_audit_logs_user_id ON identity.audit_logs(user_id);
CREATE INDEX idx_audit_logs_tenant_id ON identity.audit_logs(tenant_id);
CREATE INDEX idx_audit_logs_created_at ON identity.audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_action ON identity.audit_logs(action);

-- 插入系统默认角色
INSERT INTO identity.roles (id, name, display_name, permissions, tenant_id) VALUES
    ('role_admin', 'admin', '管理员', ARRAY['admin:*']::TEXT[], NULL),
    ('role_user', 'user', '普通用户', ARRAY['user:read', 'user:write']::TEXT[], NULL),
    ('role_guest', 'guest', '访客', ARRAY['user:read']::TEXT[], NULL)
ON CONFLICT (name) DO NOTHING;

-- 创建默认租户（用于测试）
INSERT INTO identity.tenants (id, name, display_name, status) VALUES
    ('tenant_default', 'default', '默认租户', 2)
ON CONFLICT (name) DO NOTHING;

-- 函数：自动更新 updated_at
CREATE OR REPLACE FUNCTION identity.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 触发器
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON identity.users
    FOR EACH ROW EXECUTE FUNCTION identity.update_updated_at_column();

CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON identity.tenants
    FOR EACH ROW EXECUTE FUNCTION identity.update_updated_at_column();

CREATE TRIGGER update_roles_updated_at BEFORE UPDATE ON identity.roles
    FOR EACH ROW EXECUTE FUNCTION identity.update_updated_at_column();

-- 注释
COMMENT ON TABLE identity.users IS '用户表';
COMMENT ON TABLE identity.tenants IS '租户表';
COMMENT ON TABLE identity.roles IS '角色表';
COMMENT ON TABLE identity.user_roles IS '用户角色关联表';
COMMENT ON TABLE identity.token_blacklist IS 'Token黑名单表（用于登出）';
COMMENT ON TABLE identity.audit_logs IS '审计日志表';

