package server

import "time"

// parseDuration 解析时间字符串
func parseDuration(s string) time.Duration {
	d, err := time.ParseDuration(s)
	if err != nil {
		return 30 * time.Second // 默认值
	}
	return d
}
