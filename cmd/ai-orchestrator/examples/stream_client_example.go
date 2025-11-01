package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

// StreamClient 流式客户端示例
type StreamClient struct {
	baseURL string
	client  *http.Client
}

// NewStreamClient 创建流式客户端
func NewStreamClient(baseURL string) *StreamClient {
	return &StreamClient{
		baseURL: baseURL,
		client:  &http.Client{},
	}
}

// ChatRequest 聊天请求
type ChatRequest struct {
	TaskType       string                 `json:"task_type"`
	ConversationID string                 `json:"conversation_id"`
	UserID         string                 `json:"user_id"`
	TenantID       string                 `json:"tenant_id"`
	Content        string                 `json:"content"`
	Context        map[string]interface{} `json:"context"`
	Stream         bool                   `json:"stream"`
}

// StreamEvent 流式事件
type StreamEvent struct {
	Type      string                 `json:"type"`
	Content   string                 `json:"content"`
	Metadata  map[string]interface{} `json:"metadata"`
	Timestamp string                 `json:"timestamp"`
	Done      bool                   `json:"done"`
	Error     string                 `json:"error"`
}

// ChatStream 发起流式聊天
func (c *StreamClient) ChatStream(req *ChatRequest, callback func(*StreamEvent)) error {
	// 构建请求
	req.Stream = true
	body, _ := json.Marshal(req)

	httpReq, err := http.NewRequest("POST", c.baseURL+"/v1/chat/stream", bytes.NewReader(body))
	if err != nil {
		return err
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Accept", "text/event-stream")

	// 发送请求
	resp, err := c.client.Do(httpReq)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	// 检查状态码
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	// 读取SSE流
	reader := bufio.NewReader(resp.Body)
	for {
		line, err := reader.ReadString('\n')
		if err != nil {
			if err == io.EOF {
				break
			}
			return err
		}

		line = strings.TrimSpace(line)

		// 跳过空行和注释
		if line == "" || strings.HasPrefix(line, ":") {
			continue
		}

		// 解析data行
		if strings.HasPrefix(line, "data: ") {
			data := strings.TrimPrefix(line, "data: ")

			// 检查是否结束
			if data == "[DONE]" {
				break
			}

			// 解析JSON
			var event StreamEvent
			if err := json.Unmarshal([]byte(data), &event); err != nil {
				fmt.Printf("failed to parse event: %v\n", err)
				continue
			}

			// 回调处理
			callback(&event)

			// 如果完成，退出
			if event.Done {
				break
			}
		}
	}

	return nil
}

// 使用示例
func main() {
	client := NewStreamClient("http://localhost:8000")

	req := &ChatRequest{
		TaskType:       "rag",
		ConversationID: "conv_123",
		UserID:         "user_456",
		TenantID:       "tenant_789",
		Content:        "什么是领域驱动设计？",
		Context:        map[string]interface{}{},
	}

	fmt.Println("🚀 开始流式聊天...")
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

	err := client.ChatStream(req, func(event *StreamEvent) {
		switch event.Type {
		case "task_created":
			fmt.Printf("📋 任务创建: %s\n", event.Content)
		case "intent":
			fmt.Printf("🎯 意图识别: %s\n", event.Content)
		case "step":
			fmt.Printf("⚙️  步骤: %s\n", event.Content)
		case "retrieval":
			fmt.Printf("📚 检索: %s\n", event.Content)
		case "thinking":
			fmt.Printf("💭 思考: %s\n", event.Content)
		case "tool_call":
			fmt.Printf("🔧 工具调用: %s\n", event.Content)
		case "text":
			fmt.Print(event.Content) // 逐字输出
		case "final":
			fmt.Printf("\n✅ 完成: %s\n", event.Content)
			if metadata := event.Metadata; metadata != nil {
				fmt.Printf("   Token使用: %v\n", metadata["tokens_used"])
				fmt.Printf("   成本: $%v\n", metadata["cost_usd"])
			}
		case "error":
			fmt.Printf("❌ 错误: %s\n", event.Error)
		}
	})

	if err != nil {
		fmt.Printf("❌ 错误: %v\n", err)
		return
	}

	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
	fmt.Println("✨ 流式聊天完成")
}
