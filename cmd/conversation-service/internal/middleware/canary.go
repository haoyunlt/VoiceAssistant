package middleware

import (
	"crypto/md5"
	"fmt"
	"math/rand"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-kratos/kratos/v2/log"
)

// CanaryMiddleware 灰度发布中间件
type CanaryMiddleware struct {
	config *CanaryConfig
	logger *log.Helper
	mu     sync.RWMutex
}

// CanaryConfig 灰度发布配置
type CanaryConfig struct {
	Enabled           bool                   `json:"enabled"`            // 是否启用灰度
	CanaryVersion     string                 `json:"canary_version"`     // 灰度版本号
	StableVersion     string                 `json:"stable_version"`     // 稳定版本号
	TrafficPercent    int                    `json:"traffic_percent"`    // 灰度流量百分比 (0-100)
	Rules             []*CanaryRule          `json:"rules"`              // 灰度规则
	HeaderName        string                 `json:"header_name"`        // 版本选择 Header 名称
	WhitelistUserIDs  []string               `json:"whitelist_user_ids"` // 白名单用户
	BlacklistUserIDs  []string               `json:"blacklist_user_ids"` // 黑名单用户
	CanaryUpstream    string                 `json:"canary_upstream"`    // 灰度上游服务地址
	StableUpstream    string                 `json:"stable_upstream"`    // 稳定上游服务地址
	StickySession     bool                   `json:"sticky_session"`     // 是否启用粘性会话
	StickyTTL         time.Duration          `json:"sticky_ttl"`         // 粘性会话 TTL
	stickyCache       map[string]string      // 用户粘性会话缓存
}

// CanaryRule 灰度规则
type CanaryRule struct {
	Name        string            `json:"name"`         // 规则名称
	Type        string            `json:"type"`         // 规则类型: header, query, cookie, user_id, random
	Key         string            `json:"key"`          // 匹配键
	Value       string            `json:"value"`        // 匹配值
	Operator    string            `json:"operator"`     // 操作符: eq, ne, contains, prefix, suffix, regex
	Version     string            `json:"version"`      // 匹配后路由到的版本
	Priority    int               `json:"priority"`     // 优先级（越大越优先）
}

// NewCanaryMiddleware 创建灰度发布中间件
func NewCanaryMiddleware(config *CanaryConfig, logger log.Logger) gin.HandlerFunc {
	if config == nil {
		config = &CanaryConfig{
			Enabled:        false,
			CanaryVersion:  "v2",
			StableVersion:  "v1",
			TrafficPercent: 10,
			HeaderName:     "X-Canary-Version",
			StickySession:  true,
			StickyTTL:      24 * time.Hour,
			stickyCache:    make(map[string]string),
		}
	}

	cm := &CanaryMiddleware{
		config: config,
		logger: log.NewHelper(log.With(logger, "module", "canary-middleware")),
	}

	return cm.Handle()
}

// Handle 处理灰度路由
func (cm *CanaryMiddleware) Handle() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 如果未启用灰度，直接通过
		if !cm.config.Enabled {
			c.Next()
			return
		}

		// 1. 检查显式版本选择 Header
		if version := c.GetHeader(cm.config.HeaderName); version != "" {
			cm.routeToVersion(c, version)
			c.Next()
			return
		}

		// 2. 获取用户 ID（从 JWT 或其他地方）
		userID := cm.getUserID(c)

		// 3. 检查粘性会话
		if cm.config.StickySession && userID != "" {
			if version := cm.getStickyVersion(userID); version != "" {
				cm.logger.Debugf("Sticky session hit: user=%s, version=%s", userID, version)
				cm.routeToVersion(c, version)
				c.Next()
				return
			}
		}

		// 4. 检查白名单/黑名单
		if userID != "" {
			if cm.isInWhitelist(userID) {
				cm.logger.Debugf("Whitelist hit: user=%s", userID)
				version := cm.config.CanaryVersion
				cm.setStickyVersion(userID, version)
				cm.routeToVersion(c, version)
				c.Next()
				return
			}

			if cm.isInBlacklist(userID) {
				cm.logger.Debugf("Blacklist hit: user=%s", userID)
				version := cm.config.StableVersion
				cm.setStickyVersion(userID, version)
				cm.routeToVersion(c, version)
				c.Next()
				return
			}
		}

		// 5. 应用规则匹配
		if version := cm.matchRules(c, userID); version != "" {
			cm.logger.Debugf("Rule matched: version=%s", version)
			cm.setStickyVersion(userID, version)
			cm.routeToVersion(c, version)
			c.Next()
			return
		}

		// 6. 流量百分比分流
		version := cm.selectVersionByTraffic(userID)
		cm.setStickyVersion(userID, version)
		cm.routeToVersion(c, version)

		c.Next()
	}
}

