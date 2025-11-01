package websocket

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"voicehelper/cmd/conversation-service/internal/domain"
	"voicehelper/cmd/conversation-service/internal/infra"
)

// StreamHandler AI 流式响应处理器
type StreamHandler struct {
	aiClient *infra.AIClient
	logger   *log.Helper
}

// NewStreamHandler 创建流式处理器
func NewStreamHandler(aiClient *infra.AIClient, logger log.Logger) *StreamHandler {
	return &StreamHandler{
		aiClient: aiClient,
		logger:   log.NewHelper(log.With(logger, "module", "stream-handler")),
	}
}

// HandleStreamMessage 处理流式消息请求
func (h *StreamHandler) HandleStreamMessage(client *Client, msg *Message) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	h.logger.Infof("Starting AI stream for user=%s, conversation=%s",
		client.UserID, msg.ConversationID)

	// 构建 AI 请求
	req := &infra.ProcessRequest{
		ConversationID: msg.ConversationID,
		Message:        msg.Content,
		UserID:         client.UserID,
		TenantID:       client.TenantID,
		Mode:           msg.Data["mode"].(string), // chat, rag, agent, etc.
		Config: &infra.ProcessConfig{
			Stream:      true,
			Model:       h.getModel(msg),
			Temperature: h.getTemperature(msg),
			MaxTokens:   h.getMaxTokens(msg),
			EnableRAG:   h.getBoolParam(msg, "enable_rag", false),
			EnableAgent: h.getBoolParam(msg, "enable_agent", false),
		},
		Context: h.buildContext(msg),
	}

	// 发送开始事件
	h.sendStreamStart(client, msg.ConversationID, msg.ID)

	// 启动流式处理
	chunkChan, errChan := h.aiClient.ProcessMessageStream(ctx, req)

	// 异步处理流式响应
	go h.processStreamChunks(client, msg.ConversationID, chunkChan, errChan)
}

// processStreamChunks 处理流式响应块
func (h *StreamHandler) processStreamChunks(
	client *Client,
	conversationID string,
	chunkChan <-chan *infra.StreamChunk,
	errChan <-chan error,
) {
	fullContent := ""
	citations := make([]infra.Citation, 0)
	toolCalls := make([]infra.ToolCall, 0)

	for {
		select {
		case chunk, ok := <-chunkChan:
			if !ok {
				// 流结束
				h.logger.Infof("Stream completed for conversation=%s", conversationID)
				return
			}

			// 累积内容
			fullContent += chunk.Delta

			// 构建流式消息
			streamMsg := h.buildStreamMessage(chunk, fullContent)

			// 发送给客户端
			if err := client.SendJSON(streamMsg); err != nil {
				h.logger.Errorf("Failed to send stream chunk: %v", err)
				return
			}

			// 收集引用和工具调用
			if len(chunk.Citations) > 0 {
				citations = append(citations, chunk.Citations...)
			}
			if chunk.ToolCall.ID != "" {
				toolCalls = append(toolCalls, chunk.ToolCall)
			}

			// 如果流完成，发送结束事件
			if chunk.Finished {
				h.sendStreamEnd(client, conversationID, fullContent, citations, toolCalls, chunk.FinalStats)
				return
			}

		case err := <-errChan:
			if err != nil {
				h.logger.Errorf("Stream error: %v", err)
				h.sendStreamError(client, conversationID, err)
				return
			}
		}
	}
}

// buildStreamMessage 构建流式消息
func (h *StreamHandler) buildStreamMessage(chunk *infra.StreamChunk, fullContent string) map[string]interface{} {
	msg := map[string]interface{}{
		"type":      MessageTypeAIStreamChunk,
		"task_id":   chunk.TaskID,
		"event":     chunk.EventType,
		"delta":     chunk.Delta,
		"content":   fullContent,
		"finished":  chunk.Finished,
		"timestamp": time.Now().Unix(),
	}

	// 添加引用（如果有）
	if len(chunk.Citations) > 0 {
		msg["citations"] = h.formatCitations(chunk.Citations)
	}

	// 添加工具调用（如果有）
	if chunk.ToolCall.ID != "" {
		msg["tool_call"] = h.formatToolCall(&chunk.ToolCall)
	}

	// 添加元数据
	if len(chunk.Metadata) > 0 {
		msg["metadata"] = chunk.Metadata
	}

	return msg
}

