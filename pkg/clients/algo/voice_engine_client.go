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

// VoiceEngineClient Voice Engine 客户端
type VoiceEngineClient struct {
	*BaseClient
}

// NewVoiceEngineClient 创建 Voice Engine 客户端
func NewVoiceEngineClient(baseURL string) *VoiceEngineClient {
	return &VoiceEngineClient{
		BaseClient: NewBaseClient(BaseClientConfig{
			ServiceName: "voice-engine",
			BaseURL:     baseURL,
			Timeout:     30,
			MaxRetries:  3,
		}),
	}
}

// ASRRequest ASR 请求
type ASRRequest struct {
	Language string `json:"language"` // zh/en/auto
	Model    string `json:"model"`    // tiny/base/small/medium/large
}

// ASRResponse ASR 响应
type ASRResponse struct {
	Text       string  `json:"text"`
	Language   string  `json:"language"`
	Duration   float64 `json:"duration"`
	Confidence float64 `json:"confidence"`
}

// TTSRequest TTS 请求
type TTSRequest struct {
	Text  string `json:"text"`
	Voice string `json:"voice"` // zh-CN-XiaoxiaoNeural等
	Rate  string `json:"rate"`  // -50% ~ +50%
	Pitch string `json:"pitch"` // -50Hz ~ +50Hz
}

// VADRequest VAD 请求
type VADRequest struct {
	Threshold float64 `json:"threshold"` // 0.0 ~ 1.0
}

// VADResponse VAD 响应
type VADResponse struct {
	Segments []VADSegment `json:"segments"`
	Count    int          `json:"count"`
}

// VADSegment VAD 片段
type VADSegment struct {
	Start float64 `json:"start"`
	End   float64 `json:"end"`
}

// DiarizationRequest 说话人分离请求
type DiarizationRequest struct {
	NumSpeakers int `json:"num_speakers"`
}

// DiarizationResponse 说话人分离响应
type DiarizationResponse struct {
	Segments []DiarizationSegment `json:"segments"`
}

// DiarizationSegment 说话人分离片段
type DiarizationSegment struct {
	Speaker string  `json:"speaker"`
	Start   float64 `json:"start"`
	End     float64 `json:"end"`
	Text    string  `json:"text"`
}

// EmotionResponse 情感识别响应
type EmotionResponse struct {
	Emotion    string             `json:"emotion"`
	Confidence float64            `json:"confidence"`
	Emotions   map[string]float64 `json:"emotions"`
}

// VoiceInfo 语音信息
type VoiceInfo struct {
	Name     string `json:"name"`
	Language string `json:"language"`
	Gender   string `json:"gender"`
}

// SpeechToText 语音识别 (ASR)
func (c *VoiceEngineClient) SpeechToText(ctx context.Context, audioData []byte, language, model string) (*ASRResponse, error) {
	// 创建 multipart 请求
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	// 添加音频文件
	part, err := writer.CreateFormFile("audio", "audio.wav")
	if err != nil {
		return nil, fmt.Errorf("create form file: %w", err)
	}
	if _, err := part.Write(audioData); err != nil {
		return nil, fmt.Errorf("write audio data: %w", err)
	}

	// 添加其他字段
	if language != "" {
		_ = writer.WriteField("language", language)
	}
	if model != "" {
		_ = writer.WriteField("model", model)
	}

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("close writer: %w", err)
	}

	// 发送请求
	url := c.GetBaseURL() + "/asr"
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

	var result ASRResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// TextToSpeech 文本转语音 (TTS)
// 返回音频流数据
func (c *VoiceEngineClient) TextToSpeech(ctx context.Context, req *TTSRequest) ([]byte, error) {
	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	url := c.GetBaseURL() + "/tts"
	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	audioData, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read audio data: %w", err)
	}

	return audioData, nil
}

// VoiceActivityDetection 语音活动检测 (VAD)
func (c *VoiceEngineClient) VoiceActivityDetection(ctx context.Context, audioData []byte, threshold float64) (*VADResponse, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	// 添加音频文件
	part, err := writer.CreateFormFile("audio", "audio.wav")
	if err != nil {
		return nil, fmt.Errorf("create form file: %w", err)
	}
	if _, err := part.Write(audioData); err != nil {
		return nil, fmt.Errorf("write audio data: %w", err)
	}

	// 添加阈值
	if threshold > 0 {
		_ = writer.WriteField("threshold", fmt.Sprintf("%f", threshold))
	}

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("close writer: %w", err)
	}

	url := c.GetBaseURL() + "/vad"
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

	var result VADResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// Diarization 说话人分离
func (c *VoiceEngineClient) Diarization(ctx context.Context, audioData []byte, numSpeakers int) (*DiarizationResponse, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	// 添加音频文件
	part, err := writer.CreateFormFile("audio", "audio.wav")
	if err != nil {
		return nil, fmt.Errorf("create form file: %w", err)
	}
	if _, err := part.Write(audioData); err != nil {
		return nil, fmt.Errorf("write audio data: %w", err)
	}

	// 添加说话人数量
	if numSpeakers > 0 {
		_ = writer.WriteField("num_speakers", fmt.Sprintf("%d", numSpeakers))
	}

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("close writer: %w", err)
	}

	url := c.GetBaseURL() + "/diarization"
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

	var result DiarizationResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// EmotionRecognition 情感识别
func (c *VoiceEngineClient) EmotionRecognition(ctx context.Context, audioData []byte) (*EmotionResponse, error) {
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	part, err := writer.CreateFormFile("audio", "audio.wav")
	if err != nil {
		return nil, fmt.Errorf("create form file: %w", err)
	}
	if _, err := part.Write(audioData); err != nil {
		return nil, fmt.Errorf("write audio data: %w", err)
	}

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("close writer: %w", err)
	}

	url := c.GetBaseURL() + "/emotion"
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

	var result EmotionResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &result, nil
}

// ListVoices 列出可用的 TTS 语音
func (c *VoiceEngineClient) ListVoices(ctx context.Context) ([]VoiceInfo, error) {
	var result struct {
		Voices []VoiceInfo `json:"voices"`
		Count  int         `json:"count"`
	}

	err := c.Get(ctx, "/voices", &result)
	if err != nil {
		return nil, err
	}

	return result.Voices, nil
}

// GetStats 获取统计信息
func (c *VoiceEngineClient) GetStats(ctx context.Context) (map[string]interface{}, error) {
	var result map[string]interface{}
	err := c.Get(ctx, "/stats", &result)
	if err != nil {
		return nil, err
	}
	return result, nil
}

