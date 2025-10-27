package data

import (
	"encoding/json"
	"fmt"

	"github.com/go-kratos/kratos/v2/log"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// ServiceClient gRPC服务客户端
type GRPCServiceClient struct {
	connections map[string]*grpc.ClientConn
	log         *log.Helper
}

// NewServiceClient 创建服务客户端
func NewServiceClient(logger log.Logger) *GRPCServiceClient {
	return &GRPCServiceClient{
		connections: make(map[string]*grpc.ClientConn),
		log:         log.NewHelper(logger),
	}
}

// Call 调用服务
func (c *GRPCServiceClient) Call(service, method string, input map[string]interface{}) (map[string]interface{}, error) {
	// 获取或创建连接
	_, err := c.getConnection(service)
	if err != nil {
		return nil, err
	}

	// 这里简化实现，实际应该根据服务和方法动态调用
	// 在实际项目中，需要为每个服务生成相应的gRPC client stub

	// 示例：通过HTTP调用（如果服务提供HTTP API）
	// 或者使用reflection/generic gRPC调用

	c.log.Infof("calling service: %s, method: %s", service, method)

	// 模拟返回（实际需要实现真实的gRPC调用）
	result := map[string]interface{}{
		"success": true,
		"data":    input,
	}

	return result, nil
}

// getConnection 获取或创建gRPC连接
func (c *GRPCServiceClient) getConnection(service string) (*grpc.ClientConn, error) {
	if conn, exists := c.connections[service]; exists {
		return conn, nil
	}

	// 服务地址映射（实际应该从服务发现获取）
	serviceAddrs := map[string]string{
		"retrieval-service": "localhost:9001",
		"rag-engine":        "localhost:9002",
		"agent-engine":      "localhost:9003",
		"voice-engine":      "localhost:9004",
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
			"retrieval-service": "http://localhost:8001",
			"rag-engine":        "http://localhost:8002",
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

	url := fmt.Sprintf("%s/api/v1/%s", baseURL, method)
	c.log.Infof("calling HTTP service: %s, url: %s", service, url)

	// 实际实现需要使用HTTP客户端发送请求
	// 这里简化为示例

	inputJSON, _ := json.Marshal(input)
	c.log.Debugf("request: %s", string(inputJSON))

	// 模拟返回
	result := map[string]interface{}{
		"success": true,
		"data":    input,
	}

	return result, nil
}
