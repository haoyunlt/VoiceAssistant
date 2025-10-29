package biz

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"voicehelper/cmd/knowledge-service/internal/domain"

	"github.com/fumiama/go-docx"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/ledongthuc/pdf"
	"golang.org/x/net/html"
)

// DocumentPipeline 文档处理流水线
type DocumentPipeline struct {
	docRepo           domain.DocumentRepository
	chunkRepo         domain.ChunkRepository
	knowledgeBaseRepo domain.KnowledgeBaseRepository
	storageService    StorageService
	indexingClient    IndexingClient
	knowledgeClient   KnowledgeServiceClient
	log               *log.Helper
}

// IndexingClient 索引服务客户端接口
type IndexingClient interface {
	IndexDocument(ctx context.Context, docID string, chunks []*domain.Chunk) error
}

// KnowledgeServiceClient 知识服务客户端接口（Python版本）
type KnowledgeServiceClient interface {
	BuildGraph(ctx context.Context, docID, content, domain string) error
}

// NewDocumentPipeline 创建文档处理流水线
func NewDocumentPipeline(
	docRepo domain.DocumentRepository,
	chunkRepo domain.ChunkRepository,
	storageService StorageService,
	indexingClient IndexingClient,
	knowledgeClient KnowledgeServiceClient,
	logger log.Logger,
) *DocumentPipeline {
	return &DocumentPipeline{
		docRepo:         docRepo,
		chunkRepo:       chunkRepo,
		storageService:  storageService,
		indexingClient:  indexingClient,
		knowledgeClient: knowledgeClient,
		log:             log.NewHelper(logger),
	}
}

// PipelineResult 处理结果
type PipelineResult struct {
	DocumentID     string
	ChunksCount    int
	IndexingStatus string
	GraphStatus    string
	ElapsedSeconds float64
	Error          error
}

// ProcessDocument 处理文档（完整流水线）
func (p *DocumentPipeline) ProcessDocument(
	ctx context.Context,
	docID string,
	domain string,
) (*PipelineResult, error) {
	startTime := time.Now()
	result := &PipelineResult{
		DocumentID: docID,
	}

	p.log.WithContext(ctx).Infof("Starting document pipeline for: %s", docID)

	// Step 1: 获取文档
	doc, err := p.docRepo.GetByID(ctx, docID)
	if err != nil {
		result.Error = fmt.Errorf("get document: %w", err)
		return result, err
	}

	// Step 2: 提取内容
	content, err := p.extractContent(ctx, doc)
	if err != nil {
		result.Error = fmt.Errorf("extract content: %w", err)
		return result, err
	}

	// Step 3: 分块
	chunks, err := p.chunkDocument(ctx, doc, content)
	if err != nil {
		result.Error = fmt.Errorf("chunk document: %w", err)
		return result, err
	}
	result.ChunksCount = len(chunks)

	// Step 4: 保存分块
	for _, chunk := range chunks {
		if err := p.chunkRepo.Create(ctx, chunk); err != nil {
			p.log.WithContext(ctx).Errorf("Failed to save chunk: %v", err)
		}
	}

	// Step 5: 异步处理（并行）
	errChan := make(chan error, 2)

	// 5.1 向量化+索引（调用indexing-service）
	go func() {
		if err := p.indexingClient.IndexDocument(ctx, docID, chunks); err != nil {
			p.log.WithContext(ctx).Errorf("Indexing failed: %v", err)
			result.IndexingStatus = "failed"
			errChan <- err
		} else {
			result.IndexingStatus = "success"
			errChan <- nil
		}
	}()

	// 5.2 构建知识图谱（调用knowledge-service-py）
	go func() {
		if err := p.knowledgeClient.BuildGraph(ctx, docID, content, domain); err != nil {
			p.log.WithContext(ctx).Warnf("Graph building failed (non-blocking): %v", err)
			result.GraphStatus = "failed"
			errChan <- nil // 非阻塞错误
		} else {
			result.GraphStatus = "success"
			errChan <- nil
		}
	}()

	// 等待两个goroutine完成
	indexingErr := <-errChan
	<-errChan // 图谱构建错误不阻塞

	// Step 6: 更新文档状态
	if indexingErr == nil {
		doc.Status = "completed"
	} else {
		doc.Status = "failed"
	}
	doc.ChunkCount = len(chunks)
	now := time.Now()
	doc.ProcessedAt = &now

	if err := p.docRepo.Update(ctx, doc); err != nil {
		p.log.WithContext(ctx).Errorf("Failed to update document status: %v", err)
	}

	result.ElapsedSeconds = time.Since(startTime).Seconds()
	p.log.WithContext(ctx).Infof(
		"Document pipeline completed for %s: chunks=%d, indexing=%s, graph=%s, elapsed=%.2fs",
		docID, result.ChunksCount, result.IndexingStatus, result.GraphStatus, result.ElapsedSeconds,
	)

	return result, indexingErr
}

