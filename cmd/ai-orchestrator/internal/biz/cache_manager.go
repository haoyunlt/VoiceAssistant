package biz

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"voicehelper/cmd/ai-orchestrator/internal/domain"

	"github.com/allegro/bigcache/v3"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-redis/redis/v8"
	"gorm.io/gorm"
)

// CacheManager 多层缓存管理器
type CacheManager struct {
	l1Cache *bigcache.BigCache // L1: 本地缓存（进程内）
	l2Cache *redis.Client      // L2: Redis缓存（跨实例）
	db      *gorm.DB            // L3: 数据库
	repo    domain.TaskRepository
	logger  *log.Helper
	metrics *CacheMetrics
}

// CacheMetrics 缓存指标
type CacheMetrics struct {
	L1Hits   int64 // L1命中数
	L2Hits   int64 // L2命中数
	L3Hits   int64 // L3命中数（DB查询）
	Misses   int64 // 未命中数
	L1Size   int64 // L1大小
	L2Size   int64 // L2大小
	EvictL1  int64 // L1驱逐数
	EvictL2  int64 // L2驱逐数
}

// CacheConfig 缓存配置
type CacheConfig struct {
	L1Enabled    bool          // L1启用
	L1Size       int           // L1大小（MB）
	L1TTL        time.Duration // L1 TTL
	L2Enabled    bool          // L2启用
	L2TTL        time.Duration // L2 TTL（已完成任务）
	L2TTLRunning time.Duration // L2 TTL（运行中任务，无TTL）
}

// NewCacheManager 创建缓存管理器
func NewCacheManager(
	l2Cache *redis.Client,
	db *gorm.DB,
	repo domain.TaskRepository,
	config *CacheConfig,
	logger log.Logger,
) (*CacheManager, error) {
	if config == nil {
		config = &CacheConfig{
			L1Enabled:    true,
			L1Size:       100, // 100MB
			L1TTL:        5 * time.Minute,
			L2Enabled:    true,
			L2TTL:        1 * time.Hour,
			L2TTLRunning: 0, // 无TTL（持久）
		}
	}

	manager := &CacheManager{
		l2Cache: l2Cache,
		db:      db,
		repo:    repo,
		logger:  log.NewHelper(logger),
		metrics: &CacheMetrics{},
	}

	// 初始化L1缓存（BigCache）
	if config.L1Enabled {
		l1Config := bigcache.DefaultConfig(config.L1TTL)
		l1Config.HardMaxCacheSize = config.L1Size
		l1Config.Verbose = false

		// 使用带超时的上下文初始化缓存
		initCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		l1Cache, err := bigcache.New(initCtx, l1Config)
		if err != nil {
			return nil, fmt.Errorf("failed to create L1 cache: %w", err)
		}
		manager.l1Cache = l1Cache
	}

	return manager, nil
}

// GetTask 获取任务（三层缓存）
func (m *CacheManager) GetTask(ctx context.Context, taskID string) (*domain.Task, error) {
	// L1 查询
	if m.l1Cache != nil {
		if task, err := m.getFromL1(taskID); err == nil {
			m.metrics.L1Hits++
			m.logger.Debugf("L1 cache hit: %s", taskID)
			return task, nil
		}
	}

	// L2 查询
	if m.l2Cache != nil {
		if task, err := m.getFromL2(ctx, taskID); err == nil {
			m.metrics.L2Hits++
			m.logger.Debugf("L2 cache hit: %s", taskID)

			// 回写L1
			if m.l1Cache != nil {
				m.setToL1(taskID, task)
			}
			return task, nil
		}
	}

	// L3 查询（数据库）
	task, err := m.repo.GetByID(ctx, taskID)
	if err != nil {
		m.metrics.Misses++
		return nil, err
	}

	m.metrics.L3Hits++
	m.logger.Debugf("L3 cache hit (DB): %s", taskID)

	// 回写缓存
	if task.IsCompleted() {
		// 已完成任务，缓存到L1和L2
		if m.l2Cache != nil {
			m.setToL2(ctx, taskID, task, 1*time.Hour)
		}
		if m.l1Cache != nil {
			m.setToL1(taskID, task)
		}
	} else {
		// 运行中任务，只缓存到L2（无TTL）
		if m.l2Cache != nil {
			m.setToL2(ctx, taskID, task, 0)
		}
	}

	return task, nil
}

