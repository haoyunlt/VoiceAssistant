package service

import (
	"context"
	"fmt"

	"voicehelper/cmd/identity-service/internal/biz"
	"voicehelper/cmd/identity-service/internal/domain"

	pb "voicehelper/api/proto/identity/v1"

	"github.com/go-kratos/kratos/v2/log"
	"google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// IdentityService is the identity service implementation.
type IdentityService struct {
	pb.UnimplementedIdentityServiceServer

	userUC   *biz.UserUsecase
	authUC   *biz.AuthUsecase
	tenantUC *biz.TenantUsecase
	oauthUC  *biz.OAuthUsecase
	log      *log.Helper
}

// NewIdentityService creates a new identity service.
func NewIdentityService(
	userUC *biz.UserUsecase,
	authUC *biz.AuthUsecase,
	tenantUC *biz.TenantUsecase,
	oauthUC *biz.OAuthUsecase,
	logger log.Logger,
) *IdentityService {
	return &IdentityService{
		userUC:   userUC,
		authUC:   authUC,
		tenantUC: tenantUC,
		oauthUC:  oauthUC,
		log:      log.NewHelper(logger),
	}
}

// CreateUser creates a new user.
func (s *IdentityService) CreateUser(ctx context.Context, req *pb.CreateUserRequest) (*pb.User, error) {
	s.log.WithContext(ctx).Infof("CreateUser called: %s", req.Email)

	user, err := s.userUC.CreateUser(ctx, req.Email, req.Password, req.Username, req.TenantId)
	if err != nil {
		return nil, err
	}

	return domainUserToPB(user), nil
}

// GetUser gets a user by ID.
func (s *IdentityService) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.User, error) {
	s.log.WithContext(ctx).Infof("GetUser called: %s", req.Id)

	user, err := s.userUC.GetUser(ctx, req.Id)
	if err != nil {
		return nil, err
	}

	return domainUserToPB(user), nil
}

// UpdateUser updates a user.
func (s *IdentityService) UpdateUser(ctx context.Context, req *pb.UpdateUserRequest) (*pb.User, error) {
	s.log.WithContext(ctx).Infof("UpdateUser called: %s", req.Id)

	displayName := ""
	if req.DisplayName != nil {
		displayName = *req.DisplayName
	}

	user, err := s.userUC.UpdateUserProfile(ctx, req.Id, displayName, "")
	if err != nil {
		return nil, err
	}

	return domainUserToPB(user), nil
}

// DeleteUser deletes a user.
func (s *IdentityService) DeleteUser(ctx context.Context, req *pb.DeleteUserRequest) (*emptypb.Empty, error) {
	s.log.WithContext(ctx).Infof("DeleteUser called: %s", req.Id)

	err := s.userUC.DeleteUser(ctx, req.Id)
	if err != nil {
		return nil, err
	}

	return &emptypb.Empty{}, nil
}

// Login authenticates a user.
func (s *IdentityService) Login(ctx context.Context, req *pb.LoginRequest) (*pb.LoginResponse, error) {
	s.log.WithContext(ctx).Infof("Login called: %s", req.Email)

	tokenPair, user, err := s.authUC.Login(ctx, req.Email, req.Password)
	if err != nil {
		return nil, err
	}

	return &pb.LoginResponse{
		AccessToken:  tokenPair.AccessToken,
		RefreshToken: tokenPair.RefreshToken,
		ExpiresIn:    tokenPair.ExpiresIn,
		User:         domainUserToPB(user),
	}, nil
}

// domainUserToPB converts domain.User to pb.User
func domainUserToPB(user *domain.User) *pb.User {
	return &pb.User{
		Id:          user.ID,
		Email:       user.Email,
		Username:    user.Username,
		DisplayName: user.Username, // 使用 username 作为 display_name
		TenantId:    user.TenantID,
		CreatedAt:   timestamppb.New(user.CreatedAt),
		UpdatedAt:   timestamppb.New(user.UpdatedAt),
	}
}

// Logout logs out a user and revokes tokens.
func (s *IdentityService) Logout(ctx context.Context, req *pb.LogoutRequest) (*emptypb.Empty, error) {
	s.log.WithContext(ctx).Infof("Logout called for user: %s", req.UserId)

	// 吊销用户的 token（使用提供的 token）
	err := s.authUC.Logout(ctx, req.Token, "")
	if err != nil {
		return nil, err
	}

	return &emptypb.Empty{}, nil
}

// RefreshToken refreshes access token.
func (s *IdentityService) RefreshToken(ctx context.Context, req *pb.RefreshTokenRequest) (*pb.TokenResponse, error) {
	s.log.WithContext(ctx).Infof("RefreshToken called")

	tokenPair, err := s.authUC.RefreshToken(ctx, req.RefreshToken)
	if err != nil {
		return nil, err
	}

	return &pb.TokenResponse{
		AccessToken:  tokenPair.AccessToken,
		RefreshToken: tokenPair.RefreshToken,
		ExpiresIn:    tokenPair.ExpiresIn,
	}, nil
}

// VerifyToken verifies a token.
func (s *IdentityService) VerifyToken(ctx context.Context, req *pb.VerifyTokenRequest) (*pb.TokenClaims, error) {
	s.log.WithContext(ctx).Infof("VerifyToken called")

	claims, err := s.authUC.VerifyToken(ctx, req.Token)
	if err != nil {
		return nil, err
	}

	return &pb.TokenClaims{
		UserId:   claims.UserID,
		TenantId: claims.TenantID,
		Roles:    claims.Roles,
	}, nil
}