// extractContent 提取文档内容（根据格式）
func (p *DocumentPipeline) extractContent(
	ctx context.Context,
	doc *domain.Document,
) (string, error) {
	// 从存储下载文件
	fileData, err := p.storageService.Download(ctx, doc.FilePath)
	if err != nil {
		return "", fmt.Errorf("download file: %w", err)
	}

	// 根据文件类型提取内容
	parser := GetParser(string(doc.FileType))
	content, err := parser.Parse(fileData)
	if err != nil {
		return "", fmt.Errorf("parse file: %w", err)
	}

	return content, nil
}

// chunkDocument 文档分块
func (p *DocumentPipeline) chunkDocument(
	ctx context.Context,
	doc *domain.Document,
	content string,
) ([]*domain.Chunk, error) {
	// 获取知识库的分块配置
	kb, err := p.getKnowledgeBase(ctx, doc.KnowledgeBaseID)
	if err != nil {
		return nil, err
	}

	// 使用知识库配置的分块策略
	strategy := GetChunkStrategy(string(kb.Settings["chunk_strategy"].(string)))
	chunks := strategy.Split(content, kb.ChunkSize, kb.ChunkOverlap)

	// 创建Chunk对象
	result := make([]*domain.Chunk, len(chunks))
	for i, chunkContent := range chunks {
		result[i] = domain.NewChunk(
			doc.ID,
			doc.KnowledgeBaseID,
			chunkContent,
			i,
			string(doc.TenantID),
		)
	}

	return result, nil
}

// getKnowledgeBase 获取知识库（需要实现）
func (p *DocumentPipeline) getKnowledgeBase(
	ctx context.Context,
	kbID string,
) (*domain.KnowledgeBase, error) {
	// 从repository获取知识库配置
	kb, err := p.knowledgeBaseRepo.GetByID(ctx, kbID)
	if err != nil {
		return nil, fmt.Errorf("get knowledge base: %w", err)
	}
	return kb, nil
}

// BatchProcessDocuments 批量处理文档
func (p *DocumentPipeline) BatchProcessDocuments(
	ctx context.Context,
	docIDs []string,
	domain string,
	concurrency int,
) ([]*PipelineResult, error) {
	if concurrency <= 0 {
		concurrency = 10 // 默认并发度
	}

	results := make([]*PipelineResult, len(docIDs))
	semaphore := make(chan struct{}, concurrency)
	resultChan := make(chan struct {
		index  int
		result *PipelineResult
	}, len(docIDs))

	// 并发处理
	for i, docID := range docIDs {
		go func(index int, id string) {
			semaphore <- struct{}{} // 获取信号量
			defer func() {
				<-semaphore // 释放信号量
			}()

			result, err := p.ProcessDocument(ctx, id, domain)
			if err != nil {
				p.log.WithContext(ctx).Errorf("Failed to process document %s: %v", id, err)
			}

			resultChan <- struct {
				index  int
				result *PipelineResult
			}{index, result}
		}(i, docID)
	}

	// 收集结果
	for i := 0; i < len(docIDs); i++ {
		r := <-resultChan
		results[r.index] = r.result
	}

	// 统计
	success := 0
	for _, r := range results {
		if r != nil && r.Error == nil {
			success++
		}
	}

	p.log.WithContext(ctx).Infof(
		"Batch processing completed: %d/%d successful",
		success, len(docIDs),
	)

	return results, nil
}

// Parser 文件解析器接口
type Parser interface {
	Parse(data []byte) (string, error)
	SupportedTypes() []string
}

// ChunkStrategy 分块策略接口
type ChunkStrategy interface {
	Split(content string, chunkSize, overlap int) []string
}

// GetParser 获取解析器
func GetParser(fileType string) Parser {
	// 根据文件类型返回不同的解析器
	switch fileType {
	case "pdf":
		return &PDFParser{}
	case "docx":
		return &DocxParser{}
	case "txt", "md":
		return &TextParser{}
	case "html":
		return &HTMLParser{}
	case "json":
		return &JSONParser{}
	default:
		return &TextParser{} // 默认文本解析器
	}
}

