package conf

import (
	"os"
	"time"

	"github.com/spf13/viper"
)

// Config 应用配置
type Config struct {
	Server       ServerConfig       `mapstructure:"server"`
	Database     DatabaseConfig     `mapstructure:"database"`
	ClickHouse   ClickHouseConfig   `mapstructure:"clickhouse"`
	Redis        RedisConfig        `mapstructure:"redis"`
	Cache        CacheConfig        `mapstructure:"cache"`
	Observability ObservabilityConfig `mapstructure:"observability"`
	Resilience   ResilienceConfig   `mapstructure:"resilience"`
	Auth         AuthConfig         `mapstructure:"auth"`
	Tenant       TenantConfig       `mapstructure:"tenant"`
}

// ServerConfig 服务器配置
type ServerConfig struct {
	HTTPPort        int           `mapstructure:"http_port"`
	GRPCPort        int           `mapstructure:"grpc_port"`
	ShutdownTimeout time.Duration `mapstructure:"shutdown_timeout"`
	ReadTimeout     time.Duration `mapstructure:"read_timeout"`
	WriteTimeout    time.Duration `mapstructure:"write_timeout"`
}

// DatabaseConfig 数据库配置
type DatabaseConfig struct {
	Host            string        `mapstructure:"host"`
	Port            int           `mapstructure:"port"`
	DBName          string        `mapstructure:"dbname"`
	User            string        `mapstructure:"user"`
	Password        string        `mapstructure:"password"`
	SSLMode         string        `mapstructure:"sslmode"`
	MaxOpenConns    int           `mapstructure:"max_open_conns"`
	MaxIdleConns    int           `mapstructure:"max_idle_conns"`
	ConnMaxLifetime time.Duration `mapstructure:"conn_max_lifetime"`
}

// ClickHouseConfig ClickHouse 配置
type ClickHouseConfig struct {
	Addr            string        `mapstructure:"addr"`
	Database        string        `mapstructure:"database"`
	Username        string        `mapstructure:"username"`
	Password        string        `mapstructure:"password"`
	MaxOpenConns    int           `mapstructure:"max_open_conns"`
	MaxIdleConns    int           `mapstructure:"max_idle_conns"`
	ConnMaxLifetime time.Duration `mapstructure:"conn_max_lifetime"`
	DialTimeout     time.Duration `mapstructure:"dial_timeout"`
	ReadTimeout     time.Duration `mapstructure:"read_timeout"`
	WriteTimeout    time.Duration `mapstructure:"write_timeout"`
}

// RedisConfig Redis 配置
type RedisConfig struct {
	Addr         string        `mapstructure:"addr"`
	Password     string        `mapstructure:"password"`
	DB           int           `mapstructure:"db"`
	PoolSize     int           `mapstructure:"pool_size"`
	MinIdleConns int           `mapstructure:"min_idle_conns"`
	MaxRetries   int           `mapstructure:"max_retries"`
	DialTimeout  time.Duration `mapstructure:"dial_timeout"`
	ReadTimeout  time.Duration `mapstructure:"read_timeout"`
	WriteTimeout time.Duration `mapstructure:"write_timeout"`
}

// CacheConfig 缓存配置
type CacheConfig struct {
	DefaultTTL       time.Duration `mapstructure:"default_ttl"`
	RealtimeStatsTTL time.Duration `mapstructure:"realtime_stats_ttl"`
	UsageStatsTTL    time.Duration `mapstructure:"usage_stats_ttl"`
	ModelStatsTTL    time.Duration `mapstructure:"model_stats_ttl"`
}

// ObservabilityConfig 可观测性配置
type ObservabilityConfig struct {
	OTELEndpoint   string `mapstructure:"otel_endpoint"`
	ServiceName    string `mapstructure:"service_name"`
	ServiceVersion string `mapstructure:"service_version"`
	Environment    string `mapstructure:"environment"`
	EnableTrace    bool   `mapstructure:"enable_trace"`
	EnableMetrics  bool   `mapstructure:"enable_metrics"`
	LogLevel       string `mapstructure:"log_level"`
	LogFormat      string `mapstructure:"log_format"`
}

// ResilienceConfig 弹性配置
type ResilienceConfig struct {
	RateLimit      RateLimitConfig      `mapstructure:"rate_limit"`
	CircuitBreaker CircuitBreakerConfig `mapstructure:"circuit_breaker"`
	Timeout        TimeoutConfig        `mapstructure:"timeout"`
}

// RateLimitConfig 限流配置
type RateLimitConfig struct {
	Enabled           bool    `mapstructure:"enabled"`
	RequestsPerSecond float64 `mapstructure:"requests_per_second"`
	Burst             int     `mapstructure:"burst"`
}

// CircuitBreakerConfig 熔断器配置
type CircuitBreakerConfig struct {
	Enabled     bool          `mapstructure:"enabled"`
	MaxRequests uint32        `mapstructure:"max_requests"`
	Interval    time.Duration `mapstructure:"interval"`
	Timeout     time.Duration `mapstructure:"timeout"`
	Threshold   float64       `mapstructure:"threshold"`
}

// TimeoutConfig 超时配置
type TimeoutConfig struct {
	Default          time.Duration `mapstructure:"default"`
	Query            time.Duration `mapstructure:"query"`
	ReportGeneration time.Duration `mapstructure:"report_generation"`
}

// AuthConfig 认证配置
type AuthConfig struct {
	JWTSecret    string        `mapstructure:"jwt_secret"`
	JWTExpiry    time.Duration `mapstructure:"jwt_expiry"`
	APIKeyHeader string        `mapstructure:"api_key_header"`
}

// TenantConfig 租户配置
type TenantConfig struct {
	DefaultLimit     int  `mapstructure:"default_limit"`
	MaxLimit         int  `mapstructure:"max_limit"`
	EnableQuotaCheck bool `mapstructure:"enable_quota_check"`
}

// Load 加载配置
func Load(configPath string) (*Config, error) {
	v := viper.New()

	// 设置配置文件
	if configPath != "" {
		v.SetConfigFile(configPath)
	} else {
		v.SetConfigName("analytics-service")
		v.SetConfigType("yaml")
		v.AddConfigPath("./configs")
		v.AddConfigPath("../configs")
		v.AddConfigPath("../../configs")
	}

	// 自动从环境变量读取
	v.AutomaticEnv()

	// 读取配置文件
	if err := v.ReadInConfig(); err != nil {
		return nil, err
	}

	// 解析配置
	var config Config
	if err := v.Unmarshal(&config); err != nil {
		return nil, err
	}

	// 从环境变量覆盖敏感配置
	if password := os.Getenv("DB_PASSWORD"); password != "" {
		config.Database.Password = password
	}
	if password := os.Getenv("CLICKHOUSE_PASSWORD"); password != "" {
		config.ClickHouse.Password = password
	}
	if password := os.Getenv("REDIS_PASSWORD"); password != "" {
		config.Redis.Password = password
	}
	if secret := os.Getenv("JWT_SECRET"); secret != "" {
		config.Auth.JWTSecret = secret
	}
	if endpoint := os.Getenv("OTEL_ENDPOINT"); endpoint != "" {
		config.Observability.OTELEndpoint = endpoint
	}

	return &config, nil
}
