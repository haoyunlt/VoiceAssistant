package application

import (
	"context"
	"fmt"
	"time"

	"voiceassistant/cmd/model-router/internal/domain"
)

// BudgetConfig 预算配置
type BudgetConfig struct {
	DailyBudget    float64 `json:"daily_budget"`    // 每日预算 (USD)
	WeeklyBudget   float64 `json:"weekly_budget"`   // 每周预算 (USD)
	MonthlyBudget  float64 `json:"monthly_budget"`  // 每月预算 (USD)
	AlertThreshold float64 `json:"alert_threshold"` // 告警阈值 (0-1)
}

// UsageStats 使用统计
type UsageStats struct {
	TotalCost      float64            `json:"total_cost"`       // 总成本
	TotalTokens    int64              `json:"total_tokens"`     // 总token数
	TotalRequests  int64              `json:"total_requests"`   // 总请求数
	CostByModel    map[string]float64 `json:"cost_by_model"`    // 按模型的成本
	CostByProvider map[string]float64 `json:"cost_by_provider"` // 按提供商的成本
	LastUpdated    time.Time          `json:"last_updated"`     // 最后更新时间
}

// OptimizationRecommendation 优化建议
type OptimizationRecommendation struct {
	Type        string  `json:"type"`        // 建议类型
	Description string  `json:"description"` // 描述
	Impact      string  `json:"impact"`      // 影响
	Savings     float64 `json:"savings"`     // 预计节省 (USD)
}

// CostOptimizer 成本优化器
type CostOptimizer struct {
	registry     *domain.ModelRegistry
	budgetConfig *BudgetConfig
	usageStats   *UsageStats
}

// NewCostOptimizer 创建成本优化器
func NewCostOptimizer(registry *domain.ModelRegistry, budget *BudgetConfig) *CostOptimizer {
	return &CostOptimizer{
		registry:     registry,
		budgetConfig: budget,
		usageStats: &UsageStats{
			CostByModel:    make(map[string]float64),
			CostByProvider: make(map[string]float64),
			LastUpdated:    time.Now(),
		},
	}
}

// OptimizeRoute 优化路由决策
func (o *CostOptimizer) OptimizeRoute(ctx context.Context, req *RoutingRequest, currentModel *domain.ModelInfo) (*domain.ModelInfo, error) {
	// 1. 检查预算
	if err := o.checkBudget(ctx); err != nil {
		return nil, err
	}

	// 2. 检查是否需要降级
	if o.shouldDowngrade() {
		// 寻找更便宜的替代模型
		cheaper, err := o.findCheaperAlternative(currentModel, req)
		if err == nil && cheaper != nil {
			return cheaper, nil
		}
	}

	// 3. 检查是否可以升级
	if o.canUpgrade() {
		// 寻找更好的模型（如果成本允许）
		better, err := o.findBetterAlternative(currentModel, req)
		if err == nil && better != nil {
			return better, nil
		}
	}

	return currentModel, nil
}

// checkBudget 检查预算
func (o *CostOptimizer) checkBudget(ctx context.Context) error {
	// 检查每日预算
	if o.budgetConfig.DailyBudget > 0 {
		dailyCost := o.getDailyCost()
		if dailyCost >= o.budgetConfig.DailyBudget {
			return fmt.Errorf("daily budget exceeded: $%.4f / $%.4f", dailyCost, o.budgetConfig.DailyBudget)
		}

		// 检查告警阈值
		if dailyCost >= o.budgetConfig.DailyBudget*o.budgetConfig.AlertThreshold {
			// TODO: 发送告警
		}
	}

	// 检查每周预算
	if o.budgetConfig.WeeklyBudget > 0 {
		weeklyCost := o.getWeeklyCost()
		if weeklyCost >= o.budgetConfig.WeeklyBudget {
			return fmt.Errorf("weekly budget exceeded: $%.4f / $%.4f", weeklyCost, o.budgetConfig.WeeklyBudget)
		}
	}

	// 检查每月预算
	if o.budgetConfig.MonthlyBudget > 0 {
		monthlyCost := o.getMonthlyCost()
		if monthlyCost >= o.budgetConfig.MonthlyBudget {
			return fmt.Errorf("monthly budget exceeded: $%.4f / $%.4f", monthlyCost, o.budgetConfig.MonthlyBudget)
		}
	}

	return nil
}

