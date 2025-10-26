package service

import (
	"github.com/go-kratos/kratos/v2/log"
)

// IdentityService is the identity service implementation.
type IdentityService struct {
	// Uncomment when proto is generated:
	// pb.UnimplementedIdentityServer

	log *log.Helper
}

// NewIdentityService creates a new identity service.
func NewIdentityService(logger log.Logger) *IdentityService {
	return &IdentityService{
		log: log.NewHelper(logger),
	}
}

// TODO: Implement gRPC methods based on proto definition
// Example:
// func (s *IdentityService) CreateUser(ctx context.Context, req *pb.CreateUserRequest) (*pb.User, error) {
//     s.log.WithContext(ctx).Infof("CreateUser called")
//     return &pb.User{}, nil
// }
