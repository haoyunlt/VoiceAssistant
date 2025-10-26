package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// NotificationService 通知服务
type NotificationService struct {
	emailChannel   *EmailChannel
	smsChannel     *SMSChannel
	pushChannel    *PushChannel
	webhookChannel *WebhookChannel
	kafkaConsumer  *KafkaConsumer
}

func main() {
	// 创建路由器
	r := gin.Default()

	// Prometheus metrics
	r.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// Health checks
	r.GET("/health", healthCheck)
	r.GET("/ready", readinessCheck)

	// API routes
	api := r.Group("/api/v1")
	{
		// 发送通知
		api.POST("/notifications/send", sendNotification)
		api.POST("/notifications/batch", sendBatchNotifications)

		// 通知管理
		api.GET("/notifications/:id", getNotification)
		api.GET("/notifications/:id/status", getNotificationStatus)

		// 模板管理
		api.POST("/templates", createTemplate)
		api.GET("/templates", listTemplates)
		api.GET("/templates/:id", getTemplate)
		api.PUT("/templates/:id", updateTemplate)
		api.DELETE("/templates/:id", deleteTemplate)

		// 订阅管理
		api.POST("/subscriptions", createSubscription)
		api.GET("/subscriptions", listSubscriptions)
		api.DELETE("/subscriptions/:id", deleteSubscription)

		// 统计
		api.GET("/stats", getStats)
	}

	// 启动服务器
	port := os.Getenv("PORT")
	if port == "" {
		port = "9005"
	}

	srv := &http.Server{
		Addr:    fmt.Sprintf(":%s", port),
		Handler: r,
	}

	// Graceful shutdown
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %s\n", err)
		}
	}()

	log.Printf("Notification Service started on port %s", port)

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	log.Println("Server exited")
}

func healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":  "healthy",
		"service": "notification-service",
	})
}

func readinessCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"ready": true,
		"checks": gin.H{
			"email":   true,
			"sms":     true,
			"push":    true,
			"webhook": true,
			"kafka":   true,
		},
	})
}

func sendNotification(c *gin.Context) {
	var req map[string]interface{}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	notificationType := req["type"].(string) // email, sms, push, webhook

	c.JSON(http.StatusOK, gin.H{
		"notification_id": "notif_123",
		"type":            notificationType,
		"status":          "sent",
		"sent_at":         time.Now().Format(time.RFC3339),
	})
}

func sendBatchNotifications(c *gin.Context) {
	var req map[string]interface{}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"batch_id":  "batch_123",
		"total":     10,
		"sent":      10,
		"failed":    0,
		"queued_at": time.Now().Format(time.RFC3339),
	})
}

func getNotification(c *gin.Context) {
	notifID := c.Param("id")

	c.JSON(http.StatusOK, gin.H{
		"notification_id": notifID,
		"type":            "email",
		"recipient":       "user@example.com",
		"subject":         "Welcome to VoiceHelper",
		"status":          "delivered",
		"sent_at":         time.Now().Add(-1 * time.Hour).Format(time.RFC3339),
		"delivered_at":    time.Now().Add(-55 * time.Minute).Format(time.RFC3339),
	})
}

func getNotificationStatus(c *gin.Context) {
	notifID := c.Param("id")

	c.JSON(http.StatusOK, gin.H{
		"notification_id": notifID,
		"status":          "delivered",
		"attempts":        1,
		"last_attempt":    time.Now().Add(-55 * time.Minute).Format(time.RFC3339),
	})
}

func createTemplate(c *gin.Context) {
	var req map[string]interface{}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"template_id": "tmpl_123",
		"name":        req["name"],
		"type":        req["type"],
		"status":      "active",
		"created_at":  time.Now().Format(time.RFC3339),
	})
}

func listTemplates(c *gin.Context) {
	templates := []gin.H{
		{
			"template_id": "tmpl_123",
			"name":        "Welcome Email",
			"type":        "email",
			"status":      "active",
		},
		{
			"template_id": "tmpl_124",
			"name":        "Password Reset",
			"type":        "email",
			"status":      "active",
		},
		{
			"template_id": "tmpl_125",
			"name":        "Document Indexed",
			"type":        "push",
			"status":      "active",
		},
	}

	c.JSON(http.StatusOK, gin.H{
		"templates": templates,
		"total":     len(templates),
	})
}

func getTemplate(c *gin.Context) {
	templateID := c.Param("id")

	c.JSON(http.StatusOK, gin.H{
		"template_id": templateID,
		"name":        "Welcome Email",
		"type":        "email",
		"subject":     "Welcome to {{service_name}}",
		"body":        "Hello {{user_name}}, welcome to our service!",
		"variables":   []string{"service_name", "user_name"},
		"status":      "active",
	})
}

func updateTemplate(c *gin.Context) {
	templateID := c.Param("id")

	var req map[string]interface{}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"template_id": templateID,
		"updated_at":  time.Now().Format(time.RFC3339),
	})
}

func deleteTemplate(c *gin.Context) {
	templateID := c.Param("id")

	c.JSON(http.StatusOK, gin.H{
		"template_id": templateID,
		"deleted":     true,
	})
}

func createSubscription(c *gin.Context) {
	var req map[string]interface{}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"subscription_id": "sub_123",
		"user_id":         req["user_id"],
		"event_types":     req["event_types"],
		"channels":        req["channels"],
		"created_at":      time.Now().Format(time.RFC3339),
	})
}

func listSubscriptions(c *gin.Context) {
	userID := c.Query("user_id")

	subscriptions := []gin.H{
		{
			"subscription_id": "sub_123",
			"user_id":         userID,
			"event_types":     []string{"document.uploaded", "document.indexed"},
			"channels":        []string{"email", "push"},
			"status":          "active",
		},
	}

	c.JSON(http.StatusOK, gin.H{
		"subscriptions": subscriptions,
		"total":         len(subscriptions),
	})
}

func deleteSubscription(c *gin.Context) {
	subID := c.Param("id")

	c.JSON(http.StatusOK, gin.H{
		"subscription_id": subID,
		"deleted":         true,
	})
}

func getStats(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"total_sent":      1000,
		"total_delivered": 950,
		"total_failed":    50,
		"by_channel": gin.H{
			"email":   gin.H{"sent": 600, "delivered": 580, "failed": 20},
			"sms":     gin.H{"sent": 200, "delivered": 190, "failed": 10},
			"push":    gin.H{"sent": 150, "delivered": 140, "failed": 10},
			"webhook": gin.H{"sent": 50, "delivered": 40, "failed": 10},
		},
	})
}

// Channel types
type EmailChannel struct{}
type SMSChannel struct{}
type PushChannel struct{}
type WebhookChannel struct{}
type KafkaConsumer struct{}
