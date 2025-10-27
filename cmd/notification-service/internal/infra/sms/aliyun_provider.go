package sms

import (
	"crypto/hmac"
	"crypto/sha1"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"
)

// AliyunConfig 阿里云短信配置
type AliyunConfig struct {
	AccessKeyID     string
	AccessKeySecret string
	SignName        string
	TemplateCode    string
	Endpoint        string
}

// AliyunProvider 阿里云短信提供商
type AliyunProvider struct {
	config *AliyunConfig
	client *http.Client
}

// NewAliyunProvider 创建阿里云短信提供商
func NewAliyunProvider(config *AliyunConfig) *AliyunProvider {
	if config.Endpoint == "" {
		config.Endpoint = "https://dysmsapi.aliyuncs.com"
	}

	return &AliyunProvider{
		config: config,
		client: &http.Client{Timeout: 10 * time.Second},
	}
}

// SendSMS 发送短信
func (p *AliyunProvider) SendSMS(phone, content string) error {
	// 构建请求参数
	params := p.buildParams(phone, content)

	// 签名
	signature := p.sign(params)
	params["Signature"] = signature

	// 发送请求
	return p.sendRequest(params)
}

// SendSMSWithTemplate 使用模板发送短信
func (p *AliyunProvider) SendSMSWithTemplate(
	phone string,
	templateCode string,
	templateParams map[string]string,
) error {
	// 构建请求参数
	params := map[string]string{
		"PhoneNumbers":     phone,
		"SignName":         p.config.SignName,
		"TemplateCode":     templateCode,
		"Action":           "SendSms",
		"Version":          "2017-05-25",
		"RegionId":         "cn-hangzhou",
		"Format":           "JSON",
		"AccessKeyId":      p.config.AccessKeyID,
		"SignatureMethod":  "HMAC-SHA1",
		"SignatureVersion": "1.0",
		"SignatureNonce":   generateNonce(),
		"Timestamp":        generateTimestamp(),
	}

	// 模板参数
	if len(templateParams) > 0 {
		paramsJSON, _ := json.Marshal(templateParams)
		params["TemplateParam"] = string(paramsJSON)
	}

	// 签名
	signature := p.sign(params)
	params["Signature"] = signature

	// 发送请求
	return p.sendRequest(params)
}

// buildParams 构建请求参数
func (p *AliyunProvider) buildParams(phone, content string) map[string]string {
	return map[string]string{
		"PhoneNumbers":     phone,
		"SignName":         p.config.SignName,
		"TemplateCode":     p.config.TemplateCode,
		"TemplateParam":    fmt.Sprintf(`{"content":"%s"}`, content),
		"Action":           "SendSms",
		"Version":          "2017-05-25",
		"RegionId":         "cn-hangzhou",
		"Format":           "JSON",
		"AccessKeyId":      p.config.AccessKeyID,
		"SignatureMethod":  "HMAC-SHA1",
		"SignatureVersion": "1.0",
		"SignatureNonce":   generateNonce(),
		"Timestamp":        generateTimestamp(),
	}
}

// sign 签名
func (p *AliyunProvider) sign(params map[string]string) string {
	// 1. 按key排序
	keys := make([]string, 0, len(params))
	for k := range params {
		if k != "Signature" {
			keys = append(keys, k)
		}
	}
	sort.Strings(keys)

	// 2. 构建待签名字符串
	var sortedParams []string
	for _, k := range keys {
		sortedParams = append(sortedParams, fmt.Sprintf("%s=%s",
			percentEncode(k), percentEncode(params[k])))
	}

	stringToSign := "GET&%2F&" + percentEncode(strings.Join(sortedParams, "&"))

	// 3. 计算签名
	mac := hmac.New(sha1.New, []byte(p.config.AccessKeySecret+"&"))
	mac.Write([]byte(stringToSign))
	signature := base64.StdEncoding.EncodeToString(mac.Sum(nil))

	return signature
}

// sendRequest 发送请求
func (p *AliyunProvider) sendRequest(params map[string]string) error {
	// 构建URL
	reqURL := p.config.Endpoint + "/?" + buildQueryString(params)

	// 发送GET请求
	resp, err := p.client.Get(reqURL)
	if err != nil {
		return fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	// 读取响应
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("read response: %w", err)
	}

	// 解析响应
	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		return fmt.Errorf("parse response: %w", err)
	}

	// 检查是否成功
	if code, ok := result["Code"].(string); ok && code != "OK" {
		message := result["Message"].(string)
		return fmt.Errorf("aliyun error: %s - %s", code, message)
	}

	return nil
}

// percentEncode URL编码
func percentEncode(s string) string {
	s = url.QueryEscape(s)
	s = strings.ReplaceAll(s, "+", "%20")
	s = strings.ReplaceAll(s, "*", "%2A")
	s = strings.ReplaceAll(s, "%7E", "~")
	return s
}

// buildQueryString 构建查询字符串
func buildQueryString(params map[string]string) string {
	var parts []string
	for k, v := range params {
		parts = append(parts, fmt.Sprintf("%s=%s", url.QueryEscape(k), url.QueryEscape(v)))
	}
	return strings.Join(parts, "&")
}

// generateNonce 生成随机数
func generateNonce() string {
	return fmt.Sprintf("%d", time.Now().UnixNano())
}

// generateTimestamp 生成时间戳
func generateTimestamp() string {
	return time.Now().UTC().Format("2006-01-02T15:04:05Z")
}

// SendBulkSMS 批量发送短信
func (p *AliyunProvider) SendBulkSMS(phones []string, content string) error {
	for _, phone := range phones {
		if err := p.SendSMS(phone, content); err != nil {
			// 记录错误但继续发送其他短信
			// logger.Errorf("Failed to send SMS to %s: %v", phone, err)
		}
	}
	return nil
}
