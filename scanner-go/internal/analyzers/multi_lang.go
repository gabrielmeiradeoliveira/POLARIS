package analyzers

import "github.com/polaris-sec/polaris-scanner/internal/rules_yaml"

var BuiltinRules = []rules_yaml.Rule{
	{ID: "go:GO-SEC-001", Language: "go", Severity: "CRITICAL", Confidence: "HIGH", CWE: "CWE-89", Pattern: "db.Query(", Message: "Potential SQL Injection in database/sql"},
	{ID: "kotlin:KT-SEC-001", Language: "kotlin", Severity: "CRITICAL", Confidence: "HIGH", CWE: "CWE-89", Pattern: "rawQuery(", Message: "Potential SQL Injection in rawQuery"},
	{ID: "php:PHP-SEC-001", Language: "php", Severity: "BLOCKER", Confidence: "HIGH", CWE: "CWE-94", Pattern: "eval($_GET", Message: "Remote Code Execution via eval($_GET)"},
	{ID: "tf:TF-SEC-001", Language: "terraform", Severity: "CRITICAL", Confidence: "HIGH", CWE: "CWE-284", Pattern: "0.0.0.0/0", Message: "Ingress open to 0.0.0.0/0"},
	{ID: "k8s:K8S-SEC-001", Language: "kubernetes", Severity: "CRITICAL", Confidence: "HIGH", CWE: "CWE-250", Pattern: "privileged: true", Message: "Container running in privileged mode"},
	{ID: "sh:SH-SEC-001", Language: "shell", Severity: "CRITICAL", Confidence: "HIGH", CWE: "CWE-78", Pattern: "| bash", Message: "Piping remote script directly into bash"},
}

func Analyze(lang, content string) []rules_yaml.Match {
	return rules_yaml.Evaluate(content, BuiltinRules, lang)
}
