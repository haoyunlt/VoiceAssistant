package data

import (
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"

	"voiceassistant/cmd/knowledge-service/internal/domain"
)

type collectionRepo struct {
	db *gorm.DB
}

func NewCollectionRepository(db *gorm.DB) domain.CollectionRepository {
	return &collectionRepo{db: db}
}

func (r *collectionRepo) Create(coll *domain.Collection) error {
	if coll.ID == "" {
		coll.ID = "coll_" + uuid.New().String()
	}
	coll.CreatedAt = time.Now()
	coll.UpdatedAt = time.Now()
	coll.DocumentCount = 0

	return r.db.Create(coll).Error
}

func (r *collectionRepo) GetByID(id string) (*domain.Collection, error) {
	var coll domain.Collection
	err := r.db.Where("id = ?", id).First(&coll).Error
	if err != nil {
		return nil, err
	}
	return &coll, nil
}

func (r *collectionRepo) Update(coll *domain.Collection) error {
	coll.UpdatedAt = time.Now()
	return r.db.Save(coll).Error
}

func (r *collectionRepo) Delete(id string) error {
	return r.db.Where("id = ?", id).Delete(&domain.Collection{}).Error
}

func (r *collectionRepo) List(userID, tenantID string, collectionType *domain.CollectionType, page, pageSize int) ([]*domain.Collection, int, error) {
	var colls []*domain.Collection
	var total int64

	query := r.db.Model(&domain.Collection{})

	if userID != "" {
		query = query.Where("user_id = ?", userID)
	}
	if tenantID != "" {
		query = query.Where("tenant_id = ?", tenantID)
	}
	if collectionType != nil {
		query = query.Where("type = ?", *collectionType)
	}

	// Count total
	if err := query.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	// Pagination
	offset := (page - 1) * pageSize
	if err := query.Offset(offset).Limit(pageSize).Order("updated_at DESC").Find(&colls).Error; err != nil {
		return nil, 0, err
	}

	return colls, int(total), nil
}

func (r *collectionRepo) IncrementDocumentCount(id string, delta int) error {
	return r.db.Model(&domain.Collection{}).
		Where("id = ?", id).
		UpdateColumn("document_count", gorm.Expr("document_count + ?", delta)).Error
}
