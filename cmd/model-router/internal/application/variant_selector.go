package application

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math/rand"

	"voicehelper/cmd/model-router/internal/domain"
)

// VariantSelector 变体选择策略接口
type VariantSelector interface {
	Select(testID, userID string, variants []*domain.ABVariant) (*domain.ABVariant, error)
}

// ConsistentHashSelector 一致性哈希选择器
type ConsistentHashSelector struct{}

// NewConsistentHashSelector 创建一致性哈希选择器
func NewConsistentHashSelector() *ConsistentHashSelector {
	return &ConsistentHashSelector{}
}

// Select 使用一致性哈希选择变体
func (s *ConsistentHashSelector) Select(testID, userID string, variants []*domain.ABVariant) (*domain.ABVariant, error) {
	if len(variants) == 0 {
		return nil, fmt.Errorf("no variants available")
	}

	// 生成哈希值
	hash := sha256.Sum256([]byte(testID + ":" + userID))
	hashStr := hex.EncodeToString(hash[:])
	_ = hashStr // 用于日志或调试

	// 转换为0-1之间的浮点数
	hashValue := float64(hash[0]) / 256.0

	// 根据权重选择变体
	cumulative := 0.0
	for _, v := range variants {
		cumulative += v.Weight
		if hashValue <= cumulative {
			return v, nil
		}
	}

	// 兜底返回最后一个
	return variants[len(variants)-1], nil
}

// WeightedRandomSelector 加权随机选择器
type WeightedRandomSelector struct {
	rand *rand.Rand
}

// NewWeightedRandomSelector 创建加权随机选择器
func NewWeightedRandomSelector() *WeightedRandomSelector {
	return &WeightedRandomSelector{
		rand: rand.New(rand.NewSource(rand.Int63())),
	}
}

// Select 使用加权随机选择变体
func (s *WeightedRandomSelector) Select(testID, userID string, variants []*domain.ABVariant) (*domain.ABVariant, error) {
	if len(variants) == 0 {
		return nil, fmt.Errorf("no variants available")
	}

	totalWeight := 0.0
	for _, v := range variants {
		totalWeight += v.Weight
	}

	r := s.rand.Float64() * totalWeight
	cumulative := 0.0

	for _, v := range variants {
		cumulative += v.Weight
		if r <= cumulative {
			return v, nil
		}
	}

	// 兜底返回最后一个
	return variants[len(variants)-1], nil
}

// GetVariantSelector 根据策略名称获取选择器
func GetVariantSelector(strategy string) VariantSelector {
	switch strategy {
	case "weighted_random":
		return NewWeightedRandomSelector()
	case "consistent_hash":
		return NewConsistentHashSelector()
	default:
		// 默认使用一致性哈希
		return NewConsistentHashSelector()
	}
}


