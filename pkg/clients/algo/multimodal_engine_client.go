package algo

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
)

// MultimodalEngineClient Multimodal Engine 客户端
type MultimodalEngineClient struct {
	*BaseClient
}

// NewMultimodalEngineClient 创建 Multimodal Engine 客户端
func NewMultimodalEngineClient(baseURL string) *MultimodalEngineClient {
	return &MultimodalEngineClient{
		BaseClient: NewBaseClient(BaseClientConfig{
			ServiceName: "multimodal-engine",
			BaseURL:     baseURL,
			Timeout:     20,
			MaxRetries:  3,
		}),
	}
}

// OCRRequest OCR 请求
type OCRRequest struct {
	Language string `json:"language"` // zh/en/auto
}

// OCRResponse OCR 响应
type OCRResponse struct {
	Text           string      `json:"text"`
	Regions        []OCRRegion `json:"regions"`
	ProcessingTime float64     `json:"processing_time"`
}

// OCRRegion OCR 区域
type OCRRegion struct {
	BBox       []float64 `json:"bbox"` // [x1, y1, x2, y2]
	Text       string    `json:"text"`
	Confidence float64   `json:"confidence"`
}

// VisionAnalysisRequest 视觉分析请求
type VisionAnalysisRequest struct {
	Task string `json:"task"` // caption/detect/classify/vqa
}

// VisionAnalysisResponse 视觉分析响应
type VisionAnalysisResponse struct {
	Caption        string         `json:"caption,omitempty"`
	Objects        []DetectedObject `json:"objects,omitempty"`
	Classes        []Classification `json:"classes,omitempty"`
	ProcessingTime float64        `json:"processing_time"`
}

// DetectedObject 检测到的对象
type DetectedObject struct {
	Label      string    `json:"label"`
	BBox       []float64 `json:"bbox"` // [x1, y1, x2, y2]
	Confidence float64   `json:"confidence"`
}

// Classification 分类结果
type Classification struct {
	Label      string  `json:"label"`
	Confidence float64 `json:"confidence"`
}

// VQARequest 视觉问答请求
type VQARequest struct {
	Question string `json:"question"`
}

// VQAResponse 视觉问答响应
type VQAResponse struct {
	Question   string  `json:"question"`
	Answer     string  `json:"answer"`
	Confidence float64 `json:"confidence"`
}

// MultimodalAnalysisRequest 多模态分析请求
type MultimodalAnalysisRequest struct {
	Text string `json:"text,omitempty"`
}

// MultimodalAnalysisResponse 多模态分析响应
type MultimodalAnalysisResponse struct {
	OCRText  string           `json:"ocr_text,omitempty"`
	Caption  string           `json:"caption,omitempty"`
	Objects  []DetectedObject `json:"objects,omitempty"`
	Analysis string           `json:"analysis,omitempty"`
}

// OCRExtract 文字识别 (OCR)
func (c *MultimodalEngineClient) OCRExtract(ctx context.Context, imageData []byte, language string) (*OCRResponse, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	// 添加图片文件
	part, err := writer.CreateFormFile("image", "image.jpg")
	if err != nil {
		return nil, fmt.Errorf("create form file: %w", err)
	}
	if _, err := part.Write(imageData); err != nil {
		return nil, fmt.Errorf("write image data: %w", err)
	}

	// 添加语言参数
	if language != "" {
		_ = writer.WriteField("language", language)
	}

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("close writer: %w", err)
	}

	url := c.GetBaseURL() + "/ocr/extract"
	req, err := http.NewRequestWithContext(ctx, "POST", url, body)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	var result OCRResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// VisionAnalyze 视觉理解分析
func (c *MultimodalEngineClient) VisionAnalyze(ctx context.Context, imageData []byte, task string) (*VisionAnalysisResponse, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	// 添加图片文件
	part, err := writer.CreateFormFile("image", "image.jpg")
	if err != nil {
		return nil, fmt.Errorf("create form file: %w", err)
	}
	if _, err := part.Write(imageData); err != nil {
		return nil, fmt.Errorf("write image data: %w", err)
	}

	// 添加任务参数
	if task != "" {
		_ = writer.WriteField("task", task)
	}

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("close writer: %w", err)
	}

	url := c.GetBaseURL() + "/vision/analyze"
	req, err := http.NewRequestWithContext(ctx, "POST", url, body)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	var result VisionAnalysisResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// VQA 视觉问答
func (c *MultimodalEngineClient) VQA(ctx context.Context, imageData []byte, question string) (*VQAResponse, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	// 添加图片文件
	part, err := writer.CreateFormFile("image", "image.jpg")
	if err != nil {
		return nil, fmt.Errorf("create form file: %w", err)
	}
	if _, err := part.Write(imageData); err != nil {
		return nil, fmt.Errorf("write image data: %w", err)
	}

	// 添加问题
	_ = writer.WriteField("question", question)

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("close writer: %w", err)
	}

	url := c.GetBaseURL() + "/vision/vqa"
	req, err := http.NewRequestWithContext(ctx, "POST", url, body)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	var result VQAResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// MultimodalAnalysis 多模态综合分析
func (c *MultimodalEngineClient) MultimodalAnalysis(ctx context.Context, imageData []byte, text string) (*MultimodalAnalysisResponse, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	// 添加图片文件
	part, err := writer.CreateFormFile("image", "image.jpg")
	if err != nil {
		return nil, fmt.Errorf("create form file: %w", err)
	}
	if _, err := part.Write(imageData); err != nil {
		return nil, fmt.Errorf("write image data: %w", err)
	}

	// 添加文本（可选）
	if text != "" {
		_ = writer.WriteField("text", text)
	}

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("close writer: %w", err)
	}

	url := c.GetBaseURL() + "/analysis/multimodal"
	req, err := http.NewRequestWithContext(ctx, "POST", url, body)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	var result MultimodalAnalysisResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

