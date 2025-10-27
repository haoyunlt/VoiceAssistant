package resilience

import (
	"context"
	"errors"
	"math"
	"time"
)

var (
	// ErrMaxRetriesExceeded 超过最大重试次数
	ErrMaxRetriesExceeded = errors.New("max retries exceeded")
)

// RetryPolicy 重试策略
type RetryPolicy struct {
	// MaxRetries 最大重试次数
	MaxRetries int
	// InitialDelay 初始延迟
	InitialDelay time.Duration
	// MaxDelay 最大延迟
	MaxDelay time.Duration
	// BackoffMultiplier 退避乘数（指数退避）
	BackoffMultiplier float64
	// RetryableErrors 可重试的错误判断函数
	RetryableErrors func(error) bool
	// OnRetry 重试回调
	OnRetry func(attempt int, err error, delay time.Duration)
}

// DefaultRetryPolicy 默认重试策略
func DefaultRetryPolicy() RetryPolicy {
	return RetryPolicy{
		MaxRetries:        3,
		InitialDelay:      100 * time.Millisecond,
		MaxDelay:          10 * time.Second,
		BackoffMultiplier: 2.0,
		RetryableErrors:   nil, // 默认所有错误都可重试
	}
}

// Retry 执行带重试的函数
func Retry(ctx context.Context, policy RetryPolicy, fn func() error) error {
	var lastErr error

	for attempt := 0; attempt <= policy.MaxRetries; attempt++ {
		// 第一次尝试不延迟
		if attempt > 0 {
			delay := policy.calculateDelay(attempt)

			// 调用重试回调
			if policy.OnRetry != nil {
				policy.OnRetry(attempt, lastErr, delay)
			}

			// 等待延迟
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(delay):
			}
		}

		// 执行函数
		err := fn()
		if err == nil {
			return nil
		}

		lastErr = err

		// 检查是否可重试
		if policy.RetryableErrors != nil && !policy.RetryableErrors(err) {
			return err
		}

		// 检查context
		if ctx.Err() != nil {
			return ctx.Err()
		}
	}

	// 超过最大重试次数
	return errors.Join(ErrMaxRetriesExceeded, lastErr)
}

// calculateDelay 计算延迟时间（指数退避）
func (p *RetryPolicy) calculateDelay(attempt int) time.Duration {
	delay := float64(p.InitialDelay) * math.Pow(p.BackoffMultiplier, float64(attempt-1))

	// 限制最大延迟
	if delay > float64(p.MaxDelay) {
		delay = float64(p.MaxDelay)
	}

	return time.Duration(delay)
}

// RetryWithBackoff 使用退避策略重试
func RetryWithBackoff(ctx context.Context, maxRetries int, initialDelay, maxDelay time.Duration, fn func() error) error {
	policy := RetryPolicy{
		MaxRetries:        maxRetries,
		InitialDelay:      initialDelay,
		MaxDelay:          maxDelay,
		BackoffMultiplier: 2.0,
	}
	return Retry(ctx, policy, fn)
}

// RetryWithLinearBackoff 使用线性退避策略重试
func RetryWithLinearBackoff(ctx context.Context, maxRetries int, delay time.Duration, fn func() error) error {
	policy := RetryPolicy{
		MaxRetries:        maxRetries,
		InitialDelay:      delay,
		MaxDelay:          delay * time.Duration(maxRetries),
		BackoffMultiplier: 1.0,
	}
	return Retry(ctx, policy, fn)
}

// IsRetryable 判断错误是否可重试（常见网络错误）
func IsRetryable(err error) bool {
	if err == nil {
		return false
	}

	// 可以根据具体错误类型判断
	// 例如：网络超时、连接失败、临时错误等

	// 这里简化实现，实际应该检查具体错误类型
	return true
}
