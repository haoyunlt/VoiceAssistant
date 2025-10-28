package senders

import (
	"fmt"
	"log"
	"net/smtp"

	"voicehelper/cmd/notification-service/internal/domain"
)

type EmailSender struct {
	smtpHost     string
	smtpPort     string
	smtpUser     string
	smtpPassword string
	fromEmail    string
}

func NewEmailSender(host, port, user, password, from string) *EmailSender {
	return &EmailSender{
		smtpHost:     host,
		smtpPort:     port,
		smtpUser:     user,
		smtpPassword: password,
		fromEmail:    from,
	}
}

func (s *EmailSender) Send(notification *domain.Notification) error {
	// Build email
	to := notification.Recipient
	subject := notification.Title
	body := notification.Content

	message := fmt.Sprintf("From: %s\r\n", s.fromEmail)
	message += fmt.Sprintf("To: %s\r\n", to)
	message += fmt.Sprintf("Subject: %s\r\n", subject)
	message += "\r\n" + body

	// Send email
	auth := smtp.PlainAuth("", s.smtpUser, s.smtpPassword, s.smtpHost)
	addr := fmt.Sprintf("%s:%s", s.smtpHost, s.smtpPort)

	err := smtp.SendMail(addr, auth, s.fromEmail, []string{to}, []byte(message))
	if err != nil {
		log.Printf("Failed to send email: %v", err)
		return err
	}

	log.Printf("Email sent successfully to: %s", to)
	return nil
}

