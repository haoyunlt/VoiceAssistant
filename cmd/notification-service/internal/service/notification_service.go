package service

import (
	"context"

	"voicehelper/cmd/notification-service/internal/biz"
	"voicehelper/cmd/notification-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
	"google.golang.org/protobuf/types/known/timestamppb"
)

type SendNotificationRequest struct {
	Channel   string
	TenantID  string
	UserID    string
	Recipient string
	Subject   string
	Content   string
}

type NotificationResponse struct {
	ID        string
	Channel   string
	Status    string
	Recipient string
	CreatedAt *timestamppb.Timestamp
}

type NotificationService struct {
	notifUC    *biz.NotificationUsecase
	templateUC *biz.TemplateUsecase
	log        *log.Helper
}

func NewNotificationService(
	notifUC *biz.NotificationUsecase,
	templateUC *biz.TemplateUsecase,
	logger log.Logger,
) *NotificationService {
	return &NotificationService{
		notifUC:    notifUC,
		templateUC: templateUC,
		log:        log.NewHelper(logger),
	}
}

func (s *NotificationService) SendNotification(
	ctx context.Context,
	req *SendNotificationRequest,
) (*NotificationResponse, error) {
	notification, err := s.notifUC.SendNotification(
		ctx,
		domain.NotificationChannel(req.Channel),
		req.TenantID,
		req.UserID,
		req.Recipient,
		req.Subject,
		req.Content,
	)
	if err != nil {
		s.log.WithContext(ctx).Errorf("failed to send notification: %v", err)
		return nil, err
	}

	return &NotificationResponse{
		ID:        notification.ID,
		Channel:   string(notification.Channel),
		Status:    string(notification.Status),
		Recipient: notification.Recipient,
		CreatedAt: timestamppb.New(notification.CreatedAt),
	}, nil
}