// routeToVersion 路由到指定版本
func (cm *CanaryMiddleware) routeToVersion(c *gin.Context, version string) {
	// 设置响应 Header，标识实际使用的版本
	c.Header("X-Served-By-Version", version)

	// 设置上下文，供后续处理器使用
	c.Set("canary_version", version)

	// 如果配置了上游服务地址，可以在这里设置代理目标
	if version == cm.config.CanaryVersion && cm.config.CanaryUpstream != "" {
		c.Set("upstream", cm.config.CanaryUpstream)
	} else if cm.config.StableUpstream != "" {
		c.Set("upstream", cm.config.StableUpstream)
	}

	cm.logger.Debugf("Routed to version: %s, path: %s", version, c.Request.URL.Path)
}

// matchRules 匹配规则
func (cm *CanaryMiddleware) matchRules(c *gin.Context, userID string) string {
	cm.mu.RLock()
	rules := cm.config.Rules
	cm.mu.RUnlock()

	if len(rules) == 0 {
		return ""
	}

	// 按优先级排序（已假设配置时已排序）
	for _, rule := range rules {
		if cm.evaluateRule(c, userID, rule) {
			cm.logger.Debugf("Rule matched: name=%s, version=%s", rule.Name, rule.Version)
			return rule.Version
		}
	}

	return ""
}

// evaluateRule 评估规则
func (cm *CanaryMiddleware) evaluateRule(c *gin.Context, userID string, rule *CanaryRule) bool {
	var actualValue string

	switch rule.Type {
	case "header":
		actualValue = c.GetHeader(rule.Key)

	case "query":
		actualValue = c.Query(rule.Key)

	case "cookie":
		if cookie, err := c.Cookie(rule.Key); err == nil {
			actualValue = cookie
		}

	case "user_id":
		actualValue = userID

	case "random":
		// 随机规则：基于用户 ID 或请求 ID 生成确定性随机数
		seed := userID
		if seed == "" {
			seed = c.GetHeader("X-Request-ID")
		}
		if seed != "" {
			hash := md5.Sum([]byte(seed))
			percent := int(hash[0]) % 100
			if threshold, err := strconv.Atoi(rule.Value); err == nil {
				return percent < threshold
			}
		}
		return false

	default:
		return false
	}

	// 应用操作符
	return cm.applyOperator(actualValue, rule.Value, rule.Operator)
}

// applyOperator 应用操作符
func (cm *CanaryMiddleware) applyOperator(actual, expected, operator string) bool {
	switch operator {
	case "eq", "equals":
		return actual == expected

	case "ne", "not_equals":
		return actual != expected

	case "contains":
		return strings.Contains(actual, expected)

	case "prefix":
		return strings.HasPrefix(actual, expected)

	case "suffix":
		return strings.HasSuffix(actual, expected)

	case "in":
		// 期望值是逗号分隔的列表
		values := strings.Split(expected, ",")
		for _, v := range values {
			if strings.TrimSpace(v) == actual {
				return true
			}
		}
		return false

	default:
		return false
	}
}

// selectVersionByTraffic 根据流量百分比选择版本
func (cm *CanaryMiddleware) selectVersionByTraffic(userID string) string {
	cm.mu.RLock()
	trafficPercent := cm.config.TrafficPercent
	cm.mu.RUnlock()

	// 基于用户 ID 的确定性分流（如果有）
	if userID != "" {
		hash := md5.Sum([]byte(userID))
		percent := int(hash[0]) % 100

		if percent < trafficPercent {
			return cm.config.CanaryVersion
		}
		return cm.config.StableVersion
	}

	// 随机分流
	if rand.Intn(100) < trafficPercent {
		return cm.config.CanaryVersion
	}
	return cm.config.StableVersion
}

