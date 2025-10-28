package biz

import (
	"bytes"
	"context"
	"fmt"
	"regexp"
	"strings"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/ledongthuc/pdf"
)

// ProcessedDocument 处理后的文档
type ProcessedDocument struct {
	FullText   string
	Chunks     []string
	ChunkCount int
	CharCount  int
}

// DocumentProcessor 文档处理器
type DocumentProcessor struct {
	maxChunkSize int
	chunkOverlap int
	minChunkSize int
	log          *log.Helper
}

// DocumentProcessorConfig 文档处理器配置
type DocumentProcessorConfig struct {
	MaxChunkSize int
	ChunkOverlap int
	MinChunkSize int
}

// NewDocumentProcessor 创建文档处理器
func NewDocumentProcessor(config *DocumentProcessorConfig, logger log.Logger) *DocumentProcessor {
	return &DocumentProcessor{
		maxChunkSize: config.MaxChunkSize,
		chunkOverlap: config.ChunkOverlap,
		minChunkSize: config.MinChunkSize,
		log:          log.NewHelper(log.With(logger, "module", "document-processor")),
	}
}

// ProcessDocument 处理文档
func (p *DocumentProcessor) ProcessDocument(
	ctx context.Context,
	fileName, fileType string,
	fileContent []byte,
) (*ProcessedDocument, error) {
	p.log.WithContext(ctx).Infof("开始处理文档: %s (类型: %s, 大小: %d bytes)", fileName, fileType, len(fileContent))

	// 1. 根据文件类型提取文本
	text, err := p.extractText(fileContent, fileType)
	if err != nil {
		return nil, fmt.Errorf("文本提取失败: %w", err)
	}

	// 2. 文本分块（使用语义边界）
	chunks := p.splitTextIntoChunksWithSemanticBoundary(text)

	p.log.WithContext(ctx).Infof("文档处理完成: %s (字符数: %d, 分块数: %d)", fileName, len(text), len(chunks))

	return &ProcessedDocument{
		FullText:   text,
		Chunks:     chunks,
		ChunkCount: len(chunks),
		CharCount:  len(text),
	}, nil
}

// extractText 提取文本
func (p *DocumentProcessor) extractText(fileContent []byte, fileType string) (string, error) {
	switch strings.ToLower(fileType) {
	case "pdf":
		return p.extractTextFromPDF(fileContent)
	case "txt", "text":
		return string(fileContent), nil
	case "md", "markdown":
		return string(fileContent), nil
	case "html", "htm":
		return p.extractTextFromHTML(fileContent)
	default:
		// 尝试作为纯文本处理
		return string(fileContent), nil
	}
}

// extractTextFromPDF 从PDF提取文本
func (p *DocumentProcessor) extractTextFromPDF(content []byte) (string, error) {
	bytesReader := bytes.NewReader(content)
	reader, err := pdf.NewReader(bytesReader, int64(len(content)))
	if err != nil {
		return "", err
	}

	var text strings.Builder
	numPages := reader.NumPage()

	for pageNum := 1; pageNum <= numPages; pageNum++ {
		page := reader.Page(pageNum)
		if page.V.IsNull() {
			continue
		}

		pageText, err := page.GetPlainText(nil)
		if err != nil {
			p.log.Warnf("提取第%d页失败: %v", pageNum, err)
			continue
		}

		text.WriteString(pageText)
		text.WriteString("\n\n")
	}

	return text.String(), nil
}

// extractTextFromHTML 从HTML提取文本
func (p *DocumentProcessor) extractTextFromHTML(content []byte) (string, error) {
	// 简单实现：移除HTML标签
	text := string(content)
	text = strings.ReplaceAll(text, "<script", "<removed")
	text = strings.ReplaceAll(text, "</script>", "</removed>")
	text = strings.ReplaceAll(text, "<style", "<removed")
	text = strings.ReplaceAll(text, "</style>", "</removed>")

	// 使用正则表达式移除标签
	re := regexp.MustCompile(`<[^>]*>`)
	text = re.ReplaceAllString(text, " ")

	// 清理多余空白
	text = strings.Join(strings.Fields(text), " ")

	return text, nil
}

// splitTextIntoChunks 基础滑动窗口分块
func (p *DocumentProcessor) splitTextIntoChunks(text string) []string {
	var chunks []string

	// 如果文本短于maxChunkSize，直接返回
	if len(text) <= p.maxChunkSize {
		if len(text) >= p.minChunkSize {
			return []string{text}
		}
		return []string{}
	}

	// 滑动窗口分块
	for i := 0; i < len(text); i += p.maxChunkSize - p.chunkOverlap {
		end := i + p.maxChunkSize
		if end > len(text) {
			end = len(text)
		}

		chunk := text[i:end]

		// 只保留达到最小大小的chunk
		if len(chunk) >= p.minChunkSize {
			chunks = append(chunks, chunk)
		}

		// 如果已经到达末尾，退出
		if end == len(text) {
			break
		}
	}

	return chunks
}

// splitTextIntoChunksWithSemanticBoundary 语义边界分块
func (p *DocumentProcessor) splitTextIntoChunksWithSemanticBoundary(text string) []string {
	var chunks []string

	// 1. 按段落分割
	paragraphs := p.splitIntoParagraphs(text)

	currentChunk := ""

	for _, para := range paragraphs {
		// 如果当前chunk + 段落 <= maxChunkSize，添加段落
		if len(currentChunk)+len(para) <= p.maxChunkSize {
			if currentChunk != "" {
				currentChunk += "\n\n"
			}
			currentChunk += para
		} else {
			// 保存当前chunk
			if len(currentChunk) >= p.minChunkSize {
				chunks = append(chunks, currentChunk)
			}

			// 开始新chunk
			if len(para) <= p.maxChunkSize {
				currentChunk = para
			} else {
				// 段落太长，按句子分割
				sentences := p.splitIntoSentences(para)
				currentChunk = ""
				for _, sent := range sentences {
					if len(currentChunk)+len(sent) <= p.maxChunkSize {
						if currentChunk != "" {
							currentChunk += " "
						}
						currentChunk += sent
					} else {
						if len(currentChunk) >= p.minChunkSize {
							chunks = append(chunks, currentChunk)
						}
						currentChunk = sent
					}
				}
			}
		}
	}

	// 保存最后一个chunk
	if len(currentChunk) >= p.minChunkSize {
		chunks = append(chunks, currentChunk)
	}

	return chunks
}

// splitIntoParagraphs 按段落分割
func (p *DocumentProcessor) splitIntoParagraphs(text string) []string {
	// 按双换行符分割
	paragraphs := strings.Split(text, "\n\n")

	// 清理空段落
	var result []string
	for _, para := range paragraphs {
		para = strings.TrimSpace(para)
		if para != "" {
			result = append(result, para)
		}
	}

	return result
}

// splitIntoSentences 按句子分割
func (p *DocumentProcessor) splitIntoSentences(text string) []string {
	// 简单实现：按句号、问号、感叹号分割
	text = strings.ReplaceAll(text, "。", "。\n")
	text = strings.ReplaceAll(text, "！", "！\n")
	text = strings.ReplaceAll(text, "？", "？\n")
	text = strings.ReplaceAll(text, ". ", ".\n")
	text = strings.ReplaceAll(text, "! ", "!\n")
	text = strings.ReplaceAll(text, "? ", "?\n")

	sentences := strings.Split(text, "\n")

	// 清理空句子
	var result []string
	for _, sent := range sentences {
		sent = strings.TrimSpace(sent)
		if sent != "" {
			result = append(result, sent)
		}
	}

	return result
}
