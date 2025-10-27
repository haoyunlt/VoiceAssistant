package biz

import (
	"context"
	"fmt"
	"time"

	"voiceassistant/conversation-service/internal/domain"

	"github.com/go-kratos/kratos/v2/log"
)

// ConversationUsecaseInterface 对话用例接口
type ConversationUsecaseInterface interface {
	CreateConversation(ctx context.Context, tenantID, userID, title string, mode domain.ConversationMode) (*domain.Conversation, error)
	GetConversation(ctx context.Context, id, userID string) (*domain.Conversation, error)
	UpdateConversationTitle(ctx context.Context, id, userID, title string) error
	ArchiveConversation(ctx context.Context, id, userID string) error
	DeleteConversation(ctx context.Context, id, userID string) error
	ListConversations(ctx context.Context, tenantID, userID string, limit, offset int) ([]*domain.Conversation, int, error)
}

// --- Authorization Decorator ---

// AuthorizationDecorator 权限装饰器
type AuthorizationDecorator struct {
	base ConversationUsecaseInterface
	repo domain.ConversationRepository
	log  *log.Helper
}

// NewAuthorizationDecorator 创建权限装饰器
func NewAuthorizationDecorator(
	base ConversationUsecaseInterface,
	repo domain.ConversationRepository,
	logger log.Logger,
) *AuthorizationDecorator {
	return &AuthorizationDecorator{
		base: base,
		repo: repo,
		log:  log.NewHelper(logger),
	}
}

// checkAccess 检查访问权限
func (d *AuthorizationDecorator) checkAccess(
	ctx context.Context,
	conversationID, userID string,
) error {
	conversation, err := d.repo.GetConversation(ctx, conversationID)
	if err != nil {
		return err
	}

	if conversation.UserID != userID {
		d.log.WithContext(ctx).Warnf("Unauthorized access attempt: user=%s, conversation=%s", userID, conversationID)
		return domain.ErrUnauthorized
	}

	return nil
}

// CreateConversation 创建对话
func (d *AuthorizationDecorator) CreateConversation(
	ctx context.Context,
	tenantID, userID, title string,
	mode domain.ConversationMode,
) (*domain.Conversation, error) {
	// 创建操作不需要额外权限检查
	return d.base.CreateConversation(ctx, tenantID, userID, title, mode)
}

// GetConversation 获取对话（带权限检查）
func (d *AuthorizationDecorator) GetConversation(
	ctx context.Context,
	id, userID string,
) (*domain.Conversation, error) {
	if err := d.checkAccess(ctx, id, userID); err != nil {
		return nil, err
	}

	return d.base.GetConversation(ctx, id, userID)
}

// UpdateConversationTitle 更新标题（带权限检查）
func (d *AuthorizationDecorator) UpdateConversationTitle(
	ctx context.Context,
	id, userID, title string,
) error {
	if err := d.checkAccess(ctx, id, userID); err != nil {
		return err
	}

	return d.base.UpdateConversationTitle(ctx, id, userID, title)
}

// ArchiveConversation 归档对话（带权限检查）
func (d *AuthorizationDecorator) ArchiveConversation(
	ctx context.Context,
	id, userID string,
) error {
	if err := d.checkAccess(ctx, id, userID); err != nil {
		return err
	}

	return d.base.ArchiveConversation(ctx, id, userID)
}

// DeleteConversation 删除对话（带权限检查）
func (d *AuthorizationDecorator) DeleteConversation(
	ctx context.Context,
	id, userID string,
) error {
	if err := d.checkAccess(ctx, id, userID); err != nil {
		return err
	}

	return d.base.DeleteConversation(ctx, id, userID)
}

// ListConversations 列出对话
func (d *AuthorizationDecorator) ListConversations(
	ctx context.Context,
	tenantID, userID string,
	limit, offset int,
) ([]*domain.Conversation, int, error) {
	// 列表操作已经按用户ID过滤
	return d.base.ListConversations(ctx, tenantID, userID, limit, offset)
}

// --- Logging Decorator ---

