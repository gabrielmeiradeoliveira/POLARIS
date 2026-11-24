package contract

import (
	"bytes"
	"compress/gzip"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
)

type LocationV1 struct {
	File      string `json:"file"`
	StartLine int    `json:"startLine"`
}

type IssueV1 struct {
	RuleID     string     `json:"ruleId"`
	Language   string     `json:"language"`
	Severity   string     `json:"severity"`
	Confidence string     `json:"confidence,omitempty"`
	Location   LocationV1 `json:"location"`
	Message    string     `json:"message"`
}

type AnalyzerMeta struct {
	ID      string `json:"id"`
	Version string `json:"version"`
}

type AnalysisReportV1 struct {
	SchemaVersion string       `json:"schemaVersion"`
	AnalysisID    string       `json:"analysisId"`
	ProjectKey    string       `json:"projectKey"`
	Branch        string       `json:"branch"`
	Analyzer      AnalyzerMeta `json:"analyzer"`
	Status        string       `json:"status"`
	TotalFiles    int          `json:"totalFiles"`
	Diagnostics   []any        `json:"diagnostics"`
	Issues        []IssueV1    `json:"issues"`
}

func NewReport(projectKey, branch, version string, totalFiles int) AnalysisReportV1 {
	return AnalysisReportV1{
		SchemaVersion: "1.0.0",
		AnalysisID:    "go-scan-1",
		ProjectKey:    projectKey,
		Branch:        branch,
		Analyzer:      AnalyzerMeta{ID: "polaris-scanner-go", Version: version},
		Status:        "COMPLETED",
		TotalFiles:    totalFiles,
		Diagnostics:   []any{},
		Issues:        []IssueV1{},
	}
}

func ToJSON(r AnalysisReportV1) string {
	b, _ := json.MarshalIndent(r, "", "  ")
	return string(b)
}

func ToSARIF(r AnalysisReportV1) string {
	sarif := map[string]any{
		"version": "2.1.0",
		"runs": []map[string]any{
			{"tool": map[string]any{"driver": map[string]any{"name": r.Analyzer.ID, "version": r.Analyzer.Version}}, "results": []any{}},
		},
	}
	b, _ := json.MarshalIndent(sarif, "", "  ")
	return string(b)
}

func CompressAndSign(payload []byte, hmacSecret string) ([]byte, string, error) {
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)
	if _, err := gz.Write(payload); err != nil {
		return nil, "", err
	}
	if err := gz.Close(); err != nil {
		return nil, "", err
	}
	mac := hmac.New(sha256.New, []byte(hmacSecret))
	mac.Write(buf.Bytes())
	return buf.Bytes(), hex.EncodeToString(mac.Sum(nil)), nil
}
