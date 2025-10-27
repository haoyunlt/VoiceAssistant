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

// GitHubClient GitHub OAuth客户端
type GitHubClient struct {
	clientID     string
	clientSecret string
	client       *http.Client
}

// NewGitHubClient 创建GitHub OAuth客户端
func NewGitHubClient(clientID, clientSecret string) *GitHubClient {
	return &GitHubClient{
		clientID:     clientID,
		clientSecret: clientSecret,
		client:       &http.Client{},
	}
}

// GetUserInfo 获取GitHub用户信息
func (c *GitHubClient) GetUserInfo(ctx context.Context, code string) (*domain.OAuthUserInfo, error) {
	// 1. 交换access_token
	tokenURL := "https://github.com/login/oauth/access_token"
	data := url.Values{}
	data.Set("client_id", c.clientID)
	data.Set("client_secret", c.clientSecret)
	data.Set("code", code)

	req, err := http.NewRequestWithContext(ctx, "POST", tokenURL, strings.NewReader(data.Encode()))
	if err != nil {
		return nil, fmt.Errorf("create token request: %w", err)
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request token: %w", err)
	}
	defer resp.Body.Close()

	var tokenResp struct {
		AccessToken string `json:"access_token"`
		TokenType   string `json:"token_type"`
		Scope       string `json:"scope"`
		Error       string `json:"error"`
		ErrorDesc   string `json:"error_description"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return nil, fmt.Errorf("decode token response: %w", err)
	}

	if tokenResp.Error != "" {
		return nil, fmt.Errorf("github error: %s - %s", tokenResp.Error, tokenResp.ErrorDesc)
	}

	// 2. 获取用户信息
	userInfoURL := "https://api.github.com/user"
	req, err = http.NewRequestWithContext(ctx, "GET", userInfoURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create userinfo request: %w", err)
	}
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", tokenResp.AccessToken))
	req.Header.Set("Accept", "application/json")

	resp, err = c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request userinfo: %w", err)
	}
	defer resp.Body.Close()

	var githubUser struct {
		ID        int    `json:"id"`
		Login     string `json:"login"`
		Name      string `json:"name"`
		Email     string `json:"email"`
		AvatarURL string `json:"avatar_url"`
		Bio       string `json:"bio"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&githubUser); err != nil {
		return nil, fmt.Errorf("decode userinfo response: %w", err)
	}

	// 3. 如果公开email为空，尝试获取primary email
	email := githubUser.Email
	if email == "" {
		email, _ = c.getPrimaryEmail(ctx, tokenResp.AccessToken)
	}

	// 4. 转换为统一格式
	username := githubUser.Name
	if username == "" {
		username = githubUser.Login
	}

	return &domain.OAuthUserInfo{
		ID:          fmt.Sprintf("%d", githubUser.ID),
		Name:        username,
		Email:       email,
		AvatarURL:   githubUser.AvatarURL,
		AccessToken: tokenResp.AccessToken,
		ExpiresIn:   0, // GitHub access token不过期
	}, nil
}

// getPrimaryEmail 获取用户的primary email
func (c *GitHubClient) getPrimaryEmail(ctx context.Context, accessToken string) (string, error) {
	emailsURL := "https://api.github.com/user/emails"
	req, err := http.NewRequestWithContext(ctx, "GET", emailsURL, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", accessToken))
	req.Header.Set("Accept", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	var emails []struct {
		Email      string `json:"email"`
		Primary    bool   `json:"primary"`
		Verified   bool   `json:"verified"`
		Visibility string `json:"visibility"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&emails); err != nil {
		return "", err
	}

	// 查找primary且verified的邮箱
	for _, email := range emails {
		if email.Primary && email.Verified {
			return email.Email, nil
		}
	}

	// 如果没有primary，返回第一个verified的
	for _, email := range emails {
		if email.Verified {
			return email.Email, nil
		}
	}

	return "", nil
}
