package clients

import (
	"context"
	"fmt"
	"sync"

	grpcpkg "voicehelper/pkg/grpc"
)

// ClientManager 服务客户端管理器
// 统一管理所有服务的客户端实例
type ClientManager struct {
	factory *grpcpkg.ClientFactory
	config  *ClientConfig

	// 客户端实例（懒加载）
	identityClient     *IdentityClient
	conversationClient *ConversationClient
	knowledgeClient    *KnowledgeClient
	orchestratorClient *OrchestratorClient
	modelRouterClient  *ModelRouterClient
	analyticsClient    *AnalyticsClient
	notificationClient *NotificationClient

	mu sync.RWMutex
}

// ClientConfig 客户端配置
type ClientConfig struct {
	// 服务地址配置
	Services map[string]string

	// 是否启用服务发现
	EnableDiscovery bool

	// Consul 地址（如果启用服务发现）
	ConsulAddress string
}

// DefaultClientConfig 默认配置
func DefaultClientConfig() *ClientConfig {
	return &ClientConfig{
		Services: map[string]string{
			"identity-service":     "localhost:50051",
			"conversation-service": "localhost:50052",
			"knowledge-service":    "localhost:50053",
			"ai-orchestrator":      "localhost:50054",
			"model-router":         "localhost:50055",
			"analytics-service":    "localhost:50056",
			"notification-service": "localhost:50057",
		},
		EnableDiscovery: false,
		ConsulAddress:   "localhost:8500",
	}
}

// NewClientManager 创建客户端管理器
func NewClientManager(config *ClientConfig) (*ClientManager, error) {
	if config == nil {
		config = DefaultClientConfig()
	}

	// 创建客户端工厂
	factoryConfig := &grpcpkg.FactoryConfig{
		EnableDiscovery: config.EnableDiscovery,
		ConsulAddress:   config.ConsulAddress,
	}

	factory, err := grpcpkg.NewClientFactory(factoryConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create client factory: %w", err)
	}

	return &ClientManager{
		factory: factory,
		config:  config,
	}, nil
}

// Identity 获取 Identity 服务客户端
func (m *ClientManager) Identity() (*IdentityClient, error) {
	m.mu.RLock()
	if m.identityClient != nil {
		m.mu.RUnlock()
		return m.identityClient, nil
	}
	m.mu.RUnlock()

	m.mu.Lock()
	defer m.mu.Unlock()

	if m.identityClient != nil {
		return m.identityClient, nil
	}

	target := m.config.Services["identity-service"]
	client, err := NewIdentityClient(m.factory, target)
	if err != nil {
		return nil, err
	}

	m.identityClient = client
	return client, nil
}

// Conversation 获取 Conversation 服务客户端
func (m *ClientManager) Conversation() (*ConversationClient, error) {
	m.mu.RLock()
	if m.conversationClient != nil {
		m.mu.RUnlock()
		return m.conversationClient, nil
	}
	m.mu.RUnlock()

	m.mu.Lock()
	defer m.mu.Unlock()

	if m.conversationClient != nil {
		return m.conversationClient, nil
	}

	target := m.config.Services["conversation-service"]
	client, err := NewConversationClient(m.factory, target)
	if err != nil {
		return nil, err
	}

	m.conversationClient = client
	return client, nil
}

// Knowledge 获取 Knowledge 服务客户端
func (m *ClientManager) Knowledge() (*KnowledgeClient, error) {
	m.mu.RLock()
	if m.knowledgeClient != nil {
		m.mu.RUnlock()
		return m.knowledgeClient, nil
	}
	m.mu.RUnlock()

	m.mu.Lock()
	defer m.mu.Unlock()

	if m.knowledgeClient != nil {
		return m.knowledgeClient, nil
	}

	target := m.config.Services["knowledge-service"]
	client, err := NewKnowledgeClient(m.factory, target)
	if err != nil {
		return nil, err
	}

	m.knowledgeClient = client
	return client, nil
}

