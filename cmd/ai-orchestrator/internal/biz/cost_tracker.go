package biz

import (
	"context"
	"fmt"
	"sync"
	"time"

	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-redis/redis/v8"
)

// CostTracker Token级成本追踪器
type CostTracker struct {
	cache  *redis.Client
	logger *log.Helper
	mu     sync.RWMutex

	// 内存缓存（批量写入Redis）
	pendingCosts map[string]*CostRecord
	flushTicker  *time.Ticker
}

// CostRecord 成本记录
type CostRecord struct {
	TaskID         string                 `json:"task_id"`
	TenantID       string                 `json:"tenant_id"`
	UserID         string                 `json:"user_id"`
	TaskType       string                 `json:"task_type"`
	Model          string                 `json:"model"`
	PromptTokens   int                    `json:"prompt_tokens"`
	OutputTokens   int                    `json:"output_tokens"`
	TotalTokens    int                    `json:"total_tokens"`
	CostUSD        float64                `json:"cost_usd"`
	Timestamp      time.Time              `json:"timestamp"`
	StepCosts      map[string]*StepCost   `json:"step_costs,omitempty"`
	Metadata       map[string]interface{} `json:"metadata,omitempty"`
}

// StepCost 步骤级成本
type StepCost struct {
	StepName     string  `json:"step_name"`
	Model        string  `json:"model"`
	PromptTokens int     `json:"prompt_tokens"`
	OutputTokens int     `json:"output_tokens"`
	CostUSD      float64 `json:"cost_usd"`
	DurationMS   int64   `json:"duration_ms"`
}

// ModelPricing 模型定价
type ModelPricing struct {
	Model              string  `json:"model"`
	PromptPricePer1K   float64 `json:"prompt_price_per_1k"`  // USD per 1K tokens
	OutputPricePer1K   float64 `json:"output_price_per_1k"`  // USD per 1K tokens
}

// 常见模型定价（2025年价格）
var DefaultModelPricing = map[string]*ModelPricing{
	"gpt-4": {
		Model:            "gpt-4",
		PromptPricePer1K: 0.03,
		OutputPricePer1K: 0.06,
	},
	"gpt-4-turbo": {
		Model:            "gpt-4-turbo",
		PromptPricePer1K: 0.01,
		OutputPricePer1K: 0.03,
	},
	"gpt-3.5-turbo": {
		Model:            "gpt-3.5-turbo",
		PromptPricePer1K: 0.0005,
		OutputPricePer1K: 0.0015,
	},
	"claude-3-opus": {
		Model:            "claude-3-opus",
		PromptPricePer1K: 0.015,
		OutputPricePer1K: 0.075,
	},
	"claude-3-sonnet": {
		Model:            "claude-3-sonnet",
		PromptPricePer1K: 0.003,
		OutputPricePer1K: 0.015,
	},
	"embedding-ada-002": {
		Model:            "embedding-ada-002",
		PromptPricePer1K: 0.0001,
		OutputPricePer1K: 0.0,
	},
}

// NewCostTracker 创建成本追踪器
func NewCostTracker(cache *redis.Client, logger log.Logger) *CostTracker {
	tracker := &CostTracker{
		cache:        cache,
		logger:       log.NewHelper(logger),
		pendingCosts: make(map[string]*CostRecord),
		flushTicker:  time.NewTicker(10 * time.Second), // 每10秒批量写入
	}

	// 启动后台刷新任务
	go tracker.flushLoop()

	return tracker
}

// TrackTaskCost 记录任务级成本
func (t *CostTracker) TrackTaskCost(ctx context.Context, task *domain.Task, output *domain.TaskOutput) error {
	if output == nil {
		return nil
	}

	record := &CostRecord{
		TaskID:       task.ID,
		TenantID:     task.TenantID,
		UserID:       task.UserID,
		TaskType:     string(task.Type),
		Model:        output.Model,
		PromptTokens: output.TokensUsed,          // 简化：假设全部是prompt tokens
		OutputTokens: 0,                           // 需要从output中提取
		TotalTokens:  output.TokensUsed,
		CostUSD:      output.CostUSD,
		Timestamp:    time.Now(),
		StepCosts:    make(map[string]*StepCost),
		Metadata:     output.Metadata,
	}

	// 如果output中没有cost，自动计算
	if record.CostUSD == 0 && output.Model != "" {
		record.CostUSD = t.CalculateCost(output.Model, output.TokensUsed, 0)
	}

	// 提取步骤级成本
	if steps, ok := output.Metadata["steps"].([]interface{}); ok {
		for _, s := range steps {
			if stepMap, ok := s.(map[string]interface{}); ok {
				stepCost := t.extractStepCost(stepMap)
				if stepCost != nil {
					record.StepCosts[stepCost.StepName] = stepCost
				}
			}
		}
	}

	// 写入缓存
	t.mu.Lock()
	t.pendingCosts[record.TaskID] = record
	t.mu.Unlock()

	t.logger.Infof("tracked cost for task %s: $%.4f", task.ID, record.CostUSD)
	return nil
}

