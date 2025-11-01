package domain

import (
	"encoding/base64"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
)

// MultimodalPipeline 多模态Pipeline（图文混合）
type MultimodalPipeline struct {
	client ServiceClient
	logger *log.Helper
}

// MultimodalInput 多模态输入
type MultimodalInput struct {
	Text   string   `json:"text"`
	Images []Image  `json:"images,omitempty"`
	Audio  *Audio   `json:"audio,omitempty"`
	Video  *Video   `json:"video,omitempty"`
}

// Image 图片输入
type Image struct {
	URL      string `json:"url,omitempty"`       // 图片URL
	Base64   string `json:"base64,omitempty"`    // Base64编码
	MimeType string `json:"mime_type,omitempty"` // image/jpeg, image/png
	Width    int    `json:"width,omitempty"`
	Height   int    `json:"height,omitempty"`
}

// Audio 音频输入
type Audio struct {
	URL      string `json:"url,omitempty"`
	Base64   string `json:"base64,omitempty"`
	MimeType string `json:"mime_type,omitempty"` // audio/mp3, audio/wav
	Duration int    `json:"duration,omitempty"`  // 秒
}

// Video 视频输入
type Video struct {
	URL      string `json:"url,omitempty"`
	Base64   string `json:"base64,omitempty"`
	MimeType string `json:"mime_type,omitempty"` // video/mp4
	Duration int    `json:"duration,omitempty"`
	Width    int    `json:"width,omitempty"`
	Height   int    `json:"height,omitempty"`
}

// NewMultimodalPipeline 创建多模态Pipeline
func NewMultimodalPipeline(client ServiceClient, logger log.Logger) *MultimodalPipeline {
	return &MultimodalPipeline{
		client: client,
		logger: log.NewHelper(logger),
	}
}

// Execute 执行多模态Pipeline
func (p *MultimodalPipeline) Execute(task *Task) (*TaskOutput, error) {
	p.logger.Infof("executing multimodal pipeline for task %s", task.ID)

	// 解析多模态输入
	multimodalInput, err := p.parseMultimodalInput(task.Input)
	if err != nil {
		return nil, fmt.Errorf("failed to parse multimodal input: %w", err)
	}

	// 步骤1：处理图片（OCR + 视觉理解）
	step1 := NewTaskStep("图片理解", "multimodal-engine")
	task.AddStep(step1)

	var imageContext map[string]interface{}
	if len(multimodalInput.Images) > 0 {
		imageContext, err = p.processImages(multimodalInput.Images)
		if err != nil {
			step1.FailStep(err.Error())
			return nil, err
		}
		step1.CompleteStep(imageContext)
	}

	// 步骤2：处理音频（ASR）
	step2 := NewTaskStep("音频转文本", "voice-engine")
	task.AddStep(step2)

	var audioText string
	if multimodalInput.Audio != nil {
		audioText, err = p.processAudio(multimodalInput.Audio)
		if err != nil {
			step2.FailStep(err.Error())
			return nil, err
		}
		step2.CompleteStep(map[string]interface{}{"text": audioText})
	}

	// 步骤3：RAG检索（结合文本+图片描述）
	step3 := NewTaskStep("检索相关内容", "retrieval-service")
	task.AddStep(step3)

	query := multimodalInput.Text
	if audioText != "" {
		query = query + " " + audioText
	}
	if imageContext != nil {
		if desc, ok := imageContext["description"].(string); ok {
			query = query + " " + desc
		}
	}

	retrievalResult, err := p.client.Call(
		"retrieval-service",
		"retrieve",
		map[string]interface{}{
			"query":     query,
			"tenant_id": task.TenantID,
			"top_k":     10,
		},
	)
	if err != nil {
		step3.FailStep(err.Error())
		return nil, err
	}
	step3.CompleteStep(retrievalResult)

	// 步骤4：多模态LLM生成（GPT-4V/Claude-3）
	step4 := NewTaskStep("多模态生成", "multimodal-engine")
	task.AddStep(step4)

	genResult, err := p.generateMultimodal(multimodalInput, retrievalResult)
	if err != nil {
		step4.FailStep(err.Error())
		return nil, err
	}
	step4.CompleteStep(genResult)

	// 构建输出
	output := &TaskOutput{
		Content:    genResult["answer"].(string),
		Metadata:   genResult,
		TokensUsed: int(genResult["tokens_used"].(float64)),
		Model:      genResult["model"].(string),
		CostUSD:    genResult["cost_usd"].(float64),
		LatencyMS:  int(genResult["latency_ms"].(float64)),
	}

	p.logger.Infof("multimodal pipeline completed for task %s", task.ID)
	return output, nil
}

// parseMultimodalInput 解析多模态输入
func (p *MultimodalPipeline) parseMultimodalInput(input *TaskInput) (*MultimodalInput, error) {
	multimodal := &MultimodalInput{
		Text: input.Content,
	}

	// 从Context中提取图片/音频
	if images, ok := input.Context["images"].([]interface{}); ok {
		for _, img := range images {
			if imgMap, ok := img.(map[string]interface{}); ok {
				image := Image{
					URL:      getString(imgMap, "url"),
					Base64:   getString(imgMap, "base64"),
					MimeType: getString(imgMap, "mime_type"),
					Width:    getInt(imgMap, "width"),
					Height:   getInt(imgMap, "height"),
				}
				multimodal.Images = append(multimodal.Images, image)
			}
		}
	}

	if audio, ok := input.Context["audio"].(map[string]interface{}); ok {
		multimodal.Audio = &Audio{
			URL:      getString(audio, "url"),
			Base64:   getString(audio, "base64"),
			MimeType: getString(audio, "mime_type"),
			Duration: getInt(audio, "duration"),
		}
	}

	return multimodal, nil
}

