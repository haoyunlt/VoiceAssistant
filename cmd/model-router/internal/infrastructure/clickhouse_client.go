package infrastructure

import (
	"context"
	"fmt"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"github.com/go-kratos/kratos/v2/log"
)

// ClickHouseClient ClickHouse客户端
type ClickHouseClient struct {
	conn   driver.Conn
	log    *log.Helper
	config *ClickHouseConfig

	// 连接池统计
	stats ConnectionPoolStats
}

// ClickHouseConfig ClickHouse配置
type ClickHouseConfig struct {
	Host     string
	Port     int
	Database string
	Username string
	Password string
	Debug    bool
}

// ConnectionPoolStats 连接池统计信息
type ConnectionPoolStats struct {
	TotalConnections  int64 `json:"total_connections"`
	ActiveConnections int64 `json:"active_connections"`
	IdleConnections   int64 `json:"idle_connections"`
	WaitCount         int64 `json:"wait_count"`
	WaitDuration      int64 `json:"wait_duration_ms"`
	MaxIdleClosed     int64 `json:"max_idle_closed"`
	MaxLifetimeClosed int64 `json:"max_lifetime_closed"`
}

// NewClickHouseClient 创建ClickHouse客户端
func NewClickHouseClient(config *ClickHouseConfig, logger log.Logger) (*ClickHouseClient, error) {
	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{fmt.Sprintf("%s:%d", config.Host, config.Port)},
		Auth: clickhouse.Auth{
			Database: config.Database,
			Username: config.Username,
			Password: config.Password,
		},
		Debug: config.Debug,
		Compression: &clickhouse.Compression{
			Method: clickhouse.CompressionLZ4,
		},
		MaxOpenConns: 10,
		MaxIdleConns: 5,
		DialTimeout:  5 * time.Second,
		Settings: clickhouse.Settings{
			"max_execution_time": 60,
		},
	})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to clickhouse: %w", err)
	}

	// 验证连接
	if err := conn.Ping(context.Background()); err != nil {
		return nil, fmt.Errorf("failed to ping clickhouse: %w", err)
	}

	client := &ClickHouseClient{
		conn:   conn,
		log:    log.NewHelper(logger),
		config: config,
	}

	// 初始化表结构
	if err := client.initTables(context.Background()); err != nil {
		return nil, fmt.Errorf("failed to init tables: %w", err)
	}

	client.log.Info("ClickHouse client initialized successfully")

	return client, nil
}

// initTables 初始化表结构
func (c *ClickHouseClient) initTables(ctx context.Context) error {
	// 创建请求日志表
	createRequestLogTable := `
	CREATE TABLE IF NOT EXISTS model_router.request_logs (
		request_id String,
		tenant_id String,
		user_id String,
		model_id String,
		model_name String,
		model_provider String,

		request_time DateTime64(3),
		response_time DateTime64(3),
		latency_ms UInt32,

		success UInt8,
		error_message String,
		error_code String,

		prompt_tokens UInt32,
		completion_tokens UInt32,
		total_tokens UInt32,

		cost_usd Float64,

		request_type String, -- chat, embedding, completion
		stream UInt8,

		routing_strategy String,
		fallback_used UInt8,
		ab_test_variant String,

		metadata String, -- JSON格式的额外元数据

		created_at DateTime64(3) DEFAULT now64()
	)
	ENGINE = MergeTree()
	PARTITION BY toYYYYMM(request_time)
	ORDER BY (tenant_id, request_time, model_id)
	TTL request_time + INTERVAL 90 DAY
	SETTINGS index_granularity = 8192
	`

	if err := c.conn.Exec(ctx, createRequestLogTable); err != nil {
		return fmt.Errorf("failed to create request_logs table: %w", err)
	}

	// 创建聚合表（物化视图）
	createDailyStatsView := `
	CREATE MATERIALIZED VIEW IF NOT EXISTS model_router.daily_stats
	ENGINE = SummingMergeTree()
	PARTITION BY toYYYYMM(stat_date)
	ORDER BY (stat_date, tenant_id, model_id)
	AS SELECT
		toDate(request_time) as stat_date,
		tenant_id,
		model_id,
		model_name,
		count() as request_count,
		countIf(success = 1) as success_count,
		countIf(success = 0) as error_count,
		avg(latency_ms) as avg_latency_ms,
		quantile(0.95)(latency_ms) as p95_latency_ms,
		quantile(0.99)(latency_ms) as p99_latency_ms,
		sum(prompt_tokens) as total_prompt_tokens,
		sum(completion_tokens) as total_completion_tokens,
		sum(total_tokens) as total_tokens,
		sum(cost_usd) as total_cost_usd
	FROM model_router.request_logs
	GROUP BY stat_date, tenant_id, model_id, model_name
	`

	if err := c.conn.Exec(ctx, createDailyStatsView); err != nil {
		// 忽略已存在的错误
		c.log.Warnf("failed to create daily_stats view (may already exist): %v", err)
	}

	c.log.Info("ClickHouse tables initialized")
	return nil
}