// sendStreamStart 发送流式开始事件
func (h *StreamHandler) sendStreamStart(client *Client, conversationID, messageID string) {
	startMsg := map[string]interface{}{
		"type":            MessageTypeAIStreamStart,
		"conversation_id": conversationID,
		"message_id":      messageID,
		"timestamp":       time.Now().Unix(),
	}

	if err := client.SendJSON(startMsg); err != nil {
		h.logger.Errorf("Failed to send stream start: %v", err)
	}
}

// sendStreamEnd 发送流式结束事件
func (h *StreamHandler) sendStreamEnd(
	client *Client,
	conversationID, content string,
	citations []infra.Citation,
	toolCalls []infra.ToolCall,
	stats *infra.FinalStats,
) {
	endMsg := map[string]interface{}{
		"type":            MessageTypeAIStreamEnd,
		"conversation_id": conversationID,
		"content":         content,
		"timestamp":       time.Now().Unix(),
	}

	// 添加引用
	if len(citations) > 0 {
		endMsg["citations"] = h.formatCitations(citations)
	}

	// 添加工具调用
	if len(toolCalls) > 0 {
		endMsg["tool_calls"] = h.formatToolCalls(toolCalls)
	}

	// 添加统计信息
	if stats != nil {
		endMsg["stats"] = map[string]interface{}{
			"duration_ms":      stats.DurationMs,
			"token_usage":      stats.TokenUsage,
			"engine":           stats.Engine,
			"tool_calls_count": stats.ToolCallsCount,
		}
	}

	if err := client.SendJSON(endMsg); err != nil {
		h.logger.Errorf("Failed to send stream end: %v", err)
	}
}

// sendStreamError 发送流式错误事件
func (h *StreamHandler) sendStreamError(client *Client, conversationID string, err error) {
	errorMsg := map[string]interface{}{
		"type":            MessageTypeAIStreamError,
		"conversation_id": conversationID,
		"error":           err.Error(),
		"timestamp":       time.Now().Unix(),
	}

	if sendErr := client.SendJSON(errorMsg); sendErr != nil {
		h.logger.Errorf("Failed to send stream error: %v", sendErr)
	}
}

// formatCitations 格式化引用列表
func (h *StreamHandler) formatCitations(citations []infra.Citation) []map[string]interface{} {
	result := make([]map[string]interface{}, len(citations))
	for i, c := range citations {
		result[i] = map[string]interface{}{
			"id":          c.ID,
			"document_id": c.DocumentID,
			"title":       c.Title,
			"snippet":     c.Snippet,
			"score":       c.Score,
			"metadata":    c.Metadata,
		}
	}
	return result
}

// formatToolCall 格式化单个工具调用
func (h *StreamHandler) formatToolCall(tc *infra.ToolCall) map[string]interface{} {
	return map[string]interface{}{
		"id":          tc.ID,
		"tool":        tc.Tool,
		"arguments":   tc.Arguments,
		"result":      tc.Result,
		"status":      tc.Status,
		"error":       tc.Error,
		"duration_ms": tc.DurationMs,
	}
}

// formatToolCalls 格式化工具调用列表
func (h *StreamHandler) formatToolCalls(toolCalls []infra.ToolCall) []map[string]interface{} {
	result := make([]map[string]interface{}, len(toolCalls))
	for i, tc := range toolCalls {
		result[i] = h.formatToolCall(&tc)
	}
	return result
}

// buildContext 构建对话上下文
func (h *StreamHandler) buildContext(msg *Message) *domain.ConversationContext {
	// 从消息中提取上下文信息
	if contextData, ok := msg.Data["context"]; ok {
		if contextMap, ok := contextData.(map[string]interface{}); ok {
			return &domain.ConversationContext{
				SystemPrompt: h.getStringParam(contextMap, "system_prompt", ""),
				Metadata:     h.getMapParam(contextMap, "metadata"),
			}
		}
	}
	return nil
}

