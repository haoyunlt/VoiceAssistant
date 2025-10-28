package data

import (
	"context"
	"time"

	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/gorm"

	"voicehelper/cmd/notification-service/internal/domain"
)

type notificationRepo struct {
	db  *gorm.DB
	log *log.Helper
}

// NewNotificationRepository creates a new notification repository
func NewNotificationRepository(data *Data, logger log.Logger) domain.NotificationRepository {
	return &notificationRepo{
		db:  data.db,
		log: log.NewHelper(logger),
	}
}

// Create creates a new notification
func (r *notificationRepo) Create(ctx context.Context, notification *domain.Notification) error {
	notification.CreatedAt = time.Now()
	notification.UpdatedAt = time.Now()
	
	if err := r.db.WithContext(ctx).Create(notification).Error; err != nil {
		r.log.WithContext(ctx).Errorf("failed to create notification: %v", err)
		return err
	}
	return nil
}

// Update updates a notification
func (r *notificationRepo) Update(ctx context.Context, notification *domain.Notification) error {
	notification.UpdatedAt = time.Now()
	
	if err := r.db.WithContext(ctx).Save(notification).Error; err != nil {
		r.log.WithContext(ctx).Errorf("failed to update notification: %v", err)
		return err
	}
	return nil
}

// GetByID gets a notification by ID
func (r *notificationRepo) GetByID(ctx context.Context, id string) (*domain.Notification, error) {
	var notification domain.Notification
	
	err := r.db.WithContext(ctx).Where("id = ?", id).First(&notification).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		r.log.WithContext(ctx).Errorf("failed to get notification by ID: %v", err)
		return nil, err
	}
	return &notification, nil
}

// GetByUserID gets notifications by user ID
func (r *notificationRepo) GetByUserID(ctx context.Context, userID string, limit, offset int) ([]*domain.Notification, error) {
	var notifications []*domain.Notification
	
	err := r.db.WithContext(ctx).
		Where("user_id = ?", userID).
		Order("created_at DESC").
		Limit(limit).
		Offset(offset).
		Find(&notifications).Error
	
	if err != nil {
		r.log.WithContext(ctx).Errorf("failed to get notifications by user ID: %v", err)
		return nil, err
	}
	return notifications, nil
}

// GetUnreadCount gets the count of unread notifications for a user
func (r *notificationRepo) GetUnreadCount(ctx context.Context, userID string) (int64, error) {
	var count int64
	
	err := r.db.WithContext(ctx).
		Model(&domain.Notification{}).
		Where("user_id = ? AND read_at IS NULL", userID).
		Count(&count).Error
	
	if err != nil {
		r.log.WithContext(ctx).Errorf("failed to get unread count: %v", err)
		return 0, err
	}
	return count, nil
}

// Delete deletes a notification
func (r *notificationRepo) Delete(ctx context.Context, id string) error {
	err := r.db.WithContext(ctx).Delete(&domain.Notification{}, "id = ?", id).Error
	if err != nil {
		r.log.WithContext(ctx).Errorf("failed to delete notification: %v", err)
		return err
	}
	return nil
}

// List lists notifications with filters and pagination
func (r *notificationRepo) List(
	ctx context.Context,
	userID, tenantID string,
	status *domain.NotificationStatus,
	page, pageSize int,
) ([]*domain.Notification, int64, error) {
	var notifications []*domain.Notification
	var total int64

	query := r.db.WithContext(ctx).Model(&domain.Notification{})

	// Apply filters
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
		r.log.WithContext(ctx).Errorf("failed to count notifications: %v", err)
		return nil, 0, err
	}

	// Pagination
	offset := (page - 1) * pageSize
	if err := query.
		Offset(offset).
		Limit(pageSize).
		Order("created_at DESC").
		Find(&notifications).Error; err != nil {
		r.log.WithContext(ctx).Errorf("failed to list notifications: %v", err)
		return nil, 0, err
	}

	return notifications, total, nil
}
