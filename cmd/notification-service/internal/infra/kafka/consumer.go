package kafka

import (
	"context"
	"encoding/json"
	"log"

	"github.com/segmentio/kafka-go"

	"voicehelper/cmd/notification-service/internal/biz"
)

type Consumer struct {
	reader              *kafka.Reader
	notificationUsecase *biz.NotificationUsecase
}

func NewConsumer(brokers []string, topics []string, groupID string, uc *biz.NotificationUsecase) *Consumer {
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers: brokers,
		GroupID: groupID,
		Topic:   topics[0], // 简化处理，只订阅一个 topic
	})

	return &Consumer{
		reader:              reader,
		notificationUsecase: uc,
	}
}

func (c *Consumer) Start(ctx context.Context) error {
	log.Println("Starting Kafka consumer...")

	for {
		select {
		case <-ctx.Done():
			log.Println("Stopping Kafka consumer...")
			return c.reader.Close()
		default:
			message, err := c.reader.FetchMessage(ctx)
			if err != nil {
				log.Printf("Error fetching message: %v", err)
				continue
			}

			// Process message
			if err := c.processMessage(ctx, message); err != nil {
				log.Printf("Error processing message: %v", err)
				// Don't commit if processing failed
				continue
			}

			// Commit message
			if err := c.reader.CommitMessages(ctx, message); err != nil {
				log.Printf("Error committing message: %v", err)
			}
		}
	}
}

func (c *Consumer) processMessage(ctx context.Context, message kafka.Message) error {
	// Parse event
	var event map[string]interface{}
	if err := json.Unmarshal(message.Value, &event); err != nil {
		return err
	}

	eventType, ok := event["event_type"].(string)
	if !ok {
		log.Println("Missing event_type in message")
		return nil
	}

	log.Printf("Processing event: %s", eventType)

	// Route to appropriate handler
	switch eventType {
	case "conversation.message.sent":
		return c.handleMessageSent(ctx, event)
	case "conversation.created":
		return c.handleConversationCreated(ctx, event)
	case "document.uploaded":
		return c.handleDocumentUploaded(ctx, event)
	case "document.indexed":
		return c.handleDocumentIndexed(ctx, event)
	case "user.registered":
		return c.handleUserRegistered(ctx, event)
	default:
		log.Printf("Unknown event type: %s", eventType)
	}

	return nil
}

func (c *Consumer) handleMessageSent(ctx context.Context, event map[string]interface{}) error {
	userID, _ := event["user_id"].(string)
	tenantID, _ := event["tenant_id"].(string)
	content, _ := event["content"].(string)

	// Send notification
	return c.notificationUsecase.SendNotification(ctx, &biz.SendNotificationRequest{
		UserID:    userID,
		TenantID:  tenantID,
		Type:      "in_app",
		Title:     "New Message",
		Content:   content,
		EventType: "conversation.message.sent",
		EventID:   event["event_id"].(string),
	})
}

func (c *Consumer) handleConversationCreated(ctx context.Context, event map[string]interface{}) error {
	userID, _ := event["user_id"].(string)
	tenantID, _ := event["tenant_id"].(string)
	title, _ := event["title"].(string)

	return c.notificationUsecase.SendNotification(ctx, &biz.SendNotificationRequest{
		UserID:    userID,
		TenantID:  tenantID,
		Type:      "in_app",
		Title:     "Conversation Created",
		Content:   "New conversation: " + title,
		EventType: "conversation.created",
		EventID:   event["event_id"].(string),
	})
}

func (c *Consumer) handleDocumentUploaded(ctx context.Context, event map[string]interface{}) error {
	userID, _ := event["user_id"].(string)
	tenantID, _ := event["tenant_id"].(string)
	documentName, _ := event["name"].(string)

	return c.notificationUsecase.SendNotification(ctx, &biz.SendNotificationRequest{
		UserID:    userID,
		TenantID:  tenantID,
		Type:      "email",
		Title:     "Document Uploaded",
		Content:   "Your document '" + documentName + "' has been uploaded successfully.",
		EventType: "document.uploaded",
		EventID:   event["event_id"].(string),
	})
}

func (c *Consumer) handleDocumentIndexed(ctx context.Context, event map[string]interface{}) error {
	// Get user info from document
	documentID, _ := event["document_id"].(string)

	// In production, fetch user from document service
	// For now, log it
	log.Printf("Document indexed: %s", documentID)

	return nil
}

func (c *Consumer) handleUserRegistered(ctx context.Context, event map[string]interface{}) error {
	userID, _ := event["user_id"].(string)
	email, _ := event["email"].(string)

	return c.notificationUsecase.SendNotification(ctx, &biz.SendNotificationRequest{
		UserID:    userID,
		Type:      "email",
		Recipient: email,
		Title:     "Welcome to VoiceHelper",
		Content:   "Thank you for registering!",
		EventType: "user.registered",
		EventID:   event["event_id"].(string),
	})
}
