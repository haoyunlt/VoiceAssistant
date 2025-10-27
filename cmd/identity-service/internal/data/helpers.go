package data

import "time"

// timeFromUnix converts Unix timestamp to time.Time
func timeFromUnix(unix int64) time.Time {
	if unix == 0 {
		return time.Time{}
	}
	return time.Unix(unix, 0)
}
