package websocket

import "errors"

var (
	// ErrSendBufferFull 发送缓冲区已满
	ErrSendBufferFull = errors.New("send buffer is full")

	// ErrClientNotFound 客户端未找到
	ErrClientNotFound = errors.New("client not found")

	// ErrInvalidMessage 无效的消息
	ErrInvalidMessage = errors.New("invalid message")
)
