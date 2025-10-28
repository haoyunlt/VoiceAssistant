package server

import (
	"net/http"
	"voicehelper/cmd/conversation-service/internal/domain"

	"github.com/gin-gonic/gin"
)

// Response 统一响应格式
type Response struct {
	Code    int         `json:"code"`
	Message string      `json:"message"`
	Data    interface{} `json:"data,omitempty"`
}

// Success 成功响应
func Success(c *gin.Context, data interface{}) {
	c.JSON(http.StatusOK, Response{
		Code:    0,
		Message: "success",
		Data:    data,
	})
}

// Created 创建成功响应
func Created(c *gin.Context, data interface{}) {
	c.JSON(http.StatusCreated, Response{
		Code:    0,
		Message: "created",
		Data:    data,
	})
}

// NoContent 无内容响应
func NoContent(c *gin.Context) {
	c.Status(http.StatusNoContent)
}

// Error 错误响应
func Error(c *gin.Context, err error) {
	statusCode, code, message := parseError(err)
	c.JSON(statusCode, Response{
		Code:    code,
		Message: message,
	})
}

// parseError 解析错误类型并返回相应的 HTTP 状态码
func parseError(err error) (statusCode, code int, message string) {
	switch err {
	case domain.ErrConversationNotFound, domain.ErrMessageNotFound:
		return http.StatusNotFound, 404, err.Error()
	case domain.ErrUnauthorized:
		return http.StatusForbidden, 403, err.Error()
	case domain.ErrConversationDeleted:
		return http.StatusGone, 410, err.Error()
	case domain.ErrConversationFull:
		return http.StatusUnprocessableEntity, 422, err.Error()
	case domain.ErrInvalidMessageRole:
		return http.StatusBadRequest, 400, err.Error()
	default:
		return http.StatusInternalServerError, 500, "internal server error"
	}
}
