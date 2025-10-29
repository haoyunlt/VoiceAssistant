-- Knowledge Service Tables Migration
-- Created: 2025-10-29
-- Description: 创建 knowledge-service 所需的表结构（文档、版本、权限、审计日志）

-- ==================== Documents Table ====================

CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(100) PRIMARY KEY,
    knowledge_base_id VARCHAR(100) NOT NULL,
    name VARCHAR(500) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size INTEGER NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    file_url VARCHAR(1000),
    content TEXT,
    summary TEXT,
    status VARCHAR(50) NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    tenant_id VARCHAR(100) NOT NULL,
    uploaded_by VARCHAR(100) NOT NULL,
    metadata JSONB DEFAULT '{}',
    error_message TEXT,
    processed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for documents
CREATE INDEX IF NOT EXISTS idx_documents_knowledge_base ON documents(knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_kb ON documents(tenant_id, knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);

-- Comments
COMMENT ON TABLE documents IS '文档表';
COMMENT ON COLUMN documents.id IS '文档ID';
COMMENT ON COLUMN documents.knowledge_base_id IS '知识库ID';
COMMENT ON COLUMN documents.status IS '文档状态: uploaded, pending, processing, completed, failed, infected, deleted';

-- ==================== Chunks Table ====================

CREATE TABLE IF NOT EXISTS chunks (
    id VARCHAR(100) PRIMARY KEY,
    document_id VARCHAR(100) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    knowledge_base_id VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for chunks
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_document_sequence ON chunks(document_id, sequence);
CREATE INDEX IF NOT EXISTS idx_chunks_kb ON chunks(knowledge_base_id);

-- Comments
COMMENT ON TABLE chunks IS '文档块表';
COMMENT ON COLUMN chunks.id IS '块ID';
COMMENT ON COLUMN chunks.sequence IS '块序号';

-- ==================== Versions Table ====================

CREATE TABLE IF NOT EXISTS versions (
    id VARCHAR(100) PRIMARY KEY,
    knowledge_base_id VARCHAR(100) NOT NULL,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    description TEXT,
    created_by VARCHAR(100) NOT NULL,
    tenant_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Unique constraint and indexes for versions
CREATE UNIQUE INDEX IF NOT EXISTS idx_versions_kb_version ON versions(knowledge_base_id, version);
CREATE INDEX IF NOT EXISTS idx_versions_tenant ON versions(tenant_id);

-- Comments
COMMENT ON TABLE versions IS '版本表';
COMMENT ON COLUMN versions.version IS '版本号';
COMMENT ON COLUMN versions.snapshot IS '版本快照数据';

-- ==================== Roles Table ====================

CREATE TABLE IF NOT EXISTS roles (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    permissions JSONB NOT NULL,
    tenant_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Unique constraint and indexes for roles
CREATE UNIQUE INDEX IF NOT EXISTS idx_roles_tenant_name ON roles(tenant_id, name);

-- Comments
COMMENT ON TABLE roles IS '角色表';
COMMENT ON COLUMN roles.permissions IS '权限列表（JSON数组）';

-- ==================== User Roles Table ====================

CREATE TABLE IF NOT EXISTS user_roles (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    role_id VARCHAR(100) NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    tenant_id VARCHAR(100) NOT NULL,
    resource VARCHAR(200),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- Indexes for user_roles
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_user_tenant ON user_roles(user_id, tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role_id);

-- Comments
COMMENT ON TABLE user_roles IS '用户角色关联表';
COMMENT ON COLUMN user_roles.resource IS '可选：限定角色作用的资源范围';

-- ==================== Audit Logs Table ====================

CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(100) PRIMARY KEY,
    tenant_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(200),
    details TEXT,
    ip VARCHAR(45),
    user_agent VARCHAR(500),
    status VARCHAR(20) NOT NULL,
    error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for audit_logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_user_time ON audit_logs(tenant_id, user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action_time ON audit_logs(action, created_at);

-- Comments
COMMENT ON TABLE audit_logs IS '审计日志表';
COMMENT ON COLUMN audit_logs.action IS '操作类型';
COMMENT ON COLUMN audit_logs.status IS '状态: success, failed';

-- ==================== Default Roles ====================

-- Insert default roles for the default tenant
INSERT INTO roles (id, name, description, permissions, tenant_id, created_at, updated_at)
VALUES
    ('role_admin_default', 'Administrator', 'Full access to all resources',
     '[{"resource": "*", "action": "admin", "effect": "allow", "conditions": {}}]'::jsonb,
     'default', NOW(), NOW()),
    ('role_editor_default', 'Editor', 'Can read and write knowledge bases and documents',
     '[{"resource": "kb:*", "action": "write", "effect": "allow", "conditions": {}}, {"resource": "doc:*", "action": "write", "effect": "allow", "conditions": {}}]'::jsonb,
     'default', NOW(), NOW()),
    ('role_viewer_default', 'Viewer', 'Can only read knowledge bases and documents',
     '[{"resource": "kb:*", "action": "read", "effect": "allow", "conditions": {}}, {"resource": "doc:*", "action": "read", "effect": "allow", "conditions": {}}]'::jsonb,
     'default', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- ==================== Trigger for updated_at ====================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for documents table
DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for roles table
DROP TRIGGER IF EXISTS update_roles_updated_at ON roles;
CREATE TRIGGER update_roles_updated_at
    BEFORE UPDATE ON roles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
