package grpc

import (
	"context"
	"fmt"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
)

// UnaryClientInterceptors 返回所有客户端拦截器
func UnaryClientInterceptors() []grpc.UnaryClientInterceptor {
	return []grpc.UnaryClientInterceptor{
		TracingUnaryClientInterceptor(),
		AuthUnaryClientInterceptor(),
		LoggingUnaryClientInterceptor(),
		MetricsUnaryClientInterceptor(),
	}
}

// StreamClientInterceptors 返回所有流式客户端拦截器
func StreamClientInterceptors() []grpc.StreamClientInterceptor {
	return []grpc.StreamClientInterceptor{
		TracingStreamClientInterceptor(),
		AuthStreamClientInterceptor(),
	}
}

// TracingUnaryClientInterceptor 链路追踪拦截器（Unary）
func TracingUnaryClientInterceptor() grpc.UnaryClientInterceptor {
	return func(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
		tracer := otel.Tracer("grpc-client")

		// 从目标地址提取服务名
		target := cc.Target()

		// 创建 span
		ctx, span := tracer.Start(ctx, method,
			trace.WithSpanKind(trace.SpanKindClient),
			trace.WithAttributes(
				attribute.String("rpc.system", "grpc"),
				attribute.String("rpc.method", method),
				attribute.String("rpc.service", target),
			),
		)
		defer span.End()

		// 执行调用
		err := invoker(ctx, method, req, reply, cc, opts...)

		// 记录结果
		if err != nil {
			span.RecordError(err)
			span.SetStatus(codes.Error, err.Error())
			if st, ok := status.FromError(err); ok {
				span.SetAttributes(attribute.String("rpc.grpc.status_code", st.Code().String()))
			}
		} else {
			span.SetStatus(codes.Ok, "success")
		}

		return err
	}
}

// TracingStreamClientInterceptor 链路追踪拦截器（Stream）
func TracingStreamClientInterceptor() grpc.StreamClientInterceptor {
	return func(ctx context.Context, desc *grpc.StreamDesc, cc *grpc.ClientConn, method string, streamer grpc.Streamer, opts ...grpc.CallOption) (grpc.ClientStream, error) {
		tracer := otel.Tracer("grpc-client")

		target := cc.Target()

		ctx, span := tracer.Start(ctx, method,
			trace.WithSpanKind(trace.SpanKindClient),
			trace.WithAttributes(
				attribute.String("rpc.system", "grpc"),
				attribute.String("rpc.method", method),
				attribute.String("rpc.service", target),
				attribute.Bool("rpc.stream", true),
			),
		)

		clientStream, err := streamer(ctx, desc, cc, method, opts...)
		if err != nil {
			span.RecordError(err)
			span.SetStatus(codes.Error, err.Error())
			span.End()
			return nil, err
		}

		return &tracedClientStream{
			ClientStream: clientStream,
			span:         span,
		}, nil
	}
}

type tracedClientStream struct {
	grpc.ClientStream
	span trace.Span
}

func (s *tracedClientStream) CloseSend() error {
	err := s.ClientStream.CloseSend()
	s.span.End()
	return err
}

// AuthUnaryClientInterceptor 认证拦截器（Unary）
// 自动从 context 中提取认证信息并添加到 metadata
func AuthUnaryClientInterceptor() grpc.UnaryClientInterceptor {
	return func(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
		// 从 context 中提取认证信息
		if token := extractToken(ctx); token != "" {
			ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+token)
		}

		// 传递租户 ID
		if tenantID := extractTenantID(ctx); tenantID != "" {
			ctx = metadata.AppendToOutgoingContext(ctx, "x-tenant-id", tenantID)
		}

		// 传递用户 ID
		if userID := extractUserID(ctx); userID != "" {
			ctx = metadata.AppendToOutgoingContext(ctx, "x-user-id", userID)
		}

		// 传递请求 ID（用于分布式追踪）
		if requestID := extractRequestID(ctx); requestID != "" {
			ctx = metadata.AppendToOutgoingContext(ctx, "x-request-id", requestID)
		}

		return invoker(ctx, method, req, reply, cc, opts...)
	}
}

