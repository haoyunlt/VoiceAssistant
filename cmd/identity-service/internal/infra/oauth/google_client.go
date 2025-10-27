package oauth

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"

	"github.com/VoiceAssistant/cmd/identity-service/internal/domain"
)

// GoogleClient Google OAuth客户端
type GoogleClient struct {
	clientID     string
	clientSecret string
	redirectURI  string
	client       *http.Client
}

// NewGoogleClient 创建Google OAuth客户端
func NewGoogleClient(clientID, clientSecret, redirectURI string) *GoogleClient {
	return &GoogleClient{
		clientID:     clientID,
		clientSecret: clientSecret,
		redirectURI:  redirectURI,
		client:       &http.Client{},
	}
}

// GetUserInfo 获取Google用户信息
func (c *GoogleClient) GetUserInfo(ctx context.Context, code string) (*domain.OAuthUserInfo, error) {
	// 1. 交换access_token
	tokenURL := "https://oauth2.googleapis.com/token"
	data := url.Values{}
	data.Set("client_id", c.clientID)
	data.Set("client_secret", c.clientSecret)
	data.Set("code", code)
	data.Set("redirect_uri", c.redirectURI)
	data.Set("grant_type", "authorization_code")

	req, err := http.NewRequestWithContext(ctx, "POST", tokenURL, strings.NewReader(data.Encode()))
	if err != nil {
		return nil, fmt.Errorf("create token request: %w", err)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request token: %w", err)
	}
	defer resp.Body.Close()

	var tokenResp struct {
		AccessToken  string `json:"access_token"`
		ExpiresIn    int    `json:"expires_in"`
		RefreshToken string `json:"refresh_token"`
		Scope        string `json:"scope"`
		TokenType    string `json:"token_type"`
		IDToken      string `json:"id_token"`
		Error        string `json:"error"`
		ErrorDesc    string `json:"error_description"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return nil, fmt.Errorf("decode token response: %w", err)
	}

	if tokenResp.Error != "" {
		return nil, fmt.Errorf("google error: %s - %s", tokenResp.Error, tokenResp.ErrorDesc)
	}

	// 2. 获取用户信息
	userInfoURL := "https://www.googleapis.com/oauth2/v2/userinfo"
	req, err = http.NewRequestWithContext(ctx, "GET", userInfoURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create userinfo request: %w", err)
	}
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", tokenResp.AccessToken))

	resp, err = c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request userinfo: %w", err)
	}
	defer resp.Body.Close()

	var googleUser struct {
		ID            string `json:"id"`
		Email         string `json:"email"`
		VerifiedEmail bool   `json:"verified_email"`
		Name          string `json:"name"`
		GivenName     string `json:"given_name"`
		FamilyName    string `json:"family_name"`
		Picture       string `json:"picture"`
		Locale        string `json:"locale"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&googleUser); err != nil {
		return nil, fmt.Errorf("decode userinfo response: %w", err)
	}

	// 3. 转换为统一格式
	return &domain.OAuthUserInfo{
		ID:          googleUser.ID,
		Name:        googleUser.Name,
		Email:       googleUser.Email,
		AvatarURL:   googleUser.Picture,
		AccessToken: tokenResp.AccessToken,
		ExpiresIn:   tokenResp.ExpiresIn,
	}, nil
}

// GetAuthURL 获取授权URL
func (c *GoogleClient) GetAuthURL(state string) string {
	params := url.Values{}
	params.Set("client_id", c.clientID)
	params.Set("redirect_uri", c.redirectURI)
	params.Set("response_type", "code")
	params.Set("scope", "openid email profile")
	params.Set("state", state)
	params.Set("access_type", "offline") // 获取refresh_token
	params.Set("prompt", "consent")

	return "https://accounts.google.com/o/oauth2/v2/auth?" + params.Encode()
}
