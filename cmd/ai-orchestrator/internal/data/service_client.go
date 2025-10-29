package data

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/sony/gobreaker"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// ServiceClient gRPC服务客户端
type GRPCServiceClient struct {
	connections     map[string]*grpc.ClientConn
	circuitBreakers map[string]*gobreaker.CircuitBreaker
	timeout         time.Duration
	maxRetries      int
	log             *log.Helper
}

// NewServiceClient 创建服务客户端
func NewServiceClient(logger log.Logger) *GRPCServiceClient {
	return &GRPCServiceClient{
		connections:     make(map[string]*grpc.ClientConn),
		circuitBreakers: make(map[string]*gobreaker.CircuitBreaker),
		timeout:         30 * time.Second, // 默认超时30秒
		maxRetries:      3,                // 默认重试3次
		log:             log.NewHelper(logger),
	}
}

// Call 调用服务（带重试、超时、熔断）
func (c *GRPCServiceClient) Call(service, method string, input map[string]interface{}) (map[string]interface{}, error) {
	// 获取或创建熔断器
	cb := c.getCircuitBreaker(service)

	// 通过熔断器执行调用
	result, err := cb.Execute(func() (interface{}, error) {
		return c.callWithRetry(service, method, input)
	})

	if err != nil {
		c.log.Errorf("service call failed: service=%s, method=%s, error=%v", service, method, err)
		return nil, err
	}

	return result.(map[string]interface{}), nil
}

// callWithRetry 带重试的调用
func (c *GRPCServiceClient) callWithRetry(service, method string, input map[string]interface{}) (map[string]interface{}, error) {
	var lastErr error

	for attempt := 1; attempt <= c.maxRetries; attempt++ {
		ctx, cancel := context.WithTimeout(context.Background(), c.timeout)
		defer cancel()

		result, err := c.doCall(ctx, service, method, input)
		if err == nil {
			return result, nil
		}

		lastErr = err
		c.log.Warnf("service call attempt %d/%d failed: service=%s, method=%s, error=%v",
			attempt, c.maxRetries, service, method, err)

		// 如果不是最后一次尝试，等待一段时间后重试
		if attempt < c.maxRetries {
			backoff := time.Duration(attempt) * 100 * time.Millisecond
			time.Sleep(backoff)
		}
	}

	return nil, fmt.Errorf("service call failed after %d attempts: %w", c.maxRetries, lastErr)
}

// doCall 实际执行调用
func (c *GRPCServiceClient) doCall(ctx context.Context, service, method string, input map[string]interface{}) (map[string]interface{}, error) {
	// 获取或创建连接
	_, err := c.getConnection(service)
	if err != nil {
		return nil, err
	}

	// 这里简化实现，实际应该根据服务和方法动态调用
	// 在实际项目中，需要为每个服务生成相应的gRPC client stub

	c.log.Debugf("calling service: %s, method: %s", service, method)

	// 检查context是否已取消
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	default:
	}

	// 模拟返回（实际需要实现真实的gRPC调用）
	result := map[string]interface{}{
		"success":    true,
		"data":       input,
		"latency_ms": 100.0,
	}

	return result, nil
}

// getCircuitBreaker 获取或创建熔断器
func (c *GRPCServiceClient) getCircuitBreaker(service string) *gobreaker.CircuitBreaker {
	if cb, exists := c.circuitBreakers[service]; exists {
		return cb
	}

	settings := gobreaker.Settings{
		Name:        service,
		MaxRequests: 3,                // 半开状态最大请求数
		Interval:    10 * time.Second, // 统计周期
		Timeout:     60 * time.Second, // 开启状态持续时间
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
			return counts.Requests >= 3 && failureRatio >= 0.6
		},
		OnStateChange: func(name string, from gobreaker.State, to gobreaker.State) {
			c.log.Infof("circuit breaker state changed: service=%s, from=%s, to=%s", name, from, to)
		},
	}

	cb := gobreaker.NewCircuitBreaker(settings)
	c.circuitBreakers[service] = cb
	c.log.Infof("created circuit breaker for service: %s", service)

	return cb
}

// getConnection 获取或创建gRPC连接
func (c *GRPCServiceClient) getConnection(service string) (*grpc.ClientConn, error) {
	if conn, exists := c.connections[service]; exists {
		return conn, nil
	}

	// 服务地址映射（实际应该从服务发现获取）
	// TODO: 从 configs/services.yaml 读取配置
	serviceAddrs := map[string]string{
		"retrieval-service": "localhost:8012",
		"rag-engine":        "localhost:8006",
		"agent-engine":      "localhost:8003",
		"voice-engine":      "localhost:8004",
	}

	addr, exists := serviceAddrs[service]
	if !exists {
		return nil, fmt.Errorf("unknown service: %s", service)
	}

	// 创建连接
	conn, err := grpc.Dial(
		addr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to %s: %w", service, err)
	}

	c.connections[service] = conn
	c.log.Infof("connected to service: %s at %s", service, addr)

	return conn, nil
}

// Close 关闭所有连接
func (c *GRPCServiceClient) Close() {
	for service, conn := range c.connections {
		conn.Close()
		c.log.Infof("closed connection to service: %s", service)
	}
}

// HTTPServiceClient HTTP服务客户端实现
type HTTPServiceClient struct {
	baseURLs map[string]string
	log      *log.Helper
}

// NewHTTPServiceClient 创建HTTP服务客户端
func NewHTTPServiceClient(logger log.Logger) *HTTPServiceClient {
	return &HTTPServiceClient{
		baseURLs: map[string]string{
			"retrieval-service": "http://localhost:8012",
			"rag-engine":        "http://localhost:8006",
			"agent-engine":      "http://localhost:8003",
			"voice-engine":      "http://localhost:8004",
		},
		log: log.NewHelper(logger),
	}
}

// Call 调用HTTP服务
func (c *HTTPServiceClient) Call(service, method string, input map[string]interface{}) (map[string]interface{}, error) {
	baseURL, exists := c.baseURLs[service]
	if !exists {
		return nil, fmt.Errorf("unknown service: %s", service)
	}

	// 构建URL
	url := fmt.Sprintf("%s/api/v1/%s", baseURL, method)
	c.log.Infof("calling HTTP service: %s, url: %s", service, url)

	// JSON序列化请求体
	reqBody, err := json.Marshal(input)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}
	c.log.Debugf("request body: %s", string(reqBody))

	// 创建HTTP请求
	httpReq, err := http.NewRequest("POST", url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("create HTTP request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Accept", "application/json")

	// 发送请求
	client := &http.Client{
		Timeout: 30 * time.Second,
	}
	resp, err := client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do HTTP request: %w", err)
	}
	defer resp.Body.Close()

	// 读取响应体
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response body: %w", err)
	}

	// 检查状态码
	if resp.StatusCode != http.StatusOK {
		c.log.Errorf("HTTP request failed: status=%d, body=%s", resp.StatusCode, string(respBody))
		return nil, fmt.Errorf("unexpected status code %d: %s", resp.StatusCode, string(respBody))
	}

	// 解析JSON响应
	var result map[string]interface{}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("unmarshal response: %w", err)
	}

	c.log.Infof("HTTP call successful: service=%s, method=%s", service, method)
	return result, nil
}
