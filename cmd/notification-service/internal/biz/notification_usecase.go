package biz

import (
	"context"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/voicehelper/voiceassistant/cmd/notification-service/internal/domain"
)

// NotificationUsecase 通知用例
type NotificationUsecase struct {
	notifRepo    domain.NotificationRepository
	templateRepo domain.TemplateRepository
	providers    map[domain.NotificationChannel]domain.NotificationProvider
	log          *log.Helper
}

// NewNotificationUsecase 创建通知用例
func NewNotificationUsecase(
	notifRepo domain.NotificationRepository,
	templateRepo domain.TemplateRepository,
	logger log.Logger,
) *NotificationUsecase {
	return &NotificationUsecase{
		notifRepo:    notifRepo,
		templateRepo: templateRepo,
		providers:    make(map[domain.NotificationChannel]domain.NotificationProvider),
		log:          log.NewHelper(logger),
	}
}

// RegisterProvider 注册提供商
func (uc *NotificationUsecase) RegisterProvider(provider domain.NotificationProvider) {
	uc.providers[provider.GetChannel()] = provider
}

// SendNotification 发送通知
func (uc *NotificationUsecase) SendNotification(
	ctx context.Context,
	channel domain.NotificationChannel,
	tenantID, userID string,
	recipient string,
	subject, content string,
) (*domain.Notification, error) {
	// 创建通知
	notification := domain.NewNotification(channel, tenantID, userID, recipient)
	notification.SetContent(subject, content)

	// 验证
	if err := notification.Validate(); err != nil {
		return nil, err
	}

	// 保存
	if err := uc.notifRepo.Create(ctx, notification); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to create notification: %v", err)
		return nil, err
	}

	// 异步发送
	go func() {
		if err := uc.send(context.Background(), notification); err != nil {
			uc.log.Errorf("failed to send notification: %v", err)
		}
	}()

	return notification, nil
}

// SendWithTemplate 使用模板发送通知
func (uc *NotificationUsecase) SendWithTemplate(
	ctx context.Context,
	channel domain.NotificationChannel,
	tenantID, userID string,
	recipient string,
	templateID string,
	variables map[string]interface{},
) (*domain.Notification, error) {
	// 获取模板
	template, err := uc.templateRepo.GetByID(ctx, templateID)
	if err != nil {
		return nil, err
	}

	// 渲染模板
	subject, content, err := template.Render(variables)
	if err != nil {
		return nil, err
	}

	// 创建通知
	notification := domain.NewNotification(channel, tenantID, userID, recipient)
	notification.SetTemplate(templateID)
	notification.SetContent(subject, content)

	// 保存
	if err := uc.notifRepo.Create(ctx, notification); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to create notification: %v", err)
		return nil, err
	}

	// 异步发送
	go func() {
		if err := uc.send(context.Background(), notification); err != nil {
			uc.log.Errorf("failed to send notification: %v", err)
		}
	}()

	return notification, nil
}

// send 发送通知（内部方法）
func (uc *NotificationUsecase) send(ctx context.Context, notification *domain.Notification) error {
	// 获取提供商
	provider, exists := uc.providers[notification.Channel]
	if !exists {
		notification.MarkFailed("provider not found")
		uc.notifRepo.Update(ctx, notification)
		return domain.ErrProviderNotFound
	}

	// 开始发送
	notification.StartSending()
	uc.notifRepo.Update(ctx, notification)

	// 发送
	if err := provider.Send(ctx, notification); err != nil {
		notification.MarkFailed(err.Error())
		uc.notifRepo.Update(ctx, notification)
		return err
	}

	// 标记已发送
	notification.MarkSent()
	uc.notifRepo.Update(ctx, notification)

	return nil
}

// GetNotification 获取通知
func (uc *NotificationUsecase) GetNotification(ctx context.Context, id string) (*domain.Notification, error) {
	return uc.notifRepo.GetByID(ctx, id)
}

// ListUserNotifications 列出用户通知
func (uc *NotificationUsecase) ListUserNotifications(
	ctx context.Context,
	userID string,
	offset, limit int,
) ([]*domain.Notification, int64, error) {
	return uc.notifRepo.ListByUser(ctx, userID, offset, limit)
}

// ProcessPendingNotifications 处理待发送通知
func (uc *NotificationUsecase) ProcessPendingNotifications(ctx context.Context) error {
	notifications, err := uc.notifRepo.ListPending(ctx, 100)
	if err != nil {
		return err
	}

	for _, notif := range notifications {
		if notif.ShouldSend() {
			go func(n *domain.Notification) {
				if err := uc.send(context.Background(), n); err != nil {
					uc.log.Errorf("failed to send notification: %v", err)
				}
			}(notif)
		}
	}

	return nil
}