// getModel 获取模型参数
func (h *StreamHandler) getModel(msg *Message) string {
	if model, ok := msg.Data["model"].(string); ok {
		return model
	}
	return "gpt-4" // 默认模型
}

// getTemperature 获取温度参数
func (h *StreamHandler) getTemperature(msg *Message) float32 {
	if temp, ok := msg.Data["temperature"].(float64); ok {
		return float32(temp)
	}
	return 0.7 // 默认温度
}

// getMaxTokens 获取最大 token 数
func (h *StreamHandler) getMaxTokens(msg *Message) int32 {
	if tokens, ok := msg.Data["max_tokens"].(float64); ok {
		return int32(tokens)
	}
	return 2000 // 默认值
}

// getBoolParam 获取布尔参数
func (h *StreamHandler) getBoolParam(msg *Message, key string, defaultValue bool) bool {
	if val, ok := msg.Data[key].(bool); ok {
		return val
	}
	return defaultValue
}

// getStringParam 获取字符串参数
func (h *StreamHandler) getStringParam(data map[string]interface{}, key, defaultValue string) string {
	if val, ok := data[key].(string); ok {
		return val
	}
	return defaultValue
}

// getMapParam 获取 map 参数
func (h *StreamHandler) getMapParam(data map[string]interface{}, key string) map[string]string {
	result := make(map[string]string)
	if val, ok := data[key].(map[string]interface{}); ok {
		for k, v := range val {
			if str, ok := v.(string); ok {
				result[k] = str
			}
		}
	}
	return result
}

// HandleNonStreamMessage 处理非流式消息（兼容旧逻辑）
func (h *StreamHandler) HandleNonStreamMessage(client *Client, msg *Message) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	h.logger.Infof("Processing non-stream message for user=%s, conversation=%s",
		client.UserID, msg.ConversationID)

	// 构建 AI 请求
	req := &infra.ProcessRequest{
		ConversationID: msg.ConversationID,
		Message:        msg.Content,
		UserID:         client.UserID,
		TenantID:       client.TenantID,
		Mode:           msg.Data["mode"].(string),
		Config: &infra.ProcessConfig{
			Stream:      false,
			Model:       h.getModel(msg),
			Temperature: h.getTemperature(msg),
			MaxTokens:   h.getMaxTokens(msg),
			EnableRAG:   h.getBoolParam(msg, "enable_rag", false),
			EnableAgent: h.getBoolParam(msg, "enable_agent", false),
		},
		Context: h.buildContext(msg),
	}

	// 调用 AI 服务
	resp, err := h.aiClient.ProcessMessage(ctx, req)
	if err != nil {
		h.logger.Errorf("AI processing error: %v", err)
		h.sendMessageError(client, msg.ConversationID, err)
		return
	}

	// 发送响应
	h.sendMessageResponse(client, msg.ConversationID, resp)
}

// sendMessageResponse 发送消息响应
func (h *StreamHandler) sendMessageResponse(client *Client, conversationID string, resp *infra.ProcessResponse) {
	responseMsg := map[string]interface{}{
		"type":            MessageTypeAIResponse,
		"conversation_id": conversationID,
		"task_id":         resp.TaskID,
		"content":         resp.Reply,
		"engine":          resp.Engine,
		"timestamp":       time.Now().Unix(),
	}

	if len(resp.Citations) > 0 {
		responseMsg["citations"] = h.formatCitations(resp.Citations)
	}

	if len(resp.ToolCalls) > 0 {
		responseMsg["tool_calls"] = h.formatToolCalls(resp.ToolCalls)
	}

	if resp.TokenUsage != nil {
		responseMsg["token_usage"] = resp.TokenUsage
	}

	if err := client.SendJSON(responseMsg); err != nil {
		h.logger.Errorf("Failed to send message response: %v", err)
	}
}

// sendMessageError 发送消息错误
func (h *StreamHandler) sendMessageError(client *Client, conversationID string, err error) {
	errorMsg := map[string]interface{}{
		"type":            MessageTypeError,
		"conversation_id": conversationID,
		"error":           err.Error(),
		"timestamp":       time.Now().Unix(),
	}

	if sendErr := client.SendJSON(errorMsg); sendErr != nil {
		h.logger.Errorf("Failed to send message error: %v", sendErr)
	}
}