// AuthStreamClientInterceptor 认证拦截器（Stream）
func AuthStreamClientInterceptor() grpc.StreamClientInterceptor {
	return func(ctx context.Context, desc *grpc.StreamDesc, cc *grpc.ClientConn, method string, streamer grpc.Streamer, opts ...grpc.CallOption) (grpc.ClientStream, error) {
		// 添加认证信息
		if token := extractToken(ctx); token != "" {
			ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+token)
		}
		if tenantID := extractTenantID(ctx); tenantID != "" {
			ctx = metadata.AppendToOutgoingContext(ctx, "x-tenant-id", tenantID)
		}
		if userID := extractUserID(ctx); userID != "" {
			ctx = metadata.AppendToOutgoingContext(ctx, "x-user-id", userID)
		}
		if requestID := extractRequestID(ctx); requestID != "" {
			ctx = metadata.AppendToOutgoingContext(ctx, "x-request-id", requestID)
		}

		return streamer(ctx, desc, cc, method, opts...)
	}
}

// LoggingUnaryClientInterceptor 日志拦截器
func LoggingUnaryClientInterceptor() grpc.UnaryClientInterceptor {
	return func(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
		start := time.Now()

		err := invoker(ctx, method, req, reply, cc, opts...)

		duration := time.Since(start)

		// 记录日志（可以接入日志框架）
		if err != nil {
			fmt.Printf("[gRPC Client] method=%s target=%s duration=%v error=%v\n",
				method, cc.Target(), duration, err)
		} else {
			fmt.Printf("[gRPC Client] method=%s target=%s duration=%v status=OK\n",
				method, cc.Target(), duration)
		}

		return err
	}
}

// MetricsUnaryClientInterceptor 指标拦截器
func MetricsUnaryClientInterceptor() grpc.UnaryClientInterceptor {
	return func(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
		start := time.Now()

		err := invoker(ctx, method, req, reply, cc, opts...)

		duration := time.Since(start)

		// 记录指标（可以接入 Prometheus）
		// metrics.RecordGRPCClientRequest(method, cc.Target(), err != nil, duration)

		_ = duration // 避免未使用变量警告

		return err
	}
}

// Context key types
type contextKey string

const (
	contextKeyToken     contextKey = "token"
	contextKeyTenantID  contextKey = "tenant_id"
	contextKeyUserID    contextKey = "user_id"
	contextKeyRequestID contextKey = "request_id"
)

// Context helper functions (exported)

// ExtractToken 从 context 中提取 token (exported for external use)
func ExtractToken(ctx context.Context) string {
	return extractToken(ctx)
}

// WithToken 在 context 中设置 token
func WithToken(ctx context.Context, token string) context.Context {
	return context.WithValue(ctx, contextKeyToken, token)
}

// WithTenantID 在 context 中设置租户 ID
func WithTenantID(ctx context.Context, tenantID string) context.Context {
	return context.WithValue(ctx, contextKeyTenantID, tenantID)
}

// WithUserID 在 context 中设置用户 ID
func WithUserID(ctx context.Context, userID string) context.Context {
	return context.WithValue(ctx, contextKeyUserID, userID)
}

// WithRequestID 在 context 中设置请求 ID
func WithRequestID(ctx context.Context, requestID string) context.Context {
	return context.WithValue(ctx, contextKeyRequestID, requestID)
}

// Extract functions

func extractToken(ctx context.Context) string {
	if token, ok := ctx.Value(contextKeyToken).(string); ok {
		return token
	}
	return ""
}

func extractTenantID(ctx context.Context) string {
	if tenantID, ok := ctx.Value(contextKeyTenantID).(string); ok {
		return tenantID
	}
	return ""
}

func extractUserID(ctx context.Context) string {
	if userID, ok := ctx.Value(contextKeyUserID).(string); ok {
		return userID
	}
	return ""
}

func extractRequestID(ctx context.Context) string {
	if requestID, ok := ctx.Value(contextKeyRequestID).(string); ok {
		return requestID
	}
	return ""
}

// NewClientWithInterceptors 创建带拦截器的 gRPC 客户端连接
func NewClientWithInterceptors(target string, opts ...grpc.DialOption) (*grpc.ClientConn, error) {
	// 添加拦截器
	opts = append(opts,
		grpc.WithChainUnaryInterceptor(UnaryClientInterceptors()...),
		grpc.WithChainStreamInterceptor(StreamClientInterceptors()...),
	)

	return grpc.NewClient(target, opts...)
}
