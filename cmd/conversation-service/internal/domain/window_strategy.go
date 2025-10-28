package domain

import (
	"context"
)

// WindowStrategy 窗口选择策略
type WindowStrategy interface {
	Select(
		ctx context.Context,
		repo MessageRepository,
		conversationID string,
		options *ContextOptions,
	) ([]*Message, error)
}

// RecentWindowStrategy 最近消息窗口策略
type RecentWindowStrategy struct{}

// Select 选择最近的N条消息
func (s *RecentWindowStrategy) Select(
	ctx context.Context,
	repo MessageRepository,
	conversationID string,
	options *ContextOptions,
) ([]*Message, error) {
	// 获取最近的消息
	messages, _, err := repo.ListMessages(ctx, conversationID, options.MaxMessages, 0)
	if err != nil {
		return nil, err
	}

	// 如果需要包含系统消息，确保第一条是系统消息
	if options.IncludeSystem && len(messages) > 0 {
		// 检查第一条是否为系统消息
		if messages[0].Role != RoleSystem {
			// 查询系统消息
			// TODO: 实现系统消息查询
		}
	}

	return messages, nil
}

// SlidingWindowStrategy 滑动窗口策略
type SlidingWindowStrategy struct {
	WindowSize int
}

// Select 使用滑动窗口选择消息
func (s *SlidingWindowStrategy) Select(
	ctx context.Context,
	repo MessageRepository,
	conversationID string,
	options *ContextOptions,
) ([]*Message, error) {
	windowSize := s.WindowSize
	if windowSize == 0 {
		windowSize = options.MaxMessages
	}

	messages, _, err := repo.ListMessages(ctx, conversationID, windowSize, 0)
	return messages, err
}

// FixedWindowStrategy 固定窗口策略
type FixedWindowStrategy struct {
	StartOffset int
	WindowSize  int
}

// Select 使用固定窗口选择消息
func (s *FixedWindowStrategy) Select(
	ctx context.Context,
	repo MessageRepository,
	conversationID string,
	options *ContextOptions,
) ([]*Message, error) {
	messages, _, err := repo.ListMessages(ctx, conversationID, s.WindowSize, s.StartOffset)
	return messages, err
}
