package algo

import (
	"context"
	"fmt"
	"sync"
	"time"

	"voicehelper/pkg/config"
)

// ClientManager 算法服务客户端管理器
type ClientManager struct {
	AgentEngine         *BaseClient // 保持向后兼容，实际使用时需要类型转换
	RAGEngine           *BaseClient
	RetrievalService    *BaseClient
	ModelAdapter        *BaseClient
	VoiceEngine         *VoiceEngineClient
	MultimodalEngine    *MultimodalEngineClient
	IndexingService     *IndexingServiceClient
	VectorStoreAdapter  *VectorStoreAdapterClient
	KnowledgeService    *KnowledgeServiceClient  // 统一的知识服务（合并后）

	// 内部字段
	config              *config.ServicesConfig
	healthCheckInterval time.Duration
	healthStatus        map[string]bool
	healthMu            sync.RWMutex
	stopHealthCheck     chan struct{}
}

// ClientManagerConfig 客户端管理器配置
type ClientManagerConfig struct {
	ConfigPath          string        // 配置文件路径
	HealthCheckInterval time.Duration // 健康检查间隔，0表示不启用
}

// NewClientManager 创建客户端管理器
func NewClientManager(cfg *ClientManagerConfig) (*ClientManager, error) {
	// 加载服务配置
	var serviceConfig *config.ServicesConfig
	var err error

	if cfg.ConfigPath != "" {
		serviceConfig, err = config.LoadServicesConfig(cfg.ConfigPath)
	} else {
		serviceConfig, err = config.LoadServicesConfigFromEnv()
	}
	if err != nil {
		return nil, fmt.Errorf("load services config: %w", err)
	}

	// 获取所有服务URL
	serviceURLs := serviceConfig.GetHTTPServiceURLs()

	// 创建客户端管理器
	manager := &ClientManager{
		config:              serviceConfig,
		healthCheckInterval: cfg.HealthCheckInterval,
		healthStatus:        make(map[string]bool),
		stopHealthCheck:     make(chan struct{}),
	}

	// 初始化各个客户端
	if url, ok := serviceURLs["agent-engine"]; ok {
		manager.AgentEngine = NewBaseClient(BaseClientConfig{
			ServiceName: "agent-engine",
			BaseURL:     url,
			Timeout:     60 * time.Second,
		})
	}

	// RAG Engine 已合并到 knowledge-service，保留此字段用于向后兼容
	// 如果需要 RAG 功能，请使用 knowledge-service
	// if url, ok := serviceURLs["rag-engine"]; ok {
	// 	manager.RAGEngine = NewBaseClient(BaseClientConfig{
	// 		ServiceName: "rag-engine",
	// 		BaseURL:     url,
	// 		Timeout:     30 * time.Second,
	// 	})
	// }

	if url, ok := serviceURLs["retrieval-service"]; ok {
		manager.RetrievalService = NewBaseClient(BaseClientConfig{
			ServiceName: "retrieval-service",
			BaseURL:     url,
			Timeout:     30 * time.Second,  // 更新为 30s，混合检索+重排可能较慢
		})
	}

	if url, ok := serviceURLs["model-adapter"]; ok {
		manager.ModelAdapter = NewBaseClient(BaseClientConfig{
			ServiceName: "model-adapter",
			BaseURL:     url,
			Timeout:     60 * time.Second,
		})
	}

	if url, ok := serviceURLs["voice-engine"]; ok {
		manager.VoiceEngine = NewVoiceEngineClient(url)
	}

	if url, ok := serviceURLs["multimodal-engine"]; ok {
		manager.MultimodalEngine = NewMultimodalEngineClient(url)
	}

	if url, ok := serviceURLs["indexing-service"]; ok {
		manager.IndexingService = NewIndexingServiceClient(url)
	}

	if url, ok := serviceURLs["vector-store-adapter"]; ok {
		manager.VectorStoreAdapter = NewVectorStoreAdapterClient(url)
	}

	if url, ok := serviceURLs["knowledge-service"]; ok {
		manager.KnowledgeService = NewKnowledgeServiceClient(url)
	}

	// 启动健康检查
	if manager.healthCheckInterval > 0 {
		go manager.startHealthCheck()
	}

	return manager, nil
}

// startHealthCheck 启动健康检查
func (m *ClientManager) startHealthCheck() {
	ticker := time.NewTicker(m.healthCheckInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			m.performHealthCheck()
		case <-m.stopHealthCheck:
			return
		}
	}
}

