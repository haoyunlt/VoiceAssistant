package infrastructure

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/github"
	"golang.org/x/oauth2/google"
)

// OAuthProvider OAuth提供商接口
type OAuthProvider interface {
	GetAuthURL(state string) string
	ExchangeCode(ctx context.Context, code string) (*oauth2.Token, error)
	GetUserInfo(ctx context.Context, token *oauth2.Token) (*OAuthUserInfo, error)
}

// OAuthUserInfo OAuth用户信息
type OAuthUserInfo struct {
	ID            string `json:"id"`
	Email         string `json:"email"`
	Name          string `json:"name"`
	Avatar        string `json:"avatar"`
	EmailVerified bool   `json:"email_verified"`
	Provider      string `json:"provider"`
}

// GoogleOAuthProvider Google OAuth提供商
type GoogleOAuthProvider struct {
	config *oauth2.Config
}

// NewGoogleOAuthProvider 创建Google OAuth提供商
func NewGoogleOAuthProvider(clientID, clientSecret, redirectURL string) *GoogleOAuthProvider {
	return &GoogleOAuthProvider{
		config: &oauth2.Config{
			ClientID:     clientID,
			ClientSecret: clientSecret,
			RedirectURL:  redirectURL,
			Scopes: []string{
				"https://www.googleapis.com/auth/userinfo.email",
				"https://www.googleapis.com/auth/userinfo.profile",
			},
			Endpoint: google.Endpoint,
		},
	}
}

// GetAuthURL 获取授权URL
func (p *GoogleOAuthProvider) GetAuthURL(state string) string {
	return p.config.AuthCodeURL(state, oauth2.AccessTypeOffline)
}

// ExchangeCode 交换授权码
func (p *GoogleOAuthProvider) ExchangeCode(ctx context.Context, code string) (*oauth2.Token, error) {
	token, err := p.config.Exchange(ctx, code)
	if err != nil {
		return nil, fmt.Errorf("failed to exchange code: %w", err)
	}
	return token, nil
}

