package biz

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/redis/go-redis/v9"
	"voicehelper/cmd/conversation-service/internal/domain"
)

// ShareManager 分享管理器
type ShareManager struct {
	conversationRepo domain.ConversationRepository
	messageRepo      domain.MessageRepository
	redis            *redis.Client
	logger           *log.Helper
	config           *ShareConfig
}

// ShareConfig 分享配置
type ShareConfig struct {
	BaseURL            string        // 分享链接基础 URL
	DefaultExpiration  time.Duration // 默认过期时间
	MaxExpiration      time.Duration // 最大过期时间
	RequirePassword    bool          // 是否需要密码
	AllowPublicSharing bool          // 是否允许公开分享
}

// ShareLink 分享链接
type ShareLink struct {
	ID             string            `json:"id"`              // 分享 ID
	ConversationID string            `json:"conversation_id"` // 对话 ID
	UserID         string            `json:"user_id"`         // 创建者 ID
	Title          string            `json:"title"`           // 分享标题
	ShareURL       string            `json:"share_url"`       // 完整分享链接
	AccessType     string            `json:"access_type"`     // 访问类型: public, password, whitelist
	Password       string            `json:"password,omitempty"` // 访问密码
	Whitelist      []string          `json:"whitelist,omitempty"` // 白名单用户
	MaxViews       int               `json:"max_views"`       // 最大查看次数（0=无限制）
	CurrentViews   int               `json:"current_views"`   // 当前查看次数
	Enabled        bool              `json:"enabled"`         // 是否启用
	ExpiresAt      *time.Time        `json:"expires_at,omitempty"` // 过期时间
	CreatedAt      time.Time         `json:"created_at"`
	UpdatedAt      time.Time         `json:"updated_at"`
	Metadata       map[string]string `json:"metadata,omitempty"`
}

// ShareAccessLog 分享访问日志
type ShareAccessLog struct {
	ShareID    string    `json:"share_id"`
	AccessorID string    `json:"accessor_id,omitempty"` // 访问者 ID（如果已登录）
	IPAddress  string    `json:"ip_address"`
	UserAgent  string    `json:"user_agent"`
	AccessedAt time.Time `json:"accessed_at"`
}

// NewShareManager 创建分享管理器
func NewShareManager(
	conversationRepo domain.ConversationRepository,
	messageRepo domain.MessageRepository,
	redis *redis.Client,
	config *ShareConfig,
	logger log.Logger,
) *ShareManager {
	if config == nil {
		config = &ShareConfig{
			BaseURL:            "https://app.example.com/share",
			DefaultExpiration:  7 * 24 * time.Hour, // 7 天
			MaxExpiration:      30 * 24 * time.Hour, // 30 天
			RequirePassword:    false,
			AllowPublicSharing: true,
		}
	}

	return &ShareManager{
		conversationRepo: conversationRepo,
		messageRepo:      messageRepo,
		redis:            redis,
		logger:           log.NewHelper(log.With(logger, "module", "share-manager")),
		config:           config,
	}
}

// CreateShareLink 创建分享链接
func (sm *ShareManager) CreateShareLink(
	ctx context.Context,
	conversationID, userID string,
	options *ShareOptions,
) (*ShareLink, error) {
	// 1. 获取对话
	conversation, err := sm.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, err
	}

	// 2. 权限检查
	if conversation.UserID != userID {
		return nil, domain.ErrPermissionDenied
	}

	// 3. 应用默认选项
	if options == nil {
		options = &ShareOptions{
			AccessType: "public",
			MaxViews:   0,
		}
	}

	// 4. 验证访问类型
	if !sm.config.AllowPublicSharing && options.AccessType == "public" {
		return nil, fmt.Errorf("public sharing is not allowed")
	}

	// 5. 生成分享 ID
	shareID := sm.generateShareID()

	// 6. 处理过期时间
	var expiresAt *time.Time
	if options.ExpiresIn > 0 {
		expiration := options.ExpiresIn
		if expiration > sm.config.MaxExpiration {
			expiration = sm.config.MaxExpiration
		}
		expiresTime := time.Now().Add(expiration)
		expiresAt = &expiresTime
	}

	// 7. 创建分享链接
	shareLink := &ShareLink{
		ID:             shareID,
		ConversationID: conversationID,
		UserID:         userID,
		Title:          conversation.Title,
		ShareURL:       fmt.Sprintf("%s/%s", sm.config.BaseURL, shareID),
		AccessType:     options.AccessType,
		Password:       options.Password,
		Whitelist:      options.Whitelist,
		MaxViews:       options.MaxViews,
		CurrentViews:   0,
		Enabled:        true,
		ExpiresAt:      expiresAt,
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
		Metadata:       make(map[string]string),
	}

	// 8. 保存到 Redis
	if err := sm.saveShareLink(ctx, shareLink); err != nil {
		return nil, fmt.Errorf("failed to save share link: %w", err)
	}

	sm.logger.Infof("Share link created: id=%s, conversation=%s, access_type=%s",
		shareID, conversationID, options.AccessType)

	return shareLink, nil
}

