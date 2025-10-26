-- Knowledge Service Schema
CREATE SCHEMA IF NOT EXISTS knowledge;

CREATE TABLE knowledge.collections (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type INTEGER NOT NULL DEFAULT 1,
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    document_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE knowledge.documents (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,
    collection_id VARCHAR(64),
    name VARCHAR(500) NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_path TEXT NOT NULL,
    status INTEGER NOT NULL DEFAULT 1,
    metadata JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_documents_user_id ON knowledge.documents(user_id) WHERE status != 5;
CREATE INDEX idx_documents_collection_id ON knowledge.documents(collection_id);
CREATE INDEX idx_collections_user_id ON knowledge.collections(user_id);

COMMENT ON TABLE knowledge.documents IS '文档表';
COMMENT ON TABLE knowledge.collections IS '集合表';

