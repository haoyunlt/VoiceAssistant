package domain

import (
	"time"

	"github.com/google/uuid"
)

// TemplateType 模板类型
type TemplateType string

const (
	TemplateTypeEmail   TemplateType = "email"   // 邮件模板
	TemplateTypeSMS     TemplateType = "sms"     // 短信模板
	TemplateTypePush    TemplateType = "push"    // 推送模板
	TemplateTypeGeneric TemplateType = "generic" // 通用模板
)

// Template 通知模板
type Template struct {
	ID          string
	Name        string
	Type        TemplateType
	TenantID    string
	Subject     string   // 主题模板
	Content     string   // 内容模板
	Variables   []string // 变量列表
	Description string
	IsActive    bool
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

// NewTemplate 创建新模板
func NewTemplate(
	name string,
	templateType TemplateType,
	tenantID string,
	subject, content string,
) *Template {
	id := "tmpl_" + uuid.New().String()
	now := time.Now()

	return &Template{
		ID:        id,
		Name:      name,
		Type:      templateType,
		TenantID:  tenantID,
		Subject:   subject,
		Content:   content,
		Variables: make([]string, 0),
		IsActive:  true,
		CreatedAt: now,
		UpdatedAt: now,
	}
}

// Update 更新模板
func (t *Template) Update(subject, content, description string) {
	if subject != "" {
		t.Subject = subject
	}
	if content != "" {
		t.Content = content
	}
	if description != "" {
		t.Description = description
	}
	t.UpdatedAt = time.Now()
}

// AddVariable 添加变量
func (t *Template) AddVariable(variable string) {
	for _, v := range t.Variables {
		if v == variable {
			return // 已存在
		}
	}
	t.Variables = append(t.Variables, variable)
	t.UpdatedAt = time.Now()
}

// Activate 激活模板
func (t *Template) Activate() {
	t.IsActive = true
	t.UpdatedAt = time.Now()
}

// Deactivate 停用模板
func (t *Template) Deactivate() {
	t.IsActive = false
	t.UpdatedAt = time.Now()
}

// Render 渲染模板
func (t *Template) Render(variables map[string]interface{}) (string, string, error) {
	// 简化实现，实际应该使用模板引擎（如 text/template）
	subject := t.Subject
	content := t.Content

	// 替换变量
	for key, value := range variables {
		placeholder := "{{" + key + "}}"
		valueStr := toString(value)
		// 简单字符串替换（实际应该使用更复杂的模板引擎）
		// subject = strings.ReplaceAll(subject, placeholder, valueStr)
		// content = strings.ReplaceAll(content, placeholder, valueStr)
		_ = placeholder
		_ = valueStr
	}

	return subject, content, nil
}

// Validate 验证模板
func (t *Template) Validate() error {
	if t.Name == "" {
		return ErrInvalidTemplateName
	}
	if t.Content == "" {
		return ErrInvalidTemplateContent
	}
	return nil
}

// toString 转换为字符串
func toString(value interface{}) string {
	if value == nil {
		return ""
	}
	if str, ok := value.(string); ok {
		return str
	}
	return ""
}