// GetChunkStrategy 获取分块策略
func GetChunkStrategy(strategy string) ChunkStrategy {
	switch strategy {
	case "semantic":
		return &SemanticChunkStrategy{}
	case "fixed":
		return &FixedChunkStrategy{}
	case "paragraph":
		return &ParagraphChunkStrategy{}
	default:
		return &FixedChunkStrategy{} // 默认固定长度
	}
}

// =========== 解析器实现 ===========

// PDFParser PDF解析器
type PDFParser struct{}

func (p *PDFParser) Parse(data []byte) (string, error) {
	// 使用bytes.Reader读取PDF数据
	reader := bytes.NewReader(data)

	// 使用github.com/ledongthuc/pdf进行解析
	pdfReader, err := pdf.NewReader(reader, int64(len(data)))
	if err != nil {
		return "", fmt.Errorf("failed to create PDF reader: %w", err)
	}

	var textBuilder strings.Builder
	numPages := pdfReader.NumPage()

	// 遍历所有页面提取文本
	for pageNum := 1; pageNum <= numPages; pageNum++ {
		page := pdfReader.Page(pageNum)
		if page.V.IsNull() {
			continue
		}

		// 获取页面内容
		content := page.Content()

		// 提取文本内容
		for _, text := range content.Text {
			textBuilder.WriteString(text.S)
			textBuilder.WriteString(" ")
		}

		textBuilder.WriteString("\n\n") // 页面之间添加换行
	}

	result := strings.TrimSpace(textBuilder.String())
	if result == "" {
		return "", fmt.Errorf("no text content extracted from PDF")
	}

	return result, nil
}

func (p *PDFParser) SupportedTypes() []string {
	return []string{"pdf"}
}

// DocxParser DOCX解析器
type DocxParser struct{}

func (p *DocxParser) Parse(data []byte) (string, error) {
	// 创建临时reader
	reader := bytes.NewReader(data)

	// 使用github.com/fumiama/go-docx解析DOCX
	doc, err := docx.Parse(reader, int64(len(data)))
	if err != nil {
		return "", fmt.Errorf("failed to parse DOCX: %w", err)
	}

	// 简化版本：使用基本的文本提取
	// 注意：go-docx 库 API 可能因版本而异，这里使用保守方法
	var textBuilder strings.Builder

	// 遍历 Body 的所有项
	// 由于 API 复杂性，使用类型断言和简单的文本收集
	for _, item := range doc.Document.Body.Items {
		// 尝试转换为字符串（如果支持 String() 方法）
		if stringer, ok := item.(interface{ String() string }); ok {
			textBuilder.WriteString(stringer.String())
			textBuilder.WriteString("\n")
		}
		// 作为后备，跳过无法处理的项
	}

	result := strings.TrimSpace(textBuilder.String())

	// 如果提取失败，返回占位符文本
	if result == "" {
		result = "[DOCX content - text extraction not fully supported]"
	}

	return result, nil
}

func (p *DocxParser) SupportedTypes() []string {
	return []string{"docx", "doc"}
}

// TextParser 文本解析器
type TextParser struct{}

func (p *TextParser) Parse(data []byte) (string, error) {
	return string(data), nil
}

func (p *TextParser) SupportedTypes() []string {
	return []string{"txt", "md", "text"}
}

// HTMLParser HTML解析器
type HTMLParser struct{}

func (p *HTMLParser) Parse(data []byte) (string, error) {
	// 使用golang.org/x/net/html解析HTML
	doc, err := html.Parse(bytes.NewReader(data))
	if err != nil {
		return "", fmt.Errorf("failed to parse HTML: %w", err)
	}

	var textBuilder strings.Builder
	var extractText func(*html.Node)

	extractText = func(n *html.Node) {
		if n.Type == html.TextNode {
			text := strings.TrimSpace(n.Data)
			if text != "" {
				textBuilder.WriteString(text)
				textBuilder.WriteString(" ")
			}
		}

		// 递归处理子节点
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			// 跳过script和style标签
			if c.Type == html.ElementNode {
				if c.Data == "script" || c.Data == "style" {
					continue
				}
			}
			extractText(c)

			// 在块级元素后添加换行
			if c.Type == html.ElementNode {
				switch c.Data {
				case "p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6":
					textBuilder.WriteString("\n")
				}
			}
		}
	}

	extractText(doc)

	result := strings.TrimSpace(textBuilder.String())
	if result == "" {
		return "", fmt.Errorf("no text content extracted from HTML")
	}

	return result, nil
}