// RequestLog 请求日志
type RequestLog struct {
	RequestID        string
	TenantID         string
	UserID           string
	ModelID          string
	ModelName        string
	ModelProvider    string
	RequestTime      time.Time
	ResponseTime     time.Time
	LatencyMs        uint32
	Success          bool
	ErrorMessage     string
	ErrorCode        string
	PromptTokens     uint32
	CompletionTokens uint32
	TotalTokens      uint32
	CostUSD          float64
	RequestType      string
	Stream           bool
	RoutingStrategy  string
	FallbackUsed     bool
	ABTestVariant    string
	Metadata         string
}

// InsertRequestLog 插入请求日志
func (c *ClickHouseClient) InsertRequestLog(ctx context.Context, log *RequestLog) error {
	query := `
	INSERT INTO model_router.request_logs (
		request_id, tenant_id, user_id, model_id, model_name, model_provider,
		request_time, response_time, latency_ms,
		success, error_message, error_code,
		prompt_tokens, completion_tokens, total_tokens,
		cost_usd, request_type, stream,
		routing_strategy, fallback_used, ab_test_variant,
		metadata
	) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	err := c.conn.Exec(ctx, query,
		log.RequestID, log.TenantID, log.UserID, log.ModelID, log.ModelName, log.ModelProvider,
		log.RequestTime, log.ResponseTime, log.LatencyMs,
		btoi(log.Success), log.ErrorMessage, log.ErrorCode,
		log.PromptTokens, log.CompletionTokens, log.TotalTokens,
		log.CostUSD, log.RequestType, btoi(log.Stream),
		log.RoutingStrategy, btoi(log.FallbackUsed), log.ABTestVariant,
		log.Metadata,
	)
	if err != nil {
		c.log.Errorf("failed to insert request log: %v", err)
		return err
	}

	return nil
}

// BatchInsertRequestLogs 批量插入请求日志
func (c *ClickHouseClient) BatchInsertRequestLogs(ctx context.Context, logs []*RequestLog) error {
	if len(logs) == 0 {
		return nil
	}

	batch, err := c.conn.PrepareBatch(ctx, `
		INSERT INTO model_router.request_logs (
			request_id, tenant_id, user_id, model_id, model_name, model_provider,
			request_time, response_time, latency_ms,
			success, error_message, error_code,
			prompt_tokens, completion_tokens, total_tokens,
			cost_usd, request_type, stream,
			routing_strategy, fallback_used, ab_test_variant,
			metadata
		)
	`)
	if err != nil {
		return fmt.Errorf("failed to prepare batch: %w", err)
	}

	for _, log := range logs {
		err := batch.Append(
			log.RequestID, log.TenantID, log.UserID, log.ModelID, log.ModelName, log.ModelProvider,
			log.RequestTime, log.ResponseTime, log.LatencyMs,
			btoi(log.Success), log.ErrorMessage, log.ErrorCode,
			log.PromptTokens, log.CompletionTokens, log.TotalTokens,
			log.CostUSD, log.RequestType, btoi(log.Stream),
			log.RoutingStrategy, btoi(log.FallbackUsed), log.ABTestVariant,
			log.Metadata,
		)
		if err != nil {
			return fmt.Errorf("failed to append to batch: %w", err)
		}
	}

	if err := batch.Send(); err != nil {
		c.log.Errorf("failed to send batch: %v", err)
		return err
	}

	c.log.Infof("batch inserted %d request logs", len(logs))
	return nil
}

// DailyStats 日统计数据
type DailyStats struct {
	StatDate              time.Time
	TenantID              string
	ModelID               string
	ModelName             string
	RequestCount          uint64
	SuccessCount          uint64
	ErrorCount            uint64
	AvgLatencyMs          float64
	P95LatencyMs          float64
	P99LatencyMs          float64
	TotalPromptTokens     uint64
	TotalCompletionTokens uint64
	TotalTokens           uint64
	TotalCostUSD          float64
}

// GetDailyStats 获取日统计数据
func (c *ClickHouseClient) GetDailyStats(
	ctx context.Context,
	tenantID string,
	startDate, endDate time.Time,
) ([]*DailyStats, error) {
	query := `
	SELECT
		stat_date,
		tenant_id,
		model_id,
		model_name,
		sum(request_count) as request_count,
		sum(success_count) as success_count,
		sum(error_count) as error_count,
		avg(avg_latency_ms) as avg_latency_ms,
		quantile(0.95)(p95_latency_ms) as p95_latency_ms,
		quantile(0.99)(p99_latency_ms) as p99_latency_ms,
		sum(total_prompt_tokens) as total_prompt_tokens,
		sum(total_completion_tokens) as total_completion_tokens,
		sum(total_tokens) as total_tokens,
		sum(total_cost_usd) as total_cost_usd
	FROM model_router.daily_stats
	WHERE tenant_id = ?
		AND stat_date >= ?
		AND stat_date <= ?
	GROUP BY stat_date, tenant_id, model_id, model_name
	ORDER BY stat_date DESC, total_cost_usd DESC
	`

	rows, err := c.conn.Query(ctx, query, tenantID, startDate, endDate)
	if err != nil {
		return nil, fmt.Errorf("failed to query daily stats: %w", err)
	}
	defer rows.Close()

	var stats []*DailyStats
	for rows.Next() {
		var s DailyStats
		if err := rows.Scan(
			&s.StatDate, &s.TenantID, &s.ModelID, &s.ModelName,
			&s.RequestCount, &s.SuccessCount, &s.ErrorCount,
			&s.AvgLatencyMs, &s.P95LatencyMs, &s.P99LatencyMs,
			&s.TotalPromptTokens, &s.TotalCompletionTokens,
			&s.TotalTokens, &s.TotalCostUSD,
		); err != nil {
			return nil, fmt.Errorf("failed to scan row: %w", err)
		}
		stats = append(stats, &s)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows error: %w", err)
	}

	return stats, nil
}

// ModelCostAnalysis 模型成本分析
type ModelCostAnalysis struct {
	ModelID              string
	ModelName            string
	TotalRequests        uint64
	TotalCostUSD         float64
	AvgCostPerRequest    float64
	TotalTokens          uint64
	AvgTokensPerRequest  float64
	CostPerMillionTokens float64
	ErrorRate            float64
}

// GetModelCostAnalysis 获取模型成本分析
func (c *ClickHouseClient) GetModelCostAnalysis(
	ctx context.Context,
	tenantID string,
	startTime, endTime time.Time,
	topN int,
) ([]*ModelCostAnalysis, error) {
	query := `
	SELECT
		model_id,
		model_name,
		count() as total_requests,
		sum(cost_usd) as total_cost_usd,
		avg(cost_usd) as avg_cost_per_request,
		sum(total_tokens) as total_tokens,
		avg(total_tokens) as avg_tokens_per_request,
		if(sum(total_tokens) > 0, sum(cost_usd) / sum(total_tokens) * 1000000, 0) as cost_per_million_tokens,
		countIf(success = 0) / count() as error_rate
	FROM model_router.request_logs
	WHERE tenant_id = ?
		AND request_time >= ?
		AND request_time <= ?
	GROUP BY model_id, model_name
	ORDER BY total_cost_usd DESC
	LIMIT ?
	`

	rows, err := c.conn.Query(ctx, query, tenantID, startTime, endTime, topN)
	if err != nil {
		return nil, fmt.Errorf("failed to query cost analysis: %w", err)
	}
	defer rows.Close()

	var analyses []*ModelCostAnalysis
	for rows.Next() {
		var a ModelCostAnalysis
		if err := rows.Scan(
			&a.ModelID, &a.ModelName, &a.TotalRequests, &a.TotalCostUSD,
			&a.AvgCostPerRequest, &a.TotalTokens, &a.AvgTokensPerRequest,
			&a.CostPerMillionTokens, &a.ErrorRate,
		); err != nil {
			return nil, fmt.Errorf("failed to scan row: %w", err)
		}
		analyses = append(analyses, &a)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows error: %w", err)
	}

	return analyses, nil
}

// HourlyTrend 小时趋势数据
type HourlyTrend struct {
	Hour         time.Time
	RequestCount uint64
	TotalCost    float64
	AvgLatency   float64
	ErrorRate    float64
}

// GetHourlyTrend 获取小时趋势
func (c *ClickHouseClient) GetHourlyTrend(
	ctx context.Context,
	tenantID string,
	startTime, endTime time.Time,
) ([]*HourlyTrend, error) {
	query := `
	SELECT
		toStartOfHour(request_time) as hour,
		count() as request_count,
		sum(cost_usd) as total_cost,
		avg(latency_ms) as avg_latency,
		countIf(success = 0) / count() as error_rate
	FROM model_router.request_logs
	WHERE tenant_id = ?
		AND request_time >= ?
		AND request_time <= ?
	GROUP BY hour
	ORDER BY hour ASC
	`

	rows, err := c.conn.Query(ctx, query, tenantID, startTime, endTime)
	if err != nil {
		return nil, fmt.Errorf("failed to query hourly trend: %w", err)
	}
	defer rows.Close()

	var trends []*HourlyTrend
	for rows.Next() {
		var t HourlyTrend
		if err := rows.Scan(
			&t.Hour, &t.RequestCount, &t.TotalCost,
			&t.AvgLatency, &t.ErrorRate,
		); err != nil {
			return nil, fmt.Errorf("failed to scan row: %w", err)
		}
		trends = append(trends, &t)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows error: %w", err)
	}

	return trends, nil
}

// QueryRequestLogs 查询请求日志
func (c *ClickHouseClient) QueryRequestLogs(
	ctx context.Context,
	tenantID string,
	modelID string,
	startTime, endTime time.Time,
	limit int,
) ([]*RequestLog, error) {
	query := `
	SELECT
		request_id, tenant_id, user_id, model_id, model_name, model_provider,
		request_time, response_time, latency_ms,
		success, error_message, error_code,
		prompt_tokens, completion_tokens, total_tokens,
		cost_usd, request_type, stream,
		routing_strategy, fallback_used, ab_test_variant,
		metadata
	FROM model_router.request_logs
	WHERE tenant_id = ?
		AND (? = '' OR model_id = ?)
		AND request_time >= ?
		AND request_time <= ?
	ORDER BY request_time DESC
	LIMIT ?
	`

	rows, err := c.conn.Query(ctx, query, tenantID, modelID, modelID, startTime, endTime, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query request logs: %w", err)
	}
	defer rows.Close()

	var logs []*RequestLog
	for rows.Next() {
		var log RequestLog
		var success, stream, fallbackUsed uint8

		if err := rows.Scan(
			&log.RequestID, &log.TenantID, &log.UserID, &log.ModelID, &log.ModelName, &log.ModelProvider,
			&log.RequestTime, &log.ResponseTime, &log.LatencyMs,
			&success, &log.ErrorMessage, &log.ErrorCode,
			&log.PromptTokens, &log.CompletionTokens, &log.TotalTokens,
			&log.CostUSD, &log.RequestType, &stream,
			&log.RoutingStrategy, &fallbackUsed, &log.ABTestVariant,
			&log.Metadata,
		); err != nil {
			return nil, fmt.Errorf("failed to scan row: %w", err)
		}

		log.Success = success == 1
		log.Stream = stream == 1
		log.FallbackUsed = fallbackUsed == 1

		logs = append(logs, &log)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows error: %w", err)
	}

	return logs, nil
}

// Close 关闭连接
func (c *ClickHouseClient) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// HealthCheck 健康检查
func (c *ClickHouseClient) HealthCheck(ctx context.Context) error {
	return c.conn.Ping(ctx)
}

// btoi bool to uint8
func btoi(b bool) uint8 {
	if b {
		return 1
	}
	return 0
}

// QueryStats 通用统计查询
func (c *ClickHouseClient) QueryStats(ctx context.Context, query string, args ...interface{}) (driver.Rows, error) {
	return c.conn.Query(ctx, query, args...)
}

// Exec 执行SQL
func (c *ClickHouseClient) Exec(ctx context.Context, query string, args ...interface{}) error {
	return c.conn.Exec(ctx, query, args...)
}

// GetConnectionPoolStats 获取连接池统计信息
func (c *ClickHouseClient) GetConnectionPoolStats(ctx context.Context) (*ConnectionPoolStats, error) {
	// ClickHouse系统表查询连接信息
	query := `
	SELECT
		countDistinct(user) as total_connections,
		count() as active_connections,
		countIf(query = '') as idle_connections
	FROM system.processes
	WHERE user = ?
	`

	var totalConn, activeConn, idleConn int64

	row := c.conn.QueryRow(ctx, query, c.config.Username)
	if err := row.Scan(&totalConn, &activeConn, &idleConn); err != nil {
		c.log.Warnf("Failed to query connection pool stats: %v", err)
		// 返回默认统计
		return &c.stats, nil
	}

	c.stats.TotalConnections = totalConn
	c.stats.ActiveConnections = activeConn
	c.stats.IdleConnections = idleConn

	return &c.stats, nil
}

// GetPoolUtilization 获取连接池利用率
func (c *ClickHouseClient) GetPoolUtilization(ctx context.Context) float64 {
	stats, err := c.GetConnectionPoolStats(ctx)
	if err != nil || stats.TotalConnections == 0 {
		return 0.0
	}

	return float64(stats.ActiveConnections) / float64(stats.TotalConnections)
}

// GetServerStats 获取ClickHouse服务器统计
func (c *ClickHouseClient) GetServerStats(ctx context.Context) (map[string]interface{}, error) {
	query := `
	SELECT
		name,
		value
	FROM system.metrics
	WHERE name IN (
		'Query',
		'BackgroundPoolTask',
		'BackgroundSchedulePoolTask',
		'MemoryTracking',
		'MaxPartCountForPartition'
	)
	`

	rows, err := c.conn.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query server stats: %w", err)
	}
	defer rows.Close()

	stats := make(map[string]interface{})
	for rows.Next() {
		var name string
		var value int64
		if err := rows.Scan(&name, &value); err != nil {
			c.log.Warnf("Failed to scan row: %v", err)
			continue
		}
		stats[name] = value
	}

	// 添加连接池统计
	poolStats, _ := c.GetConnectionPoolStats(ctx)
	stats["connection_pool"] = poolStats

	return stats, nil
}
