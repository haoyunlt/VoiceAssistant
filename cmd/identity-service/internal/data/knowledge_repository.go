package data

import (
	"context"
	"fmt"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/milvus-io/milvus-sdk-go/v2/client"
	"github.com/neo4j/neo4j-go-driver/v5/neo4j"
)

// KnowledgeRepositoryImpl Milvus + Neo4j混合实现
type KnowledgeRepositoryImpl struct {
	milvus     client.Client
	neo4j      neo4j.DriverWithContext
	log        *log.Helper
	collection string
}

// NewKnowledgeRepository 创建KnowledgeRepository实例
func NewKnowledgeRepository(
	milvus client.Client,
	neo4j neo4j.DriverWithContext,
	collectionName string,
	logger log.Logger,
) *KnowledgeRepositoryImpl {
	return &KnowledgeRepositoryImpl{
		milvus:     milvus,
		neo4j:      neo4j,
		log:        log.NewHelper(logger),
		collection: collectionName,
	}
}

// CountDocumentsByTenantID 统计租户的文档数
func (r *KnowledgeRepositoryImpl) CountDocumentsByTenantID(ctx context.Context, tenantID string) (int64, error) {
	// 使用Neo4j查询文档节点
	session := r.neo4j.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	query := `
		MATCH (d:Document {tenant_id: $tenant_id})
		RETURN count(d) as count
	`

	result, err := session.Run(ctx, query, map[string]interface{}{
		"tenant_id": tenantID,
	})
	if err != nil {
		return 0, fmt.Errorf("failed to query documents: %w", err)
	}

	if result.Next(ctx) {
		record := result.Record()
		count, _ := record.Get("count")
		return count.(int64), nil
	}

	return 0, nil
}

// CountEntitiesByTenantID 统计租户的实体数
func (r *KnowledgeRepositoryImpl) CountEntitiesByTenantID(ctx context.Context, tenantID string) (int64, error) {
	session := r.neo4j.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	query := `
		MATCH (e:Entity {tenant_id: $tenant_id})
		RETURN count(e) as count
	`

	result, err := session.Run(ctx, query, map[string]interface{}{
		"tenant_id": tenantID,
	})
	if err != nil {
		return 0, fmt.Errorf("failed to query entities: %w", err)
	}

	if result.Next(ctx) {
		record := result.Record()
		count, _ := record.Get("count")
		return count.(int64), nil
	}

	return 0, nil
}

// GetTotalSizeByTenantID 获取租户的数据总大小（MB）
func (r *KnowledgeRepositoryImpl) GetTotalSizeByTenantID(ctx context.Context, tenantID string) (int64, error) {
	session := r.neo4j.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	query := `
		MATCH (d:Document {tenant_id: $tenant_id})
		RETURN sum(d.size_bytes) as total_bytes
	`

	result, err := session.Run(ctx, query, map[string]interface{}{
		"tenant_id": tenantID,
	})
	if err != nil {
		return 0, fmt.Errorf("failed to query document sizes: %w", err)
	}

	if result.Next(ctx) {
		record := result.Record()
		totalBytes, ok := record.Get("total_bytes")
		if !ok || totalBytes == nil {
			return 0, nil
		}
		return totalBytes.(int64) / (1024 * 1024), nil // Convert to MB
	}

	return 0, nil
}

// DeleteByTenantID 删除租户的所有知识库数据
func (r *KnowledgeRepositoryImpl) DeleteByTenantID(ctx context.Context, tenantID string) (int64, error) {
	// 1. 从Milvus删除向量数据
	expr := fmt.Sprintf("tenant_id == '%s'", tenantID)
	if err := r.milvus.Delete(ctx, r.collection, "", expr); err != nil {
		r.log.Warnf("Failed to delete vectors from Milvus: %v", err)
	}

	// 2. 从Neo4j删除图谱数据
	session := r.neo4j.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeWrite})
	defer session.Close(ctx)

	// 删除所有租户节点和关系
	deleteQuery := `
		MATCH (n {tenant_id: $tenant_id})
		DETACH DELETE n
		RETURN count(n) as deleted_count
	`

	result, err := session.Run(ctx, deleteQuery, map[string]interface{}{
		"tenant_id": tenantID,
	})
	if err != nil {
		return 0, fmt.Errorf("failed to delete knowledge graph: %w", err)
	}

	var deletedCount int64
	if result.Next(ctx) {
		record := result.Record()
		count, _ := record.Get("deleted_count")
		deletedCount = count.(int64)
	}

	r.log.Infof("Deleted %d knowledge items for tenant %s", deletedCount, tenantID)
	return deletedCount, nil
}

// GetDocumentsByTenant 获取租户的文档列表
func (r *KnowledgeRepositoryImpl) GetDocumentsByTenant(ctx context.Context, tenantID string, offset, limit int) ([]map[string]interface{}, error) {
	session := r.neo4j.NewSession(ctx, neo4j.SessionConfig{AccessMode: neo4j.AccessModeRead})
	defer session.Close(ctx)

	query := `
		MATCH (d:Document {tenant_id: $tenant_id})
		RETURN d.id as id, d.title as title, d.size_bytes as size, d.created_at as created_at
		ORDER BY d.created_at DESC
		SKIP $offset
		LIMIT $limit
	`

	result, err := session.Run(ctx, query, map[string]interface{}{
		"tenant_id": tenantID,
		"offset":    offset,
		"limit":     limit,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to query documents: %w", err)
	}

	documents := make([]map[string]interface{}, 0)
	for result.Next(ctx) {
		record := result.Record()
		doc := make(map[string]interface{})
		doc["id"], _ = record.Get("id")
		doc["title"], _ = record.Get("title")
		doc["size"], _ = record.Get("size")
		doc["created_at"], _ = record.Get("created_at")
		documents = append(documents, doc)
	}

	return documents, nil
}
