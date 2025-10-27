package server

import (
	"context"
	"fmt"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
)

var tracer = otel.Tracer("conversation-service")

// TracingMiddleware OpenTelemetry 追踪中间件
func TracingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()

		// 开始一个新的 span
		spanName := fmt.Sprintf("%s %s", c.Request.Method, c.FullPath())
		ctx, span := tracer.Start(ctx, spanName,
			trace.WithSpanKind(trace.SpanKindServer),
			trace.WithAttributes(
				attribute.String("http.method", c.Request.Method),
				attribute.String("http.url", c.Request.URL.String()),
				attribute.String("http.route", c.FullPath()),
			),
		)
		defer span.End()

		// 将新的 context 注入到 gin.Context
		c.Request = c.Request.WithContext(ctx)

		// 执行请求
		c.Next()

		// 记录响应状态
		span.SetAttributes(attribute.Int("http.status_code", c.Writer.Status()))

		// 如果有错误，记录错误
		if len(c.Errors) > 0 {
			span.SetStatus(codes.Error, c.Errors.String())
			span.RecordError(c.Errors.Last())
		}
	}
}

// LoggingMiddleware 结构化日志中间件
func LoggingMiddleware(logger log.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		method := c.Request.Method

		// 执行请求
		c.Next()

		// 计算延迟
		latency := time.Since(start)
		statusCode := c.Writer.Status()

		// 记录日志
		_ = log.WithContext(c.Request.Context(), logger).Log(
			log.LevelInfo,
			"method", method,
			"path", path,
			"status", statusCode,
			"latency", latency.String(),
			"ip", c.ClientIP(),
			"user_agent", c.Request.UserAgent(),
		)

		// 如果有错误，记录错误日志
		if len(c.Errors) > 0 {
			for _, e := range c.Errors {
				_ = log.WithContext(c.Request.Context(), logger).Log(
					log.LevelError,
					"error", e.Error(),
					"path", path,
				)
			}
		}
	}
}

// RecoveryMiddleware 恢复中间件
func RecoveryMiddleware(logger log.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		defer func() {
			if err := recover(); err != nil {
				// 记录 panic
				_ = log.WithContext(c.Request.Context(), logger).Log(
					log.LevelError,
					"panic", fmt.Sprintf("%v", err),
					"path", c.Request.URL.Path,
				)

				// 获取当前 span（如果存在）
				span := trace.SpanFromContext(c.Request.Context())
				if span.IsRecording() {
					span.SetStatus(codes.Error, "panic recovered")
					span.RecordError(fmt.Errorf("panic: %v", err))
				}

				// 返回 500 错误
				c.JSON(500, Response{
					Code:    500,
					Message: "internal server error",
				})
				c.Abort()
			}
		}()
		c.Next()
	}
}

// TimeoutMiddleware 请求超时中间件
func TimeoutMiddleware(timeout time.Duration) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx, cancel := context.WithTimeout(c.Request.Context(), timeout)
		defer cancel()

		c.Request = c.Request.WithContext(ctx)

		finished := make(chan struct{})
		go func() {
			c.Next()
			finished <- struct{}{}
		}()

		select {
		case <-ctx.Done():
			c.JSON(504, Response{
				Code:    504,
				Message: "request timeout",
			})
			c.Abort()
		case <-finished:
		}
	}
}

// RateLimitMiddleware 限流中间件（简单实现）
func RateLimitMiddleware() gin.HandlerFunc {
	// TODO: 实现基于 Redis 的分布式限流
	return func(c *gin.Context) {
		// 暂时直接通过
		c.Next()
	}
}

// CORSMiddleware CORS 中间件
func CORSMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Requested-With")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, DELETE")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}

// AuthMiddleware 认证中间件
func AuthMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// TODO: 实现 JWT 验证
		// 目前暂时从 header 中提取 user_id 和 tenant_id
		userID := c.GetHeader("X-User-ID")
		tenantID := c.GetHeader("X-Tenant-ID")

		if userID != "" {
			c.Set("user_id", userID)
		}
		if tenantID != "" {
			c.Set("tenant_id", tenantID)
		}

		c.Next()
	}
}
