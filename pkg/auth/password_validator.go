package auth

import (
	"errors"
	"unicode"
)

// PasswordPolicy 密码策略
type PasswordPolicy struct {
	MinLength          int  `json:"min_length"`           // 最小长度
	RequireUppercase   bool `json:"require_uppercase"`    // 需要大写字母
	RequireLowercase   bool `json:"require_lowercase"`    // 需要小写字母
	RequireDigit       bool `json:"require_digit"`        // 需要数字
	RequireSpecialChar bool `json:"require_special_char"` // 需要特殊字符
	PreventReuseCount  int  `json:"prevent_reuse_count"`  // 防止重复使用最近N次密码
	MaxAgeDays         int  `json:"max_age_days"`         // 密码最长使用天数，0表示不限制
}

// DefaultPasswordPolicy 默认密码策略
var DefaultPasswordPolicy = PasswordPolicy{
	MinLength:          8,
	RequireUppercase:   true,
	RequireLowercase:   true,
	RequireDigit:       true,
	RequireSpecialChar: true,
	PreventReuseCount:  5,
	MaxAgeDays:         0, // 不限制
}

// PasswordValidator 密码验证器
type PasswordValidator struct {
	policy PasswordPolicy
}

// NewPasswordValidator 创建密码验证器
func NewPasswordValidator(policy PasswordPolicy) *PasswordValidator {
	return &PasswordValidator{
		policy: policy,
	}
}

// Validate 验证密码是否符合策略
func (v *PasswordValidator) Validate(password string) error {
	// 1. 检查长度
	if len(password) < v.policy.MinLength {
		return errors.New("密码长度不足，至少需要" + string(rune(v.policy.MinLength)) + "个字符")
	}

	hasUpper := false
	hasLower := false
	hasDigit := false
	hasSpecial := false

	// 2. 检查字符类型
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

	// 3. 根据策略检查
	if v.policy.RequireUppercase && !hasUpper {
		return errors.New("密码必须包含至少一个大写字母")
	}

	if v.policy.RequireLowercase && !hasLower {
		return errors.New("密码必须包含至少一个小写字母")
	}

	if v.policy.RequireDigit && !hasDigit {
		return errors.New("密码必须包含至少一个数字")
	}

	if v.policy.RequireSpecialChar && !hasSpecial {
		return errors.New("密码必须包含至少一个特殊字符")
	}

	return nil
}

// ValidateWithDetails 验证密码并返回详细信息
func (v *PasswordValidator) ValidateWithDetails(password string) (bool, map[string]bool) {
	details := make(map[string]bool)

	// 长度检查
	details["min_length"] = len(password) >= v.policy.MinLength

	hasUpper := false
	hasLower := false
	hasDigit := false
	hasSpecial := false

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

	details["has_uppercase"] = hasUpper
	details["has_lowercase"] = hasLower
	details["has_digit"] = hasDigit
	details["has_special_char"] = hasSpecial

	// 总体是否通过
	isValid := details["min_length"]
	if v.policy.RequireUppercase {
		isValid = isValid && hasUpper
	}
	if v.policy.RequireLowercase {
		isValid = isValid && hasLower
	}
	if v.policy.RequireDigit {
		isValid = isValid && hasDigit
	}
	if v.policy.RequireSpecialChar {
		isValid = isValid && hasSpecial
	}

	return isValid, details
}

// GetPolicy 获取当前策略
func (v *PasswordValidator) GetPolicy() PasswordPolicy {
	return v.policy
}

// CalculatePasswordStrength 计算密码强度（0-100）
func CalculatePasswordStrength(password string) int {
	if password == "" {
		return 0
	}

	strength := 0

	// 基础分数（根据长度）
	length := len(password)
	if length >= 8 {
		strength += 20
	}
	if length >= 12 {
		strength += 10
	}
	if length >= 16 {
		strength += 10
	}

	// 字符类型多样性
	hasUpper := false
	hasLower := false
	hasDigit := false
	hasSpecial := false

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

	if hasUpper {
		strength += 15
	}
	if hasLower {
		strength += 15
	}
	if hasDigit {
		strength += 15
	}
	if hasSpecial {
		strength += 15
	}

	// 确保不超过100
	if strength > 100 {
		strength = 100
	}

	return strength
}

// IsCommonPassword 检查是否为常见弱密码
func IsCommonPassword(password string) bool {
	// 常见弱密码列表（简化版，实际应该使用更完整的列表）
	commonPasswords := []string{
		"password", "123456", "12345678", "qwerty", "abc123",
		"password123", "admin", "letmein", "welcome", "monkey",
		"1234567890", "password1", "qwertyuiop", "123456789",
	}

	for _, common := range commonPasswords {
		if password == common {
			return true
		}
	}

	return false
}
