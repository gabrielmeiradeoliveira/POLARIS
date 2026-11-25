import { useEffect, useState } from "react";
import { Badge, Card } from "../components/ui";
import { IssueRow } from "./IssuesPage";

export function PullRequestsPage({ issues }: { issues: IssueRow[] }) {
  const [prKey] = useState("PR-1");
  const [estimate, setEstimate] = useState<{ estimated_total_tokens: number; is_cached: boolean } | null>(null);
  const [summary, setSummary] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/ai/estimate?target_type=pr&target_id=${encodeURIComponent(prKey)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setEstimate(d))
      .catch(() => {});
  }, [prKey]);

  const estTokens = estimate?.estimated_total_tokens ?? 1350;

  return (
    <div>
      <h1 style={{ margin: "0 0 16px", fontSize: 24, fontWeight: 600 }}>Pull Requests</h1>
      <Card title={`Pull Request ${prKey}`}>
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
          <Badge tone={issues.some((i) => i.severity === "CRITICAL" || i.severity === "BLOCKER") ? "error" : "success"}>
            {issues.some((i) => i.severity === "CRITICAL" || i.severity === "BLOCKER") ? "GATE FAILED" : "GATE PASSED"}
          </Badge>
          <span style={{ fontSize: 13, color: "var(--text-muted)" }}>{issues.length} findings detectados</span>
          <button
            disabled={loading}
            onClick={async () => {
              setLoading(true);
              setErr(null);
              try {
                const r = await fetch(`/api/prs/${encodeURIComponent(prKey)}/ai-summary`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ issues: issues.slice(0, 120) }),
                });
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                setSummary(await r.json());
              } catch (e) {
                setErr(e instanceof Error ? e.message : "Erro ao gerar resumo");
              } finally {
                setLoading(false);
              }
            }}
            style={{ backgroundColor: "#4f46e5", color: "#ffffff", border: "1px solid #6366f1", padding: "6px 14px", borderRadius: 6, fontWeight: 600, cursor: "pointer" }}
          >
            {loading
              ? `⏳ Gerando resumo com IA (~${estTokens}t)...`
              : estimate?.is_cached
              ? "⚡ Ver Resumo em Cache (0 tokens)"
              : `✦ Gerar Resumo IA (~${estTokens} tokens)`}
          </button>
          <a href="#/issues" style={{ color: "#93c5fd", fontSize: 13, textDecoration: "none" }}>
            Investigar Findings →
          </a>
        </div>
        {err && <div style={{ color: "#f87171", fontSize: 13, marginBottom: 8 }}>Erro: {err}</div>}
        {summary && (
          <div style={{ background: "#090C10", border: "1px solid #27272a", borderRadius: 6, padding: 12, fontSize: 13, display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <strong>Resumo Executivo (IA)</strong>
              {summary.cached && <Badge tone="success">Cached</Badge>}
            </div>
            <p style={{ margin: 0, color: "#e4e4e7" }}>{summary.summary || summary.raw_response}</p>
            <div style={{ fontSize: 11, color: "#a1a1aa", fontFamily: "'JetBrains Mono', monospace" }}>
              Previsto: ~{summary.estimated_tokens ?? estTokens}t · Real:{" "}
              {summary.cached ? "0t · Cache Hit" : `${summary.actual_total_tokens ?? summary.tokens_used ?? 0}t (${summary.actual_input_tokens ?? 0} in + ${summary.actual_output_tokens ?? 0} out)`}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