// SetTask 设置任务缓存
func (m *CacheManager) SetTask(ctx context.Context, task *domain.Task) error {
	// 根据任务状态决定缓存策略
	if task.IsCompleted() {
		// 已完成任务：L1 + L2
		if m.l1Cache != nil {
			m.setToL1(task.ID, task)
		}
		if m.l2Cache != nil {
			m.setToL2(ctx, task.ID, task, 1*time.Hour)
		}
	} else {
		// 运行中任务：仅L2（无TTL）
		if m.l2Cache != nil {
			m.setToL2(ctx, task.ID, task, 0)
		}
	}

	return nil
}

// InvalidateTask 失效任务缓存
func (m *CacheManager) InvalidateTask(ctx context.Context, taskID string) error {
	// 从L1删除
	if m.l1Cache != nil {
		m.l1Cache.Delete(taskID)
	}

	// 从L2删除
	if m.l2Cache != nil {
		m.l2Cache.Del(ctx, m.buildL2Key(taskID))
	}

	m.logger.Infof("invalidated cache for task: %s", taskID)
	return nil
}

// getFromL1 从L1获取
func (m *CacheManager) getFromL1(taskID string) (*domain.Task, error) {
	data, err := m.l1Cache.Get(taskID)
	if err != nil {
		return nil, err
	}

	var task domain.Task
	if err := json.Unmarshal(data, &task); err != nil {
		return nil, err
	}

	return &task, nil
}

// setToL1 写入L1
func (m *CacheManager) setToL1(taskID string, task *domain.Task) {
	data, err := json.Marshal(task)
	if err != nil {
		m.logger.Warnf("failed to marshal task for L1: %v", err)
		return
	}

	if err := m.l1Cache.Set(taskID, data); err != nil {
		m.logger.Warnf("failed to set L1 cache: %v", err)
	}
}

// getFromL2 从L2获取
func (m *CacheManager) getFromL2(ctx context.Context, taskID string) (*domain.Task, error) {
	key := m.buildL2Key(taskID)
	data, err := m.l2Cache.Get(ctx, key).Result()
	if err != nil {
		return nil, err
	}

	var task domain.Task
	if err := json.Unmarshal([]byte(data), &task); err != nil {
		return nil, err
	}

	return &task, nil
}

// setToL2 写入L2
func (m *CacheManager) setToL2(ctx context.Context, taskID string, task *domain.Task, ttl time.Duration) {
	key := m.buildL2Key(taskID)
	data, err := json.Marshal(task)
	if err != nil {
		m.logger.Warnf("failed to marshal task for L2: %v", err)
		return
	}

	if err := m.l2Cache.Set(ctx, key, string(data), ttl).Err(); err != nil {
		m.logger.Warnf("failed to set L2 cache: %v", err)
	}
}

// buildL2Key 构建L2键
func (m *CacheManager) buildL2Key(taskID string) string {
	return fmt.Sprintf("task:%s", taskID)
}

// GetMetrics 获取缓存指标
func (m *CacheManager) GetMetrics() *CacheMetrics {
	// 更新L1大小
	if m.l1Cache != nil {
		stats := m.l1Cache.Stats()
		m.metrics.L1Size = int64(stats.Capacity)
	}

	return m.metrics
}

// GetHitRate 获取缓存命中率
func (m *CacheManager) GetHitRate() float64 {
	total := m.metrics.L1Hits + m.metrics.L2Hits + m.metrics.L3Hits + m.metrics.Misses
	if total == 0 {
		return 0
	}

	hits := m.metrics.L1Hits + m.metrics.L2Hits
	return float64(hits) / float64(total)
}

// WarmUp 预热缓存
func (m *CacheManager) WarmUp(ctx context.Context, taskIDs []string) error {
	m.logger.Infof("warming up cache with %d tasks", len(taskIDs))

	for _, taskID := range taskIDs {
		task, err := m.repo.GetByID(ctx, taskID)
		if err != nil {
			m.logger.Warnf("failed to warm up task %s: %v", taskID, err)
			continue
		}

		// 写入缓存
		m.SetTask(ctx, task)
	}

	m.logger.Info("cache warm-up completed")
	return nil
}

// Close 关闭缓存
func (m *CacheManager) Close() error {
	if m.l1Cache != nil {
		return m.l1Cache.Close()
	}
	return nil
}
