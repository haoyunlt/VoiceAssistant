package middleware

import (
	"context"

	"github.com/go-kratos/kratos/v2/middleware"
	"github.com/go-kratos/kratos/v2/transport"
)

// TenantID is the key for tenant ID in context.
type TenantID string

const tenantIDKey TenantID = "tenant_id"

// Tenant returns a tenant middleware that extracts tenant ID from headers.
func Tenant() middleware.Middleware {
	return func(handler middleware.Handler) middleware.Handler {
		return func(ctx context.Context, req interface{}) (interface{}, error) {
			if tr, ok := transport.FromServerContext(ctx); ok {
				tenantID := tr.RequestHeader().Get("X-Tenant-ID")
				if tenantID != "" {
					ctx = context.WithValue(ctx, tenantIDKey, tenantID)
				}
			}

			return handler(ctx, req)
		}
	}
}

// GetTenantID gets tenant ID from context.
func GetTenantID(ctx context.Context) string {
	if tenantID, ok := ctx.Value(tenantIDKey).(string); ok {
		return tenantID
	}
	return ""
}
