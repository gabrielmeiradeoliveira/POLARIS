package cpd

import "strings"

type Clone struct {
	FileA string
	FileB string
	LineA int
	LineB int
}

func RollingHashLines(content string, minLines int) map[uint64]int {
	lines := strings.Split(content, "\n")
	hashes := make(map[uint64]int)
	if len(lines) < minLines || minLines <= 0 {
		return hashes
	}
	const base uint64 = 257
	for i := 0; i <= len(lines)-minLines; i++ {
		var h uint64
		for j := 0; j < minLines; j++ {
			for _, b := range []byte(strings.TrimSpace(lines[i+j])) {
				h = h*base + uint64(b)
			}
			h = h*base + '\n'
		}
		if _, exists := hashes[h]; !exists {
			hashes[h] = i + 1
		}
	}
	return hashes
}
