package biz

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"
	"voicehelper/cmd/notification-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// NotificationRequest 通知请求
type NotificationRequest struct {
	TenantID    string
	UserID      string
	Recipient   string // email address, phone number, etc.
	Channel     domain.NotificationChannel
	Priority    domain.NotificationPriority
	TemplateID  string
	Variables   map[string]interface{}
	Title       string
	Content     string
	Metadata    domain.MetadataMap
	ScheduledAt *time.Time // 定时发送
}

// EmailProvider 邮件提供商接口
type EmailProvider interface {
	SendEmail(ctx context.Context, to, subject, body string) error
}

// SMSProvider 短信提供商接口
type SMSProvider interface {
	SendSMS(ctx context.Context, to, content string) error
}

// WebSocketManager WebSocket管理器接口
type WebSocketManager interface {
	SendToUser(ctx context.Context, userID string, message interface{}) error
	BroadcastToTenant(ctx context.Context, tenantID string, message interface{}) error
}

// NotificationUsecase 通知用例
type NotificationUsecase struct {
	notificationRepo domain.NotificationRepository
	templateRepo     domain.TemplateRepository
	emailProvider    EmailProvider
	smsProvider      SMSProvider
	wsManager        WebSocketManager
	log              *log.Helper
}

// NewNotificationUsecase 创建通知用例
func NewNotificationUsecase(
	notificationRepo domain.NotificationRepository,
	templateRepo domain.TemplateRepository,
	emailProvider EmailProvider,
	smsProvider SMSProvider,
	wsManager WebSocketManager,
	logger log.Logger,
) *NotificationUsecase {
	return &NotificationUsecase{
		notificationRepo: notificationRepo,
		templateRepo:     templateRepo,
		emailProvider:    emailProvider,
		smsProvider:      smsProvider,
		wsManager:        wsManager,
		log:              log.NewHelper(logger),
	}
}

// SendNotification 发送通知（简化版）
func (uc *NotificationUsecase) SendNotification(
	ctx context.Context,
	channel domain.NotificationChannel,
	tenantID, userID, recipient, subject, content string,
) (*domain.Notification, error) {
	req := &NotificationRequest{
		TenantID:  tenantID,
		UserID:    userID,
		Recipient: recipient,
		Channel:   channel,
		Priority:  domain.PriorityMedium,
		Title:     subject,
		Content:   content,
		Metadata:  make(domain.MetadataMap),
	}
	return uc.SendNotificationWithRequest(ctx, req)
}

// SendNotificationWithRequest 发送通知（完整版）
func (uc *NotificationUsecase) SendNotificationWithRequest(
	ctx context.Context,
	req *NotificationRequest,
) (*domain.Notification, error) {
	// 1. 渲染内容（如果使用模板）
	title := req.Title
	content := req.Content

	if req.TemplateID != "" {
		template, err := uc.templateRepo.GetByID(ctx, req.TemplateID)
		if err != nil {
			uc.log.WithContext(ctx).Errorf("failed to get template: %v", err)
			return nil, fmt.Errorf("get template: %w", err)
		}

		if template == nil {
			return nil, fmt.Errorf("template not found: %s", req.TemplateID)
		}

		title, err = uc.renderTemplate(template.Title, req.Variables)
		if err != nil {
			return nil, fmt.Errorf("render title: %w", err)
		}

		content, err = uc.renderTemplate(template.Content, req.Variables)
		if err != nil {
			return nil, fmt.Errorf("render content: %w", err)
		}
	}

	// 2. 创建通知记录
	notification := domain.NewNotification(
		req.TenantID,
		req.UserID,
		req.Recipient,
		req.Channel,
		req.Priority,
		title,
		content,
	)

	// Set metadata
	if req.Metadata != nil {
		notification.Metadata = req.Metadata
	}

	// Validate
	if err := notification.Validate(); err != nil {
		uc.log.WithContext(ctx).Errorf("invalid notification: %v", err)
		return nil, fmt.Errorf("validate notification: %w", err)
	}

	// Save to database
	if err := uc.notificationRepo.Create(ctx, notification); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to create notification: %v", err)
		return nil, fmt.Errorf("create notification: %w", err)
	}

	uc.log.WithContext(ctx).Infof("created notification: %s for user: %s", notification.ID, notification.UserID)

	// 3. 如果是定时发送，加入队列
	if req.ScheduledAt != nil && req.ScheduledAt.After(time.Now()) {
		// TODO: 加入定时任务队列
		uc.log.WithContext(ctx).Infof("notification %s scheduled for %v", notification.ID, req.ScheduledAt)
		return notification, nil
	}

	// 4. 立即发送（异步）
	go uc.sendNotificationAsync(notification)

	return notification, nil
}

