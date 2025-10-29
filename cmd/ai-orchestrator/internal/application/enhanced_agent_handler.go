package application

import (
	"context"
	"fmt"

	"github.com/go-kratos/kratos/v2/log"

	"voicehelper/cmd/ai-orchestrator/internal/infrastructure"
)

// EnhancedAgentHandler 增强的Agent处理器 - 支持新增的算法API
type EnhancedAgentHandler struct {
	aiClient *infrastructure.AIServiceClient
	log      *log.Helper
}

// NewEnhancedAgentHandler 创建增强的Agent处理器
func NewEnhancedAgentHandler(aiClient *infrastructure.AIServiceClient, logger log.Logger) *EnhancedAgentHandler {
	return &EnhancedAgentHandler{
		aiClient: aiClient,
		log:      log.NewHelper(logger),
	}
}

// ============ Multi-Agent 协作相关方法 ============

// MultiAgentCollaborate 执行Multi-Agent协作
func (h *EnhancedAgentHandler) MultiAgentCollaborate(ctx context.Context, req *MultiAgentCollaborateRequest) (*MultiAgentCollaborateResponse, error) {
	h.log.WithContext(ctx).Infof("MultiAgentCollaborate: task=%s, mode=%s, tenant=%s, user=%s",
		req.Task, req.Mode, req.TenantID, req.UserID)

	// 验证请求参数
	if req.Task == "" {
		return nil, fmt.Errorf("task is required")
	}
	if req.Mode == "" {
		req.Mode = "parallel" // 默认并行模式
	}
	if req.Priority <= 0 {
		req.Priority = 5 // 默认优先级
	}

	// 调用AI服务
	aiReq := &infrastructure.MultiAgentCollaborateRequest{
		Task:     req.Task,
		Mode:     req.Mode,
		AgentIDs: req.AgentIDs,
		Priority: req.Priority,
		TenantID: req.TenantID,
		UserID:   req.UserID,
	}

	result, err := h.aiClient.MultiAgentCollaborate(ctx, aiReq)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to call MultiAgentCollaborate: %v", err)
		return nil, fmt.Errorf("multi-agent collaborate failed: %w", err)
	}

	// 转换响应
	response := &MultiAgentCollaborateResponse{
		Task:                req.Task,
		Mode:                result.Mode,
		AgentsInvolved:      result.AgentsInvolved,
		FinalResult:         fmt.Sprintf("%v", result.FinalResult),
		QualityScore:        result.QualityScore,
		CompletionTime:      result.CompletionTime,
		Status:              result.Status,
		Metadata:            result.Metadata,
	}

	h.log.WithContext(ctx).Infof("MultiAgentCollaborate completed: status=%s, quality=%.2f",
		result.Status, result.QualityScore)

	return response, nil
}

// RegisterAgent 注册Agent
func (h *EnhancedAgentHandler) RegisterAgent(ctx context.Context, req *RegisterAgentRequest) (*RegisterAgentResponse, error) {
	h.log.WithContext(ctx).Infof("RegisterAgent: agent_id=%s, role=%s, tenant=%s",
		req.AgentID, req.Role, req.TenantID)

	if req.AgentID == "" {
		return nil, fmt.Errorf("agent_id is required")
	}
	if req.Role == "" {
		return nil, fmt.Errorf("role is required")
	}

	aiReq := &infrastructure.RegisterAgentRequest{
		AgentID:  req.AgentID,
		Role:     req.Role,
		Tools:    req.Tools,
		TenantID: req.TenantID,
		UserID:   req.UserID,
	}

	result, err := h.aiClient.RegisterAgent(ctx, aiReq)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to register agent: %v", err)
		return nil, fmt.Errorf("register agent failed: %w", err)
	}

	response := &RegisterAgentResponse{
		AgentID: result.AgentID,
		Role:    result.Role,
		Message: result.Message,
	}

	return response, nil
}

// ListAgents 列出所有Agents
func (h *EnhancedAgentHandler) ListAgents(ctx context.Context, tenantID, userID string) (*ListAgentsResponse, error) {
	h.log.WithContext(ctx).Infof("ListAgents: tenant=%s, user=%s", tenantID, userID)

	result, err := h.aiClient.ListAgents(ctx, tenantID, userID)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to list agents: %v", err)
		return nil, fmt.Errorf("list agents failed: %w", err)
	}

	// 转换响应
	agents := make([]*AgentInfo, len(result.Agents))
	for i, agent := range result.Agents {
		agents[i] = &AgentInfo{
			AgentID:           agent.AgentID,
			Role:              agent.Role,
			ToolsCount:        agent.ToolsCount,
			ProcessedMessages: agent.ProcessedMessages,
		}
	}

	response := &ListAgentsResponse{
		Agents: agents,
		Count:  result.Count,
	}

	return response, nil
}

