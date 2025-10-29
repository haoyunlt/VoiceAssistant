package server

import (
	"context"
	"fmt"
	"net/http"
	"strings"

	"voicehelper/cmd/knowledge-service/internal/biz"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware"
	"github.com/go-kratos/kratos/v2/transport"
)

// AuthzMiddleware 权限检查中间件
func AuthzMiddleware(authzService *biz.AuthzService, logger log.Logger) middleware.Middleware {
	helper := log.NewHelper(logger)

	return func(handler middleware.Handler) middleware.Handler {
		return func(ctx context.Context, req interface{}) (interface{}, error) {
			// 获取transport信息
			tr, ok := transport.FromServerContext(ctx)
			if !ok {
				return nil, fmt.Errorf("no transport in context")
			}

			// 从header获取用户ID
			userID := tr.RequestHeader().Get("X-User-ID")
			if userID == "" {
				helper.Debug("No user ID in request, skipping authz")
				return handler(ctx, req)
			}

			// 提取资源和操作
			resource, action := extractResourceAndAction(tr)
			if resource == "" {
				// 不需要权限检查的路径
				return handler(ctx, req)
			}

			// 检查权限
			allowed, err := authzService.CheckPermission(ctx, userID, resource, action)
			if err != nil {
				helper.Errorf("Permission check failed: %v", err)
				return nil, fmt.Errorf("permission check failed: %w", err)
			}

			if !allowed {
				// 记录审计日志
				authzService.LogAudit(ctx, action, resource, "", "denied", "permission denied")
				return nil, fmt.Errorf("permission denied: %s on %s", action, resource)
			}

			// 记录审计日志（成功）
			go func() {
				authzService.LogAudit(context.Background(), action, resource, "", "success", "")
			}()

			return handler(ctx, req)
		}
	}
}

// extractResourceAndAction 从请求中提取资源和操作
func extractResourceAndAction(tr transport.Transporter) (resource, action string) {
	operation := tr.Operation()
	method := ""

	if httpTr, ok := tr.(interface{ Request() *http.Request }); ok {
		method = httpTr.Request().Method
	}

	// 根据HTTP方法确定操作
	switch method {
	case "GET", "HEAD":
		action = "read"
	case "POST":
		action = "write"
	case "PUT", "PATCH":
		action = "write"
	case "DELETE":
		action = "delete"
	default:
		action = "read"
	}

	// 从operation提取资源
	// 例如: "/api/v1/knowledge-bases/{id}" -> "kb:{id}"
	resource = parseResource(operation)

	return resource, action
}

// parseResource 解析资源
func parseResource(operation string) string {
	// 简化实现：根据路径模式识别资源
	parts := strings.Split(strings.TrimPrefix(operation, "/"), "/")

	if len(parts) < 3 {
		return ""
	}

	// /api/v1/knowledge-bases/{id}
	if parts[2] == "knowledge-bases" {
		if len(parts) >= 4 {
			return fmt.Sprintf("kb:%s", parts[3])
		}
		return "kb:*"
	}

	// /api/v1/documents/{id}
	if parts[2] == "documents" {
		if len(parts) >= 4 {
			return fmt.Sprintf("doc:%s", parts[3])
		}
		return "doc:*"
	}

	// /api/v1/versions/{id}
	if parts[2] == "versions" {
		if len(parts) >= 4 {
			return fmt.Sprintf("version:%s", parts[3])
		}
		return "version:*"
	}

	return ""
}

// AuditMiddleware 审计日志中间件
func AuditMiddleware(authzService *biz.AuthzService, logger log.Logger) middleware.Middleware {
	helper := log.NewHelper(logger)

	return func(handler middleware.Handler) middleware.Handler {
		return func(ctx context.Context, req interface{}) (interface{}, error) {
			tr, ok := transport.FromServerContext(ctx)
			if !ok {
				return handler(ctx, req)
			}

			resource, action := extractResourceAndAction(tr)
			if resource == "" {
				return handler(ctx, req)
			}

			// 执行处理
			resp, err := handler(ctx, req)

			// 记录审计日志
			status := "success"
			errorMsg := ""
			if err != nil {
				status = "failed"
				errorMsg = err.Error()
			}

			go func() {
				if logErr := authzService.LogAudit(
					context.Background(),
					action,
					resource,
					fmt.Sprintf("operation=%s", tr.Operation()),
					status,
					errorMsg,
				); logErr != nil {
					helper.Errorf("Failed to log audit: %v", logErr)
				}
			}()

			return resp, err
		}
	}
}
