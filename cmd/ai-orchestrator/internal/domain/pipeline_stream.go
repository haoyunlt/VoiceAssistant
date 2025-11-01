package domain

import (
	"fmt"
	"time"
)

// ExecuteStream 执行RAG流程（流式）
func (p *RAGPipeline) ExecuteStream(task *Task, stream chan<- *StreamEvent) error {
	// 发送开始事件
	stream <- NewStreamEvent(StreamEventTypeStep, "开始RAG流程...")

	// 步骤1：检索文档
	step1 := NewTaskStep("检索文档", "retrieval-service")
	task.AddStep(step1)

	stream <- NewStreamEvent(StreamEventTypeStep, "正在检索相关文档...")

	retrievalResult, err := p.client.Call(
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
		stream <- NewStreamEvent(StreamEventTypeError, "").WithError(err)
		return err
	}
	step1.CompleteStep(retrievalResult)

	// 发送检索结果
	chunksCount := 0
	if chunks, ok := retrievalResult["chunks"].([]interface{}); ok {
		chunksCount = len(chunks)
	}
	stream <- NewStreamEvent(StreamEventTypeRetrieval, fmt.Sprintf("检索到 %d 个相关文档片段", chunksCount)).
		WithMetadata("chunks_count", chunksCount)

	// 步骤2：RAG生成（模拟流式）
	step2 := NewTaskStep("RAG生成", "rag-engine")
	task.AddStep(step2)

	stream <- NewStreamEvent(StreamEventTypeStep, "正在生成回答...")

	// 注意：这里需要调用支持流式的RAG Engine接口
	// 目前使用非流式接口模拟
	ragResult, err := p.client.Call(
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
		stream <- NewStreamEvent(StreamEventTypeError, "").WithError(err)
		return err
	}
	step2.CompleteStep(ragResult)

	// 发送生成的文本（模拟流式输出）
	if answer, ok := ragResult["answer"].(string); ok {
		// 将答案分段发送（模拟流式效果）
		chunkSize := 50
		for i := 0; i < len(answer); i += chunkSize {
			end := i + chunkSize
			if end > len(answer) {
				end = len(answer)
			}
			chunk := answer[i:end]
			stream <- NewStreamEvent(StreamEventTypeText, chunk)
			time.Sleep(50 * time.Millisecond) // 模拟延迟
		}
	}

	// 构建输出
	output := &TaskOutput{
		Metadata: ragResult,
	}

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

	// 发送最终事件
	stream <- NewStreamEvent(StreamEventTypeFinal, "RAG流程完成").
		WithMetadata("tokens_used", output.TokensUsed).
		WithMetadata("cost_usd", output.CostUSD).
		WithDone()

	return nil
}

// ExecuteStream 执行Agent流程（流式）
func (p *AgentPipeline) ExecuteStream(task *Task, stream chan<- *StreamEvent) error {
	// 发送开始事件
	stream <- NewStreamEvent(StreamEventTypeStep, "开始Agent流程...")

	step := NewTaskStep("Agent执行", "agent-engine")
	task.AddStep(step)

	stream <- NewStreamEvent(StreamEventTypeThinking, "Agent正在分析任务...")

	// 注意：这里需要调用支持流式的Agent Engine接口
	// 目前使用非流式接口模拟
	result, err := p.client.Call(
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
		stream <- NewStreamEvent(StreamEventTypeError, "").WithError(err)
		return err
	}
	step.CompleteStep(result)

	// 模拟Agent思考和工具调用过程
	stream <- NewStreamEvent(StreamEventTypeThinking, "决定调用工具: weather_api")
	time.Sleep(100 * time.Millisecond)

	stream <- NewStreamEvent(StreamEventTypeToolCall, "调用 weather_api").
		WithMetadata("tool", "weather_api").
		WithMetadata("args", map[string]interface{}{"city": "北京"})
	time.Sleep(500 * time.Millisecond)

	stream <- NewStreamEvent(StreamEventTypeThinking, "工具调用完成，生成最终答案...")
	time.Sleep(100 * time.Millisecond)

	// 发送结果文本
	if resultStr, ok := result["result"].(string); ok {
		stream <- NewStreamEvent(StreamEventTypeText, resultStr)
	}

	// 构建输出
	output := &TaskOutput{
		Metadata: result,
	}

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

	// 发送最终事件
	stream <- NewStreamEvent(StreamEventTypeFinal, "Agent流程完成").
		WithMetadata("tokens_used", output.TokensUsed).
		WithMetadata("steps", 3).
		WithDone()

	return nil
}

// ExecuteStream 执行语音流程（流式）
func (p *VoicePipeline) ExecuteStream(task *Task, stream chan<- *StreamEvent) error {
	// 发送开始事件
	stream <- NewStreamEvent(StreamEventTypeStep, "开始语音识别...")

	step1 := NewTaskStep("语音识别", "voice-engine")
	task.AddStep(step1)

	stream <- NewStreamEvent(StreamEventTypeStep, "正在处理音频...")

	asrResult, err := p.client.Call(
		"voice-engine",
		"asr",
		map[string]interface{}{
			"audio_data": task.Input.Content,
		},
	)
	if err != nil {
		step1.FailStep(err.Error())
		stream <- NewStreamEvent(StreamEventTypeError, "").WithError(err)
		return err
	}
	step1.CompleteStep(asrResult)

	// 发送识别结果
	if text, ok := asrResult["text"].(string); ok {
		stream <- NewStreamEvent(StreamEventTypeText, text).
			WithMetadata("confidence", asrResult["confidence"])
	}

	// 构建输出
	output := &TaskOutput{
		Metadata: asrResult,
	}

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

	// 发送最终事件
	stream <- NewStreamEvent(StreamEventTypeFinal, "语音识别完成").
		WithDone()

	return nil
}
