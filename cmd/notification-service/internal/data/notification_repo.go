package data

import (
	"time"

	"gorm.io/gorm"

	"voiceassistant/cmd/notification-service/internal/domain"
)

type notificationRepo struct {
	db *gorm.DB
}

func NewNotificationRepository(db *gorm.DB) domain.NotificationRepository {
	return &notificationRepo{db: db}
}

func (r *notificationRepo) Create(notification *domain.Notification) error {
	notification.CreatedAt = time.Now()
	notification.UpdatedAt = time.Now()
	return r.db.Create(notification).Error
}

func (r *notificationRepo) GetByID(id string) (*domain.Notification, error) {
	var notification domain.Notification
	err := r.db.Where("id = ?", id).First(&notification).Error
	if err != nil {
		return nil, err
	}
	return &notification, nil
}

func (r *notificationRepo) Update(notification *domain.Notification) error {
	notification.UpdatedAt = time.Now()
	return r.db.Save(notification).Error
}

func (r *notificationRepo) GetByUserID(userID string, limit, offset int) ([]*domain.Notification, error) {
	var notifications []*domain.Notification
	err := r.db.Where("user_id = ?", userID).Limit(limit).Offset(offset).Find(&notifications).Error
	return notifications, err
}

func (r *notificationRepo) GetUnreadCount(userID string) (int64, error) {
	var count int64
	err := r.db.Model(&domain.Notification{}).Where("user_id = ? AND read_at IS NULL", userID).Count(&count).Error
	return count, err
}

func (r *notificationRepo) Delete(id string) error {
	return r.db.Delete(&domain.Notification{}, "id = ?", id).Error
}

func (r *notificationRepo) List(userID, tenantID string, status *string, page, pageSize int) ([]*domain.Notification, int64, error) {
	var notifications []*domain.Notification
	var total int64

	query := r.db.Model(&domain.Notification{})

	if userID != "" {
		query = query.Where("user_id = ?", userID)
	}
	if tenantID != "" {
		query = query.Where("tenant_id = ?", tenantID)
	}
	if status != nil {
		query = query.Where("status = ?", *status)
	}

	// Count total
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	// Pagination
	offset := (page - 1) * pageSize
	if err := query.Offset(offset).Limit(pageSize).
		Order("created_at DESC").
		Find(&notifications).Error; err != nil {
		return nil, 0, err
	}

	return notifications, total, nil
}