// processImages 处理图片（OCR + 视觉理解）
func (p *MultimodalPipeline) processImages(images []Image) (map[string]interface{}, error) {
	p.logger.Infof("processing %d images", len(images))

	// 调用Multimodal Engine处理图片
	result, err := p.client.Call(
		"multimodal-engine",
		"process_images",
		map[string]interface{}{
			"images": images,
			"tasks":  []string{"ocr", "caption", "objects"},
		},
	)
	if err != nil {
		return nil, err
	}

	return result, nil
}

// processAudio 处理音频（ASR）
func (p *MultimodalPipeline) processAudio(audio *Audio) (string, error) {
	p.logger.Info("processing audio")

	// 调用Voice Engine进行ASR
	result, err := p.client.Call(
		"voice-engine",
		"asr",
		map[string]interface{}{
			"audio_url": audio.URL,
			"format":    audio.MimeType,
		},
	)
	if err != nil {
		return "", err
	}

	text, ok := result["text"].(string)
	if !ok {
		return "", fmt.Errorf("invalid ASR result")
	}

	return text, nil
}

// generateMultimodal 多模态生成
func (p *MultimodalPipeline) generateMultimodal(
	input *MultimodalInput,
	retrievalResult map[string]interface{},
) (map[string]interface{}, error) {
	p.logger.Info("generating multimodal response")

	// 调用Multimodal Engine（GPT-4V/Claude-3）
	result, err := p.client.Call(
		"multimodal-engine",
		"generate",
		map[string]interface{}{
			"text":     input.Text,
			"images":   input.Images,
			"context":  retrievalResult,
			"model":    "gpt-4-vision-preview",
		},
	)
	if err != nil {
		return nil, err
	}

	return result, nil
}

// Name Pipeline名称
func (p *MultimodalPipeline) Name() string {
	return "multimodal_pipeline"
}

// ExecuteStream 流式执行（支持流式输出）
func (p *MultimodalPipeline) ExecuteStream(task *Task, stream chan<- *StreamEvent) error {
	// 发送进度事件
	stream <- NewStreamEvent(StreamEventTypeProgress, "解析多模态输入...").WithMetadata("step", "parse")

	// 解析输入
	multimodalInput, err := p.parseMultimodalInput(task.Input)
	if err != nil {
		stream <- NewStreamEvent(StreamEventTypeError, "解析失败").WithError(err)
		return err
	}

	// 处理图片
	if len(multimodalInput.Images) > 0 {
		stream <- NewStreamEvent(StreamEventTypeProgress, fmt.Sprintf("处理 %d 张图片...", len(multimodalInput.Images))).WithMetadata("step", "image")
		imageContext, err := p.processImages(multimodalInput.Images)
		if err != nil {
			stream <- NewStreamEvent(StreamEventTypeError, "图片处理失败").WithError(err)
			return err
		}
		stream <- NewStreamEvent(StreamEventTypeProgress, "图片处理完成").WithMetadata("image_context", imageContext)
	}

	// 处理音频
	if multimodalInput.Audio != nil {
		stream <- NewStreamEvent(StreamEventTypeProgress, "转录音频...").WithMetadata("step", "audio")
		audioText, err := p.processAudio(multimodalInput.Audio)
		if err != nil {
			stream <- NewStreamEvent(StreamEventTypeError, "音频处理失败").WithError(err)
			return err
		}
		stream <- NewStreamEvent(StreamEventTypeProgress, "音频转录完成").WithMetadata("audio_text", audioText)
	}

	// 检索
	stream <- NewStreamEvent(StreamEventTypeProgress, "检索相关内容...").WithMetadata("step", "retrieval")
	// ... 执行检索和生成

	stream <- NewStreamEvent(StreamEventTypeFinal, "多模态处理完成").WithDone()
	return nil
}

// 辅助函数
func getString(m map[string]interface{}, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

func getInt(m map[string]interface{}, key string) int {
	if v, ok := m[key].(int); ok {
		return v
	}
	if v, ok := m[key].(float64); ok {
		return int(v)
	}
	return 0
}

// ValidateImage 验证图片输入
func ValidateImage(img *Image) error {
	if img.URL == "" && img.Base64 == "" {
		return fmt.Errorf("image URL or base64 is required")
	}

	// 验证Base64
	if img.Base64 != "" {
		_, err := base64.StdEncoding.DecodeString(img.Base64)
		if err != nil {
			return fmt.Errorf("invalid base64 image: %w", err)
		}
	}

	// 验证MimeType
	validMimeTypes := []string{"image/jpeg", "image/png", "image/gif", "image/webp"}
	valid := false
	for _, mt := range validMimeTypes {
		if img.MimeType == mt {
			valid = true
			break
		}
	}
	if !valid && img.MimeType != "" {
		return fmt.Errorf("unsupported mime type: %s", img.MimeType)
	}

	return nil
}