// shouldDowngrade 判断是否应该降级
func (o *CostOptimizer) shouldDowngrade() bool {
	if o.budgetConfig.DailyBudget <= 0 {
		return false
	}

	dailyCost := o.getDailyCost()
	usageRate := dailyCost / o.budgetConfig.DailyBudget

	// 如果使用率超过80%，考虑降级
	return usageRate > 0.8
}

// canUpgrade 判断是否可以升级
func (o *CostOptimizer) canUpgrade() bool {
	if o.budgetConfig.DailyBudget <= 0 {
		return true // 没有预算限制，可以升级
	}

	dailyCost := o.getDailyCost()
	usageRate := dailyCost / o.budgetConfig.DailyBudget

	// 如果使用率低于50%，可以考虑升级
	return usageRate < 0.5
}

// findCheaperAlternative 寻找更便宜的替代模型
func (o *CostOptimizer) findCheaperAlternative(current *domain.ModelInfo, req *RoutingRequest) (*domain.ModelInfo, error) {
	// 获取所有可用模型
	allModels := o.registry.ListAll()

	estimatedInputTokens := len(req.Prompt) / 4
	currentCost := current.EstimateCost(estimatedInputTokens, req.MaxTokens)

	var bestAlternative *domain.ModelInfo
	bestCost := currentCost

	for _, model := range allModels {
		if model.ModelID == current.ModelID {
			continue
		}

		// 检查是否满足基本要求
		if !model.IsHealthy() {
			continue
		}

		// 检查能力
		if req.Capability != nil && !model.HasCapability(*req.Capability) {
			continue
		}

		// 计算成本
		cost := model.EstimateCost(estimatedInputTokens, req.MaxTokens)

		// 寻找更便宜的模型
		if cost < bestCost {
			bestCost = cost
			bestAlternative = model
		}
	}

	if bestAlternative != nil {
		return bestAlternative, nil
	}

	return nil, fmt.Errorf("no cheaper alternative found")
}

// findBetterAlternative 寻找更好的替代模型
func (o *CostOptimizer) findBetterAlternative(current *domain.ModelInfo, req *RoutingRequest) (*domain.ModelInfo, error) {
	// 获取所有可用模型
	allModels := o.registry.ListAll()

	estimatedInputTokens := len(req.Prompt) / 4
	currentCost := current.EstimateCost(estimatedInputTokens, req.MaxTokens)
	maxAcceptableCost := currentCost * 1.5 // 最多接受50%的成本增加

	var bestAlternative *domain.ModelInfo
	bestScore := o.calculateQualityScore(current)

	for _, model := range allModels {
		if model.ModelID == current.ModelID {
			continue
		}

		// 检查是否满足基本要求
		if !model.IsHealthy() {
			continue
		}

		// 检查能力
		if req.Capability != nil && !model.HasCapability(*req.Capability) {
			continue
		}

		// 检查成本
		cost := model.EstimateCost(estimatedInputTokens, req.MaxTokens)
		if cost > maxAcceptableCost {
			continue
		}

		// 计算质量分数
		score := o.calculateQualityScore(model)

		// 寻找质量更好的模型
		if score > bestScore {
			bestScore = score
			bestAlternative = model
		}
	}

	if bestAlternative != nil {
		return bestAlternative, nil
	}

	return nil, fmt.Errorf("no better alternative found")
}

// calculateQualityScore 计算质量分数
func (o *CostOptimizer) calculateQualityScore(model *domain.ModelInfo) float64 {
	// 综合评分: 可用性40% + 低错误率30% + 上下文长度30%
	availabilityScore := model.Availability * 0.4
	errorScore := (1 - model.ErrorRate) * 0.3
	contextScore := float64(model.ContextLength) / 200000.0 * 0.3

	return availabilityScore + errorScore + contextScore
}

