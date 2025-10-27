package oauth

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/VoiceAssistant/cmd/identity-service/internal/domain"
)

// WechatClient 微信OAuth客户端
type WechatClient struct {
	appID     string
	appSecret string
	client    *http.Client
}

// NewWechatClient 创建微信OAuth客户端
func NewWechatClient(appID, appSecret string) *WechatClient {
	return &WechatClient{
		appID:     appID,
		appSecret: appSecret,
		client:    &http.Client{},
	}
}

// GetUserInfo 获取微信用户信息
func (c *WechatClient) GetUserInfo(ctx context.Context, code string) (*domain.OAuthUserInfo, error) {
	// 1. 获取access_token
	tokenURL := fmt.Sprintf(
		"https://api.weixin.qq.com/sns/oauth2/access_token?appid=%s&secret=%s&code=%s&grant_type=authorization_code",
		c.appID,
		c.appSecret,
		code,
	)

	req, err := http.NewRequestWithContext(ctx, "GET", tokenURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create token request: %w", err)
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request token: %w", err)
	}
	defer resp.Body.Close()

	var tokenResp struct {
		AccessToken  string `json:"access_token"`
		ExpiresIn    int    `json:"expires_in"`
		RefreshToken string `json:"refresh_token"`
		OpenID       string `json:"openid"`
		Scope        string `json:"scope"`
		UnionID      string `json:"unionid"`
		ErrCode      int    `json:"errcode"`
		ErrMsg       string `json:"errmsg"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return nil, fmt.Errorf("decode token response: %w", err)
	}

	if tokenResp.ErrCode != 0 {
		return nil, fmt.Errorf("wechat error: %s (code: %d)", tokenResp.ErrMsg, tokenResp.ErrCode)
	}

	// 2. 获取用户信息
	userInfoURL := fmt.Sprintf(
		"https://api.weixin.qq.com/sns/userinfo?access_token=%s&openid=%s&lang=zh_CN",
		tokenResp.AccessToken,
		tokenResp.OpenID,
	)

	req, err = http.NewRequestWithContext(ctx, "GET", userInfoURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create userinfo request: %w", err)
	}

	resp, err = c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request userinfo: %w", err)
	}
	defer resp.Body.Close()

	var wechatUser struct {
		OpenID     string `json:"openid"`
		Nickname   string `json:"nickname"`
		Sex        int    `json:"sex"`
		Province   string `json:"province"`
		City       string `json:"city"`
		Country    string `json:"country"`
		HeadImgURL string `json:"headimgurl"`
		UnionID    string `json:"unionid"`
		ErrCode    int    `json:"errcode"`
		ErrMsg     string `json:"errmsg"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&wechatUser); err != nil {
		return nil, fmt.Errorf("decode userinfo response: %w", err)
	}

	if wechatUser.ErrCode != 0 {
		return nil, fmt.Errorf("wechat error: %s (code: %d)", wechatUser.ErrMsg, wechatUser.ErrCode)
	}

	// 3. 转换为统一格式（优先使用UnionID，因为它在同一主体的不同应用间是唯一的）
	userID := wechatUser.UnionID
	if userID == "" {
		userID = wechatUser.OpenID
	}

	return &domain.OAuthUserInfo{
		ID:          userID,
		Name:        wechatUser.Nickname,
		Email:       "", // 微信不提供邮箱
		AvatarURL:   wechatUser.HeadImgURL,
		AccessToken: tokenResp.AccessToken,
		ExpiresIn:   tokenResp.ExpiresIn,
	}, nil
}
