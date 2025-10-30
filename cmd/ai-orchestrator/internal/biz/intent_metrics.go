package biz

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// IntentRecognitionTotal 意图识别总数
	IntentRecognitionTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "intent_recognition_total",
			Help: "Total number of intent recognitions",
		},
		[]string{"intent_type", "recognizer", "tenant_id"},
	)

	// IntentRecognitionDuration 意图识别耗时
	IntentRecognitionDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "intent_recognition_duration_seconds",
			Help:    "Intent recognition duration in seconds",
			Buckets: []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0},
		},
		[]string{"intent_type", "recognizer", "tenant_id"},
	)

	// IntentConfidence 意图识别置信度
	IntentConfidence = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "intent_confidence",
			Help:    "Intent recognition confidence score",
			Buckets: []float64{0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0},
		},
		[]string{"intent_type", "recognizer", "tenant_id"},
	)

	// IntentCacheHits 意图缓存命中数
	IntentCacheHits = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "intent_cache_hits_total",
			Help: "Total number of intent cache hits",
		},
		[]string{"tenant_id"},
	)

	// IntentCacheMisses 意图缓存未命中数
	IntentCacheMisses = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "intent_cache_misses_total",
			Help: "Total number of intent cache misses",
		},
		[]string{"tenant_id"},
	)

	// IntentCacheSize 意图缓存大小
	IntentCacheSize = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "intent_cache_size",
			Help: "Current size of intent cache",
		},
		[]string{"cache_type"},
	)

	// IntentRecognitionErrors 意图识别错误数
	IntentRecognitionErrors = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "intent_recognition_errors_total",
			Help: "Total number of intent recognition errors",
		},
		[]string{"recognizer", "error_type", "tenant_id"},
	)

	// IntentModeSwitch 意图模式切换
	IntentModeSwitch = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "intent_mode_switch_total",
			Help: "Total number of intent mode switches",
		},
		[]string{"from_intent", "to_mode", "tenant_id"},
	)

	// IntentLowConfidence 低置信度意图识别数
	IntentLowConfidence = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "intent_low_confidence_total",
			Help: "Total number of low confidence intent recognitions",
		},
		[]string{"intent_type", "tenant_id"},
	)

	// IntentFallback 意图降级数
	IntentFallback = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "intent_fallback_total",
			Help: "Total number of intent fallbacks",
		},
		[]string{"original_intent", "fallback_intent", "tenant_id"},
	)

	// IntentRecognizerLatency 各识别器延迟
	IntentRecognizerLatency = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "intent_recognizer_latency_seconds",
			Help:    "Latency of each intent recognizer",
			Buckets: []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0},
		},
		[]string{"recognizer"},
	)

	// IntentAlternatives 备选意图数量
	IntentAlternatives = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "intent_alternatives_count",
			Help:    "Number of alternative intents provided",
			Buckets: []float64{0, 1, 2, 3, 4, 5},
		},
		[]string{"intent_type"},
	)
)

// RecordIntentRecognition 记录意图识别指标
func RecordIntentRecognition(intentType, recognizer, tenantID string, confidence, durationSeconds float64) {
	IntentRecognitionTotal.WithLabelValues(intentType, recognizer, tenantID).Inc()
	IntentRecognitionDuration.WithLabelValues(intentType, recognizer, tenantID).Observe(durationSeconds)
	IntentConfidence.WithLabelValues(intentType, recognizer, tenantID).Observe(confidence)
}

// RecordIntentCacheHit 记录缓存命中
func RecordIntentCacheHit(tenantID string) {
	IntentCacheHits.WithLabelValues(tenantID).Inc()
}

// RecordIntentCacheMiss 记录缓存未命中
func RecordIntentCacheMiss(tenantID string) {
	IntentCacheMisses.WithLabelValues(tenantID).Inc()
}

// RecordIntentError 记录意图识别错误
func RecordIntentError(recognizer, errorType, tenantID string) {
	IntentRecognitionErrors.WithLabelValues(recognizer, errorType, tenantID).Inc()
}

// RecordIntentModeSwitch 记录模式切换
func RecordIntentModeSwitch(fromIntent, toMode, tenantID string) {
	IntentModeSwitch.WithLabelValues(fromIntent, toMode, tenantID).Inc()
}

// RecordIntentLowConfidence 记录低置信度
func RecordIntentLowConfidence(intentType, tenantID string) {
	IntentLowConfidence.WithLabelValues(intentType, tenantID).Inc()
}

// RecordIntentFallback 记录意图降级
func RecordIntentFallback(originalIntent, fallbackIntent, tenantID string) {
	IntentFallback.WithLabelValues(originalIntent, fallbackIntent, tenantID).Inc()
}

// RecordRecognizerLatency 记录识别器延迟
func RecordRecognizerLatency(recognizer string, durationSeconds float64) {
	IntentRecognizerLatency.WithLabelValues(recognizer).Observe(durationSeconds)
}

// RecordIntentAlternatives 记录备选意图数量
func RecordIntentAlternatives(intentType string, count int) {
	IntentAlternatives.WithLabelValues(intentType).Observe(float64(count))
}

// UpdateCacheSize 更新缓存大小
func UpdateCacheSize(cacheType string, size int) {
	IntentCacheSize.WithLabelValues(cacheType).Set(float64(size))
}