// RecordUsage 记录使用情况
func (o *CostOptimizer) RecordUsage(modelID string, inputTokens, outputTokens int, cost float64) error {
	model, err := o.registry.Get(modelID)
	if err != nil {
		return err
	}

	// 更新总成本
	o.usageStats.TotalCost += cost
	o.usageStats.TotalTokens += int64(inputTokens + outputTokens)
	o.usageStats.TotalRequests++

	// 更新按模型的成本
	o.usageStats.CostByModel[modelID] += cost

	// 更新按提供商的成本
	providerKey := string(model.Provider)
	o.usageStats.CostByProvider[providerKey] += cost

	o.usageStats.LastUpdated = time.Now()

	return nil
}

// GetUsageStats 获取使用统计
func (o *CostOptimizer) GetUsageStats() *UsageStats {
	return o.usageStats
}

// GetRecommendations 获取优化建议
func (o *CostOptimizer) GetRecommendations() []*OptimizationRecommendation {
	var recommendations []*OptimizationRecommendation

	// 1. 检查是否有高成本模型使用过多
	for modelID, cost := range o.usageStats.CostByModel {
		if cost > o.usageStats.TotalCost*0.3 { // 单个模型超过30%的成本
			model, _ := o.registry.Get(modelID)
			if model != nil {
				recommendations = append(recommendations, &OptimizationRecommendation{
					Type:        "high_cost_model",
					Description: fmt.Sprintf("Model %s accounts for %.1f%% of total cost", model.DisplayName, cost/o.usageStats.TotalCost*100),
					Impact:      "Consider using cheaper alternatives for non-critical tasks",
					Savings:     cost * 0.5, // 假设可以节省50%
				})
			}
		}
	}

	// 2. 检查是否有更便宜的替代方案
	allModels := o.registry.ListAll()
	for _, model := range allModels {
		if model.Provider == domain.ProviderOpenAI && model.ModelName == "gpt-4" {
			// 检查GPT-4的使用
			if cost, exists := o.usageStats.CostByModel[model.ModelID]; exists && cost > 0 {
				recommendations = append(recommendations, &OptimizationRecommendation{
					Type:        "expensive_model",
					Description: "GPT-4 is being used extensively",
					Impact:      "Consider using GPT-3.5-turbo for simpler tasks (10x cheaper)",
					Savings:     cost * 0.9,
				})
			}
		}
	}

	// 3. 检查预算使用情况
	if o.budgetConfig.DailyBudget > 0 {
		dailyCost := o.getDailyCost()
		usageRate := dailyCost / o.budgetConfig.DailyBudget

		if usageRate > 0.8 {
			recommendations = append(recommendations, &OptimizationRecommendation{
				Type:        "budget_warning",
				Description: fmt.Sprintf("Daily budget usage: %.1f%%", usageRate*100),
				Impact:      "Budget limit may be exceeded soon",
				Savings:     0,
			})
		}
	}

	return recommendations
}

// getDailyCost 获取今日成本
func (o *CostOptimizer) getDailyCost() float64 {
	// 简化实现: 返回总成本
	// 实际应该从数据库查询今日成本
	return o.usageStats.TotalCost
}

// getWeeklyCost 获取本周成本
func (o *CostOptimizer) getWeeklyCost() float64 {
	// 简化实现: 返回总成本
	// 实际应该从数据库查询本周成本
	return o.usageStats.TotalCost
}

// getMonthlyCost 获取本月成本
func (o *CostOptimizer) getMonthlyCost() float64 {
	// 简化实现: 返回总成本
	// 实际应该从数据库查询本月成本
	return o.usageStats.TotalCost
}

// PredictCost 预测成本
func (o *CostOptimizer) PredictCost(modelID string, inputTokens, outputTokens int) (float64, error) {
	model, err := o.registry.Get(modelID)
	if err != nil {
		return 0, err
	}

	return model.EstimateCost(inputTokens, outputTokens), nil
}

// CompareCosts 比较不同模型的成本
func (o *CostOptimizer) CompareCosts(modelIDs []string, inputTokens, outputTokens int) (map[string]float64, error) {
	costs := make(map[string]float64)

	for _, modelID := range modelIDs {
		model, err := o.registry.Get(modelID)
		if err != nil {
			continue
		}

		costs[modelID] = model.EstimateCost(inputTokens, outputTokens)
	}

	return costs, nil
}
