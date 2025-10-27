package senders

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"voiceassistant/cmd/notification-service/internal/domain"
)

type WebhookSender struct {
	client *http.Client
}

func NewWebhookSender() *WebhookSender {
	return &WebhookSender{
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

func (s *WebhookSender) Send(notification *domain.Notification) error {
	webhookURL := notification.Recipient

	// Build payload
	payload := map[string]interface{}{
		"notification_id": notification.ID,
		"event_type":      notification.EventType,
		"title":           notification.Title,
		"content":         notification.Content,
		"data":            notification.Data,
		"timestamp":       notification.CreatedAt,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	// Send webhook
	req, err := http.NewRequest("POST", webhookURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "VoiceAssistant-Notification/1.0")

	resp, err := s.client.Do(req)
	if err != nil {
		log.Printf("Failed to send webhook: %v", err)
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("webhook returned status: %d", resp.StatusCode)
	}

	log.Printf("Webhook sent successfully to: %s", webhookURL)
	return nil
}

