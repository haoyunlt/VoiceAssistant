package domain

import "time"

// CompressedContext 压缩的上下文
type CompressedContext struct {
	ConversationID       string     // 对话 ID
	Summary              string     // 压缩摘要
	OriginalMessageCount int        // 原始消息数
	CompressedAt         time.Time  // 压缩时间
	KeptMessages         []*Message // 保留的最近消息
	CompressionRatio     float64    // 压缩比
}

// ConversationSummary 对话摘要
type ConversationSummary struct {
	ConversationID string    // 对话 ID
	Summary        string    // 完整摘要
	MessageCount   int       // 消息总数
	GeneratedAt    time.Time // 生成时间
	Topics         []string  // 话题列表
	KeyPoints      []string  // 关键点列表
}

// SummaryStatistics 摘要统计
type SummaryStatistics struct {
	TotalSummaries   int       // 总摘要数
	AvgLength        int       // 平均长度
	AvgCompression   float64   // 平均压缩比
	LastGeneratedAt  time.Time // 最后生成时间
}
