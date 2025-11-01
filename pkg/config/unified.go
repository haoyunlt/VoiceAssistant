package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/spf13/viper"
)

// UnifiedConfig 统一配置接口
type UnifiedConfig interface {
	// GetString 获取字符串配置
	GetString(key string) string
	// GetInt 获取整数配置
	GetInt(key string) int
	// GetBool 获取布尔配置
	GetBool(key string) bool
	// GetDuration 获取时间间隔配置
	GetDuration(key string) time.Duration
	// Unmarshal 解析配置到结构体
	Unmarshal(rawVal interface{}) error
	// UnmarshalKey 解析指定key的配置到结构体
	UnmarshalKey(key string, rawVal interface{}) error
	// IsSet 检查key是否被设置
	IsSet(key string) bool
	// GetMode 获取配置模式
	GetMode() ConfigMode
	// Close 关闭配置管理器
	Close() error
}

// LoaderOptions 配置加载选项
type LoaderOptions struct {
	// ConfigPath 配置文件路径
	ConfigPath string
	// ServiceName 服务名称
	ServiceName string
	// EnvPrefix 环境变量前缀（默认为服务名大写）
	EnvPrefix string
	// AllowEnvOverride 是否允许环境变量覆盖配置文件
	AllowEnvOverride bool
	// RequiredKeys 必需的配置键
	RequiredKeys []string
}

// UnifiedConfigLoader 统一配置加载器
type UnifiedConfigLoader struct {
	manager *Manager
	options *LoaderOptions
}

// NewUnifiedConfigLoader 创建统一配置加载器
func NewUnifiedConfigLoader(opts *LoaderOptions) *UnifiedConfigLoader {
	if opts.EnvPrefix == "" {
		// 默认使用服务名的大写作为环境变量前缀
		opts.EnvPrefix = strings.ToUpper(strings.ReplaceAll(opts.ServiceName, "-", "_"))
	}
	if opts.AllowEnvOverride {
		// 默认允许环境变量覆盖
		opts.AllowEnvOverride = true
	}

	return &UnifiedConfigLoader{
		manager: NewManager(),
		options: opts,
	}
}

// Load 加载配置
func (l *UnifiedConfigLoader) Load() (UnifiedConfig, error) {
	// 1. 加载基础配置（本地或 Nacos）
	if err := l.manager.LoadConfig(l.options.ConfigPath, l.options.ServiceName); err != nil {
		return nil, fmt.Errorf("failed to load config: %w", err)
	}

	// 2. 如果允许环境变量覆盖，则设置自动环境变量
	if l.options.AllowEnvOverride {
		l.manager.viper.SetEnvPrefix(l.options.EnvPrefix)
		l.manager.viper.AutomaticEnv()
		l.manager.viper.SetEnvKeyReplacer(strings.NewReplacer(".", "_", "-", "_"))
	}

	// 3. 验证必需的配置键
	if err := l.validateRequiredKeys(); err != nil {
		return nil, err
	}

	return l.manager, nil
}

// validateRequiredKeys 验证必需的配置键
func (l *UnifiedConfigLoader) validateRequiredKeys() error {
	var missing []string
	for _, key := range l.options.RequiredKeys {
		if !l.manager.viper.IsSet(key) {
			missing = append(missing, key)
		}
	}

	if len(missing) > 0 {
		return fmt.Errorf("missing required config keys: %v", missing)
	}

	return nil
}

// ==================== Manager 实现 UnifiedConfig 接口 ====================

// GetDuration 获取时间间隔配置
func (m *Manager) GetDuration(key string) time.Duration {
	return m.viper.GetDuration(key)
}

// IsSet 检查key是否被设置
func (m *Manager) IsSet(key string) bool {
	return m.viper.IsSet(key)
}

// ==================== 辅助函数 ====================

// GetEnvOrDefault 从环境变量获取配置，如果不存在则返回默认值
func GetEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// GetEnvAsIntOrDefault 从环境变量获取整数配置
func GetEnvAsIntOrDefault(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return intVal
		}
	}
	return defaultValue
}

// GetEnvAsBoolOrDefault 从环境变量获取布尔配置
func GetEnvAsBoolOrDefault(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		return strings.ToLower(value) == "true" || value == "1"
	}
	return defaultValue
}

// GetEnvAsDurationOrDefault 从环境变量获取时间间隔配置
func GetEnvAsDurationOrDefault(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if duration, err := time.ParseDuration(value); err == nil {
			return duration
		}
	}
	return defaultValue
}

// ==================== 配置验证器 ====================

// Validator 配置验证器
type Validator struct {
	rules []ValidationRule
}

// ValidationRule 验证规则
type ValidationRule struct {
	Key       string
	Required  bool
	Validator func(value interface{}) error
}

// NewValidator 创建验证器
func NewValidator() *Validator {
	return &Validator{
		rules: make([]ValidationRule, 0),
	}
}

// AddRule 添加验证规则
func (v *Validator) AddRule(key string, required bool, validator func(value interface{}) error) {
	v.rules = append(v.rules, ValidationRule{
		Key:       key,
		Required:  required,
		Validator: validator,
	})
}

// Validate 验证配置
func (v *Validator) Validate(config UnifiedConfig) error {
	for _, rule := range v.rules {
		if rule.Required && !config.IsSet(rule.Key) {
			return fmt.Errorf("required config key '%s' is not set", rule.Key)
		}

		if config.IsSet(rule.Key) && rule.Validator != nil {
			value := config.GetString(rule.Key)
			if err := rule.Validator(value); err != nil {
				return fmt.Errorf("validation failed for key '%s': %w", rule.Key, err)
			}
		}
	}
	return nil
}

// ==================== 常用验证器 ====================

// ValidateURL 验证 URL 格式
func ValidateURL(value interface{}) error {
	str, ok := value.(string)
	if !ok {
		return fmt.Errorf("expected string, got %T", value)
	}
	if !strings.HasPrefix(str, "http://") && !strings.HasPrefix(str, "https://") {
		return fmt.Errorf("invalid URL format: %s", str)
	}
	return nil
}

// ValidatePort 验证端口号
func ValidatePort(value interface{}) error {
	var port int
	switch v := value.(type) {
	case int:
		port = v
	case string:
		var err error
		port, err = strconv.Atoi(v)
		if err != nil {
			return fmt.Errorf("invalid port number: %s", v)
		}
	default:
		return fmt.Errorf("expected int or string, got %T", value)
	}

	if port < 1 || port > 65535 {
		return fmt.Errorf("port number out of range: %d", port)
	}
	return nil
}

// ValidateNotEmpty 验证非空
func ValidateNotEmpty(value interface{}) error {
	str, ok := value.(string)
	if !ok {
		return fmt.Errorf("expected string, got %T", value)
	}
	if strings.TrimSpace(str) == "" {
		return fmt.Errorf("value cannot be empty")
	}
	return nil
}