// performHealthCheck 执行健康检查
func (m *ClientManager) performHealthCheck() {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	clients := map[string]interface{}{
		"agent-engine":         m.AgentEngine,
		// "rag-engine":           m.RAGEngine,  // 已废弃，已合并到 knowledge-service
		"retrieval-service":    m.RetrievalService,
		"model-adapter":        m.ModelAdapter,
		"voice-engine":         m.VoiceEngine,
		"multimodal-engine":    m.MultimodalEngine,
		"indexing-service":     m.IndexingService,
		"vector-store-adapter": m.VectorStoreAdapter,
		"knowledge-service":    m.KnowledgeService,
	}

	m.healthMu.Lock()
	defer m.healthMu.Unlock()

	for name, client := range clients {
		if client == nil {
			m.healthStatus[name] = false
			continue
		}

		// 根据类型执行健康检查
		var err error
		switch c := client.(type) {
		case *BaseClient:
			err = c.HealthCheck(ctx)
		case *VoiceEngineClient:
			err = c.HealthCheck(ctx)
		case *MultimodalEngineClient:
			err = c.HealthCheck(ctx)
		case *IndexingServiceClient:
			err = c.HealthCheck(ctx)
		case *VectorStoreAdapterClient:
			err = c.HealthCheck(ctx)
		case *KnowledgeServiceClient:
			err = c.HealthCheck(ctx)
		}

		m.healthStatus[name] = (err == nil)
	}
}

// GetHealthStatus 获取健康状态
func (m *ClientManager) GetHealthStatus() map[string]bool {
	m.healthMu.RLock()
	defer m.healthMu.RUnlock()

	// 复制状态
	status := make(map[string]bool)
	for k, v := range m.healthStatus {
		status[k] = v
	}

	return status
}

// IsServiceHealthy 检查服务是否健康
func (m *ClientManager) IsServiceHealthy(serviceName string) bool {
	m.healthMu.RLock()
	defer m.healthMu.RUnlock()

	healthy, ok := m.healthStatus[serviceName]
	return ok && healthy
}

// GetAllServiceStatus 获取所有服务的详细状态
func (m *ClientManager) GetAllServiceStatus(ctx context.Context) map[string]ServiceStatus {
	clients := map[string]interface{}{
		"agent-engine":         m.AgentEngine,
		// "rag-engine":           m.RAGEngine,  // 已废弃，已合并到 knowledge-service
		"retrieval-service":    m.RetrievalService,
		"model-adapter":        m.ModelAdapter,
		"voice-engine":         m.VoiceEngine,
		"multimodal-engine":    m.MultimodalEngine,
		"indexing-service":     m.IndexingService,
		"vector-store-adapter": m.VectorStoreAdapter,
		"knowledge-service":    m.KnowledgeService,
	}

	status := make(map[string]ServiceStatus)

	for name, client := range clients {
		if client == nil {
			status[name] = ServiceStatus{
				Name:      name,
				Available: false,
				Healthy:   false,
			}
			continue
		}

		svcStatus := ServiceStatus{
			Name:      name,
			Available: true,
		}

		// 执行健康检查
		var err error
		switch c := client.(type) {
		case *BaseClient:
			svcStatus.BaseURL = c.GetBaseURL()
			svcStatus.CircuitBreakerState = c.GetCircuitBreakerState().String()
			err = c.HealthCheck(ctx)
		case *VoiceEngineClient:
			svcStatus.BaseURL = c.GetBaseURL()
			svcStatus.CircuitBreakerState = c.GetCircuitBreakerState().String()
			err = c.HealthCheck(ctx)
		case *MultimodalEngineClient:
			svcStatus.BaseURL = c.GetBaseURL()
			svcStatus.CircuitBreakerState = c.GetCircuitBreakerState().String()
			err = c.HealthCheck(ctx)
		case *IndexingServiceClient:
			svcStatus.BaseURL = c.GetBaseURL()
			svcStatus.CircuitBreakerState = c.GetCircuitBreakerState().String()
			err = c.HealthCheck(ctx)
		case *VectorStoreAdapterClient:
			svcStatus.BaseURL = c.GetBaseURL()
			svcStatus.CircuitBreakerState = c.GetCircuitBreakerState().String()
			err = c.HealthCheck(ctx)
		case *KnowledgeServiceClient:
			svcStatus.BaseURL = c.GetBaseURL()
			svcStatus.CircuitBreakerState = c.GetCircuitBreakerState().String()
			err = c.HealthCheck(ctx)
		}

		svcStatus.Healthy = (err == nil)
		if err != nil {
			svcStatus.Error = err.Error()
		}

		status[name] = svcStatus
	}

	return status
}

// ServiceStatus 服务状态
type ServiceStatus struct {
	Name                 string `json:"name"`
	BaseURL              string `json:"base_url"`
	Available            bool   `json:"available"`
	Healthy              bool   `json:"healthy"`
	CircuitBreakerState  string `json:"circuit_breaker_state"`
	Error                string `json:"error,omitempty"`
}

// Close 关闭客户端管理器
func (m *ClientManager) Close() {
	if m.healthCheckInterval > 0 {
		close(m.stopHealthCheck)
	}
}

// NewClientManagerFromEnv 从环境变量创建客户端管理器
func NewClientManagerFromEnv() (*ClientManager, error) {
	return NewClientManager(&ClientManagerConfig{
		ConfigPath:          "", // 使用环境变量
		HealthCheckInterval: 30 * time.Second,
	})
}

// NewClientManagerFromConfig 从配置文件创建客户端管理器
func NewClientManagerFromConfig(configPath string) (*ClientManager, error) {
	return NewClientManager(&ClientManagerConfig{
		ConfigPath:          configPath,
		HealthCheckInterval: 30 * time.Second,
	})
}
