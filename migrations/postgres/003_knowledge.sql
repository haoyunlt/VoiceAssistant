-- Knowledge Service Schema
CREATE SCHEMA IF NOT EXISTS knowledge;

-- 启用向量扩展（如果使用pgvector）
-- CREATE EXTENSION IF NOT EXISTS vector;

-- 知识库表
CREATE TABLE IF NOT EXISTS knowledge.knowledge_bases (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,
    created_by VARCHAR(64) NOT NULL,
    embedding_model VARCHAR(50) NOT NULL,
    embedding_dim INT NOT NULL,
    chunk_size INT NOT NULL,
    chunk_overlap INT NOT NULL,
    settings JSONB,
    document_count INT NOT NULL DEFAULT 0,
    chunk_count INT NOT NULL DEFAULT 0,
    total_size BIGINT NOT NULL DEFAULT 0,
    last_indexed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 文档表
CREATE TABLE IF NOT EXISTS knowledge.documents (
    id VARCHAR(64) PRIMARY KEY,
    knowledge_base_id VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    file_size BIGINT NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_url VARCHAR(500),
    content TEXT,
    summary TEXT,
    status VARCHAR(20) NOT NULL,
    chunk_count INT NOT NULL DEFAULT 0,
    tenant_id VARCHAR(64) NOT NULL,
    uploaded_by VARCHAR(64) NOT NULL,
    metadata JSONB,
    error_message TEXT,
    processed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (knowledge_base_id) REFERENCES knowledge.knowledge_bases(id) ON DELETE CASCADE
);

-- 分块表
CREATE TABLE IF NOT EXISTS knowledge.chunks (
    id VARCHAR(64) PRIMARY KEY,
    document_id VARCHAR(64) NOT NULL,
    knowledge_base_id VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64),
    position INT NOT NULL,
    token_count INT NOT NULL,
    char_count INT NOT NULL,
    metadata JSONB,
    embedding FLOAT4[],  -- PostgreSQL数组存储向量
    -- 如果使用pgvector: embedding vector(1536),
    embedding_status VARCHAR(20) NOT NULL,
    tenant_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES knowledge.documents(id) ON DELETE CASCADE,
    FOREIGN KEY (knowledge_base_id) REFERENCES knowledge.knowledge_bases(id) ON DELETE CASCADE
);

-- 知识库索引
CREATE INDEX idx_knowledge_bases_name ON knowledge.knowledge_bases(name);
CREATE INDEX idx_knowledge_bases_type ON knowledge.knowledge_bases(type);
CREATE INDEX idx_knowledge_bases_status ON knowledge.knowledge_bases(status);
CREATE INDEX idx_knowledge_bases_tenant ON knowledge.knowledge_bases(tenant_id);
CREATE INDEX idx_knowledge_bases_created_at ON knowledge.knowledge_bases(created_at DESC);

-- 文档索引
CREATE INDEX idx_documents_knowledge_base ON knowledge.documents(knowledge_base_id);
CREATE INDEX idx_documents_status ON knowledge.documents(status);
CREATE INDEX idx_documents_tenant ON knowledge.documents(tenant_id);
CREATE INDEX idx_documents_created_at ON knowledge.documents(created_at DESC);
CREATE INDEX idx_documents_kb_status ON knowledge.documents(knowledge_base_id, status);

-- 分块索引
CREATE INDEX idx_chunks_document ON knowledge.chunks(document_id);
CREATE INDEX idx_chunks_knowledge_base ON knowledge.chunks(knowledge_base_id);
CREATE INDEX idx_chunks_content_hash ON knowledge.chunks(content_hash);
CREATE INDEX idx_chunks_embedding_status ON knowledge.chunks(embedding_status);
CREATE INDEX idx_chunks_tenant ON knowledge.chunks(tenant_id);
CREATE INDEX idx_chunks_doc_position ON knowledge.chunks(document_id, position);

-- 向量索引（如果使用pgvector）
-- CREATE INDEX idx_chunks_embedding_ivfflat ON knowledge.chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_chunks_embedding_hnsw ON knowledge.chunks USING hnsw (embedding vector_cosine_ops);

-- 更新时间触发器
CREATE OR REPLACE FUNCTION knowledge.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_knowledge_bases_updated_at BEFORE UPDATE ON knowledge.knowledge_bases
FOR EACH ROW EXECUTE FUNCTION knowledge.update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON knowledge.documents
FOR EACH ROW EXECUTE FUNCTION knowledge.update_updated_at_column();

CREATE TRIGGER update_chunks_updated_at BEFORE UPDATE ON knowledge.chunks
FOR EACH ROW EXECUTE FUNCTION knowledge.update_updated_at_column();

-- 注释
COMMENT ON TABLE knowledge.knowledge_bases IS '知识库表';
COMMENT ON COLUMN knowledge.knowledge_bases.id IS '知识库ID';
COMMENT ON COLUMN knowledge.knowledge_bases.name IS '知识库名称';
COMMENT ON COLUMN knowledge.knowledge_bases.type IS '知识库类型：general/product/faq/policy/custom';
COMMENT ON COLUMN knowledge.knowledge_bases.status IS '状态：active/inactive/archived';
COMMENT ON COLUMN knowledge.knowledge_bases.embedding_model IS '向量化模型：openai/cohere/huggingface/local';
COMMENT ON COLUMN knowledge.knowledge_bases.embedding_dim IS '向量维度';
COMMENT ON COLUMN knowledge.knowledge_bases.chunk_size IS '分块大小';
COMMENT ON COLUMN knowledge.knowledge_bases.chunk_overlap IS '分块重叠';

COMMENT ON TABLE knowledge.documents IS '文档表';
COMMENT ON COLUMN knowledge.documents.id IS '文档ID';
COMMENT ON COLUMN knowledge.documents.status IS '状态：pending/processing/completed/failed/deleted';

COMMENT ON TABLE knowledge.chunks IS '文档分块表';
COMMENT ON COLUMN knowledge.chunks.id IS '分块ID';
COMMENT ON COLUMN knowledge.chunks.content IS '分块内容';
COMMENT ON COLUMN knowledge.chunks.embedding IS '向量表示（FLOAT4数组）';
COMMENT ON COLUMN knowledge.chunks.embedding_status IS '向量化状态：pending/completed/failed';
