import { useState } from "react";

export function IssueAiAssistant({ issue }: { issue: Record<string, any> }) {
  const [aiResult, setAiResult] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  return (
    <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 600 }}>Assistente de Segurança (Sob Demanda)</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          disabled={loading}
          onClick={async () => {
            setLoading(true);
            try {
              const r = await fetch(`/api/issues/${issue.issue_id}/ai-analyze`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(issue),
              });
              setAiResult(await r.json());
            } finally {
              setLoading(false);
            }
          }}
          style={{ background: "#2563eb", color: "#ffffff", border: "none", padding: "6px 12px", borderRadius: 6, cursor: "pointer", fontWeight: 600 }}
        >
          {loading ? "Analisando..." : "✦ Explicar & Sugerir Ajuste"}
        </button>
        <button
          onClick={() => navigator.clipboard?.writeText(`${issue.rule_id} (${issue.cwe ?? "N/A"})\n${issue.message ?? ""}`)}
          style={{ background: aiResult?.needs_broader_refactor ? "#5A4212" : "#27272a", color: "#e4e4e7", border: "1px solid #3f3f46", padding: "6px 12px", borderRadius: 6, cursor: "pointer" }}
        >
          Copiar Prompt Cirúrgico
        </button>
      </div>
      {aiResult && (
        <div style={{ background: "#090C10", border: "1px solid #27272a", borderRadius: 6, padding: 10, fontSize: 12, display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ padding: "2px 6px", borderRadius: 4, fontWeight: 600, color: "#fff", background: aiResult.verdict === "CONFIRMED_EXPLOITABLE" ? "#dc2626" : aiResult.verdict === "LIKELY_FALSE_POSITIVE" ? "#16a34a" : "#d97706" }}>
              {aiResult.verdict ?? "NEEDS_REVIEW"}
            </span>
            <span style={{ color: "#a1a1aa", fontFamily: "'JetBrains Mono', monospace" }}>
              {aiResult.max_tokens_applied >= 1000 ? "Legado 1200t" : "Moderno 500t"}
            </span>
            {aiResult.cached && <span style={{ color: "#4ade80" }}>Cached</span>}
          </div>
          <p style={{ margin: 0, color: "#e4e4e7" }}>{aiResult.summary || aiResult.raw_response}</p>
          {aiResult.suggested_snippet && (
            <>
              <pre style={{ margin: 0, background: "#18181b", color: "#e4e4e7", padding: 8, borderRadius: 4, overflowX: "auto", fontFamily: "'JetBrains Mono', monospace" }}>
                {aiResult.suggested_snippet}
              </pre>
              <button
                onClick={() => {
                  navigator.clipboard?.writeText(aiResult.suggested_snippet);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }}
                style={{ background: "#27272a", color: "#e4e4e7", border: "1px solid #3f3f46", padding: "4px 8px", borderRadius: 4, cursor: "pointer", alignSelf: "flex-start" }}
              >
                {copied ? "Copiado!" : "Copiar Snippet"}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
