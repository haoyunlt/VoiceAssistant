package application

import (
	"context"
	"fmt"

	"voicehelper/pkg/clients/algo"
)

// AlgoClientHandler 算法服务客户端处理器
// 提供统一的算法服务调用接口
type AlgoClientHandler struct {
	clientManager *algo.ClientManager
}

// NewAlgoClientHandler 创建算法服务客户端处理器
func NewAlgoClientHandler(clientManager *algo.ClientManager) *AlgoClientHandler {
	return &AlgoClientHandler{
		clientManager: clientManager,
	}
}

// ===== Agent Engine =====

// ExecuteAgentTask 执行Agent任务
func (h *AlgoClientHandler) ExecuteAgentTask(ctx context.Context, req *AgentTaskRequest) (*AgentTaskResponse, error) {
	if !h.clientManager.IsServiceHealthy("agent-engine") {
		return nil, fmt.Errorf("agent-engine is not healthy")
	}

	// 构建请求
	agentReq := map[string]interface{}{
		"task":            req.Task,
		"mode":            req.Mode,
		"max_steps":       req.MaxSteps,
		"tools":           req.Tools,
		"conversation_id": req.ConversationID,
		"tenant_id":       req.TenantID,
	}

	// 调用Agent Engine
	var result AgentTaskResponse
	err := h.clientManager.AgentEngine.Post(ctx, "/execute", agentReq, &result)
	if err != nil {
		return nil, fmt.Errorf("execute agent task: %w", err)
	}

	return &result, nil
}

// ===== RAG Engine =====

// GenerateRAGAnswer 生成RAG答案
func (h *AlgoClientHandler) GenerateRAGAnswer(ctx context.Context, req *RAGQueryRequest) (*RAGQueryResponse, error) {
	if !h.clientManager.IsServiceHealthy("rag-engine") {
		return nil, fmt.Errorf("rag-engine is not healthy")
	}

	// 调用RAG Engine
	var result RAGQueryResponse
	err := h.clientManager.RAGEngine.Post(ctx, "/api/v1/generate", req, &result)
	if err != nil {
		return nil, fmt.Errorf("generate rag answer: %w", err)
	}

	return &result, nil
}

// ===== Retrieval Service =====

// RetrieveDocuments 检索文档
func (h *AlgoClientHandler) RetrieveDocuments(ctx context.Context, req *RetrievalRequest) (*RetrievalResponse, error) {
	if !h.clientManager.IsServiceHealthy("retrieval-service") {
		return nil, fmt.Errorf("retrieval-service is not healthy")
	}

	// 调用Retrieval Service
	var result RetrievalResponse
	err := h.clientManager.RetrievalService.Post(ctx, "/retrieve", req, &result)
	if err != nil {
		return nil, fmt.Errorf("retrieve documents: %w", err)
	}

	return &result, nil
}

// ===== Voice Engine =====

// SpeechToText 语音识别
func (h *AlgoClientHandler) SpeechToText(ctx context.Context, audioData []byte, language, model string) (*algo.ASRResponse, error) {
	if !h.clientManager.IsServiceHealthy("voice-engine") {
		return nil, fmt.Errorf("voice-engine is not healthy")
	}

	return h.clientManager.VoiceEngine.SpeechToText(ctx, audioData, language, model)
}

// TextToSpeech 文本转语音
func (h *AlgoClientHandler) TextToSpeech(ctx context.Context, req *algo.TTSRequest) ([]byte, error) {
	if !h.clientManager.IsServiceHealthy("voice-engine") {
		return nil, fmt.Errorf("voice-engine is not healthy")
	}

	return h.clientManager.VoiceEngine.TextToSpeech(ctx, req)
}

// VoiceActivityDetection 语音活动检测
func (h *AlgoClientHandler) VoiceActivityDetection(ctx context.Context, audioData []byte, threshold float64) (*algo.VADResponse, error) {
	if !h.clientManager.IsServiceHealthy("voice-engine") {
		return nil, fmt.Errorf("voice-engine is not healthy")
	}

	return h.clientManager.VoiceEngine.VoiceActivityDetection(ctx, audioData, threshold)
}

// ===== Multimodal Engine =====

// OCRExtract 文字识别
func (h *AlgoClientHandler) OCRExtract(ctx context.Context, imageData []byte, language string) (*algo.OCRResponse, error) {
	if !h.clientManager.IsServiceHealthy("multimodal-engine") {
		return nil, fmt.Errorf("multimodal-engine is not healthy")
	}

	return h.clientManager.MultimodalEngine.OCRExtract(ctx, imageData, language)
}

// VisionAnalyze 视觉理解
func (h *AlgoClientHandler) VisionAnalyze(ctx context.Context, imageData []byte, task string) (*algo.VisionAnalysisResponse, error) {
	if !h.clientManager.IsServiceHealthy("multimodal-engine") {
		return nil, fmt.Errorf("multimodal-engine is not healthy")
	}

	return h.clientManager.MultimodalEngine.VisionAnalyze(ctx, imageData, task)
}