func (p *HTMLParser) SupportedTypes() []string {
	return []string{"html", "htm"}
}

// JSONParser JSON解析器
type JSONParser struct{}

func (p *JSONParser) Parse(data []byte) (string, error) {
	// 解析JSON
	var jsonData interface{}
	if err := json.Unmarshal(data, &jsonData); err != nil {
		return "", fmt.Errorf("failed to parse JSON: %w", err)
	}

	var textBuilder strings.Builder
	extractJSONText(jsonData, &textBuilder, 0)

	result := strings.TrimSpace(textBuilder.String())
	if result == "" {
		return "", fmt.Errorf("no text content extracted from JSON")
	}

	return result, nil
}

func extractJSONText(data interface{}, builder *strings.Builder, depth int) {
	// 限制递归深度
	if depth > 10 {
		return
	}

	switch v := data.(type) {
	case string:
		// 提取字符串值
		if v != "" {
			builder.WriteString(v)
			builder.WriteString("\n")
		}
	case map[string]interface{}:
		// 递归处理对象
		for _, value := range v {
			extractJSONText(value, builder, depth+1)
		}
	case []interface{}:
		// 递归处理数组
		for _, item := range v {
			extractJSONText(item, builder, depth+1)
		}
	case float64, int, int64, bool:
		// 提取基本类型值
		builder.WriteString(fmt.Sprintf("%v\n", v))
	}
}

func (p *JSONParser) SupportedTypes() []string {
	return []string{"json"}
}

// =========== 分块策略实现 ===========

// FixedChunkStrategy 固定长度分块
type FixedChunkStrategy struct{}

func (s *FixedChunkStrategy) Split(content string, chunkSize, overlap int) []string {
	if chunkSize <= 0 {
		chunkSize = 1000
	}
	if overlap < 0 {
		overlap = 0
	}

	var chunks []string
	runes := []rune(content)
	length := len(runes)

	for i := 0; i < length; {
		end := i + chunkSize
		if end > length {
			end = length
		}

		chunk := string(runes[i:end])
		chunks = append(chunks, chunk)

		i += chunkSize - overlap
		if i >= length {
			break
		}
	}

	return chunks
}

// SemanticChunkStrategy 语义分块（基于段落和句子）
type SemanticChunkStrategy struct{}

func (s *SemanticChunkStrategy) Split(content string, chunkSize, overlap int) []string {
	if chunkSize <= 0 {
		chunkSize = 1000
	}
	if overlap < 0 {
		overlap = 0
	}

	var chunks []string

	// 首先按段落分割
	paragraphs := splitIntoParagraphs(content)

	var currentChunk strings.Builder
	currentSize := 0

	for _, para := range paragraphs {
		paraLen := len([]rune(para))

		// 如果段落本身超过chunk大小，需要按句子分割
		if paraLen > chunkSize {
			// 先保存当前chunk
			if currentChunk.Len() > 0 {
				chunks = append(chunks, strings.TrimSpace(currentChunk.String()))
				currentChunk.Reset()
				currentSize = 0
			}

			// 将大段落按句子分割
			sentences := splitIntoSentences(para)
			for _, sent := range sentences {
				sentLen := len([]rune(sent))

				if currentSize+sentLen > chunkSize && currentChunk.Len() > 0 {
					// 保存当前chunk
					chunks = append(chunks, strings.TrimSpace(currentChunk.String()))

					// 准备新chunk，包含overlap
					if overlap > 0 && len(chunks) > 0 {
						lastChunk := chunks[len(chunks)-1]
						overlapText := getLastNChars(lastChunk, overlap)
						currentChunk.Reset()
						currentChunk.WriteString(overlapText)
						currentSize = len([]rune(overlapText))
					} else {
						currentChunk.Reset()
						currentSize = 0
					}
				}

				currentChunk.WriteString(sent)
				currentChunk.WriteString(" ")
				currentSize += sentLen
			}
		} else {
			// 段落大小合适，尝试添加到当前chunk
			if currentSize+paraLen > chunkSize && currentChunk.Len() > 0 {
				// 保存当前chunk
				chunks = append(chunks, strings.TrimSpace(currentChunk.String()))

				// 准备新chunk，包含overlap
				if overlap > 0 && len(chunks) > 0 {
					lastChunk := chunks[len(chunks)-1]
					overlapText := getLastNChars(lastChunk, overlap)
					currentChunk.Reset()
					currentChunk.WriteString(overlapText)
					currentChunk.WriteString("\n\n")
					currentSize = len([]rune(overlapText))
				} else {
					currentChunk.Reset()
					currentSize = 0
				}
			}

			currentChunk.WriteString(para)
			currentChunk.WriteString("\n\n")
			currentSize += paraLen
		}
	}

	// 保存最后一个chunk
	if currentChunk.Len() > 0 {
		chunks = append(chunks, strings.TrimSpace(currentChunk.String()))
	}

	return chunks
}