// LoggingDecorator 日志装饰器
type LoggingDecorator struct {
	base ConversationUsecaseInterface
	log  *log.Helper
}

// NewLoggingDecorator 创建日志装饰器
func NewLoggingDecorator(
	base ConversationUsecaseInterface,
	logger log.Logger,
) *LoggingDecorator {
	return &LoggingDecorator{
		base: base,
		log:  log.NewHelper(logger),
	}
}

// CreateConversation 创建对话（带日志）
func (d *LoggingDecorator) CreateConversation(
	ctx context.Context,
	tenantID, userID, title string,
	mode domain.ConversationMode,
) (*domain.Conversation, error) {
	d.log.WithContext(ctx).Infof("Creating conversation: user=%s, tenant=%s, title=%s", userID, tenantID, title)

	conversation, err := d.base.CreateConversation(ctx, tenantID, userID, title, mode)

	if err != nil {
		d.log.WithContext(ctx).Errorf("Failed to create conversation: %v", err)
		return nil, err
	}

	d.log.WithContext(ctx).Infof("Conversation created: id=%s", conversation.ID)
	return conversation, nil
}

// GetConversation 获取对话（带日志）
func (d *LoggingDecorator) GetConversation(
	ctx context.Context,
	id, userID string,
) (*domain.Conversation, error) {
	d.log.WithContext(ctx).Debugf("Getting conversation: id=%s, user=%s", id, userID)

	conversation, err := d.base.GetConversation(ctx, id, userID)

	if err != nil {
		d.log.WithContext(ctx).Errorf("Failed to get conversation: %v", err)
		return nil, err
	}

	return conversation, nil
}

// UpdateConversationTitle 更新标题（带日志）
func (d *LoggingDecorator) UpdateConversationTitle(
	ctx context.Context,
	id, userID, title string,
) error {
	d.log.WithContext(ctx).Infof("Updating conversation title: id=%s, user=%s, title=%s", id, userID, title)

	err := d.base.UpdateConversationTitle(ctx, id, userID, title)

	if err != nil {
		d.log.WithContext(ctx).Errorf("Failed to update conversation title: %v", err)
		return err
	}

	return nil
}

// ArchiveConversation 归档对话（带日志）
func (d *LoggingDecorator) ArchiveConversation(
	ctx context.Context,
	id, userID string,
) error {
	d.log.WithContext(ctx).Infof("Archiving conversation: id=%s, user=%s", id, userID)

	err := d.base.ArchiveConversation(ctx, id, userID)

	if err != nil {
		d.log.WithContext(ctx).Errorf("Failed to archive conversation: %v", err)
		return err
	}

	return nil
}

// DeleteConversation 删除对话（带日志）
func (d *LoggingDecorator) DeleteConversation(
	ctx context.Context,
	id, userID string,
) error {
	d.log.WithContext(ctx).Infof("Deleting conversation: id=%s, user=%s", id, userID)

	err := d.base.DeleteConversation(ctx, id, userID)

	if err != nil {
		d.log.WithContext(ctx).Errorf("Failed to delete conversation: %v", err)
		return err
	}

	return nil
}

// ListConversations 列出对话（带日志）
func (d *LoggingDecorator) ListConversations(
	ctx context.Context,
	tenantID, userID string,
	limit, offset int,
) ([]*domain.Conversation, int, error) {
	d.log.WithContext(ctx).Debugf("Listing conversations: user=%s, limit=%d, offset=%d", userID, limit, offset)

	conversations, total, err := d.base.ListConversations(ctx, tenantID, userID, limit, offset)

	if err != nil {
		d.log.WithContext(ctx).Errorf("Failed to list conversations: %v", err)
		return nil, 0, err
	}

	d.log.WithContext(ctx).Debugf("Found %d conversations (total: %d)", len(conversations), total)
	return conversations, total, nil
}

// --- Metrics Decorator ---

// MetricsDecorator 指标装饰器
type MetricsDecorator struct {
	base ConversationUsecaseInterface
}