// UnregisterAgent 注销Agent
func (h *EnhancedAgentHandler) UnregisterAgent(ctx context.Context, agentID, tenantID, userID string) error {
	h.log.WithContext(ctx).Infof("UnregisterAgent: agent_id=%s, tenant=%s", agentID, tenantID)

	if agentID == "" {
		return fmt.Errorf("agent_id is required")
	}

	err := h.aiClient.UnregisterAgent(ctx, agentID, tenantID, userID)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to unregister agent: %v", err)
		return fmt.Errorf("unregister agent failed: %w", err)
	}

	return nil
}

// GetMultiAgentStats 获取Multi-Agent统计信息
func (h *EnhancedAgentHandler) GetMultiAgentStats(ctx context.Context, tenantID, userID string) (*MultiAgentStatsResponse, error) {
	h.log.WithContext(ctx).Infof("GetMultiAgentStats: tenant=%s, user=%s", tenantID, userID)

	result, err := h.aiClient.GetMultiAgentStats(ctx, tenantID, userID)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to get multi-agent stats: %v", err)
		return nil, fmt.Errorf("get multi-agent stats failed: %w", err)
	}

	response := &MultiAgentStatsResponse{
		TotalTasks:              result.TotalTasks,
		CompletedTasks:          result.CompletedTasks,
		FailedTasks:             result.FailedTasks,
		SuccessRate:             result.SuccessRate,
		AvgCompletionTime:       result.AvgCompletionTime,
		CollaborationQualityAvg: result.CollaborationQualityAvg,
		ActiveAgents:            result.ActiveAgents,
		AgentLoad:               result.AgentLoad,
	}

	return response, nil
}

// ============ Self-RAG 相关方法 ============

// SelfRAGQuery 执行Self-RAG查询
func (h *EnhancedAgentHandler) SelfRAGQuery(ctx context.Context, req *SelfRAGQueryRequest) (*SelfRAGQueryResponse, error) {
	h.log.WithContext(ctx).Infof("SelfRAGQuery: query=%s, mode=%s, tenant=%s",
		req.Query, req.Mode, req.TenantID)

	if req.Query == "" {
		return nil, fmt.Errorf("query is required")
	}
	if req.Mode == "" {
		req.Mode = "adaptive" // 默认自适应模式
	}

	aiReq := &infrastructure.SelfRAGQueryRequest{
		Query:           req.Query,
		Mode:            req.Mode,
		Context:         req.Context,
		EnableCitations: req.EnableCitations,
		MaxRefinements:  req.MaxRefinements,
		TenantID:        req.TenantID,
		UserID:          req.UserID,
	}

	result, err := h.aiClient.SelfRAGQuery(ctx, aiReq)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to execute Self-RAG query: %v", err)
		return nil, fmt.Errorf("self-rag query failed: %w", err)
	}

	// 转换引用
	citations := make([]*Citation, len(result.Citations))
	for i, c := range result.Citations {
		citations[i] = &Citation{
			Source:         c.Source,
			Content:        c.Content,
			URL:            c.URL,
			RelevanceScore: c.RelevanceScore,
		}
	}

	response := &SelfRAGQueryResponse{
		Query:              result.Query,
		Answer:             result.Answer,
		Confidence:         result.Confidence,
		RetrievalStrategy:  result.RetrievalStrategy,
		RefinementCount:    result.RefinementCount,
		HallucinationLevel: result.HallucinationLevel,
		IsGrounded:         result.IsGrounded,
		Citations:          citations,
		Metadata:           result.Metadata,
	}

	h.log.WithContext(ctx).Infof("SelfRAGQuery completed: confidence=%.2f, refinements=%d",
		result.Confidence, result.RefinementCount)

	return response, nil
}

// GetSelfRAGStats 获取Self-RAG统计信息
func (h *EnhancedAgentHandler) GetSelfRAGStats(ctx context.Context, tenantID, userID string) (*SelfRAGStatsResponse, error) {
	h.log.WithContext(ctx).Infof("GetSelfRAGStats: tenant=%s, user=%s", tenantID, userID)

	result, err := h.aiClient.GetSelfRAGStats(ctx, tenantID, userID)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to get self-rag stats: %v", err)
		return nil, fmt.Errorf("get self-rag stats failed: %w", err)
	}

	response := &SelfRAGStatsResponse{
		TotalQueries:         result.TotalQueries,
		RefinementTriggered:  result.RefinementTriggered,
		HallucinationDetected: result.HallucinationDetected,
		QueryRewrites:        result.QueryRewrites,
		RefinementRate:       result.RefinementRate,
		HallucinationRate:    result.HallucinationRate,
		CacheHitRate:         result.CacheHitRate,
	}

	return response, nil
}

