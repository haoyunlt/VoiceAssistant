package domain

// Pipeline AI处理流程
type Pipeline interface {
	// Execute 执行流程
	Execute(task *Task) (*TaskOutput, error)

	// Name 流程名称
	Name() string
}

// PipelineStep 流程步骤接口
type PipelineStep interface {
	// Execute 执行步骤
	Execute(input map[string]interface{}) (map[string]interface{}, error)

	// Name 步骤名称
	Name() string

	// Service 调用的服务
	Service() string
}

// ServiceClient 服务客户端接口
type ServiceClient interface {
	// Call 调用服务
	Call(service, method string, input map[string]interface{}) (map[string]interface{}, error)
}

// RAGPipeline RAG处理流程
type RAGPipeline struct {
	retrievalClient ServiceClient
	ragEngineClient ServiceClient
}

// NewRAGPipeline 创建RAG流程
func NewRAGPipeline(retrievalClient, ragEngineClient ServiceClient) *RAGPipeline {
	return &RAGPipeline{
		retrievalClient: retrievalClient,
		ragEngineClient: ragEngineClient,
	}
}

// Execute 执行RAG流程
func (p *RAGPipeline) Execute(task *Task) (*TaskOutput, error) {
	// 1. 检索相关文档
	step1 := NewTaskStep("检索文档", "retrieval-service")
	task.AddStep(step1)

	retrievalResult, err := p.retrievalClient.Call(
		"retrieval-service",
		"retrieve",
		map[string]interface{}{
			"query":     task.Input.Content,
			"tenant_id": task.TenantID,
			"top_k":     20,
		},
	)
	if err != nil {
		step1.FailStep(err.Error())
		return nil, err
	}
	step1.CompleteStep(retrievalResult)

	// 2. RAG生成
	step2 := NewTaskStep("RAG生成", "rag-engine")
	task.AddStep(step2)

	ragResult, err := p.ragEngineClient.Call(
		"rag-engine",
		"generate",
		map[string]interface{}{
			"query":   task.Input.Content,
			"context": retrievalResult["chunks"],
			"history": task.Input.Context["history"],
		},
	)
	if err != nil {
		step2.FailStep(err.Error())
		return nil, err
	}
	step2.CompleteStep(ragResult)

	// 3. 构建输出
	output := &TaskOutput{
		Metadata: ragResult,
	}

	// 安全地提取字段
	if answer, ok := ragResult["answer"].(string); ok {
		output.Content = answer
	}
	if tokensUsed, ok := ragResult["tokens_used"].(float64); ok {
		output.TokensUsed = int(tokensUsed)
	}
	if model, ok := ragResult["model"].(string); ok {
		output.Model = model
	}
	if costUSD, ok := ragResult["cost_usd"].(float64); ok {
		output.CostUSD = costUSD
	}
	if latencyMS, ok := ragResult["latency_ms"].(float64); ok {
		output.LatencyMS = int(latencyMS)
	}

	return output, nil
}

// Name RAG流程名称
func (p *RAGPipeline) Name() string {
	return "RAG Pipeline"
}

// AgentPipeline Agent执行流程
type AgentPipeline struct {
	agentClient ServiceClient
}

// NewAgentPipeline 创建Agent流程
func NewAgentPipeline(agentClient ServiceClient) *AgentPipeline {
	return &AgentPipeline{
		agentClient: agentClient,
	}
}

// Execute 执行Agent流程
func (p *AgentPipeline) Execute(task *Task) (*TaskOutput, error) {
	step := NewTaskStep("Agent执行", "agent-engine")
	task.AddStep(step)

	result, err := p.agentClient.Call(
		"agent-engine",
		"execute",
		map[string]interface{}{
			"task":           task.Input.Content,
			"context":        task.Input.Context,
			"max_iterations": 10,
		},
	)
	if err != nil {
		step.FailStep(err.Error())
		return nil, err
	}
	step.CompleteStep(result)

	output := &TaskOutput{
		Metadata: result,
	}

	// 安全地提取字段
	if resultStr, ok := result["result"].(string); ok {
		output.Content = resultStr
	}
	if latencyMS, ok := result["latency_ms"].(float64); ok {
		output.LatencyMS = int(latencyMS)
	}
	if tokensUsed, ok := result["tokens_used"].(float64); ok {
		output.TokensUsed = int(tokensUsed)
	}
	if model, ok := result["model"].(string); ok {
		output.Model = model
	}
	if costUSD, ok := result["cost_usd"].(float64); ok {
		output.CostUSD = costUSD
	}

	return output, nil
}

// Name Agent流程名称
func (p *AgentPipeline) Name() string {
	return "Agent Pipeline"
}

// VoicePipeline 语音处理流程
type VoicePipeline struct {
	voiceClient ServiceClient
}

// NewVoicePipeline 创建语音流程
func NewVoicePipeline(voiceClient ServiceClient) *VoicePipeline {
	return &VoicePipeline{
		voiceClient: voiceClient,
	}
}

// Execute 执行语音流程
func (p *VoicePipeline) Execute(task *Task) (*TaskOutput, error) {
	// ASR - 语音转文字
	step1 := NewTaskStep("语音识别", "voice-engine")
	task.AddStep(step1)

	asrResult, err := p.voiceClient.Call(
		"voice-engine",
		"asr",
		map[string]interface{}{
			"audio_data": task.Input.Content,
		},
	)
	if err != nil {
		step1.FailStep(err.Error())
		return nil, err
	}
	step1.CompleteStep(asrResult)

	output := &TaskOutput{
		Metadata: asrResult,
	}

	// 安全地提取字段
	if text, ok := asrResult["text"].(string); ok {
		output.Content = text
	}
	if latencyMS, ok := asrResult["latency_ms"].(float64); ok {
		output.LatencyMS = int(latencyMS)
	}
	if tokensUsed, ok := asrResult["tokens_used"].(float64); ok {
		output.TokensUsed = int(tokensUsed)
	}
	if model, ok := asrResult["model"].(string); ok {
		output.Model = model
	}
	if costUSD, ok := asrResult["cost_usd"].(float64); ok {
		output.CostUSD = costUSD
	}

	return output, nil
}

// Name 语音流程名称
func (p *VoicePipeline) Name() string {
	return "Voice Pipeline"
}
