package service

import (
	"context"

	"github.com/go-kratos/kratos/v2/log"
	pb "github.com/voicehelper/voiceassistant/api/proto/identity/v1"
	"github.com/voicehelper/voiceassistant/cmd/identity-service/internal/biz"
	"github.com/voicehelper/voiceassistant/cmd/identity-service/internal/domain"
)

// IdentityService is the identity service implementation.
type IdentityService struct {
	pb.UnimplementedIdentityServer

	userUC   *biz.UserUsecase
	authUC   *biz.AuthUsecase
	tenantUC *biz.TenantUsecase
	log      *log.Helper
}

// NewIdentityService creates a new identity service.
func NewIdentityService(
	userUC *biz.UserUsecase,
	authUC *biz.AuthUsecase,
	tenantUC *biz.TenantUsecase,
	logger log.Logger,
) *IdentityService {
	return &IdentityService{
		userUC:   userUC,
		authUC:   authUC,
		tenantUC: tenantUC,
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

	user, err := s.userUC.UpdateUserProfile(ctx, req.Id, req.Username, "")
	if err != nil {
		return nil, err
	}

	return domainUserToPB(user), nil
}

// DeleteUser deletes a user.
func (s *IdentityService) DeleteUser(ctx context.Context, req *pb.DeleteUserRequest) (*pb.DeleteUserResponse, error) {
	s.log.WithContext(ctx).Infof("DeleteUser called: %s", req.Id)

	err := s.userUC.DeleteUser(ctx, req.Id)
	if err != nil {
		return nil, err
	}

	return &pb.DeleteUserResponse{Success: true}, nil
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
		Id:        user.ID,
		Email:     user.Email,
		Username:  user.Username,
		TenantId:  user.TenantID,
		CreatedAt: user.CreatedAt.Unix(),
		UpdatedAt: user.UpdatedAt.Unix(),
	}
}