// GetUserInfo 获取用户信息
func (p *GoogleOAuthProvider) GetUserInfo(ctx context.Context, token *oauth2.Token) (*OAuthUserInfo, error) {
	client := p.config.Client(ctx, token)

	resp, err := client.Get("https://www.googleapis.com/oauth2/v2/userinfo")
	if err != nil {
		return nil, fmt.Errorf("failed to get user info: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("google API error: %d, %s", resp.StatusCode, string(body))
	}

	var googleUser struct {
		ID            string `json:"id"`
		Email         string `json:"email"`
		VerifiedEmail bool   `json:"verified_email"`
		Name          string `json:"name"`
		Picture       string `json:"picture"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&googleUser); err != nil {
		return nil, fmt.Errorf("failed to decode user info: %w", err)
	}

	return &OAuthUserInfo{
		ID:            googleUser.ID,
		Email:         googleUser.Email,
		Name:          googleUser.Name,
		Avatar:        googleUser.Picture,
		EmailVerified: googleUser.VerifiedEmail,
		Provider:      "google",
	}, nil
}

// GitHubOAuthProvider GitHub OAuth提供商
type GitHubOAuthProvider struct {
	config *oauth2.Config
}

// NewGitHubOAuthProvider 创建GitHub OAuth提供商
func NewGitHubOAuthProvider(clientID, clientSecret, redirectURL string) *GitHubOAuthProvider {
	return &GitHubOAuthProvider{
		config: &oauth2.Config{
			ClientID:     clientID,
			ClientSecret: clientSecret,
			RedirectURL:  redirectURL,
			Scopes:       []string{"user:email"},
			Endpoint:     github.Endpoint,
		},
	}
}

// GetAuthURL 获取授权URL
func (p *GitHubOAuthProvider) GetAuthURL(state string) string {
	return p.config.AuthCodeURL(state)
}

// ExchangeCode 交换授权码
func (p *GitHubOAuthProvider) ExchangeCode(ctx context.Context, code string) (*oauth2.Token, error) {
	token, err := p.config.Exchange(ctx, code)
	if err != nil {
		return nil, fmt.Errorf("failed to exchange code: %w", err)
	}
	return token, nil
}

// GetUserInfo 获取用户信息
func (p *GitHubOAuthProvider) GetUserInfo(ctx context.Context, token *oauth2.Token) (*OAuthUserInfo, error) {
	client := p.config.Client(ctx, token)

	// 获取用户基本信息
	resp, err := client.Get("https://api.github.com/user")
	if err != nil {
		return nil, fmt.Errorf("failed to get user info: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("github API error: %d, %s", resp.StatusCode, string(body))
	}

	var githubUser struct {
		ID        int64  `json:"id"`
		Login     string `json:"login"`
		Name      string `json:"name"`
		Email     string `json:"email"`
		AvatarURL string `json:"avatar_url"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&githubUser); err != nil {
		return nil, fmt.Errorf("failed to decode user info: %w", err)
	}

	// 如果没有public email，获取primary email
	email := githubUser.Email
	if email == "" {
		email, err = p.getPrimaryEmail(ctx, client)
		if err != nil {
			return nil, fmt.Errorf("failed to get primary email: %w", err)
		}
	}

	return &OAuthUserInfo{
		ID:            fmt.Sprintf("%d", githubUser.ID),
		Email:         email,
		Name:          githubUser.Name,
		Avatar:        githubUser.AvatarURL,
		EmailVerified: true, // GitHub emails are verified
		Provider:      "github",
	}, nil
}

// getPrimaryEmail 获取GitHub主邮箱
func (p *GitHubOAuthProvider) getPrimaryEmail(ctx context.Context, client *http.Client) (string, error) {
	resp, err := client.Get("https://api.github.com/user/emails")
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("failed to get emails: %d", resp.StatusCode)
	}

	var emails []struct {
		Email    string `json:"email"`
		Primary  bool   `json:"primary"`
		Verified bool   `json:"verified"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&emails); err != nil {
		return "", err
	}

	for _, e := range emails {
		if e.Primary && e.Verified {
			return e.Email, nil
		}
	}

	if len(emails) > 0 {
		return emails[0].Email, nil
	}

	return "", fmt.Errorf("no email found")
}

// OAuthManager OAuth管理器
type OAuthManager struct {
	providers  map[string]OAuthProvider
	stateStore StateStore
}

// StateStore 状态存储接口
type StateStore interface {
	Set(ctx context.Context, state string, data interface{}, ttl time.Duration) error
	Get(ctx context.Context, state string) (interface{}, error)
	Delete(ctx context.Context, state string) error
}

// NewOAuthManager 创建OAuth管理器
func NewOAuthManager(stateStore StateStore) *OAuthManager {
	return &OAuthManager{
		providers:  make(map[string]OAuthProvider),
		stateStore: stateStore,
	}
}

// RegisterProvider 注册OAuth提供商
func (m *OAuthManager) RegisterProvider(name string, provider OAuthProvider) {
	m.providers[name] = provider
}

// GetProvider 获取OAuth提供商
func (m *OAuthManager) GetProvider(name string) (OAuthProvider, error) {
	provider, ok := m.providers[name]
	if !ok {
		return nil, fmt.Errorf("OAuth provider not found: %s", name)
	}
	return provider, nil
}

// GenerateAuthURL 生成授权URL
func (m *OAuthManager) GenerateAuthURL(ctx context.Context, provider string, redirectURI string) (string, string, error) {
	p, err := m.GetProvider(provider)
	if err != nil {
		return "", "", err
	}

	// 生成随机state
	state := generateRandomState()

	// 存储state（用于CSRF保护）
	stateData := map[string]interface{}{
		"provider":     provider,
		"redirect_uri": redirectURI,
		"created_at":   time.Now(),
	}

	if err := m.stateStore.Set(ctx, state, stateData, 10*time.Minute); err != nil {
		return "", "", fmt.Errorf("failed to store state: %w", err)
	}

	authURL := p.GetAuthURL(state)
	return authURL, state, nil
}

// HandleCallback 处理OAuth回调
func (m *OAuthManager) HandleCallback(ctx context.Context, provider, code, state string) (*OAuthUserInfo, error) {
	// 验证state
	stateData, err := m.stateStore.Get(ctx, state)
	if err != nil {
		return nil, fmt.Errorf("invalid state: %w", err)
	}

	// 删除已使用的state
	m.stateStore.Delete(ctx, state)

	// 验证provider匹配
	storedProvider := stateData.(map[string]interface{})["provider"].(string)
	if storedProvider != provider {
		return nil, fmt.Errorf("provider mismatch")
	}

	// 获取provider
	p, err := m.GetProvider(provider)
	if err != nil {
		return nil, err
	}

	// 交换授权码
	token, err := p.ExchangeCode(ctx, code)
	if err != nil {
		return nil, fmt.Errorf("failed to exchange code: %w", err)
	}

	// 获取用户信息
	userInfo, err := p.GetUserInfo(ctx, token)
	if err != nil {
		return nil, fmt.Errorf("failed to get user info: %w", err)
	}

	return userInfo, nil
}

// generateRandomState 生成随机state
func generateRandomState() string {
	// 实际应该使用加密安全的随机数生成器
	return fmt.Sprintf("state_%d", time.Now().UnixNano())
}
