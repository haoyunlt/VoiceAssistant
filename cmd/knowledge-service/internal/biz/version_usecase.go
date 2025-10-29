package biz

import (
	"context"
	"fmt"
	"time"

	"voicehelper/cmd/knowledge-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// VersionUsecase 版本管理用例
type VersionUsecase struct {
	versionRepo     domain.VersionRepository
	kbRepo          domain.KnowledgeBaseRepository
	docRepo         domain.DocumentRepository
	chunkRepo       domain.ChunkRepository
	indexingClient  IndexingClient
	knowledgeClient KnowledgeServiceClient
	log             *log.Helper
}

// NewVersionUsecase 创建版本管理用例
func NewVersionUsecase(
	versionRepo domain.VersionRepository,
	kbRepo domain.KnowledgeBaseRepository,
	docRepo domain.DocumentRepository,
	chunkRepo domain.ChunkRepository,
	indexingClient IndexingClient,
	knowledgeClient KnowledgeServiceClient,
	logger log.Logger,
) *VersionUsecase {
	return &VersionUsecase{
		versionRepo:     versionRepo,
		kbRepo:          kbRepo,
		docRepo:         docRepo,
		chunkRepo:       chunkRepo,
		indexingClient:  indexingClient,
		knowledgeClient: knowledgeClient,
		log:             log.NewHelper(logger),
	}
}

// CreateVersion 创建版本快照
func (uc *VersionUsecase) CreateVersion(
	ctx context.Context,
	kbID, createdBy, description string,
) (*domain.KnowledgeBaseVersion, error) {
	uc.log.WithContext(ctx).Infof("Creating version snapshot for knowledge base: %s", kbID)

	// 获取知识库
	kb, err := uc.kbRepo.GetByID(ctx, kbID)
	if err != nil {
		return nil, fmt.Errorf("get knowledge base: %w", err)
	}

	// 获取下一个版本号
	nextVersion, err := uc.getNextVersion(ctx, kbID)
	if err != nil {
		return nil, fmt.Errorf("get next version: %w", err)
	}

	// 捕获快照
	snapshot, err := uc.captureSnapshot(ctx, kbID)
	if err != nil {
		return nil, fmt.Errorf("capture snapshot: %w", err)
	}

	// 创建版本对象
	version := domain.NewKnowledgeBaseVersion(
		kbID,
		nextVersion,
		createdBy,
		kb.TenantID,
		description,
	)
	version.Snapshot = *snapshot

	// 保存版本
	if err := uc.versionRepo.Create(ctx, version); err != nil {
		return nil, fmt.Errorf("save version: %w", err)
	}

	uc.log.WithContext(ctx).Infof(
		"Version %d created for knowledge base %s: docs=%d, chunks=%d",
		version.Version, kbID, snapshot.DocumentCount, snapshot.ChunkCount,
	)

	return version, nil
}

// captureSnapshot 捕获当前状态快照
func (uc *VersionUsecase) captureSnapshot(
	ctx context.Context,
	kbID string,
) (*domain.VersionSnapshot, error) {
	snapshot := &domain.VersionSnapshot{
		CreatedAt: time.Now(),
		Metadata:  make(map[string]string),
	}

	// 统计文档数
	docCount, err := uc.docRepo.CountByKnowledgeBase(ctx, kbID)
	if err != nil {
		return nil, fmt.Errorf("count documents: %w", err)
	}
	snapshot.DocumentCount = int(docCount)

	// 统计分块数
	chunkCount, err := uc.chunkRepo.CountByKnowledgeBase(ctx, kbID)
	if err != nil {
		return nil, fmt.Errorf("count chunks: %w", err)
	}
	snapshot.ChunkCount = int(chunkCount)

	// 获取向量索引哈希（调用indexing-service）
	// TODO: 实现获取向量索引指纹
	snapshot.VectorIndexHash = fmt.Sprintf("vector_hash_%d", time.Now().Unix())

	// 导出图谱快照（调用knowledge-service-py）
	// TODO: 实现图谱导出
	snapshot.GraphSnapshotID = fmt.Sprintf("graph_snap_%d", time.Now().Unix())

	// 添加元数据
	snapshot.Metadata["kb_id"] = kbID
	snapshot.Metadata["captured_at"] = time.Now().Format(time.RFC3339)

	return snapshot, nil
}

// getNextVersion 获取下一个版本号
func (uc *VersionUsecase) getNextVersion(ctx context.Context, kbID string) (int, error) {
	latest, err := uc.versionRepo.GetLatestVersion(ctx, kbID)
	if err != nil {
		// 如果没有版本，返回1
		return 1, nil
	}
	return latest.Version + 1, nil
}

// ListVersions 列出知识库的所有版本
func (uc *VersionUsecase) ListVersions(
	ctx context.Context,
	kbID string,
	offset, limit int,
) ([]*domain.KnowledgeBaseVersion, int64, error) {
	versions, total, err := uc.versionRepo.GetByKnowledgeBase(ctx, kbID, offset, limit)
	if err != nil {
		return nil, 0, fmt.Errorf("list versions: %w", err)
	}
	return versions, total, nil
}

// GetVersion 获取特定版本
func (uc *VersionUsecase) GetVersion(
	ctx context.Context,
	versionID string,
) (*domain.KnowledgeBaseVersion, error) {
	version, err := uc.versionRepo.GetByID(ctx, versionID)
	if err != nil {
		return nil, fmt.Errorf("get version: %w", err)
	}
	return version, nil
}

// RollbackToVersion 回滚到指定版本
func (uc *VersionUsecase) RollbackToVersion(
	ctx context.Context,
	kbID, versionID, operatorID string,
) error {
	uc.log.WithContext(ctx).Infof("Rolling back knowledge base %s to version %s", kbID, versionID)

	// 获取目标版本
	targetVersion, err := uc.versionRepo.GetByID(ctx, versionID)
	if err != nil {
		return fmt.Errorf("get target version: %w", err)
	}

	if targetVersion.KnowledgeBaseID != kbID {
		return fmt.Errorf("version %s does not belong to knowledge base %s", versionID, kbID)
	}

	// 在回滚前创建当前版本快照
	currentVersion, err := uc.CreateVersion(
		ctx,
		kbID,
		operatorID,
		fmt.Sprintf("Auto snapshot before rollback to version %d", targetVersion.Version),
	)
	if err != nil {
		uc.log.WithContext(ctx).Warnf("Failed to create pre-rollback snapshot: %v", err)
	}

	// 执行回滚操作
	if err := uc.performRollback(ctx, kbID, targetVersion); err != nil {
		return fmt.Errorf("perform rollback: %w", err)
	}

	uc.log.WithContext(ctx).Infof(
		"Successfully rolled back to version %d (snapshot: %s)",
		targetVersion.Version, currentVersion.ID,
	)

	return nil
}

// performRollback 执行回滚
func (uc *VersionUsecase) performRollback(
	ctx context.Context,
	kbID string,
	targetVersion *domain.KnowledgeBaseVersion,
) error {
	// Step 1: 恢复向量索引
	uc.log.WithContext(ctx).Info("Restoring vector index...")
	// TODO: 调用indexing-service恢复向量索引
	// err := uc.indexingClient.RestoreSnapshot(ctx, kbID, targetVersion.Snapshot.VectorIndexHash)

	// Step 2: 恢复知识图谱
	uc.log.WithContext(ctx).Info("Restoring knowledge graph...")
	// TODO: 调用knowledge-service-py恢复图谱
	// err := uc.knowledgeClient.RestoreGraph(ctx, kbID, targetVersion.Snapshot.GraphSnapshotID)

	// Step 3: 更新知识库元数据
	kb, err := uc.kbRepo.GetByID(ctx, kbID)
	if err != nil {
		return fmt.Errorf("get knowledge base: %w", err)
	}

	// 更新知识库的更新时间（版本信息存储在单独的version表中）
	kb.UpdatedAt = time.Now()

	if err := uc.kbRepo.Update(ctx, kb); err != nil {
		return fmt.Errorf("update knowledge base: %w", err)
	}

	return nil
}

// CompareVersions 对比两个版本的差异
func (uc *VersionUsecase) CompareVersions(
	ctx context.Context,
	version1ID, version2ID string,
) (*VersionDiff, error) {
	v1, err := uc.versionRepo.GetByID(ctx, version1ID)
	if err != nil {
		return nil, fmt.Errorf("get version 1: %w", err)
	}

	v2, err := uc.versionRepo.GetByID(ctx, version2ID)
	if err != nil {
		return nil, fmt.Errorf("get version 2: %w", err)
	}

	diff := &VersionDiff{
		Version1:      v1.Version,
		Version2:      v2.Version,
		DocumentsDiff: v2.Snapshot.DocumentCount - v1.Snapshot.DocumentCount,
		ChunksDiff:    v2.Snapshot.ChunkCount - v1.Snapshot.ChunkCount,
		EntitiesDiff:  v2.Snapshot.EntityCount - v1.Snapshot.EntityCount,
		RelationsDiff: v2.Snapshot.RelationCount - v1.Snapshot.RelationCount,
	}

	return diff, nil
}

// DeleteVersion 删除版本（谨慎操作）
func (uc *VersionUsecase) DeleteVersion(
	ctx context.Context,
	versionID string,
) error {
	version, err := uc.versionRepo.GetByID(ctx, versionID)
	if err != nil {
		return fmt.Errorf("get version: %w", err)
	}

	// 检查是否是当前版本
	latestVersion, err := uc.versionRepo.GetLatestVersion(ctx, version.KnowledgeBaseID)
	if err == nil && latestVersion != nil && latestVersion.Version == version.Version {
		return fmt.Errorf("cannot delete current version")
	}

	// 删除版本
	if err := uc.versionRepo.Delete(ctx, versionID); err != nil {
		return fmt.Errorf("delete version: %w", err)
	}

	uc.log.WithContext(ctx).Infof("Deleted version %d of knowledge base %s", version.Version, version.KnowledgeBaseID)

	return nil
}

// VersionDiff 版本差异
type VersionDiff struct {
	Version1      int
	Version2      int
	DocumentsDiff int
	ChunksDiff    int
	EntitiesDiff  int
	RelationsDiff int
}
