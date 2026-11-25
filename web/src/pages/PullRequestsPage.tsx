import { useState } from "react";
import { Badge, Button, Card } from "../components/ui";
import { IssueRow } from "./IssuesPage";

export function PullRequestsPage({ issues }: { issues: IssueRow[] }) {
  const [prKey, setPrKey] = useState("PR-1");
  const [summary, setSummary] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);

  return (
    <div>
      <h1 style={{ margin: "0 0 16px", fontSize: 24, fontWeight: 600 }}>Pull Requests</h1>
      <Card title={`Pull Request ${prKey}`}>
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
          <Badge tone={issues.some((i) => i.severity === "CRITICAL" || i.severity === "BLOCKER") ? "error" : "success"}>
            {issues.some((i) => i.severity === "CRITICAL" || i.severity === "BLOCKER") ? "GATE FAILED" : "GATE PASSED"}
          </Badge>
          <span style={{ fontSize: 13, color: "var(--text-muted)" }}>{issues.length} findings detectados</span>
          <Button
            disabled={loading}
            onClick={async () => {
              setLoading(true);
              try {
                const r = await fetch(`/api/prs/${encodeURIComponent(prKey)}/ai-summary`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ issues: issues.slice(0, 10) }),
                });
                setSummary(await r.json());
              } finally {
                setLoading(false);
              }
            }}
          >
            {loading ? "Gerando resumo..." : "✦ Gerar Resumo IA do PR"}
          </Button>
        </div>
        {summary && (
          <div style={{ background: "#090C10", border: "1px solid #27272a", borderRadius: 6, padding: 12, fontSize: 13 }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>Resumo Executivo (IA)</div>
            <p style={{ margin: 0, color: "#e4e4e7" }}>{summary.summary || summary.raw_response}</p>
          </div>
        )}
      </Card>
    </div>
  );
}