// ============ Smart Memory 相关方法 ============

// AddMemory 添加记忆
func (h *EnhancedAgentHandler) AddMemory(ctx context.Context, req *AddMemoryRequest) (*AddMemoryResponse, error) {
	h.log.WithContext(ctx).Infof("AddMemory: content_len=%d, tier=%s, tenant=%s",
		len(req.Content), req.Tier, req.TenantID)

	if req.Content == "" {
		return nil, fmt.Errorf("content is required")
	}
	if req.Tier == "" {
		req.Tier = "short_term" // 默认短期记忆
	}

	aiReq := &infrastructure.AddMemoryRequest{
		Content:    req.Content,
		Tier:       req.Tier,
		Importance: req.Importance,
		Metadata:   req.Metadata,
		TenantID:   req.TenantID,
		UserID:     req.UserID,
	}

	result, err := h.aiClient.AddMemory(ctx, aiReq)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to add memory: %v", err)
		return nil, fmt.Errorf("add memory failed: %w", err)
	}

	response := &AddMemoryResponse{
		MemoryID:   result.MemoryID,
		Tier:       result.Tier,
		Importance: result.Importance,
		Message:    result.Message,
	}

	return response, nil
}

// RetrieveMemory 检索记忆
func (h *EnhancedAgentHandler) RetrieveMemory(ctx context.Context, req *RetrieveMemoryRequest) (*RetrieveMemoryResponse, error) {
	h.log.WithContext(ctx).Infof("RetrieveMemory: query=%s, top_k=%d, tenant=%s",
		req.Query, req.TopK, req.TenantID)

	if req.Query == "" {
		return nil, fmt.Errorf("query is required")
	}
	if req.TopK <= 0 {
		req.TopK = 5 // 默认返回5条
	}

	aiReq := &infrastructure.RetrieveMemoryRequest{
		Query:         req.Query,
		TopK:          req.TopK,
		TierFilter:    req.TierFilter,
		MinImportance: req.MinImportance,
		TenantID:      req.TenantID,
		UserID:        req.UserID,
	}

	result, err := h.aiClient.RetrieveMemory(ctx, aiReq)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to retrieve memory: %v", err)
		return nil, fmt.Errorf("retrieve memory failed: %w", err)
	}

	// 转换记忆项
	memories := make([]*MemoryItem, len(result.Memories))
	for i, m := range result.Memories {
		memories[i] = &MemoryItem{
			MemoryID:          m.MemoryID,
			Content:           m.Content,
			Tier:              m.Tier,
			Importance:        m.Importance,
			CurrentImportance: m.CurrentImportance,
			AccessCount:       m.AccessCount,
			CreatedAt:         m.CreatedAt,
			LastAccessed:      m.LastAccessed,
		}
	}

	response := &RetrieveMemoryResponse{
		Memories: memories,
		Count:    result.Count,
	}

	h.log.WithContext(ctx).Infof("RetrieveMemory completed: found %d memories", result.Count)

	return response, nil
}

// CompressMemory 压缩记忆
func (h *EnhancedAgentHandler) CompressMemory(ctx context.Context, tier, tenantID, userID string) (*CompressMemoryResponse, error) {
	h.log.WithContext(ctx).Infof("CompressMemory: tier=%s, tenant=%s", tier, tenantID)

	if tier == "" {
		tier = "short_term" // 默认压缩短期记忆
	}

	result, err := h.aiClient.CompressMemory(ctx, tier, tenantID, userID)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to compress memory: %v", err)
		return nil, fmt.Errorf("compress memory failed: %w", err)
	}

	response := &CompressMemoryResponse{
		Summary:         result.Summary,
		OriginalCount:   result.OriginalCount,
		CompressedRatio: result.CompressedRatio,
		Message:         result.Message,
	}

	h.log.WithContext(ctx).Infof("CompressMemory completed: %d -> ratio=%.2f",
		result.OriginalCount, result.CompressedRatio)

	return response, nil
}

// MaintainMemory 维护记忆
func (h *EnhancedAgentHandler) MaintainMemory(ctx context.Context, tenantID, userID string) (*MemoryStatsResponse, error) {
	h.log.WithContext(ctx).Infof("MaintainMemory: tenant=%s, user=%s", tenantID, userID)

	result, err := h.aiClient.MaintainMemory(ctx, tenantID, userID)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to maintain memory: %v", err)
		return nil, fmt.Errorf("maintain memory failed: %w", err)
	}

	response := &MemoryStatsResponse{
		TotalAdded:      result.TotalAdded,
		TotalForgotten:  result.TotalForgotten,
		TotalPromoted:   result.TotalPromoted,
		TotalDemoted:    result.TotalDemoted,
		TotalCompressed: result.TotalCompressed,
		MemoryCounts:    result.MemoryCounts,
		TotalMemories:   result.TotalMemories,
		AvgImportance:   result.AvgImportance,
	}

	return response, nil
}

