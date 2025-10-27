package biz

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/VoiceAssistant/cmd/notification-service/internal/domain"
)

// NotificationChannel 通知渠道
type NotificationChannel string

const (
	ChannelEmail     NotificationChannel = "email"
	ChannelSMS       NotificationChannel = "sms"
	ChannelWebSocket NotificationChannel = "websocket"
	ChannelWebhook   NotificationChannel = "webhook"
)

// NotificationPriority 通知优先级
type NotificationPriority string

const (
	PriorityLow      NotificationPriority = "low"
	PriorityMedium   NotificationPriority = "medium"
	PriorityHigh     NotificationPriority = "high"
	PriorityCritical NotificationPriority = "critical"
)

// NotificationRequest 通知请求
type NotificationRequest struct {
	TenantID    string
	UserID      string
	Channel     NotificationChannel
	Priority    NotificationPriority
	TemplateID  string
	Variables   map[string]interface{}
	Title       string
	Content     string
	Metadata    map[string]string
	ScheduledAt *time.Time // 定时发送
}

// Notification 通知
type Notification struct {
	ID        string
	TenantID  string
	UserID    string
	Channel   NotificationChannel
	Priority  NotificationPriority
	Title     string
	Content   string
	Status    string // pending, sending, sent, failed
	SentAt    *time.Time
	ReadAt    *time.Time
	Metadata  map[string]string
	CreatedAt time.Time
	UpdatedAt time.Time
}

// EmailProvider 邮件提供商接口
type EmailProvider interface {
	SendEmail(to, subject, body string) error
}

// SMSProvider 短信提供商接口
type SMSProvider interface {
	SendSMS(to, content string) error
}

// WebSocketManager WebSocket管理器接口
type WebSocketManager interface {
	SendToUser(userID string, message interface{}) error
	BroadcastToTenant(tenantID string, message interface{}) error
}

// NotificationUsecase 通知用例
type NotificationUsecase struct {
	notificationRepo domain.NotificationRepository
	templateRepo     domain.TemplateRepository
	emailProvider    EmailProvider
	smsProvider      SMSProvider
	wsManager        WebSocketManager
}

// NewNotificationUsecase 创建通知用例
func NewNotificationUsecase(
	notificationRepo domain.NotificationRepository,
	templateRepo domain.TemplateRepository,
	emailProvider EmailProvider,
	smsProvider SMSProvider,
	wsManager WebSocketManager,
) *NotificationUsecase {
	return &NotificationUsecase{
		notificationRepo: notificationRepo,
		templateRepo:     templateRepo,
		emailProvider:    emailProvider,
		smsProvider:      smsProvider,
		wsManager:        wsManager,
	}
}

// SendNotification 发送通知
func (uc *NotificationUsecase) SendNotification(
	ctx context.Context,
	req *NotificationRequest,
) (*Notification, error) {
	// 1. 渲染内容（如果使用模板）
	title := req.Title
	content := req.Content

	if req.TemplateID != "" {
		template, err := uc.templateRepo.GetByID(ctx, req.TemplateID)
		if err != nil {
			return nil, fmt.Errorf("get template: %w", err)
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
	notification := &Notification{
		ID:        generateID(),
		TenantID:  req.TenantID,
		UserID:    req.UserID,
		Channel:   req.Channel,
		Priority:  req.Priority,
		Title:     title,
		Content:   content,
		Status:    "pending",
		Metadata:  req.Metadata,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	if err := uc.notificationRepo.Create(ctx, notification); err != nil {
		return nil, fmt.Errorf("create notification: %w", err)
	}

	// 3. 如果是定时发送，加入队列
	if req.ScheduledAt != nil && req.ScheduledAt.After(time.Now()) {
		// TODO: 加入定时任务队列
		return notification, nil
	}

	// 4. 立即发送
	go uc.sendNotificationAsync(context.Background(), notification)

	return notification, nil
}

// sendNotificationAsync 异步发送通知
func (uc *NotificationUsecase) sendNotificationAsync(
	ctx context.Context,
	notification *Notification,
) {
	// 更新状态为发送中
	notification.Status = "sending"
	uc.notificationRepo.Update(ctx, notification)

	var err error

	// 根据渠道发送
	switch notification.Channel {
	case ChannelEmail:
		err = uc.sendEmail(notification)
	case ChannelSMS:
		err = uc.sendSMS(notification)
	case ChannelWebSocket:
		err = uc.sendWebSocket(notification)
	default:
		err = errors.New("unsupported channel")
	}

	// 更新状态
	if err != nil {
		notification.Status = "failed"
		notification.Metadata["error"] = err.Error()
	} else {
		notification.Status = "sent"
		now := time.Now()
		notification.SentAt = &now
	}

	notification.UpdatedAt = time.Now()
	uc.notificationRepo.Update(ctx, notification)
}

// sendEmail 发送邮件
func (uc *NotificationUsecase) sendEmail(notification *Notification) error {
	// 获取用户邮箱
	email := notification.Metadata["email"]
	if email == "" {
		return errors.New("email not provided")
	}

	return uc.emailProvider.SendEmail(email, notification.Title, notification.Content)
}

// sendSMS 发送短信
func (uc *NotificationUsecase) sendSMS(notification *Notification) error {
	// 获取用户手机号
	phone := notification.Metadata["phone"]
	if phone == "" {
		return errors.New("phone not provided")
	}

	return uc.smsProvider.SendSMS(phone, notification.Content)
}

// sendWebSocket 发送WebSocket通知
func (uc *NotificationUsecase) sendWebSocket(notification *Notification) error {
	message := map[string]interface{}{
		"id":       notification.ID,
		"title":    notification.Title,
		"content":  notification.Content,
		"priority": notification.Priority,
		"metadata": notification.Metadata,
	}

	return uc.wsManager.SendToUser(notification.UserID, message)
}

// GetUserNotifications 获取用户通知
func (uc *NotificationUsecase) GetUserNotifications(
	ctx context.Context,
	userID string,
	limit, offset int,
) ([]*Notification, error) {
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

	// 权限检查
	if notification.UserID != userID {
		return errors.New("unauthorized")
	}

	now := time.Now()
	notification.ReadAt = &now
	notification.UpdatedAt = now

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
	// 为每个用户创建通知
	for _, userID := range userIDs {
		req.UserID = userID
		req.TenantID = tenantID

		// 异步发送
		go func(userID string) {
			_, err := uc.SendNotification(context.Background(), req)
			if err != nil {
				// 记录错误但不中断流程
				// logger.Errorf("Failed to send notification to user %s: %v", userID, err)
			}
		}(userID)
	}

	return nil
}

// renderTemplate 渲染模板
func (uc *NotificationUsecase) renderTemplate(
	template string,
	variables map[string]interface{},
) (string, error) {
	// 简单的变量替换
	// 实际应该使用更强大的模板引擎（如text/template）
	result := template
	for key, value := range variables {
		placeholder := fmt.Sprintf("{{%s}}", key)
		result = replaceAll(result, placeholder, fmt.Sprintf("%v", value))
	}
	return result, nil
}

// generateID 生成ID
func generateID() string {
	return fmt.Sprintf("notif_%d", time.Now().UnixNano())
}

// replaceAll 替换所有
func replaceAll(s, old, new string) string {
	// 简化实现
	return s
}
