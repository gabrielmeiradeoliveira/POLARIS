package rules_yaml

import (
	"regexp"
	"strings"
)

type Rule struct {
	ID         string `yaml:"id"`
	Language   string `yaml:"language"`
	Severity   string `yaml:"severity"`
	Confidence string `yaml:"confidence"`
	CWE        string `yaml:"cwe"`
	Pattern    string `yaml:"pattern"`
	PatternNot string `yaml:"pattern-not"`
	Message    string `yaml:"message"`
}

type Match struct {
	RuleID     string
	Line       int
	Message    string
	Severity   string
	Confidence string
}

var metaVarRe = regexp.MustCompile(`\$[A-Z_][A-Z0-9_]*`)

func compilePattern(pat string) *regexp.Regexp {
	escaped := regexp.QuoteMeta(pat)
	replaced := metaVarRe.ReplaceAllString(escaped, `(.+?)`)
	return regexp.MustCompile(replaced)
}

func Evaluate(content string, rules []Rule, lang string) []Match {
	var out []Match
	lines := strings.Split(content, "\n")
	for _, r := range rules {
		if r.Language != lang || r.Pattern == "" {
			continue
		}
		re := compilePattern(r.Pattern)
		for idx, line := range lines {
			if re.MatchString(line) {
				if r.PatternNot != "" && strings.Contains(line, r.PatternNot) {
					continue
				}
				out = append(out, Match{
					RuleID:     r.ID,
					Line:       idx + 1,
					Message:    r.Message,
					Severity:   r.Severity,
					Confidence: r.Confidence,
				})
			}
		}
	}
	return out
}