// GetMemoryStats 获取记忆统计信息
func (h *EnhancedAgentHandler) GetMemoryStats(ctx context.Context, tenantID, userID string) (*MemoryStatsResponse, error) {
	h.log.WithContext(ctx).Infof("GetMemoryStats: tenant=%s, user=%s", tenantID, userID)

	result, err := h.aiClient.GetMemoryStats(ctx, tenantID, userID)
	if err != nil {
		h.log.WithContext(ctx).Errorf("Failed to get memory stats: %v", err)
		return nil, fmt.Errorf("get memory stats failed: %w", err)
	}

	response := &MemoryStatsResponse{
		TotalAdded:      result.TotalAdded,
		TotalForgotten:  result.TotalForgotten,
		TotalPromoted:   result.TotalPromoted,
		TotalDemoted:    result.TotalDemoted,
		TotalCompressed: result.TotalCompressed,
		MemoryCounts:    result.MemoryCounts,
		TotalMemories:   result.TotalMemories,
		AvgImportance:   result.AvgImportance,
	}

	return response, nil
}

// ============ 请求和响应模型 ============

// Multi-Agent协作相关
type MultiAgentCollaborateRequest struct {
	Task     string
	Mode     string
	AgentIDs []string
	Priority int
	TenantID string
	UserID   string
}

type MultiAgentCollaborateResponse struct {
	Task                string
	Mode                string
	AgentsInvolved      []string
	FinalResult         string
	QualityScore        float64
	CompletionTime      float64
	Status              string
	Metadata            map[string]interface{}
}

type RegisterAgentRequest struct {
	AgentID  string
	Role     string
	Tools    []string
	TenantID string
	UserID   string
}

type RegisterAgentResponse struct {
	AgentID string
	Role    string
	Message string
}

type ListAgentsResponse struct {
	Agents []*AgentInfo
	Count  int
}

type AgentInfo struct {
	AgentID           string
	Role              string
	ToolsCount        int
	ProcessedMessages int
}

type MultiAgentStatsResponse struct {
	TotalTasks              int
	CompletedTasks          int
	FailedTasks             int
	SuccessRate             float64
	AvgCompletionTime       float64
	CollaborationQualityAvg float64
	ActiveAgents            int
	AgentLoad               map[string]int
}

// Self-RAG相关
type SelfRAGQueryRequest struct {
	Query           string
	Mode            string
	Context         map[string]interface{}
	EnableCitations bool
	MaxRefinements  int
	TenantID        string
	UserID          string
}

type SelfRAGQueryResponse struct {
	Query              string
	Answer             string
	Confidence         float64
	RetrievalStrategy  string
	RefinementCount    int
	HallucinationLevel string
	IsGrounded         bool
	Citations          []*Citation
	Metadata           map[string]interface{}
}

type Citation struct {
	Source         string
	Content        string
	URL            string
	RelevanceScore float64
}

type SelfRAGStatsResponse struct {
	TotalQueries         int
	RefinementTriggered  int
	HallucinationDetected int
	QueryRewrites        int
	RefinementRate       float64
	HallucinationRate    float64
	CacheHitRate         float64
}

// Smart Memory相关
type AddMemoryRequest struct {
	Content    string
	Tier       string
	Importance float64
	Metadata   map[string]interface{}
	TenantID   string
	UserID     string
}

type AddMemoryResponse struct {
	MemoryID   string
	Tier       string
	Importance float64
	Message    string
}

type RetrieveMemoryRequest struct {
	Query         string
	TopK          int
	TierFilter    string
	MinImportance float64
	TenantID      string
	UserID        string
}

type RetrieveMemoryResponse struct {
	Memories []*MemoryItem
	Count    int
}

type MemoryItem struct {
	MemoryID          string
	Content           string
	Tier              string
	Importance        float64
	CurrentImportance float64
	AccessCount       int
	CreatedAt         string
	LastAccessed      string
}

type CompressMemoryResponse struct {
	Summary         string
	OriginalCount   int
	CompressedRatio float64
	Message         string
}

type MemoryStatsResponse struct {
	TotalAdded      int
	TotalForgotten  int
	TotalPromoted   int
	TotalDemoted    int
	TotalCompressed int
	MemoryCounts    map[string]int
	TotalMemories   int
	AvgImportance   float64
}