// GetShareLink 获取分享链接信息
func (sm *ShareManager) GetShareLink(ctx context.Context, shareID string) (*ShareLink, error) {
	return sm.loadShareLink(ctx, shareID)
}

// AccessShareLink 访问分享链接
func (sm *ShareManager) AccessShareLink(
	ctx context.Context,
	shareID string,
	accessInfo *AccessInfo,
) (*ShareAccessResult, error) {
	// 1. 获取分享链接
	shareLink, err := sm.loadShareLink(ctx, shareID)
	if err != nil {
		return nil, err
	}

	// 2. 检查是否启用
	if !shareLink.Enabled {
		return nil, fmt.Errorf("share link is disabled")
	}

	// 3. 检查过期时间
	if shareLink.ExpiresAt != nil && time.Now().After(*shareLink.ExpiresAt) {
		return nil, fmt.Errorf("share link has expired")
	}

	// 4. 检查查看次数限制
	if shareLink.MaxViews > 0 && shareLink.CurrentViews >= shareLink.MaxViews {
		return nil, fmt.Errorf("share link has reached max views")
	}

	// 5. 访问权限验证
	if err := sm.verifyAccess(shareLink, accessInfo); err != nil {
		return nil, err
	}

	// 6. 获取对话和消息
	conversation, err := sm.conversationRepo.GetConversation(ctx, shareLink.ConversationID)
	if err != nil {
		return nil, err
	}

	messages, err := sm.messageRepo.ListMessages(ctx, shareLink.ConversationID, 1000, 0)
	if err != nil {
		return nil, err
	}

	// 7. 记录访问
	shareLink.CurrentViews++
	shareLink.UpdatedAt = time.Now()
	if err := sm.saveShareLink(ctx, shareLink); err != nil {
		sm.logger.Errorf("Failed to update share link views: %v", err)
	}

	// 8. 记录访问日志
	sm.logAccess(ctx, shareLink.ID, accessInfo)

	sm.logger.Infof("Share link accessed: id=%s, views=%d/%d",
		shareID, shareLink.CurrentViews, shareLink.MaxViews)

	return &ShareAccessResult{
		ShareLink:    shareLink,
		Conversation: conversation,
		Messages:     messages,
	}, nil
}

// RevokeShareLink 撤销分享链接
func (sm *ShareManager) RevokeShareLink(ctx context.Context, shareID, userID string) error {
	// 1. 获取分享链接
	shareLink, err := sm.loadShareLink(ctx, shareID)
	if err != nil {
		return err
	}

	// 2. 权限检查
	if shareLink.UserID != userID {
		return domain.ErrPermissionDenied
	}

	// 3. 禁用分享链接
	shareLink.Enabled = false
	shareLink.UpdatedAt = time.Now()

	// 4. 保存
	if err := sm.saveShareLink(ctx, shareLink); err != nil {
		return fmt.Errorf("failed to revoke share link: %w", err)
	}

	sm.logger.Infof("Share link revoked: id=%s", shareID)

	return nil
}

// UpdateShareLink 更新分享链接
func (sm *ShareManager) UpdateShareLink(
	ctx context.Context,
	shareID, userID string,
	updates *ShareOptions,
) (*ShareLink, error) {
	// 1. 获取分享链接
	shareLink, err := sm.loadShareLink(ctx, shareID)
	if err != nil {
		return nil, err
	}

	// 2. 权限检查
	if shareLink.UserID != userID {
		return nil, domain.ErrPermissionDenied
	}

	// 3. 更新字段
	if updates.AccessType != "" {
		shareLink.AccessType = updates.AccessType
	}
	if updates.Password != "" {
		shareLink.Password = updates.Password
	}
	if updates.Whitelist != nil {
		shareLink.Whitelist = updates.Whitelist
	}
	if updates.MaxViews >= 0 {
		shareLink.MaxViews = updates.MaxViews
	}
	if updates.ExpiresIn > 0 {
		expiresTime := time.Now().Add(updates.ExpiresIn)
		shareLink.ExpiresAt = &expiresTime
	}

	shareLink.UpdatedAt = time.Now()

	// 4. 保存
	if err := sm.saveShareLink(ctx, shareLink); err != nil {
		return nil, fmt.Errorf("failed to update share link: %w", err)
	}

	sm.logger.Infof("Share link updated: id=%s", shareID)

	return shareLink, nil
}

