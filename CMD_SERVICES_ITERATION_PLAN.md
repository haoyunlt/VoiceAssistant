# Go 服务迭代计划（Cmd Services）

> **版本**: v2.0  
> **生成日期**: 2025-10-27  
> **适用服务**: Identity Service, Conversation Service, Knowledge Service, AI Orchestrator, Analytics Service, Model Router, Notification Service

---

## 📋 目录

- [1. Identity Service（身份认证服务）](#1-identity-service)
- [2. Conversation Service（对话管理服务）](#2-conversation-service)
- [3. Knowledge Service（知识管理服务）](#3-knowledge-service)
- [4. AI Orchestrator（AI编排服务）](#4-ai-orchestrator)
- [5. Analytics Service（分析服务）](#5-analytics-service)
- [6. Model Router（模型路由服务）](#6-model-router)
- [7. Notification Service（通知服务）](#7-notification-service)

---

## 1. Identity Service

### 1.1 当前实现状态

#### ✅ 已实现功能

| 功能模块 | 实现状态 | 说明 |
|---------|---------|------|
| 用户管理 | ✅ 完成 | 注册、登录、密码管理 |
| 认证授权 | ✅ 完成 | JWT Token（Access + Refresh） |
| 租户管理 | ✅ 完成 | 多租户支持、配额管理 |
| RBAC | ✅ 完成 | 角色权限控制 |
| 数据访问 | ✅ 完成 | PostgreSQL + GORM |

#### 🔄 待完善功能

| 优先级 | 功能 | 状态 | 预计工作量 |
|-------|------|------|-----------|
| P0 | OAuth2第三方登录 | 未实现 | 5天 |
| P0 | 密码重置流程 | 未实现 | 2天 |
| P0 | Token黑名单 | 未实现 | 2天 |
| P1 | 审计日志 | 未实现 | 3天 |
| P1 | 权限动态配置 | 未实现 | 4天 |
| P2 | 单点登录（SSO） | 未实现 | 7天 |
| P2 | 多因素认证（MFA） | 未实现 | 5天 |

### 1.2 迭代计划

#### Sprint 1: OAuth2第三方登录（1周）

**目标**: 支持微信、GitHub、Google OAuth2登录

**设计方案**:

```go
// File: internal/domain/oauth_provider.go

package domain

type OAuthProvider string

const (
	OAuthProviderWechat OAuthProvider = "wechat"
	OAuthProviderGitHub OAuthProvider = "github"
	OAuthProviderGoogle OAuthProvider = "google"
)

type OAuthAccount struct {
	ID         string
	UserID     string
	Provider   OAuthProvider
	ProviderID string        // 第三方用户ID
	AccessToken string
	RefreshToken string
	ExpiresAt    time.Time
	CreatedAt    time.Time
	UpdatedAt    time.Time
}

func NewOAuthAccount(
	userID string,
	provider OAuthProvider,
	providerID string,
	accessToken string,
) *OAuthAccount {
	return &OAuthAccount{
		ID:          generateID(),
		UserID:      userID,
		Provider:    provider,
		ProviderID:  providerID,
		AccessToken: accessToken,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}
}

// File: internal/biz/oauth_usecase.go

type OAuthUsecase struct {
	userRepo      UserRepository
	oauthRepo     OAuthRepository
	tenantRepo    TenantRepository
	wechatClient  *OAuthWechatClient
	githubClient  *OAuthGitHubClient
	googleClient  *OAuthGoogleClient
}

func (uc *OAuthUsecase) LoginWithOAuth(
	ctx context.Context,
	provider OAuthProvider,
	code string,
) (*AuthTokenPair, error) {
	// 1. 根据provider获取用户信息
	var oauthUser *OAuthUserInfo
	var err error
	
	switch provider {
	case OAuthProviderWechat:
		oauthUser, err = uc.wechatClient.GetUserInfo(ctx, code)
	case OAuthProviderGitHub:
		oauthUser, err = uc.githubClient.GetUserInfo(ctx, code)
	case OAuthProviderGoogle:
		oauthUser, err = uc.googleClient.GetUserInfo(ctx, code)
	default:
		return nil, ErrUnsupportedProvider
	}
	
	if err != nil {
		return nil, err
	}
	
	// 2. 查找是否已绑定
	oauthAccount, err := uc.oauthRepo.GetByProviderID(ctx, provider, oauthUser.ID)
	if err != nil && !errors.Is(err, ErrOAuthAccountNotFound) {
		return nil, err
	}
	
	var user *User
	if oauthAccount != nil {
		// 已绑定，获取用户
		user, err = uc.userRepo.GetByID(ctx, oauthAccount.UserID)
		if err != nil {
			return nil, err
		}
	} else {
		// 未绑定，创建新用户
		user, err = uc.createUserFromOAuth(ctx, oauthUser)
		if err != nil {
			return nil, err
		}
		
		// 创建绑定关系
		oauthAccount = NewOAuthAccount(
			user.ID,
			provider,
			oauthUser.ID,
			oauthUser.AccessToken,
		)
		if err := uc.oauthRepo.Create(ctx, oauthAccount); err != nil {
			return nil, err
		}
	}
	
	// 3. 生成Token
	tokenPair, err := uc.generateTokenPair(user)
	if err != nil {
		return nil, err
	}
	
	return tokenPair, nil
}

func (uc *OAuthUsecase) createUserFromOAuth(
	ctx context.Context,
	oauthUser *OAuthUserInfo,
) (*User, error) {
	// 1. 获取默认租户
	tenant, err := uc.tenantRepo.GetByName(ctx, "default")
	if err != nil {
		return nil, err
	}
	
	// 2. 创建用户
	user := NewUser(
		oauthUser.Email,
		generateRandomPassword(), // OAuth用户无需密码
		oauthUser.Name,
		tenant.ID,
	)
	user.AvatarURL = oauthUser.AvatarURL
	
	if err := uc.userRepo.Create(ctx, user); err != nil {
		return nil, err
	}
	
	return user, nil
}

// File: internal/infra/oauth/wechat_client.go

type OAuthWechatClient struct {
	appID     string
	appSecret string
}

func (c *OAuthWechatClient) GetUserInfo(
	ctx context.Context,
	code string,
) (*OAuthUserInfo, error) {
	// 1. 获取access_token
	tokenURL := fmt.Sprintf(
		"https://api.weixin.qq.com/sns/oauth2/access_token?appid=%s&secret=%s&code=%s&grant_type=authorization_code",
		c.appID,
		c.appSecret,
		code,
	)
	
	resp, err := http.Get(tokenURL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	var tokenResp struct {
		AccessToken  string `json:"access_token"`
		OpenID       string `json:"openid"`
		ExpiresIn    int    `json:"expires_in"`
		RefreshToken string `json:"refresh_token"`
	}
	
	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return nil, err
	}
	
	// 2. 获取用户信息
	userInfoURL := fmt.Sprintf(
		"https://api.weixin.qq.com/sns/userinfo?access_token=%s&openid=%s&lang=zh_CN",
		tokenResp.AccessToken,
		tokenResp.OpenID,
	)
	
	resp, err = http.Get(userInfoURL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	
	var wechatUser struct {
		OpenID     string `json:"openid"`
		Nickname   string `json:"nickname"`
		HeadImgURL string `json:"headimgurl"`
		UnionID    string `json:"unionid"`
	}
	
	if err := json.NewDecoder(resp.Body).Decode(&wechatUser); err != nil {
		return nil, err
	}
	
	// 3. 转换为统一格式
	return &OAuthUserInfo{
		ID:          wechatUser.OpenID,
		Name:        wechatUser.Nickname,
		Email:       "", // 微信不提供邮箱
		AvatarURL:   wechatUser.HeadImgURL,
		AccessToken: tokenResp.AccessToken,
	}, nil
}
```

**API接口**:

```go
// File: internal/service/identity_service.go

func (s *IdentityService) LoginWithOAuth(
	ctx context.Context,
	req *pb.OAuthLoginRequest,
) (*pb.AuthResponse, error) {
	// 1. 调用OAuth登录
	tokenPair, err := s.oauthUC.LoginWithOAuth(
		ctx,
		OAuthProvider(req.Provider),
		req.Code,
	)
	if err != nil {
		return nil, err
	}
	
	// 2. 返回Token
	return &pb.AuthResponse{
		AccessToken:  tokenPair.AccessToken,
		RefreshToken: tokenPair.RefreshToken,
		ExpiresIn:    3600,
		TokenType:    "Bearer",
	}, nil
}
```

#### Sprint 2: 密码重置和Token黑名单（1周）

**1. 密码重置流程**

```go
// File: internal/biz/password_reset_usecase.go

type PasswordResetUsecase struct {
	userRepo      UserRepository
	resetTokenRepo ResetTokenRepository
	emailService  EmailService
}

func (uc *PasswordResetUsecase) RequestPasswordReset(
	ctx context.Context,
	email string,
) error {
	// 1. 查找用户
	user, err := uc.userRepo.GetByEmail(ctx, email)
	if err != nil {
		// 安全考虑：即使用户不存在也返回成功
		return nil
	}
	
	// 2. 生成重置Token
	resetToken := &ResetToken{
		ID:        generateID(),
		UserID:    user.ID,
		Token:     generateSecureToken(32),
		ExpiresAt: time.Now().Add(1 * time.Hour),
		CreatedAt: time.Now(),
	}
	
	if err := uc.resetTokenRepo.Create(ctx, resetToken); err != nil {
		return err
	}
	
	// 3. 发送重置邮件
	resetURL := fmt.Sprintf("https://app.voicehelper.ai/reset-password?token=%s", resetToken.Token)
	if err := uc.emailService.SendPasswordResetEmail(user.Email, resetURL); err != nil {
		return err
	}
	
	return nil
}

func (uc *PasswordResetUsecase) ResetPassword(
	ctx context.Context,
	token string,
	newPassword string,
) error {
	// 1. 验证Token
	resetToken, err := uc.resetTokenRepo.GetByToken(ctx, token)
	if err != nil {
		return ErrInvalidResetToken
	}
	
	// 2. 检查是否过期
	if time.Now().After(resetToken.ExpiresAt) {
		return ErrResetTokenExpired
	}
	
	// 3. 获取用户
	user, err := uc.userRepo.GetByID(ctx, resetToken.UserID)
	if err != nil {
		return err
	}
	
	// 4. 更新密码
	if err := user.UpdatePassword(newPassword); err != nil {
		return err
	}
	
	if err := uc.userRepo.Update(ctx, user); err != nil {
		return err
	}
	
	// 5. 删除重置Token
	if err := uc.resetTokenRepo.Delete(ctx, resetToken.ID); err != nil {
		return err
	}
	
	return nil
}
```

**2. Token黑名单**

```go
// File: internal/infra/redis/token_blacklist.go

type TokenBlacklist struct {
	redisClient *redis.Client
}

func NewTokenBlacklist(redisClient *redis.Client) *TokenBlacklist {
	return &TokenBlacklist{
		redisClient: redisClient,
	}
}

func (tb *TokenBlacklist) Add(ctx context.Context, token string, expiresIn time.Duration) error {
	key := fmt.Sprintf("token:blacklist:%s", token)
	return tb.redisClient.Set(ctx, key, "1", expiresIn).Err()
}

func (tb *TokenBlacklist) IsBlacklisted(ctx context.Context, token string) (bool, error) {
	key := fmt.Sprintf("token:blacklist:%s", token)
	exists, err := tb.redisClient.Exists(ctx, key).Result()
	if err != nil {
		return false, err
	}
	return exists > 0, nil
}

// 集成到认证中间件
func (s *IdentityService) VerifyToken(
	ctx context.Context,
	token string,
) (*UserClaims, error) {
	// 1. 检查黑名单
	isBlacklisted, err := s.tokenBlacklist.IsBlacklisted(ctx, token)
	if err != nil {
		return nil, err
	}
	if isBlacklisted {
		return nil, ErrTokenBlacklisted
	}
	
	// 2. 验证Token
	claims, err := s.authUC.VerifyToken(ctx, token)
	if err != nil {
		return nil, err
	}
	
	return claims, nil
}

func (s *IdentityService) Logout(
	ctx context.Context,
	token string,
) error {
	// 1. 解析Token获取过期时间
	claims, err := s.authUC.VerifyToken(ctx, token)
	if err != nil {
		return err
	}
	
	// 2. 加入黑名单
	expiresIn := time.Until(claims.ExpiresAt)
	if err := s.tokenBlacklist.Add(ctx, token, expiresIn); err != nil {
		return err
	}
	
	return nil
}
```

#### Sprint 3: 审计日志（1周）

**目标**: 记录所有重要操作，用于安全审计

```go
// File: internal/domain/audit_log.go

type AuditLog struct {
	ID         string
	TenantID   string
	UserID     string
	Action     string        // login, logout, create_user, update_user, etc.
	Resource   string        // 资源类型
	ResourceID string        // 资源ID
	IP         string
	UserAgent  string
	Metadata   map[string]interface{}
	Success    bool
	ErrorMsg   string
	CreatedAt  time.Time
}

// File: internal/biz/audit_usecase.go

type AuditUsecase struct {
	auditRepo AuditRepository
}

func (uc *AuditUsecase) LogAction(
	ctx context.Context,
	tenantID, userID string,
	action, resource, resourceID string,
	metadata map[string]interface{},
	success bool,
	errorMsg string,
) error {
	// 从context获取IP和User-Agent
	ip := getIPFromContext(ctx)
	userAgent := getUserAgentFromContext(ctx)
	
	auditLog := &AuditLog{
		ID:         generateID(),
		TenantID:   tenantID,
		UserID:     userID,
		Action:     action,
		Resource:   resource,
		ResourceID: resourceID,
		IP:         ip,
		UserAgent:  userAgent,
		Metadata:   metadata,
		Success:    success,
		ErrorMsg:   errorMsg,
		CreatedAt:  time.Now(),
	}
	
	return uc.auditRepo.Create(ctx, auditLog)
}

// 在UserUsecase中集成审计日志
func (uc *UserUsecase) CreateUser(
	ctx context.Context,
	email, password, username, tenantID string,
) (*User, error) {
	// ... 创建用户逻辑 ...
	
	// 记录审计日志
	err := uc.auditUC.LogAction(
		ctx,
		tenantID,
		"", // 创建用户时还没有userID
		"create_user",
		"user",
		user.ID,
		map[string]interface{}{
			"email": email,
			"username": username,
		},
		err == nil,
		errorMessage(err),
	)
	
	return user, err
}
```

### 1.3 性能指标

| 指标 | 当前值 | 目标值 | 验收标准 |
|-----|--------|--------|----------|
| 登录延迟 | ~100ms | < 80ms | P95 < 150ms |
| Token验证延迟 | ~10ms | < 5ms | P95 < 20ms |
| OAuth登录成功率 | N/A | > 95% | 错误率 < 5% |
| 黑名单查询延迟 | N/A | < 5ms | Redis查询 |

---

## 2. Conversation Service

### 2.1 当前实现状态

#### ✅ 已实现功能

| 功能模块 | 实现状态 | 说明 |
|---------|---------|------|
| 对话管理 | ✅ 完成 | 创建、更新、归档、删除 |
| 消息管理 | ✅ 完成 | 发送、获取、列表 |
| 上下文管理 | ✅ 完成 | 消息数/Token限制 |
| 权限控制 | ✅ 完成 | 用户级权限、租户隔离 |

#### 🔄 待完善功能

| 优先级 | 功能 | 状态 | 预计工作量 |
|-------|------|------|-----------|
| P0 | 流式对话响应 | 未实现 | 3天 |
| P0 | 事件发布（Kafka） | 未实现 | 3天 |
| P1 | 上下文压缩 | 未实现 | 4天 |
| P1 | 智能标题生成 | 未实现 | 2天 |
| P2 | 对话总结 | 未实现 | 3天 |
| P2 | 对话分享 | 未实现 | 4天 |

### 2.2 迭代计划

#### Sprint 1: 流式对话响应（1周）

**目标**: 实现SSE流式返回对话响应

```go
// File: internal/biz/conversation_usecase.go

func (uc *ConversationUsecase) SendMessageStream(
	ctx context.Context,
	conversationID, userID, content string,
) (<-chan MessageChunk, error) {
	// 1. 验证对话
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return nil, err
	}
	
	// 2. 权限检查
	if conversation.UserID != userID {
		return nil, ErrUnauthorized
	}
	
	// 3. 创建用户消息
	userMsg := NewMessage(conversationID, conversation.TenantID, userID, MessageRoleUser, content)
	if err := uc.messageRepo.CreateMessage(ctx, userMsg); err != nil {
		return nil, err
	}
	
	// 4. 创建流式通道
	chunkChan := make(chan MessageChunk, 100)
	
	// 5. 异步处理
	go func() {
		defer close(chunkChan)
		
		// 获取对话历史
		history, _ := uc.messageRepo.ListMessages(ctx, conversationID, 10, 0)
		
		// 调用AI Orchestrator流式生成
		stream, err := uc.orchestratorClient.GenerateStream(ctx, &orchestrator.GenerateRequest{
			ConversationId: conversationID,
			Query:          content,
			History:        convertToHistory(history),
		})
		
		if err != nil {
			chunkChan <- MessageChunk{Error: err}
			return
		}
		
		var fullContent string
		for {
			chunk, err := stream.Recv()
			if err == io.EOF {
				break
			}
			if err != nil {
				chunkChan <- MessageChunk{Error: err}
				return
			}
			
			fullContent += chunk.Content
			chunkChan <- MessageChunk{
				Content:   chunk.Content,
				IsPartial: true,
			}
		}
		
		// 保存完整的助手消息
		assistantMsg := NewMessage(
			conversationID,
			conversation.TenantID,
			"assistant",
			MessageRoleAssistant,
			fullContent,
		)
		uc.messageRepo.CreateMessage(ctx, assistantMsg)
		
		// 发送完成信号
		chunkChan <- MessageChunk{
			Content:   fullContent,
			IsPartial: false,
			MessageID: assistantMsg.ID,
		}
	}()
	
	return chunkChan, nil
}

// File: internal/server/http.go

func (s *HTTPServer) sendMessageStream(c *gin.Context) {
	var req struct {
		ConversationID string `json:"conversation_id" binding:"required"`
		UserID         string `json:"user_id" binding:"required"`
		Content        string `json:"content" binding:"required"`
	}
	
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	
	// 设置SSE头
	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	
	// 获取流式通道
	chunkChan, err := s.service.SendMessageStream(
		c.Request.Context(),
		req.ConversationID,
		req.UserID,
		req.Content,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	
	// 流式返回
	c.Stream(func(w io.Writer) bool {
		chunk, ok := <-chunkChan
		if !ok {
			return false
		}
		
		if chunk.Error != nil {
			c.SSEvent("error", gin.H{"error": chunk.Error.Error()})
			return false
		}
		
		c.SSEvent("message", gin.H{
			"content":    chunk.Content,
			"is_partial": chunk.IsPartial,
			"message_id": chunk.MessageID,
		})
		
		return true
	})
}
```

#### Sprint 2: 事件发布（1周）

**目标**: 发布对话事件到Kafka，供其他服务消费

```go
// File: internal/infra/kafka/producer.go

type EventProducer struct {
	producer sarama.SyncProducer
}

func NewEventProducer(brokers []string) (*EventProducer, error) {
	config := sarama.NewConfig()
	config.Producer.Return.Successes = true
	config.Producer.RequiredAcks = sarama.WaitForAll
	
	producer, err := sarama.NewSyncProducer(brokers, config)
	if err != nil {
		return nil, err
	}
	
	return &EventProducer{producer: producer}, nil
}

func (p *EventProducer) PublishEvent(topic string, event interface{}) error {
	eventBytes, err := json.Marshal(event)
	if err != nil {
		return err
	}
	
	msg := &sarama.ProducerMessage{
		Topic: topic,
		Value: sarama.ByteEncoder(eventBytes),
	}
	
	_, _, err = p.producer.SendMessage(msg)
	return err
}

// File: internal/biz/conversation_usecase.go

func (uc *ConversationUsecase) CreateConversation(
	ctx context.Context,
	tenantID, userID, title string,
	mode ConversationMode,
) (*Conversation, error) {
	// 创建对话
	conversation := NewConversation(tenantID, userID, title, mode)
	
	if err := uc.conversationRepo.CreateConversation(ctx, conversation); err != nil {
		return nil, err
	}
	
	// 发布事件
	event := ConversationCreatedEvent{
		ConversationID: conversation.ID,
		TenantID:       tenantID,
		UserID:         userID,
		Title:          title,
		Mode:           string(mode),
		CreatedAt:      conversation.CreatedAt,
	}
	
	if err := uc.eventProducer.PublishEvent("conversation.created", event); err != nil {
		// 记录错误但不影响主流程
		logger.Errorf("Failed to publish event: %v", err)
	}
	
	return conversation, nil
}
```

#### Sprint 3: 智能标题生成（1周）

**目标**: 自动为对话生成有意义的标题

```go
// File: internal/biz/title_generator_usecase.go

type TitleGeneratorUsecase struct {
	llmClient     LLMClient
	conversationRepo ConversationRepository
	messageRepo   MessageRepository
}

func (uc *TitleGeneratorUsecase) GenerateTitle(
	ctx context.Context,
	conversationID string,
) (string, error) {
	// 1. 获取对话的前3条消息
	messages, err := uc.messageRepo.ListMessages(ctx, conversationID, 3, 0)
	if err != nil {
		return "", err
	}
	
	if len(messages) == 0 {
		return "", ErrNoMessages
	}
	
	// 2. 构建提示词
	prompt := uc.buildTitlePrompt(messages)
	
	// 3. 调用LLM生成标题
	response, err := uc.llmClient.ChatCompletion(ctx, &LLMRequest{
		Model: "gpt-3.5-turbo",
		Messages: []LLMMessage{
			{
				Role:    "user",
				Content: prompt,
			},
		},
		MaxTokens:   20,
		Temperature: 0.7,
	})
	
	if err != nil {
		return "", err
	}
	
	title := strings.TrimSpace(response.Choices[0].Message.Content)
	
	// 4. 更新对话标题
	conversation, err := uc.conversationRepo.GetConversation(ctx, conversationID)
	if err != nil {
		return "", err
	}
	
	conversation.Title = title
	if err := uc.conversationRepo.UpdateConversation(ctx, conversation); err != nil {
		return "", err
	}
	
	return title, nil
}

func (uc *TitleGeneratorUsecase) buildTitlePrompt(messages []Message) string {
	var conversationText string
	for _, msg := range messages {
		conversationText += fmt.Sprintf("%s: %s\n", msg.Role, msg.Content)
	}
	
	return fmt.Sprintf(`根据以下对话内容，生成一个简洁的标题（不超过10个字）：

%s

标题：`, conversationText)
}

// 自动触发标题生成
func (uc *ConversationUsecase) SendMessage(
	ctx context.Context,
	conversationID, userID string,
	role MessageRole,
	content string,
) (*Message, error) {
	// ... 创建消息逻辑 ...
	
	// 如果是第一条用户消息，自动生成标题
	conversation, _ := uc.conversationRepo.GetConversation(ctx, conversationID)
	if conversation.MessageCount == 1 && conversation.Title == "" {
		go func() {
			title, err := uc.titleGeneratorUC.GenerateTitle(context.Background(), conversationID)
			if err != nil {
				logger.Errorf("Failed to generate title: %v", err)
			} else {
				logger.Infof("Generated title for conversation %s: %s", conversationID, title)
			}
		}()
	}
	
	return message, nil
}
```

### 2.3 性能指标

| 指标 | 当前值 | 目标值 | 验收标准 |
|-----|--------|--------|----------|
| 创建对话延迟 | ~100ms | < 80ms | P95 < 150ms |
| 发送消息延迟 | ~100ms | < 80ms | P95 < 150ms |
| 流式TTFB | N/A | < 500ms | 首字节 < 500ms |
| 并发支持 | 未测试 | > 500 RPS | 无降级 |

---

## 3-7. 其他服务简要计划

### 3. Knowledge Service (Go)

**P0任务**:
- Proto定义完善
- gRPC服务实现
- 与Indexing Service集成

**P1任务**:
- 知识库统计和分析
- 文档导入导出
- 权限控制细化

### 4. AI Orchestrator

**P0任务**:
- Proto定义和gRPC注册
- 服务发现集成（Consul）
- 流式响应支持

**P1任务**:
- Kafka任务队列
- 任务优先级调度
- 监控和告警完善

### 5. Analytics Service

**P0任务**:
- 物化视图优化
- 实时看板API
- 报表导出完善

**P1任务**:
- 自定义查询
- 告警功能
- 趋势预测

### 6. Model Router

**P0任务**:
- A/B测试支持
- 智能路由策略
- 熔断降级完善

**P1任务**:
- 成本优化算法
- 模型性能监控
- 自动扩缩容

### 7. Notification Service

**P0任务**:
- 邮件通知
- 短信通知（阿里云）
- WebSocket实时通知

**P1任务**:
- 通知模板管理
- 批量通知
- 通知统计

---

## 总体时间线

### Phase 1: 核心功能完善（1-2个月）

**Week 1-2**: Identity OAuth2 + Conversation流式响应
**Week 3-4**: Identity密码重置 + Conversation事件发布
**Week 5-6**: Knowledge Service gRPC + AI Orchestrator服务发现
**Week 7-8**: Analytics实时看板 + Model Router智能路由

### Phase 2: 高级功能开发（2-3个月）

**Week 9-12**: Identity审计日志 + Conversation智能标题 + 通知服务
**Week 13-16**: 权限动态配置 + 对话总结 + A/B测试

### Phase 3: 性能优化和测试（1个月）

**Week 17-20**: 性能测试、压力测试、优化调优

---

## 验收标准

### 功能验收

- ✅ 所有P0功能实现并测试通过
- ✅ 所有P1功能至少完成80%
- ✅ API文档完整（Proto + OpenAPI）
- ✅ 单元测试覆盖率 > 75%

### 性能验收

- ✅ 满足所有性能指标目标值
- ✅ 并发压力测试通过（500+ RPS）
- ✅ 内存和CPU使用在合理范围

### 质量验收

- ✅ 代码审查通过
- ✅ 安全扫描无高危漏洞
- ✅ 监控和告警配置完整
- ✅ 文档完整（README + 实现总结）

---

**文档版本**: v2.0  
**最后更新**: 2025-10-27  
**维护者**: VoiceHelper Team


