package biz

import (
	"context"

	"github.com/go-kratos/kratos/v2/log"
)

// User is the user model.
type User struct {
	ID       string
	Email    string
	Username string
	TenantID string
}

// UserRepo is the user repository interface.
type UserRepo interface {
	CreateUser(ctx context.Context, user *User) error
	GetUser(ctx context.Context, id string) (*User, error)
	UpdateUser(ctx context.Context, user *User) error
	DeleteUser(ctx context.Context, id string) error
}

// UserUsecase is the user usecase.
type UserUsecase struct {
	repo UserRepo
	log  *log.Helper
}

// NewUserUsecase creates a new user usecase.
func NewUserUsecase(repo UserRepo, logger log.Logger) *UserUsecase {
	return &UserUsecase{
		repo: repo,
		log:  log.NewHelper(logger),
	}
}

// CreateUser creates a new user.
func (uc *UserUsecase) CreateUser(ctx context.Context, user *User) error {
	uc.log.WithContext(ctx).Infof("Creating user: %s", user.Email)
	return uc.repo.CreateUser(ctx, user)
}

// GetUser gets a user by ID.
func (uc *UserUsecase) GetUser(ctx context.Context, id string) (*User, error) {
	uc.log.WithContext(ctx).Infof("Getting user: %s", id)
	return uc.repo.GetUser(ctx, id)
}
