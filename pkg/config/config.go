package config

import (
	"fmt"
	"os"
	"strings"

	"github.com/nacos-group/nacos-sdk-go/v2/clients"
	"github.com/nacos-group/nacos-sdk-go/v2/clients/config_client"
	"github.com/nacos-group/nacos-sdk-go/v2/common/constant"
	"github.com/nacos-group/nacos-sdk-go/v2/vo"
	"github.com/spf13/viper"
)

// ConfigMode 配置模式
type ConfigMode string

const (
	// ModeLocal 本地配置模式
	ModeLocal ConfigMode = "local"
	// ModeNacos Nacos配置中心模式
	ModeNacos ConfigMode = "nacos"
)

// NacosConfig Nacos配置
type NacosConfig struct {
	ServerAddr string `mapstructure:"server_addr" yaml:"server_addr"`
	ServerPort uint64 `mapstructure:"server_port" yaml:"server_port"`
	Namespace  string `mapstructure:"namespace" yaml:"namespace"`
	Group      string `mapstructure:"group" yaml:"group"`
	DataID     string `mapstructure:"data_id" yaml:"data_id"`
	Username   string `mapstructure:"username" yaml:"username"`
	Password   string `mapstructure:"password" yaml:"password"`
	LogDir     string `mapstructure:"log_dir" yaml:"log_dir"`
	CacheDir   string `mapstructure:"cache_dir" yaml:"cache_dir"`
	LogLevel   string `mapstructure:"log_level" yaml:"log_level"`
	TimeoutMs  uint64 `mapstructure:"timeout_ms" yaml:"timeout_ms"`
}

// Manager 配置管理器
type Manager struct {
	mode        ConfigMode
	nacosClient config_client.IConfigClient
	nacosConfig *NacosConfig
	viper       *viper.Viper
	localConfig string
}

// NewManager 创建配置管理器
func NewManager() *Manager {
	return &Manager{
		viper: viper.New(),
	}
}

// LoadConfig 加载配置
// configPath: 本地配置文件路径（用于本地模式或Nacos连接配置）
// serviceName: 服务名称（用作Nacos DataID的前缀）
func (m *Manager) LoadConfig(configPath, serviceName string) error {
	// 从环境变量获取配置模式，默认为本地模式
	mode := os.Getenv("CONFIG_MODE")
	if mode == "" {
		mode = string(ModeLocal)
	}
	m.mode = ConfigMode(strings.ToLower(mode))

	switch m.mode {
	case ModeNacos:
		return m.loadFromNacos(configPath, serviceName)
	case ModeLocal:
		return m.loadFromLocal(configPath)
	default:
		return fmt.Errorf("unsupported config mode: %s", mode)
	}
}

// loadFromLocal 从本地文件加载配置
func (m *Manager) loadFromLocal(configPath string) error {
	m.localConfig = configPath
	m.viper.SetConfigFile(configPath)

	if err := m.viper.ReadInConfig(); err != nil {
		return fmt.Errorf("read local config failed: %w", err)
	}

	fmt.Printf("✅ Loaded config from local file: %s\n", configPath)
	return nil
}