// getUserID 获取用户 ID
func (cm *CanaryMiddleware) getUserID(c *gin.Context) string {
	// 尝试从 JWT claims 中获取
	if claims, exists := c.Get("claims"); exists {
		if claimsMap, ok := claims.(map[string]interface{}); ok {
			if userID, ok := claimsMap["user_id"].(string); ok {
				return userID
			}
		}
	}

	// 尝试从 Header 获取
	if userID := c.GetHeader("X-User-ID"); userID != "" {
		return userID
	}

	return ""
}

// isInWhitelist 检查是否在白名单
func (cm *CanaryMiddleware) isInWhitelist(userID string) bool {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	for _, id := range cm.config.WhitelistUserIDs {
		if id == userID {
			return true
		}
	}
	return false
}

// isInBlacklist 检查是否在黑名单
func (cm *CanaryMiddleware) isInBlacklist(userID string) bool {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	for _, id := range cm.config.BlacklistUserIDs {
		if id == userID {
			return true
		}
	}
	return false
}

// getStickyVersion 获取粘性会话版本
func (cm *CanaryMiddleware) getStickyVersion(userID string) string {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	if cm.config.stickyCache == nil {
		return ""
	}

	return cm.config.stickyCache[userID]
}

// setStickyVersion 设置粘性会话版本
func (cm *CanaryMiddleware) setStickyVersion(userID, version string) {
	if userID == "" || version == "" {
		return
	}

	cm.mu.Lock()
	defer cm.mu.Unlock()

	if cm.config.stickyCache == nil {
		cm.config.stickyCache = make(map[string]string)
	}

	cm.config.stickyCache[userID] = version

	// 简单的 TTL 清理（生产环境应使用 Redis）
	go func() {
		time.Sleep(cm.config.StickyTTL)
		cm.mu.Lock()
		delete(cm.config.stickyCache, userID)
		cm.mu.Unlock()
	}()
}

// UpdateConfig 更新配置（支持热更新）
func (cm *CanaryMiddleware) UpdateConfig(config *CanaryConfig) {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	cm.config = config
	cm.logger.Infof("Canary config updated: enabled=%v, traffic_percent=%d",
		config.Enabled, config.TrafficPercent)
}

// GetConfig 获取当前配置
func (cm *CanaryMiddleware) GetConfig() *CanaryConfig {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	return cm.config
}

// GetStats 获取灰度统计信息
func (cm *CanaryMiddleware) GetStats() *CanaryStats {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	return &CanaryStats{
		Enabled:              cm.config.Enabled,
		CanaryVersion:        cm.config.CanaryVersion,
		StableVersion:        cm.config.StableVersion,
		TrafficPercent:       cm.config.TrafficPercent,
		WhitelistCount:       len(cm.config.WhitelistUserIDs),
		BlacklistCount:       len(cm.config.BlacklistUserIDs),
		RuleCount:            len(cm.config.Rules),
		StickySessions:       len(cm.config.stickyCache),
	}
}

// CanaryStats 灰度统计信息
type CanaryStats struct {
	Enabled              bool   `json:"enabled"`
	CanaryVersion        string `json:"canary_version"`
	StableVersion        string `json:"stable_version"`
	TrafficPercent       int    `json:"traffic_percent"`
	WhitelistCount       int    `json:"whitelist_count"`
	BlacklistCount       int    `json:"blacklist_count"`
	RuleCount            int    `json:"rule_count"`
	StickySessions       int    `json:"sticky_sessions"`
}

// CanaryAdminHandler 灰度管理 API Handler
func CanaryAdminHandler(cm *CanaryMiddleware) gin.HandlerFunc {
	return func(c *gin.Context) {
		switch c.Request.Method {
		case http.MethodGet:
			// 获取灰度配置和统计
			c.JSON(http.StatusOK, gin.H{
				"config": cm.GetConfig(),
				"stats":  cm.GetStats(),
			})

		case http.MethodPut:
			// 更新灰度配置
			var newConfig CanaryConfig
			if err := c.BindJSON(&newConfig); err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
				return
			}

			cm.UpdateConfig(&newConfig)
			c.JSON(http.StatusOK, gin.H{
				"message": "Canary config updated",
				"config":  newConfig,
			})

		default:
			c.JSON(http.StatusMethodNotAllowed, gin.H{"error": "method not allowed"})
		}
	}
}