// GetBlacklistStats gets token blacklist statistics.
func (s *IdentityService) GetBlacklistStats(ctx context.Context, req *pb.GetBlacklistStatsRequest) (*pb.GetBlacklistStatsResponse, error) {
	s.log.WithContext(ctx).Infof("GetBlacklistStats called")

	stats, err := s.authUC.GetBlacklistStats(ctx)
	if err != nil {
		return nil, err
	}

	response := &pb.GetBlacklistStatsResponse{
		Enabled: stats["enabled"].(bool),
	}

	if enabled, ok := stats["enabled"].(bool); ok && enabled {
		if totalTokens, ok := stats["total_tokens"].(int64); ok {
			response.TotalTokens = totalTokens
		}
		if avgTTL, ok := stats["average_ttl_seconds"].(float64); ok {
			response.AverageTtlSeconds = avgTTL
		}
		if revokedUsers, ok := stats["revoked_users"].(int64); ok {
			response.RevokedUsers = revokedUsers
		}
	}

	return response, nil
}

// ChangePassword changes user password and revokes all tokens.
func (s *IdentityService) ChangePassword(ctx context.Context, req *pb.ChangePasswordRequest) (*emptypb.Empty, error) {
	s.log.WithContext(ctx).Infof("ChangePassword called for user: %s", req.UserId)

	err := s.authUC.ChangePassword(ctx, req.UserId, req.OldPassword, req.NewPassword)
	if err != nil {
		return nil, err
	}

	return &emptypb.Empty{}, nil
}

// LoginWithOAuth logins with OAuth2 provider.
func (s *IdentityService) LoginWithOAuth(ctx context.Context, req *pb.LoginWithOAuthRequest) (*pb.LoginResponse, error) {
	s.log.WithContext(ctx).Infof("LoginWithOAuth called: provider=%s", req.Provider)

	// 将 proto 的 provider 转换为 domain 的 OAuthProvider
	provider := domain.OAuthProvider(req.Provider)

	// 调用 OAuth 用例
	tokenPair, err := s.oauthUC.LoginWithOAuth(ctx, provider, req.Code)
	if err != nil {
		return nil, err
	}

	// 获取用户信息（通过 Token Claims 中的 UserID）
	// 这里简化处理，实际可能需要从 tokenPair 中解析用户信息
	// 或者修改 OAuthUsecase.LoginWithOAuth 返回 user 对象

	return &pb.LoginResponse{
		AccessToken:  tokenPair.AccessToken,
		RefreshToken: tokenPair.RefreshToken,
		ExpiresIn:    tokenPair.ExpiresIn,
		// User 字段需要从 tokenPair 中获取，这里暂时省略
		// 实际实现中应该修改 LoginWithOAuth 返回用户对象
	}, nil
}

// BindOAuthAccount binds an OAuth account to a user.
func (s *IdentityService) BindOAuthAccount(ctx context.Context, req *pb.BindOAuthAccountRequest) (*emptypb.Empty, error) {
	s.log.WithContext(ctx).Infof("BindOAuthAccount called: user_id=%s, provider=%s", req.UserId, req.Provider)

	provider := domain.OAuthProvider(req.Provider)

	err := s.oauthUC.BindOAuthAccount(ctx, req.UserId, provider, req.Code)
	if err != nil {
		return nil, err
	}

	return &emptypb.Empty{}, nil
}

// UnbindOAuthAccount unbinds an OAuth account from a user.
func (s *IdentityService) UnbindOAuthAccount(ctx context.Context, req *pb.UnbindOAuthAccountRequest) (*emptypb.Empty, error) {
	s.log.WithContext(ctx).Infof("UnbindOAuthAccount called: user_id=%s, provider=%s", req.UserId, req.Provider)

	provider := domain.OAuthProvider(req.Provider)

	err := s.oauthUC.UnbindOAuthAccount(ctx, req.UserId, provider)
	if err != nil {
		return nil, err
	}

	return &emptypb.Empty{}, nil
}

// GetOAuthAuthURL gets OAuth authorization URL.
func (s *IdentityService) GetOAuthAuthURL(ctx context.Context, req *pb.GetOAuthAuthURLRequest) (*pb.GetOAuthAuthURLResponse, error) {
	s.log.WithContext(ctx).Infof("GetOAuthAuthURL called: provider=%s", req.Provider)

	// 根据 provider 获取授权 URL
	// 这个逻辑需要在 infra/oauth 中的客户端实现
	// 这里简化处理，返回固定的 URL

	var authURL string
	switch req.Provider {
	case "google":
		// 实际应该调用 GoogleClient.GetAuthURL
		authURL = "https://accounts.google.com/o/oauth2/v2/auth?client_id=xxx&redirect_uri=xxx&response_type=code&scope=openid+email+profile&state=" + req.State
	case "github":
		authURL = "https://github.com/login/oauth/authorize?client_id=xxx&redirect_uri=xxx&scope=read:user+user:email&state=" + req.State
	default:
		return nil, fmt.Errorf("unsupported provider: %s", req.Provider)
	}

	return &pb.GetOAuthAuthURLResponse{
		AuthUrl: authURL,
	}, nil
}