// TrackStepCost 记录步骤级成本
func (t *CostTracker) TrackStepCost(
	ctx context.Context,
	taskID string,
	stepName string,
	model string,
	promptTokens int,
	outputTokens int,
	durationMS int64,
) error {
	cost := t.CalculateCost(model, promptTokens, outputTokens)

	stepCost := &StepCost{
		StepName:     stepName,
		Model:        model,
		PromptTokens: promptTokens,
		OutputTokens: outputTokens,
		CostUSD:      cost,
		DurationMS:   durationMS,
	}

	// 更新任务的步骤成本
	t.mu.Lock()
	if record, ok := t.pendingCosts[taskID]; ok {
		record.StepCosts[stepName] = stepCost
		record.TotalTokens += (promptTokens + outputTokens)
		record.CostUSD += cost
	}
	t.mu.Unlock()

	t.logger.Debugf("tracked step cost: %s/%s = $%.4f", taskID, stepName, cost)
	return nil
}

// CalculateCost 计算成本
func (t *CostTracker) CalculateCost(model string, promptTokens int, outputTokens int) float64 {
	pricing, ok := DefaultModelPricing[model]
	if !ok {
		t.logger.Warnf("unknown model pricing: %s, using default", model)
		pricing = DefaultModelPricing["gpt-3.5-turbo"]
	}

	promptCost := float64(promptTokens) / 1000.0 * pricing.PromptPricePer1K
	outputCost := float64(outputTokens) / 1000.0 * pricing.OutputPricePer1K

	return promptCost + outputCost
}

// GetTaskCost 获取任务成本
func (t *CostTracker) GetTaskCost(ctx context.Context, taskID string) (*CostRecord, error) {
	// 先查内存缓存
	t.mu.RLock()
	if record, ok := t.pendingCosts[taskID]; ok {
		t.mu.RUnlock()
		return record, nil
	}
	t.mu.RUnlock()

	// 从Redis查询
	key := t.buildKey(taskID)
	data, err := t.cache.Get(ctx, key).Result()
	if err != nil {
		return nil, err
	}

	var record CostRecord
	if err := json.Unmarshal([]byte(data), &record); err != nil {
		return nil, err
	}

	return &record, nil
}

// GetTenantCost 获取租户总成本
func (t *CostTracker) GetTenantCost(
	ctx context.Context,
	tenantID string,
	startTime, endTime time.Time,
) (*TenantCostSummary, error) {
	// 从Redis查询租户的所有成本记录
	pattern := fmt.Sprintf("cost:tenant:%s:*", tenantID)
	keys, err := t.cache.Keys(ctx, pattern).Result()
	if err != nil {
		return nil, err
	}

	summary := &TenantCostSummary{
		TenantID:    tenantID,
		StartTime:   startTime,
		EndTime:     endTime,
		TotalCostUSD: 0,
		TotalTokens: 0,
		TaskCount:   0,
		ByTaskType:  make(map[string]*TaskTypeCost),
		ByModel:     make(map[string]*ModelCost),
	}

	for _, key := range keys {
		data, _ := t.cache.Get(ctx, key).Result()
		var record CostRecord
		if err := json.Unmarshal([]byte(data), &record); err != nil {
			continue
		}

		// 时间过滤
		if record.Timestamp.Before(startTime) || record.Timestamp.After(endTime) {
			continue
		}

		// 聚合统计
		summary.TotalCostUSD += record.CostUSD
		summary.TotalTokens += record.TotalTokens
		summary.TaskCount++

		// 按任务类型统计
		if _, ok := summary.ByTaskType[record.TaskType]; !ok {
			summary.ByTaskType[record.TaskType] = &TaskTypeCost{}
		}
		summary.ByTaskType[record.TaskType].Count++
		summary.ByTaskType[record.TaskType].CostUSD += record.CostUSD
		summary.ByTaskType[record.TaskType].Tokens += record.TotalTokens

		// 按模型统计
		if _, ok := summary.ByModel[record.Model]; !ok {
			summary.ByModel[record.Model] = &ModelCost{}
		}
		summary.ByModel[record.Model].Count++
		summary.ByModel[record.Model].CostUSD += record.CostUSD
		summary.ByModel[record.Model].Tokens += record.TotalTokens
	}

	return summary, nil
}

