package infra

import (
	"context"
	"fmt"
	"voiceassistant/cmd/notification-service/internal/biz"

	"github.com/go-kratos/kratos/v2/log"
)

// MockEmailProvider implements EmailProvider interface for development
type MockEmailProvider struct {
	log *log.Helper
}

// NewEmailProvider creates a new email provider
func NewEmailProvider(logger log.Logger) biz.EmailProvider {
	return &MockEmailProvider{
		log: log.NewHelper(logger),
	}
}

// SendEmail sends an email
func (p *MockEmailProvider) SendEmail(ctx context.Context, to, subject, body string) error {
	p.log.WithContext(ctx).Infof("sending email to %s: %s", to, subject)
	// TODO: implement real email sending logic (SMTP, SendGrid, AWS SES, etc.)
	return nil
}

// MockSMSProvider implements SMSProvider interface for development
type MockSMSProvider struct {
	log *log.Helper
}

// NewSMSProvider creates a new SMS provider
func NewSMSProvider(logger log.Logger) biz.SMSProvider {
	return &MockSMSProvider{
		log: log.NewHelper(logger),
	}
}

// SendSMS sends an SMS
func (p *MockSMSProvider) SendSMS(ctx context.Context, to, content string) error {
	p.log.WithContext(ctx).Infof("sending SMS to %s: %s", to, content)
	// TODO: implement real SMS sending logic (Twilio, Aliyun, etc.)
	return nil
}

// MockWebSocketManager implements WebSocketManager interface for development
type MockWebSocketManager struct {
	log *log.Helper
}

// NewWebSocketManager creates a new WebSocket manager
func NewWebSocketManager(logger log.Logger) biz.WebSocketManager {
	return &MockWebSocketManager{
		log: log.NewHelper(logger),
	}
}

// SendToUser sends a message to a specific user
func (m *MockWebSocketManager) SendToUser(ctx context.Context, userID string, message interface{}) error {
	m.log.WithContext(ctx).Infof("sending websocket message to user %s: %v", userID, message)
	// TODO: implement real WebSocket message sending
	return nil
}

// BroadcastToTenant broadcasts a message to all users in a tenant
func (m *MockWebSocketManager) BroadcastToTenant(ctx context.Context, tenantID string, message interface{}) error {
	m.log.WithContext(ctx).Infof("broadcasting websocket message to tenant %s: %v", tenantID, message)
	// TODO: implement real WebSocket broadcasting
	return nil
}

// MetricsCollector collects notification metrics
type MetricsCollector struct {
	log *log.Helper
}

// NewMetricsCollector creates a new metrics collector
func NewMetricsCollector(logger log.Logger) *MetricsCollector {
	return &MetricsCollector{
		log: log.NewHelper(logger),
	}
}

// RecordNotificationSent records a notification sent event
func (m *MetricsCollector) RecordNotificationSent(channel, status string) {
	m.log.Infof("notification sent: channel=%s status=%s", channel, status)
	// TODO: implement Prometheus metrics
}

// HealthChecker checks the health of external dependencies
type HealthChecker struct {
	log *log.Helper
}

// NewHealthChecker creates a new health checker
func NewHealthChecker(logger log.Logger) *HealthChecker {
	return &HealthChecker{
		log: log.NewHelper(logger),
	}
}

// CheckEmail checks if email service is healthy
func (h *HealthChecker) CheckEmail() error {
	// TODO: implement real health check
	return nil
}

// CheckSMS checks if SMS service is healthy
func (h *HealthChecker) CheckSMS() error {
	// TODO: implement real health check
	return nil
}

// CheckWebSocket checks if WebSocket service is healthy
func (h *HealthChecker) CheckWebSocket() error {
	// TODO: implement real health check
	return nil
}

// CheckAll checks all services
func (h *HealthChecker) CheckAll() error {
	if err := h.CheckEmail(); err != nil {
		return fmt.Errorf("email service unhealthy: %w", err)
	}
	if err := h.CheckSMS(); err != nil {
		return fmt.Errorf("SMS service unhealthy: %w", err)
	}
	if err := h.CheckWebSocket(); err != nil {
		return fmt.Errorf("WebSocket service unhealthy: %w", err)
	}
	return nil
}
