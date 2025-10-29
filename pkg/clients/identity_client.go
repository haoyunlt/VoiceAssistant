package clients

import (
	"context"
	"fmt"

	identitypb "voicehelper/api/proto/identity/v1"
	grpcpkg "voicehelper/pkg/grpc"
)

// IdentityClient Identity 服务客户端包装器
type IdentityClient struct {
	client  identitypb.IdentityServiceClient
	factory *grpcpkg.ClientFactory
	target  string
}

// NewIdentityClient 创建 Identity 服务客户端
func NewIdentityClient(factory *grpcpkg.ClientFactory, target string) (*IdentityClient, error) {
	if factory == nil {
		factory = grpcpkg.GetGlobalFactory()
	}

	return &IdentityClient{
		factory: factory,
		target:  target,
	}, nil
}

// getClient 获取或创建 gRPC 客户端
func (c *IdentityClient) getClient(ctx context.Context) (identitypb.IdentityServiceClient, error) {
	if c.client != nil {
		return c.client, nil
	}

	conn, err := c.factory.GetClientConn(ctx, "identity-service", c.target)
	if err != nil {
		return nil, fmt.Errorf("failed to get identity service connection: %w", err)
	}

	c.client = identitypb.NewIdentityServiceClient(conn)
	return c.client, nil
}

// Login 用户登录
func (c *IdentityClient) Login(ctx context.Context, email, password, tenantID string) (*identitypb.LoginResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.Login(ctx, &identitypb.LoginRequest{
		Email:    email,
		Password: password,
		TenantId: tenantID,
	})
}

// VerifyToken 验证 Token
func (c *IdentityClient) VerifyToken(ctx context.Context, token string) (*identitypb.TokenClaims, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.VerifyToken(ctx, &identitypb.VerifyTokenRequest{
		Token: token,
	})
}

// GetUser 获取用户信息
func (c *IdentityClient) GetUser(ctx context.Context, userID string) (*identitypb.User, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetUser(ctx, &identitypb.GetUserRequest{
		Id: userID,
	})
}

// CheckPermission 检查权限
func (c *IdentityClient) CheckPermission(ctx context.Context, userID, resource, action string) (*identitypb.PermissionResult, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.CheckPermission(ctx, &identitypb.CheckPermissionRequest{
		UserId:   userID,
		Resource: resource,
		Action:   action,
	})
}

// CreateUser 创建用户
func (c *IdentityClient) CreateUser(ctx context.Context, req *identitypb.CreateUserRequest) (*identitypb.User, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.CreateUser(ctx, req)
}

// UpdateUser 更新用户
func (c *IdentityClient) UpdateUser(ctx context.Context, req *identitypb.UpdateUserRequest) (*identitypb.User, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.UpdateUser(ctx, req)
}

// ListUsers 列出用户
func (c *IdentityClient) ListUsers(ctx context.Context, req *identitypb.ListUsersRequest) (*identitypb.ListUsersResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.ListUsers(ctx, req)
}

// GetTenant 获取租户信息
func (c *IdentityClient) GetTenant(ctx context.Context, tenantID string) (*identitypb.Tenant, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetTenant(ctx, &identitypb.GetTenantRequest{
		Id: tenantID,
	})
}

// RefreshToken 刷新 Token
func (c *IdentityClient) RefreshToken(ctx context.Context, refreshToken string) (*identitypb.TokenResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.RefreshToken(ctx, &identitypb.RefreshTokenRequest{
		RefreshToken: refreshToken,
	})
}

// ChangePassword 修改密码
func (c *IdentityClient) ChangePassword(ctx context.Context, req *identitypb.ChangePasswordRequest) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.ChangePassword(ctx, req)
	return err
}

// GetBlacklistStats 获取黑名单统计
func (c *IdentityClient) GetBlacklistStats(ctx context.Context) (*identitypb.GetBlacklistStatsResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetBlacklistStats(ctx, &identitypb.GetBlacklistStatsRequest{})
}

// LoginWithOAuth OAuth登录
func (c *IdentityClient) LoginWithOAuth(ctx context.Context, provider, code string) (*identitypb.LoginResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.LoginWithOAuth(ctx, &identitypb.LoginWithOAuthRequest{
		Provider: provider,
		Code:     code,
	})
}

// BindOAuthAccount 绑定OAuth账号
func (c *IdentityClient) BindOAuthAccount(ctx context.Context, userID, provider, code string) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.BindOAuthAccount(ctx, &identitypb.BindOAuthAccountRequest{
		UserId:   userID,
		Provider: provider,
		Code:     code,
	})
	return err
}

// UnbindOAuthAccount 解绑OAuth账号
func (c *IdentityClient) UnbindOAuthAccount(ctx context.Context, userID, provider string) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.UnbindOAuthAccount(ctx, &identitypb.UnbindOAuthAccountRequest{
		UserId:   userID,
		Provider: provider,
	})
	return err
}

// GetOAuthAuthURL 获取OAuth授权URL
func (c *IdentityClient) GetOAuthAuthURL(ctx context.Context, provider, state string) (string, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return "", err
	}

	resp, err := client.GetOAuthAuthURL(ctx, &identitypb.GetOAuthAuthURLRequest{
		Provider: provider,
		State:    state,
	})
	if err != nil {
		return "", err
	}
	return resp.AuthUrl, nil
}