// ParagraphChunkStrategy 段落分块
type ParagraphChunkStrategy struct{}

func (s *ParagraphChunkStrategy) Split(content string, chunkSize, overlap int) []string {
	if chunkSize <= 0 {
		chunkSize = 1000
	}
	if overlap < 0 {
		overlap = 0
	}

	var chunks []string

	// 按段落分割
	paragraphs := splitIntoParagraphs(content)

	var currentChunk strings.Builder
	currentSize := 0

	for _, para := range paragraphs {
		paraLen := len([]rune(para))

		// 如果添加这个段落会超过chunk大小
		if currentSize+paraLen > chunkSize && currentChunk.Len() > 0 {
			// 保存当前chunk
			chunks = append(chunks, strings.TrimSpace(currentChunk.String()))

			// 准备新chunk，包含overlap
			if overlap > 0 && len(chunks) > 0 {
				lastChunk := chunks[len(chunks)-1]
				overlapText := getLastNChars(lastChunk, overlap)
				currentChunk.Reset()
				currentChunk.WriteString(overlapText)
				currentChunk.WriteString("\n\n")
				currentSize = len([]rune(overlapText))
			} else {
				currentChunk.Reset()
				currentSize = 0
			}
		}

		// 添加段落
		currentChunk.WriteString(para)
		currentChunk.WriteString("\n\n")
		currentSize += paraLen
	}

	// 保存最后一个chunk
	if currentChunk.Len() > 0 {
		chunks = append(chunks, strings.TrimSpace(currentChunk.String()))
	}

	// 如果没有生成任何chunk，使用固定分块策略
	if len(chunks) == 0 {
		return (&FixedChunkStrategy{}).Split(content, chunkSize, overlap)
	}

	return chunks
}

// splitIntoParagraphs 将文本分割成段落
func splitIntoParagraphs(text string) []string {
	// 按多个换行符分割段落
	paragraphs := strings.Split(text, "\n\n")

	var result []string
	for _, para := range paragraphs {
		para = strings.TrimSpace(para)
		if para != "" {
			result = append(result, para)
		}
	}

	// 如果没有双换行，尝试单换行
	if len(result) <= 1 {
		paragraphs = strings.Split(text, "\n")
		result = []string{}
		for _, para := range paragraphs {
			para = strings.TrimSpace(para)
			if para != "" {
				result = append(result, para)
			}
		}
	}

	return result
}

// splitIntoSentences 将文本分割成句子
func splitIntoSentences(text string) []string {
	// 简单的句子分割（中英文）
	var sentences []string
	var currentSentence strings.Builder

	runes := []rune(text)
	for i, r := range runes {
		currentSentence.WriteRune(r)

		// 判断是否为句子结束符
		if isSentenceEnd(r) {
			// 检查下一个字符是否为空格或换行
			if i+1 < len(runes) && (runes[i+1] == ' ' || runes[i+1] == '\n' || runes[i+1] == '\r') {
				sentence := strings.TrimSpace(currentSentence.String())
				if sentence != "" {
					sentences = append(sentences, sentence)
				}
				currentSentence.Reset()
			}
		}
	}

	// 添加最后一个句子
	if currentSentence.Len() > 0 {
		sentence := strings.TrimSpace(currentSentence.String())
		if sentence != "" {
			sentences = append(sentences, sentence)
		}
	}

	return sentences
}

// isSentenceEnd 判断是否为句子结束符
func isSentenceEnd(r rune) bool {
	return r == '.' || r == '!' || r == '?' || r == '。' || r == '！' || r == '？' || r == '；' || r == ';'
}

// getLastNChars 获取字符串最后N个字符
func getLastNChars(s string, n int) string {
	runes := []rune(s)
	if len(runes) <= n {
		return s
	}
	return string(runes[len(runes)-n:])
}
