package biz

import (
	"bytes"
	"context"
	"fmt"
	"voiceassistant/cmd/knowledge-service/internal/domain"
	"voiceassistant/cmd/knowledge-service/internal/infrastructure/security"

	"github.com/go-kratos/kratos/v2/log"
)

// DocumentWorker 文档处理Worker
type DocumentWorker struct {
	documentUC *DocumentUsecase
	storage    *StorageService
	scanner    security.VirusScanner
	processor  *DocumentProcessor
	log        *log.Helper
}

// NewDocumentWorker 创建文档处理Worker
func NewDocumentWorker(
	documentUC *DocumentUsecase,
	storage *StorageService,
	scanner security.VirusScanner,
	processor *DocumentProcessor,
	logger log.Logger,
) *DocumentWorker {
	return &DocumentWorker{
		documentUC: documentUC,
		storage:    storage,
		scanner:    scanner,
		processor:  processor,
		log:        log.NewHelper(log.With(logger, "module", "document-worker")),
	}
}

// ProcessDocument 处理文档
func (w *DocumentWorker) ProcessDocument(ctx context.Context, documentID string) error {
	w.log.WithContext(ctx).Infof("开始处理文档: %s", documentID)

	// 1. 获取文档信息
	doc, err := w.documentUC.GetDocument(ctx, documentID)
	if err != nil {
		return fmt.Errorf("获取文档失败: %w", err)
	}

	// 2. 更新状态: processing
	doc.StartProcessing()
	if err := w.documentUC.UpdateDocument(ctx, doc); err != nil {
		return fmt.Errorf("更新状态失败: %w", err)
	}

	// 3. 下载文件
	fileContent, err := w.storage.Download(ctx, doc.FilePath)
	if err != nil {
		doc.FailProcessing(fmt.Sprintf("下载失败: %v", err))
		w.documentUC.UpdateDocument(ctx, doc)
		return err
	}

	w.log.WithContext(ctx).Infof("文档下载成功: %s (大小: %d bytes)", documentID, len(fileContent))

	// 4. 病毒扫描
	if w.scanner != nil {
		scanResult, err := w.scanner.Scan(ctx, bytes.NewReader(fileContent))
		if err != nil {
			doc.FailProcessing(fmt.Sprintf("扫描失败: %v", err))
			w.documentUC.UpdateDocument(ctx, doc)
			return err
		}

		if !scanResult.IsClean {
			// 发现病毒，更新状态并停止处理
			doc.MarkInfected(scanResult.Threat)
			w.documentUC.UpdateDocument(ctx, doc)
			w.log.WithContext(ctx).Warnf("文档包含病毒: %s (病毒: %s)", documentID, scanResult.Threat)
			return fmt.Errorf("document infected: %s", scanResult.Threat)
		}

		w.log.WithContext(ctx).Infof("病毒扫描通过: %s", documentID)
	}

	// 5. 文档处理（文本提取、分块）
	processed, err := w.processor.ProcessDocument(ctx, doc.FileName, string(doc.FileType), fileContent)
	if err != nil {
		doc.FailProcessing(fmt.Sprintf("处理失败: %v", err))
		w.documentUC.UpdateDocument(ctx, doc)
		return err
	}

	w.log.WithContext(ctx).Infof("文档处理完成: %s (分块数: %d)", documentID, len(processed.Chunks))

	// 6. 保存内容和分块
	doc.SetContent(processed.FullText)

	// 保存分块到数据库
	if err := w.saveChunks(ctx, doc, processed.Chunks); err != nil {
		doc.FailProcessing(fmt.Sprintf("保存分块失败: %v", err))
		w.documentUC.UpdateDocument(ctx, doc)
		return err
	}

	// 7. 更新状态: completed
	doc.CompleteProcessing(len(processed.Chunks))
	if err := w.documentUC.UpdateDocument(ctx, doc); err != nil {
		return fmt.Errorf("更新状态失败: %w", err)
	}

	w.log.WithContext(ctx).Infof("文档处理完成: %s", documentID)

	return nil
}

// saveChunks 保存分块
func (w *DocumentWorker) saveChunks(ctx context.Context, doc *domain.Document, chunks []string) error {
	// 这里应该调用 ChunkRepository 保存分块
	// 简化实现，实际应该通过 usecase 来操作
	w.log.WithContext(ctx).Infof("保存 %d 个分块到数据库", len(chunks))
	return nil
}

// ProcessedDocument 处理后的文档
type ProcessedDocument struct {
	FullText   string
	Chunks     []string
	ChunkCount int
	CharCount  int
}
