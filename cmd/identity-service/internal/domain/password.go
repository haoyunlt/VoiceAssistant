package domain

import (
	"fmt"
	"unicode"
)

// PasswordPolicy 密码策略
type PasswordPolicy struct {
	MinLength      int
	RequireUpper   bool
	RequireLower   bool
	RequireDigit   bool
	RequireSpecial bool
}

// DefaultPasswordPolicy 默认密码策略
var DefaultPasswordPolicy = &PasswordPolicy{
	MinLength:      8,
	RequireUpper:   true,
	RequireLower:   true,
	RequireDigit:   true,
	RequireSpecial: false,
}

// ValidatePassword 验证密码强度
func ValidatePassword(password string, policy *PasswordPolicy) error {
	if policy == nil {
		policy = DefaultPasswordPolicy
	}

	if len(password) < policy.MinLength {
		return fmt.Errorf("密码长度至少需要 %d 个字符", policy.MinLength)
	}

	var (
		hasUpper   = false
		hasLower   = false
		hasDigit   = false
		hasSpecial = false
	)

	for _, char := range password {
		switch {
		case unicode.IsUpper(char):
			hasUpper = true
		case unicode.IsLower(char):
			hasLower = true
		case unicode.IsDigit(char):
			hasDigit = true
		case unicode.IsPunct(char) || unicode.IsSymbol(char):
			hasSpecial = true
		}
	}

	if policy.RequireUpper && !hasUpper {
		return fmt.Errorf("密码必须包含至少一个大写字母")
	}

	if policy.RequireLower && !hasLower {
		return fmt.Errorf("密码必须包含至少一个小写字母")
	}

	if policy.RequireDigit && !hasDigit {
		return fmt.Errorf("密码必须包含至少一个数字")
	}

	if policy.RequireSpecial && !hasSpecial {
		return fmt.Errorf("密码必须包含至少一个特殊字符")
	}

	return nil
}

// ValidateEmail 验证邮箱格式（简单验证）
func ValidateEmail(email string) error {
	if len(email) < 3 || len(email) > 255 {
		return fmt.Errorf("邮箱长度无效")
	}

	// 简单的邮箱格式检查
	hasAt := false
	hasDot := false
	atIndex := -1

	for i, char := range email {
		if char == '@' {
			if hasAt {
				return fmt.Errorf("邮箱格式无效：包含多个 @ 符号")
			}
			hasAt = true
			atIndex = i
		}
		if char == '.' && hasAt && i > atIndex {
			hasDot = true
		}
	}

	if !hasAt || !hasDot {
		return fmt.Errorf("邮箱格式无效")
	}

	if atIndex == 0 || atIndex == len(email)-1 {
		return fmt.Errorf("邮箱格式无效")
	}

	return nil
}
