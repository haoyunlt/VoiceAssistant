package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"voiceassistant/cmd/model-router/internal/application"
	"voiceassistant/cmd/model-router/internal/domain"
)

// 演示如何使用 PostHog 集成的 A/B 测试

func main() {
	// 1. 初始化 PostHog 服务
	posthogConfig := application.PostHogConfig{
		APIKey:  "phc_YOUR_API_KEY",              // 替换为你的 API Key
		Host:    "https://app.posthog.com",       // 或自托管地址
		Enabled: true,
	}

	// 创建 PostHog 服务
	posthog, err := application.NewPostHogABTestingService(posthogConfig, nil)
	if err != nil {
		log.Fatalf("Failed to create PostHog service: %v", err)
	}
	defer posthog.Close()

	ctx := context.Background()

	// 2. 使用特性标志
	fmt.Println("=== 特性标志示例 ===")
	
	userID := "user_12345"
	userProperties := map[string]interface{}{
		"subscription": "premium",
		"region":       "us-west",
	}

	// 检查是否启用 GPT-4
	enableGPT4, err := posthog.IsFeatureEnabled(
		ctx,
		"enable_gpt4_turbo",
		userID,
		userProperties,
	)
	if err != nil {
		log.Printf("Error checking feature flag: %v", err)
	} else {
		fmt.Printf("GPT-4 enabled for user %s: %v\n", userID, enableGPT4)
	}

	// 3. 多变体实验
	fmt.Println("\n=== 多变体实验 ===")

	variant, err := posthog.GetFeatureFlagVariant(
		ctx,
		"llm_comparison_2024",
		userID,
		userProperties,
	)
	if err != nil {
		log.Printf("Error getting variant: %v", err)
	} else {
		fmt.Printf("Assigned variant for user %s: %s\n", userID, variant)
	}

	// 4. 跟踪模型选择
	fmt.Println("\n=== 跟踪模型选择 ===")

	err = posthog.TrackModelSelection(
		ctx,
		userID,
		"llm_comparison_2024",  // experimentID
		variant,                // variantID
		"gpt-4-turbo",          // selectedModel
		"chat",                 // requestType
		map[string]interface{}{
			"prompt_length": 100,
			"temperature":   0.7,
		},
	)
	if err != nil {
		log.Printf("Error tracking model selection: %v", err)
	} else {
		fmt.Println("Model selection tracked successfully")
	}

	// 5. 跟踪性能指标
	fmt.Println("\n=== 跟踪性能指标 ===")

	metrics := &domain.ModelMetrics{
		LatencyMS:  150,
		TokensUsed: 200,
		Cost:       0.004,
		Success:    true,
	}

	err = posthog.TrackModelPerformance(
		ctx,
		userID,
		"llm_comparison_2024",
		variant,
		"gpt-4-turbo",
		metrics,
	)
	if err != nil {
		log.Printf("Error tracking performance: %v", err)
	} else {
		fmt.Println("Performance metrics tracked successfully")
	}

	// 6. 识别用户
	fmt.Println("\n=== 识别用户 ===")

	err = posthog.IdentifyUser(
		ctx,
		userID,
		map[string]interface{}{
			"email":        "user@example.com",
			"subscription": "premium",
			"signup_date":  time.Now().Format("2006-01-02"),
			"usage_count":  150,
		},
	)
	if err != nil {
		log.Printf("Error identifying user: %v", err)
	} else {
		fmt.Println("User identified successfully")
	}

	// 7. 获取所有特性标志
	fmt.Println("\n=== 获取所有特性标志 ===")

	allFlags, err := posthog.GetAllFeatureFlags(ctx, userID, userProperties)
	if err != nil {
		log.Printf("Error getting all flags: %v", err)
	} else {
		fmt.Printf("User has %d feature flags\n", len(allFlags))
		for key, value := range allFlags {
			fmt.Printf("  - %s: %v\n", key, value)
		}
	}

	// 8. 跟踪自定义事件
	fmt.Println("\n=== 跟踪自定义事件 ===")

	err = posthog.TrackEvent(
		ctx,
		"model_switch",
		userID,
		map[string]interface{}{
			"from_model": "gpt-3.5-turbo",
			"to_model":   "gpt-4-turbo",
			"reason":     "user_upgrade",
		},
	)
	if err != nil {
		log.Printf("Error tracking event: %v", err)
	} else {
		fmt.Println("Custom event tracked successfully")
	}

	fmt.Println("\n=== 完成 ===")
	fmt.Println("查看 PostHog 控制台以查看数据")
}