// sendNotificationAsync 异步发送通知
func (uc *NotificationUsecase) sendNotificationAsync(notification *domain.Notification) {
	ctx := context.Background()
	ctx = context.WithValue(ctx, "notification_id", notification.ID)

	uc.log.WithContext(ctx).Infof("sending notification %s via %s", notification.ID, notification.Channel)

	// 更新状态为发送中
	notification.Status = domain.StatusSending
	if err := uc.notificationRepo.Update(ctx, notification); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update notification status: %v", err)
	}

	var err error
	maxRetries := 3

	// 重试机制
	for attempt := 1; attempt <= maxRetries; attempt++ {
		// 根据渠道发送
		switch notification.Channel {
		case domain.ChannelEmail:
			err = uc.sendEmail(ctx, notification)
		case domain.ChannelSMS:
			err = uc.sendSMS(ctx, notification)
		case domain.ChannelWebSocket, domain.ChannelInApp:
			err = uc.sendWebSocket(ctx, notification)
		default:
			err = fmt.Errorf("unsupported channel: %s", notification.Channel)
		}

		if err == nil {
			break
		}

		uc.log.WithContext(ctx).Warnf("attempt %d failed: %v", attempt, err)
		notification.IncrementAttempts()

		if attempt < maxRetries {
			time.Sleep(time.Duration(attempt) * time.Second)
		}
	}

	// 更新状态
	if err != nil {
		notification.MarkAsFailed(err)
		uc.log.WithContext(ctx).Errorf("failed to send notification after %d attempts: %v", maxRetries, err)
	} else {
		notification.MarkAsSent()
		uc.log.WithContext(ctx).Infof("notification sent successfully: %s", notification.ID)
	}

	if err := uc.notificationRepo.Update(ctx, notification); err != nil {
		uc.log.WithContext(ctx).Errorf("failed to update notification: %v", err)
	}
}

// sendEmail 发送邮件
func (uc *NotificationUsecase) sendEmail(ctx context.Context, notification *domain.Notification) error {
	if notification.Recipient == "" {
		return errors.New("email recipient not provided")
	}

	return uc.emailProvider.SendEmail(ctx, notification.Recipient, notification.Title, notification.Content)
}

// sendSMS 发送短信
func (uc *NotificationUsecase) sendSMS(ctx context.Context, notification *domain.Notification) error {
	if notification.Recipient == "" {
		return errors.New("phone number not provided")
	}

	return uc.smsProvider.SendSMS(ctx, notification.Recipient, notification.Content)
}

// sendWebSocket 发送WebSocket通知
func (uc *NotificationUsecase) sendWebSocket(ctx context.Context, notification *domain.Notification) error {
	message := map[string]interface{}{
		"id":       notification.ID,
		"title":    notification.Title,
		"content":  notification.Content,
		"priority": notification.Priority,
		"metadata": notification.Metadata,
	}

	return uc.wsManager.SendToUser(ctx, notification.UserID, message)
}

// GetUserNotifications 获取用户通知
func (uc *NotificationUsecase) GetUserNotifications(
	ctx context.Context,
	userID string,
	limit, offset int,
) ([]*domain.Notification, error) {
	return uc.notificationRepo.GetByUserID(ctx, userID, limit, offset)
}

// MarkAsRead 标记为已读
func (uc *NotificationUsecase) MarkAsRead(
	ctx context.Context,
	notificationID, userID string,
) error {
	notification, err := uc.notificationRepo.GetByID(ctx, notificationID)
	if err != nil {
		return err
	}

	if notification == nil {
		return errors.New("notification not found")
	}

	// 权限检查
	if notification.UserID != userID {
		return errors.New("unauthorized")
	}

	notification.MarkAsRead()

	return uc.notificationRepo.Update(ctx, notification)
}

// GetUnreadCount 获取未读数量
func (uc *NotificationUsecase) GetUnreadCount(
	ctx context.Context,
	userID string,
) (int64, error) {
	return uc.notificationRepo.GetUnreadCount(ctx, userID)
}

// SendBulkNotification 批量发送通知
func (uc *NotificationUsecase) SendBulkNotification(
	ctx context.Context,
	tenantID string,
	userIDs []string,
	req *NotificationRequest,
) error {
	uc.log.WithContext(ctx).Infof("sending bulk notification to %d users", len(userIDs))

	// 为每个用户创建通知
	for _, uid := range userIDs {
		// Create a copy of the request for each user
		userReq := &NotificationRequest{
			TenantID:    tenantID,
			UserID:      uid,
			Recipient:   req.Recipient,
			Channel:     req.Channel,
			Priority:    req.Priority,
			TemplateID:  req.TemplateID,
			Variables:   req.Variables,
			Title:       req.Title,
			Content:     req.Content,
			Metadata:    req.Metadata,
			ScheduledAt: req.ScheduledAt,
		}

		// 异步发送
		go func(userID string, request *NotificationRequest) {
			_, err := uc.SendNotificationWithRequest(context.Background(), request)
			if err != nil {
				uc.log.Errorf("failed to send notification to user %s: %v", userID, err)
			}
		}(uid, userReq)
	}

	return nil
}

// renderTemplate 渲染模板
func (uc *NotificationUsecase) renderTemplate(
	template string,
	variables map[string]interface{},
) (string, error) {
	// 简单的变量替换
	// 生产环境应该使用更强大的模板引擎（如text/template）
	result := template
	for key, value := range variables {
		placeholder := fmt.Sprintf("{{%s}}", key)
		result = strings.ReplaceAll(result, placeholder, fmt.Sprintf("%v", value))
	}
	return result, nil
}
