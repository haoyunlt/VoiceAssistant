package clients

import (
	"context"
	"fmt"

	notificationpb "voicehelper/api/proto/notification/v1"
	grpcpkg "voicehelper/pkg/grpc"

	"google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// NotificationClient Notification 服务客户端包装器
type NotificationClient struct {
	client  notificationpb.NotificationServiceClient
	factory *grpcpkg.ClientFactory
	target  string
}

// NewNotificationClient 创建 Notification 服务客户端
func NewNotificationClient(factory *grpcpkg.ClientFactory, target string) (*NotificationClient, error) {
	if factory == nil {
		factory = grpcpkg.GetGlobalFactory()
	}

	return &NotificationClient{
		factory: factory,
		target:  target,
	}, nil
}

// getClient 获取或创建 gRPC 客户端
func (c *NotificationClient) getClient(ctx context.Context) (notificationpb.NotificationServiceClient, error) {
	if c.client != nil {
		return c.client, nil
	}

	conn, err := c.factory.GetClientConn(ctx, "notification-service", c.target)
	if err != nil {
		return nil, fmt.Errorf("failed to get notification service connection: %w", err)
	}

	c.client = notificationpb.NewNotificationServiceClient(conn)
	return c.client, nil
}

// SendNotification 发送通知
func (c *NotificationClient) SendNotification(ctx context.Context, req *notificationpb.SendNotificationRequest) (*notificationpb.SendNotificationResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.SendNotification(ctx, req)
}

// SendBatch 批量发送通知
func (c *NotificationClient) SendBatch(ctx context.Context, notifications []*notificationpb.SendNotificationRequest) (*notificationpb.SendBatchResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.SendBatch(ctx, &notificationpb.SendBatchRequest{
		Notifications: notifications,
	})
}

// GetNotificationStatus 获取通知状态
func (c *NotificationClient) GetNotificationStatus(ctx context.Context, notificationID string) (*notificationpb.NotificationStatus, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetNotificationStatus(ctx, &notificationpb.GetNotificationStatusRequest{
		NotificationId: notificationID,
	})
}

// ListUserNotifications 获取用户通知列表
func (c *NotificationClient) ListUserNotifications(ctx context.Context, req *notificationpb.ListUserNotificationsRequest) (*notificationpb.ListUserNotificationsResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.ListUserNotifications(ctx, req)
}

// MarkAsRead 标记为已读
func (c *NotificationClient) MarkAsRead(ctx context.Context, userID string, notificationIDs []string) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.MarkAsRead(ctx, &notificationpb.MarkAsReadRequest{
		UserId:          userID,
		NotificationIds: notificationIDs,
	})
	return err
}

// CreateTemplate 创建模板
func (c *NotificationClient) CreateTemplate(ctx context.Context, req *notificationpb.CreateTemplateRequest) (*notificationpb.Template, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.CreateTemplate(ctx, req)
}

// GetTemplate 获取模板
func (c *NotificationClient) GetTemplate(ctx context.Context, templateID, tenantID string) (*notificationpb.Template, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.GetTemplate(ctx, &notificationpb.GetTemplateRequest{
		TemplateId: templateID,
		TenantId:   tenantID,
	})
}

// UpdateTemplate 更新模板
func (c *NotificationClient) UpdateTemplate(ctx context.Context, req *notificationpb.UpdateTemplateRequest) (*notificationpb.Template, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.UpdateTemplate(ctx, req)
}

// DeleteTemplate 删除模板
func (c *NotificationClient) DeleteTemplate(ctx context.Context, templateID, tenantID string) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.DeleteTemplate(ctx, &notificationpb.DeleteTemplateRequest{
		TemplateId: templateID,
		TenantId:   tenantID,
	})
	return err
}

// HealthCheck 健康检查
func (c *NotificationClient) HealthCheck(ctx context.Context) (*notificationpb.HealthResponse, error) {
	client, err := c.getClient(ctx)
	if err != nil {
		return nil, err
	}

	return client.HealthCheck(ctx, &emptypb.Empty{})
}

// 便捷方法

// SendSimpleNotification 发送简单通知
func (c *NotificationClient) SendSimpleNotification(
	ctx context.Context,
	tenantID, userID, subject, content string,
	channel notificationpb.NotificationChannel,
	notifType notificationpb.NotificationType,
) (*notificationpb.SendNotificationResponse, error) {
	return c.SendNotification(ctx, &notificationpb.SendNotificationRequest{
		TenantId: tenantID,
		UserId:   userID,
		Subject:  subject,
		Content:  content,
		Channel:  channel,
		Type:     notifType,
		Priority: notificationpb.NotificationPriority_PRIORITY_NORMAL,
	})
}

// SendEmailNotification 发送邮件通知
func (c *NotificationClient) SendEmailNotification(
	ctx context.Context,
	tenantID, userID, subject, content string,
) (*notificationpb.SendNotificationResponse, error) {
	return c.SendSimpleNotification(
		ctx,
		tenantID,
		userID,
		subject,
		content,
		notificationpb.NotificationChannel_CHANNEL_EMAIL,
		notificationpb.NotificationType_NOTIFICATION_TYPE_INFO,
	)
}

// SendInAppNotification 发送应用内通知
func (c *NotificationClient) SendInAppNotification(
	ctx context.Context,
	tenantID, userID, subject, content string,
	notifType notificationpb.NotificationType,
) (*notificationpb.SendNotificationResponse, error) {
	return c.SendSimpleNotification(
		ctx,
		tenantID,
		userID,
		subject,
		content,
		notificationpb.NotificationChannel_CHANNEL_INAPP,
		notifType,
	)
}

// SendTemplateNotification 使用模板发送通知
func (c *NotificationClient) SendTemplateNotification(
	ctx context.Context,
	tenantID, userID, templateID string,
	templateVars map[string]string,
	channel notificationpb.NotificationChannel,
) (*notificationpb.SendNotificationResponse, error) {
	return c.SendNotification(ctx, &notificationpb.SendNotificationRequest{
		TenantId:     tenantID,
		UserId:       userID,
		TemplateId:   templateID,
		TemplateVars: templateVars,
		Channel:      channel,
		Type:         notificationpb.NotificationType_NOTIFICATION_TYPE_INFO,
		Priority:     notificationpb.NotificationPriority_PRIORITY_NORMAL,
	})
}

// ScheduleNotification 定时发送通知
func (c *NotificationClient) ScheduleNotification(
	ctx context.Context,
	tenantID, userID, subject, content string,
	channel notificationpb.NotificationChannel,
	scheduleAt *timestamppb.Timestamp,
) (*notificationpb.SendNotificationResponse, error) {
	return c.SendNotification(ctx, &notificationpb.SendNotificationRequest{
		TenantId:   tenantID,
		UserId:     userID,
		Subject:    subject,
		Content:    content,
		Channel:    channel,
		Type:       notificationpb.NotificationType_NOTIFICATION_TYPE_INFO,
		Priority:   notificationpb.NotificationPriority_PRIORITY_NORMAL,
		ScheduleAt: scheduleAt,
	})
}

// MarkAllAsRead 标记所有为已读
func (c *NotificationClient) MarkAllAsRead(ctx context.Context, userID string) error {
	client, err := c.getClient(ctx)
	if err != nil {
		return err
	}

	_, err = client.MarkAsRead(ctx, &notificationpb.MarkAsReadRequest{
		UserId:  userID,
		MarkAll: true,
	})
	return err
}
