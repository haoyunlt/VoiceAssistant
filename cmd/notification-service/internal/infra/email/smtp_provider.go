package email

import (
	"crypto/tls"
	"fmt"
	"net/smtp"
)

// SMTPConfig SMTP配置
type SMTPConfig struct {
	Host     string
	Port     int
	Username string
	Password string
	From     string
	UseTLS   bool
}

// SMTPProvider SMTP邮件提供商
type SMTPProvider struct {
	config *SMTPConfig
}

// NewSMTPProvider 创建SMTP提供商
func NewSMTPProvider(config *SMTPConfig) *SMTPProvider {
	return &SMTPProvider{
		config: config,
	}
}

// SendEmail 发送邮件
func (p *SMTPProvider) SendEmail(to, subject, body string) error {
	// 构建邮件内容
	message := p.buildMessage(to, subject, body)

	// 连接SMTP服务器
	addr := fmt.Sprintf("%s:%d", p.config.Host, p.config.Port)

	// 认证
	auth := smtp.PlainAuth(
		"",
		p.config.Username,
		p.config.Password,
		p.config.Host,
	)

	// 发送
	if p.config.UseTLS {
		return p.sendWithTLS(addr, auth, to, message)
	}

	return smtp.SendMail(
		addr,
		auth,
		p.config.From,
		[]string{to},
		[]byte(message),
	)
}

// sendWithTLS 使用TLS发送
func (p *SMTPProvider) sendWithTLS(addr string, auth smtp.Auth, to string, message string) error {
	// 创建TLS配置
	tlsConfig := &tls.Config{
		ServerName: p.config.Host,
	}

	// 连接
	conn, err := tls.Dial("tcp", addr, tlsConfig)
	if err != nil {
		return fmt.Errorf("tls dial: %w", err)
	}
	defer conn.Close()

	// 创建SMTP客户端
	client, err := smtp.NewClient(conn, p.config.Host)
	if err != nil {
		return fmt.Errorf("create smtp client: %w", err)
	}
	defer client.Quit()

	// 认证
	if err := client.Auth(auth); err != nil {
		return fmt.Errorf("auth: %w", err)
	}

	// 设置发件人
	if err := client.Mail(p.config.From); err != nil {
		return fmt.Errorf("set from: %w", err)
	}

	// 设置收件人
	if err := client.Rcpt(to); err != nil {
		return fmt.Errorf("set to: %w", err)
	}

	// 发送邮件内容
	writer, err := client.Data()
	if err != nil {
		return fmt.Errorf("get writer: %w", err)
	}
	defer writer.Close()

	_, err = writer.Write([]byte(message))
	if err != nil {
		return fmt.Errorf("write message: %w", err)
	}

	return nil
}

// buildMessage 构建邮件消息
func (p *SMTPProvider) buildMessage(to, subject, body string) string {
	headers := make(map[string]string)
	headers["From"] = p.config.From
	headers["To"] = to
	headers["Subject"] = subject
	headers["MIME-Version"] = "1.0"
	headers["Content-Type"] = "text/html; charset=UTF-8"

	message := ""
	for k, v := range headers {
		message += fmt.Sprintf("%s: %s\r\n", k, v)
	}
	message += "\r\n" + body

	return message
}

// SendBulkEmail 批量发送邮件
func (p *SMTPProvider) SendBulkEmail(recipients []string, subject, body string) error {
	for _, to := range recipients {
		if err := p.SendEmail(to, subject, body); err != nil {
			// 记录错误但继续发送其他邮件
			// logger.Errorf("Failed to send email to %s: %v", to, err)
		}
	}
	return nil
}
