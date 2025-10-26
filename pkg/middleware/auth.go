package middleware

import (
	"context"
	"strings"

	"github.com/go-kratos/kratos/v2/errors"
	"github.com/go-kratos/kratos/v2/middleware"
	"github.com/go-kratos/kratos/v2/transport"
)

var (
	ErrMissingJWTToken = errors.Unauthorized("UNAUTHORIZED", "JWT token is missing")
	ErrInvalidJWTToken = errors.Unauthorized("UNAUTHORIZED", "JWT token is invalid")
)

// JWT returns a JWT middleware.
func JWT(secret string) middleware.Middleware {
	return func(handler middleware.Handler) middleware.Handler {
		return func(ctx context.Context, req interface{}) (interface{}, error) {
			if tr, ok := transport.FromServerContext(ctx); ok {
				tokenString := tr.RequestHeader().Get("Authorization")
				if tokenString == "" {
					return nil, ErrMissingJWTToken
				}

				// Remove "Bearer " prefix
				tokenString = strings.TrimPrefix(tokenString, "Bearer ")

				// TODO: Implement JWT validation
				// claims, err := validateJWT(tokenString, secret)
				// if err != nil {
				// 	return nil, ErrInvalidJWTToken
				// }

				// Add claims to context
				// ctx = context.WithValue(ctx, "claims", claims)
			}

			return handler(ctx, req)
		}
	}
}
