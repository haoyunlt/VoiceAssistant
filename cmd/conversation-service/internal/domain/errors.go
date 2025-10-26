package domain

import "errors"

var (
	// ErrConversationNotFound 对话未找到
	ErrConversationNotFound = errors.New("conversation not found")

	// ErrMessageNotFound 消息未找到
	ErrMessageNotFound = errors.New("message not found")

	// ErrConversationDeleted 对话已删除
	ErrConversationDeleted = errors.New("conversation is deleted")

	// ErrConversationFull 对话已满
	ErrConversationFull = errors.New("conversation is full")

	// ErrInvalidMessageRole 无效的消息角色
	ErrInvalidMessageRole = errors.New("invalid message role")

	// ErrUnauthorized 未授权
	ErrUnauthorized = errors.New("unauthorized")
)