// TenantCostSummary 租户成本汇总
type TenantCostSummary struct {
	TenantID     string                    `json:"tenant_id"`
	StartTime    time.Time                 `json:"start_time"`
	EndTime      time.Time                 `json:"end_time"`
	TotalCostUSD float64                   `json:"total_cost_usd"`
	TotalTokens  int                       `json:"total_tokens"`
	TaskCount    int                       `json:"task_count"`
	ByTaskType   map[string]*TaskTypeCost  `json:"by_task_type"`
	ByModel      map[string]*ModelCost     `json:"by_model"`
}

// TaskTypeCost 任务类型成本
type TaskTypeCost struct {
	Count   int     `json:"count"`
	CostUSD float64 `json:"cost_usd"`
	Tokens  int     `json:"tokens"`
}

// ModelCost 模型成本
type ModelCost struct {
	Count   int     `json:"count"`
	CostUSD float64 `json:"cost_usd"`
	Tokens  int     `json:"tokens"`
}

// flushLoop 后台刷新循环
func (t *CostTracker) flushLoop() {
	for range t.flushTicker.C {
		t.flush()
	}
}

// flush 批量写入Redis
func (t *CostTracker) flush() {
	t.mu.Lock()
	defer t.mu.Unlock()

	if len(t.pendingCosts) == 0 {
		return
	}

	t.logger.Infof("flushing %d cost records to Redis", len(t.pendingCosts))

	ctx := context.Background()
	for taskID, record := range t.pendingCosts {
		data, err := json.Marshal(record)
		if err != nil {
			t.logger.Errorf("failed to marshal cost record: %v", err)
			continue
		}

		// 写入Redis
		key := t.buildKey(taskID)
		if err := t.cache.Set(ctx, key, string(data), 30*24*time.Hour).Err(); err != nil {
			t.logger.Errorf("failed to write cost to Redis: %v", err)
			continue
		}

		// 租户索引
		tenantKey := t.buildTenantKey(record.TenantID, taskID)
		t.cache.Set(ctx, tenantKey, string(data), 30*24*time.Hour)

		delete(t.pendingCosts, taskID)
	}

	t.logger.Info("cost records flushed")
}

// buildKey 构建Redis键
func (t *CostTracker) buildKey(taskID string) string {
	return fmt.Sprintf("cost:task:%s", taskID)
}

// buildTenantKey 构建租户索引键
func (t *CostTracker) buildTenantKey(tenantID, taskID string) string {
	return fmt.Sprintf("cost:tenant:%s:%s", tenantID, taskID)
}

// extractStepCost 从步骤元数据提取成本
func (t *CostTracker) extractStepCost(stepData map[string]interface{}) *StepCost {
	name, _ := stepData["name"].(string)
	model, _ := stepData["model"].(string)
	promptTokens, _ := stepData["prompt_tokens"].(int)
	outputTokens, _ := stepData["output_tokens"].(int)
	durationMS, _ := stepData["duration_ms"].(int64)

	if name == "" {
		return nil
	}

	cost := t.CalculateCost(model, promptTokens, outputTokens)

	return &StepCost{
		StepName:     name,
		Model:        model,
		PromptTokens: promptTokens,
		OutputTokens: outputTokens,
		CostUSD:      cost,
		DurationMS:   durationMS,
	}
}

// Close 关闭追踪器
func (t *CostTracker) Close() error {
	t.flushTicker.Stop()
	t.flush() // 最后一次刷新
	return nil
}

// 辅助函数
import "encoding/json"