// VQA 视觉问答
func (h *AlgoClientHandler) VQA(ctx context.Context, imageData []byte, question string) (*algo.VQAResponse, error) {
	if !h.clientManager.IsServiceHealthy("multimodal-engine") {
		return nil, fmt.Errorf("multimodal-engine is not healthy")
	}

	return h.clientManager.MultimodalEngine.VQA(ctx, imageData, question)
}

// ===== Indexing Service =====

// TriggerIndexing 触发文档索引
func (h *AlgoClientHandler) TriggerIndexing(ctx context.Context, documentID string) error {
	if !h.clientManager.IsServiceHealthy("indexing-service") {
		return fmt.Errorf("indexing-service is not healthy")
	}

	return h.clientManager.IndexingService.TriggerIndexing(ctx, documentID)
}

// IncrementalUpdate 增量更新文档
func (h *AlgoClientHandler) IncrementalUpdate(ctx context.Context, req *algo.IncrementalUpdateRequest) (*algo.IncrementalUpdateResponse, error) {
	if !h.clientManager.IsServiceHealthy("indexing-service") {
		return nil, fmt.Errorf("indexing-service is not healthy")
	}

	return h.clientManager.IndexingService.IncrementalUpdate(ctx, req)
}

// ===== Vector Store Adapter =====

// InsertVectors 插入向量
func (h *AlgoClientHandler) InsertVectors(ctx context.Context, collectionName string, req *algo.InsertVectorsRequest) (*algo.InsertVectorsResponse, error) {
	if !h.clientManager.IsServiceHealthy("vector-store-adapter") {
		return nil, fmt.Errorf("vector-store-adapter is not healthy")
	}

	return h.clientManager.VectorStoreAdapter.InsertVectors(ctx, collectionName, req)
}

// SearchVectors 检索向量
func (h *AlgoClientHandler) SearchVectors(ctx context.Context, collectionName string, req *algo.SearchVectorsRequest) (*algo.SearchVectorsResponse, error) {
	if !h.clientManager.IsServiceHealthy("vector-store-adapter") {
		return nil, fmt.Errorf("vector-store-adapter is not healthy")
	}

	return h.clientManager.VectorStoreAdapter.SearchVectors(ctx, collectionName, req)
}

// ===== Health Check =====

// GetAllServiceStatus 获取所有服务状态
func (h *AlgoClientHandler) GetAllServiceStatus(ctx context.Context) map[string]algo.ServiceStatus {
	return h.clientManager.GetAllServiceStatus(ctx)
}

// GetHealthStatus 获取健康状态摘要
func (h *AlgoClientHandler) GetHealthStatus() map[string]bool {
	return h.clientManager.GetHealthStatus()
}

// IsServiceHealthy 检查服务是否健康
func (h *AlgoClientHandler) IsServiceHealthy(serviceName string) bool {
	return h.clientManager.IsServiceHealthy(serviceName)
}

// ===== Request/Response Types =====

// AgentTaskRequest Agent任务请求
type AgentTaskRequest struct {
	Task           string   `json:"task"`
	Mode           string   `json:"mode"`            // react/plan_execute/reflexion/simple
	MaxSteps       int      `json:"max_steps"`
	Tools          []string `json:"tools"`
	ConversationID string   `json:"conversation_id"`
	TenantID       string   `json:"tenant_id"`
}

// AgentTaskResponse Agent任务响应
type AgentTaskResponse struct {
	Result   string                   `json:"result"`
	Steps    []map[string]interface{} `json:"steps"`
	Metadata map[string]interface{}   `json:"metadata"`
}

// RAGQueryRequest RAG查询请求
type RAGQueryRequest struct {
	Query    string                 `json:"query"`
	TenantID string                 `json:"tenant_id"`
	History  []Message              `json:"history,omitempty"`
	Options  map[string]interface{} `json:"options,omitempty"`
}

// RAGQueryResponse RAG查询响应
type RAGQueryResponse struct {
	Answer   string                   `json:"answer"`
	Sources  []map[string]interface{} `json:"sources,omitempty"`
	Metadata map[string]interface{}   `json:"metadata,omitempty"`
}

// RetrievalRequest 检索请求
type RetrievalRequest struct {
	Query          string `json:"query"`
	TenantID       string `json:"tenant_id"`
	TopK           int    `json:"top_k"`
	Method         string `json:"method"`          // vector/bm25/hybrid
	EnableRerank   bool   `json:"enable_rerank"`
}

// RetrievalResponse 检索响应
type RetrievalResponse struct {
	Results       []RetrievalResult `json:"results"`
	RetrievalTime float64           `json:"retrieval_time"`
}

// RetrievalResult 检索结果
type RetrievalResult struct {
	Content  string                 `json:"content"`
	Score    float64                `json:"score"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// Message 消息
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

