package algo

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"time"

	"github.com/sony/gobreaker"
)

// BaseClient 算法服务基础客户端
type BaseClient struct {
	serviceName     string
	baseURL         string
	httpClient      *http.Client
	circuitBreaker  *gobreaker.CircuitBreaker
	maxRetries      int
	retryDelay      time.Duration
	defaultTimeout  time.Duration
}

// BaseClientConfig 基础客户端配置
type BaseClientConfig struct {
	ServiceName    string
	BaseURL        string
	Timeout        time.Duration
	MaxRetries     int
	RetryDelay     time.Duration
}

// NewBaseClient 创建基础客户端
func NewBaseClient(config BaseClientConfig) *BaseClient {
	if config.Timeout == 0 {
		config.Timeout = 60 * time.Second
	}
	if config.MaxRetries == 0 {
		config.MaxRetries = 3
	}
	if config.RetryDelay == 0 {
		config.RetryDelay = 100 * time.Millisecond
	}

	client := &BaseClient{
		serviceName: config.ServiceName,
		baseURL:     config.BaseURL,
		httpClient: &http.Client{
			Timeout: config.Timeout,
		},
		maxRetries:     config.MaxRetries,
		retryDelay:     config.RetryDelay,
		defaultTimeout: config.Timeout,
	}

	client.circuitBreaker = client.createCircuitBreaker()

	return client
}

// createCircuitBreaker 创建熔断器
func (c *BaseClient) createCircuitBreaker() *gobreaker.CircuitBreaker {
	settings := gobreaker.Settings{
		Name:        c.serviceName,
		MaxRequests: 3,                // 半开状态下最大请求数
		Interval:    10 * time.Second, // 统计周期
		Timeout:     30 * time.Second, // 熔断器开启后等待时间
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			// 失败率 >= 60% 且请求数 >= 5 时触发熔断
			failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
			return counts.Requests >= 5 && failureRatio >= 0.6
		},
	}
	return gobreaker.NewCircuitBreaker(settings)
}

// Get 发送GET请求
func (c *BaseClient) Get(ctx context.Context, path string, result interface{}) error {
	url := c.baseURL + path
	return c.callWithRetry(ctx, "GET", url, nil, result)
}

// Post 发送POST请求
func (c *BaseClient) Post(ctx context.Context, path string, body interface{}, result interface{}) error {
	url := c.baseURL + path

	var reqBody []byte
	var err error
	if body != nil {
		reqBody, err = json.Marshal(body)
		if err != nil {
			return fmt.Errorf("marshal request: %w", err)
		}
	}

	return c.callWithRetry(ctx, "POST", url, reqBody, result)
}

// Put 发送PUT请求
func (c *BaseClient) Put(ctx context.Context, path string, body interface{}, result interface{}) error {
	url := c.baseURL + path

	var reqBody []byte
	var err error
	if body != nil {
		reqBody, err = json.Marshal(body)
		if err != nil {
			return fmt.Errorf("marshal request: %w", err)
		}
	}

	return c.callWithRetry(ctx, "PUT", url, reqBody, result)
}

// Delete 发送DELETE请求
func (c *BaseClient) Delete(ctx context.Context, path string) error {
	url := c.baseURL + path
	return c.callWithRetry(ctx, "DELETE", url, nil, nil)
}

// callWithRetry 带重试的HTTP调用
func (c *BaseClient) callWithRetry(ctx context.Context, method, url string, reqBody []byte, result interface{}) error {
	var lastErr error

	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		if attempt > 0 {
			// 指数退避
			backoff := time.Duration(math.Pow(2, float64(attempt-1))) * c.retryDelay
			if backoff > 5*time.Second {
				backoff = 5 * time.Second
			}

			select {
			case <-time.After(backoff):
			case <-ctx.Done():
				return ctx.Err()
			}
		}

		// 通过熔断器执行调用
		response, err := c.circuitBreaker.Execute(func() (interface{}, error) {
			return c.doHTTPCall(ctx, method, url, reqBody)
		})

		if err == nil {
			respBody := response.([]byte)
			if result != nil && len(respBody) > 0 {
				if err := json.Unmarshal(respBody, result); err != nil {
					return fmt.Errorf("unmarshal response: %w", err)
				}
			}
			return nil
		}

		lastErr = err

		// 判断是否应该重试
		if !c.shouldRetry(err) {
			break
		}
	}

	return fmt.Errorf("%s: failed after %d attempts: %w", c.serviceName, c.maxRetries+1, lastErr)
}

// doHTTPCall 执行实际的HTTP调用
func (c *BaseClient) doHTTPCall(ctx context.Context, method, url string, reqBody []byte) ([]byte, error) {
	var bodyReader io.Reader
	if reqBody != nil {
		bodyReader = bytes.NewReader(reqBody)
	}

	httpReq, err := http.NewRequestWithContext(ctx, method, url, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	if reqBody != nil {
		httpReq.Header.Set("Content-Type", "application/json")
	}
	httpReq.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("do request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(respBody))
	}

	return respBody, nil
}

// shouldRetry 判断错误是否应该重试
func (c *BaseClient) shouldRetry(err error) bool {
	// 超时错误、取消错误不重试
	if err == context.DeadlineExceeded || err == context.Canceled {
		return false
	}
	// 熔断器开启时不重试
	if err == gobreaker.ErrOpenState || err == gobreaker.ErrTooManyRequests {
		return false
	}
	// 其他错误默认重试
	return true
}

// GetServiceName 获取服务名称
func (c *BaseClient) GetServiceName() string {
	return c.serviceName
}

// GetBaseURL 获取基础URL
func (c *BaseClient) GetBaseURL() string {
	return c.baseURL
}

// GetCircuitBreakerState 获取熔断器状态
func (c *BaseClient) GetCircuitBreakerState() gobreaker.State {
	return c.circuitBreaker.State()
}

// HealthCheck 健康检查
func (c *BaseClient) HealthCheck(ctx context.Context) error {
	var result map[string]interface{}
	err := c.Get(ctx, "/health", &result)
	if err != nil {
		return fmt.Errorf("health check failed: %w", err)
	}

	status, ok := result["status"].(string)
	if !ok || status != "healthy" {
		return fmt.Errorf("service unhealthy: %v", result)
	}

	return nil
}

// ReadinessCheck 就绪检查
func (c *BaseClient) ReadinessCheck(ctx context.Context) (bool, map[string]interface{}, error) {
	var result map[string]interface{}
	err := c.Get(ctx, "/ready", &result)
	if err != nil {
		return false, nil, fmt.Errorf("readiness check failed: %w", err)
	}

	ready, ok := result["ready"].(bool)
	if !ok {
		return false, result, fmt.Errorf("invalid readiness response")
	}

	checks, _ := result["checks"].(map[string]interface{})
	return ready, checks, nil
}