// Orchestrator 获取 Orchestrator 服务客户端
func (m *ClientManager) Orchestrator() (*OrchestratorClient, error) {
	m.mu.RLock()
	if m.orchestratorClient != nil {
		m.mu.RUnlock()
		return m.orchestratorClient, nil
	}
	m.mu.RUnlock()

	m.mu.Lock()
	defer m.mu.Unlock()

	if m.orchestratorClient != nil {
		return m.orchestratorClient, nil
	}

	target := m.config.Services["ai-orchestrator"]
	client, err := NewOrchestratorClient(m.factory, target)
	if err != nil {
		return nil, err
	}

	m.orchestratorClient = client
	return client, nil
}

// ModelRouter 获取 Model Router 服务客户端
func (m *ClientManager) ModelRouter() (*ModelRouterClient, error) {
	m.mu.RLock()
	if m.modelRouterClient != nil {
		m.mu.RUnlock()
		return m.modelRouterClient, nil
	}
	m.mu.RUnlock()

	m.mu.Lock()
	defer m.mu.Unlock()

	if m.modelRouterClient != nil {
		return m.modelRouterClient, nil
	}

	target := m.config.Services["model-router"]
	client, err := NewModelRouterClient(m.factory, target)
	if err != nil {
		return nil, err
	}

	m.modelRouterClient = client
	return client, nil
}

// Analytics 获取 Analytics 服务客户端
func (m *ClientManager) Analytics() (*AnalyticsClient, error) {
	m.mu.RLock()
	if m.analyticsClient != nil {
		m.mu.RUnlock()
		return m.analyticsClient, nil
	}
	m.mu.RUnlock()

	m.mu.Lock()
	defer m.mu.Unlock()

	if m.analyticsClient != nil {
		return m.analyticsClient, nil
	}

	target := m.config.Services["analytics-service"]
	client, err := NewAnalyticsClient(m.factory, target)
	if err != nil {
		return nil, err
	}

	m.analyticsClient = client
	return client, nil
}

// Notification 获取 Notification 服务客户端
func (m *ClientManager) Notification() (*NotificationClient, error) {
	m.mu.RLock()
	if m.notificationClient != nil {
		m.mu.RUnlock()
		return m.notificationClient, nil
	}
	m.mu.RUnlock()

	m.mu.Lock()
	defer m.mu.Unlock()

	if m.notificationClient != nil {
		return m.notificationClient, nil
	}

	target := m.config.Services["notification-service"]
	client, err := NewNotificationClient(m.factory, target)
	if err != nil {
		return nil, err
	}

	m.notificationClient = client
	return client, nil
}

// Close 关闭所有客户端连接
func (m *ClientManager) Close() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	return m.factory.Close()
}

// HealthCheck 检查所有服务的健康状态
func (m *ClientManager) HealthCheck(ctx context.Context) map[string]bool {
	return m.factory.HealthCheck(ctx)
}

// GetMetrics 获取所有服务的指标
func (m *ClientManager) GetMetrics() map[string]interface{} {
	return m.factory.GetMetrics()
}

// 全局客户端管理器
var (
	globalManager     *ClientManager
	globalManagerOnce sync.Once
	globalManagerErr  error
)

// GetGlobalManager 获取全局客户端管理器
func GetGlobalManager() (*ClientManager, error) {
	globalManagerOnce.Do(func() {
		globalManager, globalManagerErr = NewClientManager(DefaultClientConfig())
	})
	return globalManager, globalManagerErr
}

// InitGlobalManager 初始化全局客户端管理器（带自定义配置）
func InitGlobalManager(config *ClientConfig) error {
	manager, err := NewClientManager(config)
	if err != nil {
		return err
	}
	globalManager = manager
	globalManagerErr = nil
	return nil
}

// MustGetGlobalManager 获取全局客户端管理器（panic on error）
func MustGetGlobalManager() *ClientManager {
	manager, err := GetGlobalManager()
	if err != nil {
		panic(fmt.Sprintf("failed to get global client manager: %v", err))
	}
	return manager
}
