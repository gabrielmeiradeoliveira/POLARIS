import { useState } from "react";
import { Badge, Button } from "./ui";

export function IssueAiAssistant({ issue }: { issue: Record<string, any> }) {
  const [aiResult, setAiResult] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  return (
    <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>Análise sob demanda</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Button
          variant="secondary"
          size="sm"
          disabled={loading}
          onClick={async () => {
            setLoading(true);
            try {
              const r = await fetch(`/api/issues/${issue.issue_id}/ai-analyze`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  issue_id: issue.issue_id,
                  rule_id: issue.rule_id,
                  cwe: issue.cwe,
                  file_path: issue.file_path,
                  start_line: issue.start_line,
                  code_snippet: issue.snippet,
                  severity: issue.severity,
                  message: issue.message,
                }),
              });
              setAiResult(await r.json());
            } finally {
              setLoading(false);
            }
          }}
        >
          {loading ? "Analisando..." : "Explicar e sugerir ajuste"}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigator.clipboard?.writeText(`${issue.rule_id} (${issue.cwe ?? "N/A"})\n${issue.message ?? ""}`)}
          style={{
            border: "1px solid var(--border-subtle)",
            color: "var(--text-secondary)",
          }}
        >
          Copiar prompt
        </Button>
      </div>
      {aiResult && (
        <div style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: 10, fontSize: 12, display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <Badge tone={aiResult.verdict === "CONFIRMED_EXPLOITABLE" ? "error" : aiResult.verdict === "LIKELY_FALSE_POSITIVE" ? "success" : "warning"}>
              {aiResult.verdict ?? "NEEDS_REVIEW"}
            </Badge>
            <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>
              {aiResult.max_tokens_applied >= 1000 ? "Legado 1200t" : "Moderno 500t"}
            </span>
            {aiResult.cached && (
              <span style={{ color: "var(--color-success)", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>
                Em cache
              </span>
            )}
          </div>
          <p style={{ margin: 0, color: "var(--text-primary)", lineHeight: 1.4 }}>{aiResult.summary || aiResult.raw_response}</p>
          
          {/* Comparativo Visual Antes -> Depois */}
          <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-critical)" }}>
              Antes (Linha {issue.start_line ?? 1}):
            </div>
            <pre style={{ margin: 0, background: "rgba(248, 81, 73, 0.08)", border: "1px solid rgba(248, 81, 73, 0.25)", color: "var(--color-critical)", padding: "6px 8px", borderRadius: "var(--radius-sm)", overflowX: "auto", fontFamily: "var(--font-mono)", fontSize: 11 }}>
              {issue.snippet || `Linha ${issue.start_line ?? 1}: Trecho vulnerável detectado`}
            </pre>

            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-success)", marginTop: 4 }}>
              Depois (Linha Corrigida Sugerida):
            </div>
            <pre style={{ margin: 0, background: "rgba(63, 185, 80, 0.08)", border: "1px solid rgba(63, 185, 80, 0.25)", color: "var(--color-success)", padding: "6px 8px", borderRadius: "var(--radius-sm)", overflowX: "auto", fontFamily: "var(--font-mono)", fontSize: 11 }}>
              {aiResult.suggested_snippet || "// Correção recomendada: sanitizar entrada ou usar query parametrizada"}
            </pre>
          </div>

          {aiResult.suggested_snippet && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                navigator.clipboard?.writeText(aiResult.suggested_snippet);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              style={{ alignSelf: "flex-start", marginTop: 4 }}
            >
              {copied ? "Copiado!" : "Copiar Correção"}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