// ListShareLinks 列出用户的分享链接
func (sm *ShareManager) ListShareLinks(
	ctx context.Context,
	userID string,
) ([]*ShareLink, error) {
	// 使用 Redis SCAN 获取所有分享链接
	pattern := fmt.Sprintf("share:link:*")
	
	var shareLinks []*ShareLink
	iter := sm.redis.Scan(ctx, 0, pattern, 100).Iterator()
	
	for iter.Next(ctx) {
		key := iter.Val()
		shareLink, err := sm.loadShareLinkByKey(ctx, key)
		if err != nil {
			continue
		}

		if shareLink.UserID == userID {
			shareLinks = append(shareLinks, shareLink)
		}
	}

	if err := iter.Err(); err != nil {
		return nil, err
	}

	return shareLinks, nil
}

// verifyAccess 验证访问权限
func (sm *ShareManager) verifyAccess(shareLink *ShareLink, accessInfo *AccessInfo) error {
	switch shareLink.AccessType {
	case "public":
		// 公开访问，无需验证
		return nil

	case "password":
		// 密码保护
		if shareLink.Password == "" {
			return fmt.Errorf("password is required but not set")
		}
		if accessInfo.Password != shareLink.Password {
			return fmt.Errorf("incorrect password")
		}
		return nil

	case "whitelist":
		// 白名单访问
		if accessInfo.UserID == "" {
			return fmt.Errorf("login required for whitelist access")
		}
		for _, allowedID := range shareLink.Whitelist {
			if allowedID == accessInfo.UserID {
				return nil
			}
		}
		return fmt.Errorf("user not in whitelist")

	default:
		return fmt.Errorf("unknown access type: %s", shareLink.AccessType)
	}
}

// saveShareLink 保存分享链接
func (sm *ShareManager) saveShareLink(ctx context.Context, shareLink *ShareLink) error {
	key := fmt.Sprintf("share:link:%s", shareLink.ID)
	
	data, err := sm.serializeShareLink(shareLink)
	if err != nil {
		return err
	}

	// 设置过期时间
	var expiration time.Duration
	if shareLink.ExpiresAt != nil {
		expiration = time.Until(*shareLink.ExpiresAt)
		if expiration < 0 {
			expiration = 0
		}
	} else {
		expiration = sm.config.DefaultExpiration
	}

	return sm.redis.Set(ctx, key, data, expiration).Err()
}

// loadShareLink 加载分享链接
func (sm *ShareManager) loadShareLink(ctx context.Context, shareID string) (*ShareLink, error) {
	key := fmt.Sprintf("share:link:%s", shareID)
	return sm.loadShareLinkByKey(ctx, key)
}

// loadShareLinkByKey 通过键加载分享链接
func (sm *ShareManager) loadShareLinkByKey(ctx context.Context, key string) (*ShareLink, error) {
	data, err := sm.redis.Get(ctx, key).Result()
	if err != nil {
		return nil, err
	}

	return sm.deserializeShareLink(data)
}

// serializeShareLink 序列化分享链接
func (sm *ShareManager) serializeShareLink(shareLink *ShareLink) (string, error) {
	data, err := sm.redis.JSONSet(shareLink).Result()
	if err != nil {
		return "", err
	}
	return data, nil
}

// deserializeShareLink 反序列化分享链接
func (sm *ShareManager) deserializeShareLink(data string) (*ShareLink, error) {
	var shareLink ShareLink
	if err := sm.redis.JSONGet(&shareLink, data).Err(); err != nil {
		return nil, err
	}
	return &shareLink, nil
}

// logAccess 记录访问日志
func (sm *ShareManager) logAccess(ctx context.Context, shareID string, accessInfo *AccessInfo) {
	log := &ShareAccessLog{
		ShareID:    shareID,
		AccessorID: accessInfo.UserID,
		IPAddress:  accessInfo.IPAddress,
		UserAgent:  accessInfo.UserAgent,
		AccessedAt: time.Now(),
	}

	// 保存到 Redis List（保留最近 1000 条）
	key := fmt.Sprintf("share:access_log:%s", shareID)
	sm.redis.LPush(ctx, key, log)
	sm.redis.LTrim(ctx, key, 0, 999)
	sm.redis.Expire(ctx, key, 30*24*time.Hour)
}

// generateShareID 生成分享 ID
func (sm *ShareManager) generateShareID() string {
	b := make([]byte, 16)
	rand.Read(b)
	return base64.URLEncoding.EncodeToString(b)[:16]
}

// ShareOptions 分享选项
type ShareOptions struct {
	AccessType string        // public, password, whitelist
	Password   string        // 密码（如果需要）
	Whitelist  []string      // 白名单用户 ID
	MaxViews   int           // 最大查看次数
	ExpiresIn  time.Duration // 过期时间
}

// AccessInfo 访问信息
type AccessInfo struct {
	UserID    string // 用户 ID（如果已登录）
	Password  string // 密码（如果需要）
	IPAddress string // IP 地址
	UserAgent string // User Agent
}

// ShareAccessResult 分享访问结果
type ShareAccessResult struct {
	ShareLink    *ShareLink            `json:"share_link"`
	Conversation *domain.Conversation  `json:"conversation"`
	Messages     []*domain.Message     `json:"messages"`
}