// loadFromNacos 从Nacos配置中心加载配置
func (m *Manager) loadFromNacos(configPath, serviceName string) error {
	// 1. 先从本地文件读取Nacos连接配置
	localViper := viper.New()
	localViper.SetConfigFile(configPath)
	if err := localViper.ReadInConfig(); err != nil {
		return fmt.Errorf("read nacos connection config failed: %w", err)
	}

	// 2. 解析Nacos配置
	m.nacosConfig = &NacosConfig{}
	if err := localViper.UnmarshalKey("nacos", m.nacosConfig); err != nil {
		return fmt.Errorf("unmarshal nacos config failed: %w", err)
	}

	// 环境变量覆盖
	if addr := os.Getenv("NACOS_SERVER_ADDR"); addr != "" {
		m.nacosConfig.ServerAddr = addr
	}
	if ns := os.Getenv("NACOS_NAMESPACE"); ns != "" {
		m.nacosConfig.Namespace = ns
	}
	if group := os.Getenv("NACOS_GROUP"); group != "" {
		m.nacosConfig.Group = group
	}
	if dataID := os.Getenv("NACOS_DATA_ID"); dataID != "" {
		m.nacosConfig.DataID = dataID
	} else if m.nacosConfig.DataID == "" {
		// 默认使用服务名作为DataID
		m.nacosConfig.DataID = serviceName + ".yaml"
	}
	if username := os.Getenv("NACOS_USERNAME"); username != "" {
		m.nacosConfig.Username = username
	}
	if password := os.Getenv("NACOS_PASSWORD"); password != "" {
		m.nacosConfig.Password = password
	}

	// 设置默认值
	if m.nacosConfig.ServerPort == 0 {
		m.nacosConfig.ServerPort = 8848
	}
	if m.nacosConfig.Group == "" {
		m.nacosConfig.Group = "DEFAULT_GROUP"
	}
	if m.nacosConfig.LogDir == "" {
		m.nacosConfig.LogDir = "/tmp/nacos/log"
	}
	if m.nacosConfig.CacheDir == "" {
		m.nacosConfig.CacheDir = "/tmp/nacos/cache"
	}
	if m.nacosConfig.LogLevel == "" {
		m.nacosConfig.LogLevel = "info"
	}
	if m.nacosConfig.TimeoutMs == 0 {
		m.nacosConfig.TimeoutMs = 5000
	}

	// 3. 创建Nacos客户端
	serverConfigs := []constant.ServerConfig{
		*constant.NewServerConfig(
			m.nacosConfig.ServerAddr,
			m.nacosConfig.ServerPort,
			constant.WithContextPath("/nacos"),
		),
	}

	clientConfig := *constant.NewClientConfig(
		constant.WithNamespaceId(m.nacosConfig.Namespace),
		constant.WithTimeoutMs(m.nacosConfig.TimeoutMs),
		constant.WithNotLoadCacheAtStart(true),
		constant.WithLogDir(m.nacosConfig.LogDir),
		constant.WithCacheDir(m.nacosConfig.CacheDir),
		constant.WithLogLevel(m.nacosConfig.LogLevel),
		constant.WithUsername(m.nacosConfig.Username),
		constant.WithPassword(m.nacosConfig.Password),
	)

	configClient, err := clients.NewConfigClient(
		vo.NacosClientParam{
			ClientConfig:  &clientConfig,
			ServerConfigs: serverConfigs,
		},
	)
	if err != nil {
		return fmt.Errorf("create nacos client failed: %w", err)
	}
	m.nacosClient = configClient

	// 4. 从Nacos获取配置
	content, err := configClient.GetConfig(vo.ConfigParam{
		DataId: m.nacosConfig.DataID,
		Group:  m.nacosConfig.Group,
	})
	if err != nil {
		return fmt.Errorf("get config from nacos failed: %w", err)
	}

	// 5. 将配置内容加载到viper
	m.viper.SetConfigType("yaml")
	if err := m.viper.ReadConfig(strings.NewReader(content)); err != nil {
		return fmt.Errorf("parse nacos config failed: %w", err)
	}

	fmt.Printf("✅ Loaded config from Nacos: %s/%s (namespace: %s)\n",
		m.nacosConfig.Group, m.nacosConfig.DataID, m.nacosConfig.Namespace)

	// 6. 监听配置变更
	if err := m.watchConfigChange(); err != nil {
		fmt.Printf("⚠️  Watch config change failed: %v\n", err)
	}

	return nil
}

// watchConfigChange 监听配置变更
func (m *Manager) watchConfigChange() error {
	return m.nacosClient.ListenConfig(vo.ConfigParam{
		DataId: m.nacosConfig.DataID,
		Group:  m.nacosConfig.Group,
		OnChange: func(namespace, group, dataId, data string) {
			fmt.Printf("🔄 Config changed: %s/%s\n", group, dataId)
			// 重新加载配置
			m.viper.SetConfigType("yaml")
			if err := m.viper.ReadConfig(strings.NewReader(data)); err != nil {
				fmt.Printf("❌ Reload config failed: %v\n", err)
			} else {
				fmt.Println("✅ Config reloaded successfully")
			}
		},
	})
}

// Unmarshal 解析配置到结构体
func (m *Manager) Unmarshal(rawVal interface{}) error {
	return m.viper.Unmarshal(rawVal)
}

// UnmarshalKey 解析指定key的配置到结构体
func (m *Manager) UnmarshalKey(key string, rawVal interface{}) error {
	return m.viper.UnmarshalKey(key, rawVal)
}

// Get 获取配置值
func (m *Manager) Get(key string) interface{} {
	return m.viper.Get(key)
}

// GetString 获取字符串配置
func (m *Manager) GetString(key string) string {
	return m.viper.GetString(key)
}

// GetInt 获取整数配置
func (m *Manager) GetInt(key string) int {
	return m.viper.GetInt(key)
}

// GetBool 获取布尔配置
func (m *Manager) GetBool(key string) bool {
	return m.viper.GetBool(key)
}

// GetMode 获取配置模式
func (m *Manager) GetMode() ConfigMode {
	return m.mode
}

// Viper 获取底层viper实例
func (m *Manager) Viper() *viper.Viper {
	return m.viper
}

// Close 关闭配置管理器
func (m *Manager) Close() error {
	if m.nacosClient != nil {
		m.nacosClient.CancelListenConfig(vo.ConfigParam{
			DataId: m.nacosConfig.DataID,
			Group:  m.nacosConfig.Group,
		})
	}
	return nil
}