// NewMetricsDecorator 创建指标装饰器
func NewMetricsDecorator(
	base ConversationUsecaseInterface,
) *MetricsDecorator {
	return &MetricsDecorator{
		base: base,
	}
}

// recordMetric 记录指标
func (d *MetricsDecorator) recordMetric(operation string, startTime time.Time, err error) {
	duration := time.Since(startTime)
	success := err == nil

	// TODO: 发送到Prometheus
	fmt.Printf("[METRICS] operation=%s, duration=%v, success=%v\n", operation, duration, success)
}

// CreateConversation 创建对话（带指标）
func (d *MetricsDecorator) CreateConversation(
	ctx context.Context,
	tenantID, userID, title string,
	mode domain.ConversationMode,
) (*domain.Conversation, error) {
	startTime := time.Now()
	conversation, err := d.base.CreateConversation(ctx, tenantID, userID, title, mode)
	d.recordMetric("create_conversation", startTime, err)
	return conversation, err
}

// GetConversation 获取对话（带指标）
func (d *MetricsDecorator) GetConversation(
	ctx context.Context,
	id, userID string,
) (*domain.Conversation, error) {
	startTime := time.Now()
	conversation, err := d.base.GetConversation(ctx, id, userID)
	d.recordMetric("get_conversation", startTime, err)
	return conversation, err
}

// UpdateConversationTitle 更新标题（带指标）
func (d *MetricsDecorator) UpdateConversationTitle(
	ctx context.Context,
	id, userID, title string,
) error {
	startTime := time.Now()
	err := d.base.UpdateConversationTitle(ctx, id, userID, title)
	d.recordMetric("update_conversation_title", startTime, err)
	return err
}

// ArchiveConversation 归档对话（带指标）
func (d *MetricsDecorator) ArchiveConversation(
	ctx context.Context,
	id, userID string,
) error {
	startTime := time.Now()
	err := d.base.ArchiveConversation(ctx, id, userID)
	d.recordMetric("archive_conversation", startTime, err)
	return err
}

// DeleteConversation 删除对话（带指标）
func (d *MetricsDecorator) DeleteConversation(
	ctx context.Context,
	id, userID string,
) error {
	startTime := time.Now()
	err := d.base.DeleteConversation(ctx, id, userID)
	d.recordMetric("delete_conversation", startTime, err)
	return err
}

// ListConversations 列出对话（带指标）
func (d *MetricsDecorator) ListConversations(
	ctx context.Context,
	tenantID, userID string,
	limit, offset int,
) ([]*domain.Conversation, int, error) {
	startTime := time.Now()
	conversations, total, err := d.base.ListConversations(ctx, tenantID, userID, limit, offset)
	d.recordMetric("list_conversations", startTime, err)
	return conversations, total, err
}

// --- Builder 用于组装装饰器链 ---

// ConversationUsecaseBuilder 对话用例构建器
type ConversationUsecaseBuilder struct {
	base ConversationUsecaseInterface
}

// NewConversationUsecaseBuilder 创建构建器
func NewConversationUsecaseBuilder(base ConversationUsecaseInterface) *ConversationUsecaseBuilder {
	return &ConversationUsecaseBuilder{base: base}
}

// WithLogging 添加日志装饰器
func (b *ConversationUsecaseBuilder) WithLogging(logger log.Logger) *ConversationUsecaseBuilder {
	b.base = NewLoggingDecorator(b.base, logger)
	return b
}

// WithAuthorization 添加权限装饰器
func (b *ConversationUsecaseBuilder) WithAuthorization(
	repo domain.ConversationRepository,
	logger log.Logger,
) *ConversationUsecaseBuilder {
	b.base = NewAuthorizationDecorator(b.base, repo, logger)
	return b
}

// WithMetrics 添加指标装饰器
func (b *ConversationUsecaseBuilder) WithMetrics() *ConversationUsecaseBuilder {
	b.base = NewMetricsDecorator(b.base)
	return b
}

// Build 构建最终的用例
func (b *ConversationUsecaseBuilder) Build() ConversationUsecaseInterface {
	return b.base
}
