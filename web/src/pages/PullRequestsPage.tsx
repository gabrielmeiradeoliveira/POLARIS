import { useEffect, useState } from "react";
import { Badge, Button, DataTable, ErrorState } from "../components/ui";
import { IssueRow } from "./IssuesPage";
import { TaintTrail } from "../components/TaintTrail";
import { TriageStatusBadge } from "../components/TriageStatusBadge";
import { TriageActionStatus } from "../components/BatchTriageBar";
import { CodeEvidenceBlock } from "../components/CodeEvidenceBlock";
import { TechnicalBadge } from "../components/TechnicalBadge";
import { FinOpsComparisonChart } from "../components/FinOpsComparisonChart";
import { IssueAiAssistant } from "../components/IssueAiAssistant";
import { parseRoute } from "../App";

export function PullRequestsPage({ issues, onMutated }: { issues: IssueRow[]; onMutated?: () => void }) {
  const nav = parseRoute(window.location.hash);
  const prKey = nav.query.get("pr") || "PR-1";

  const [estimate, setEstimate] = useState<{ estimated_total_tokens: number; is_cached: boolean } | null>(null);
  const [summary, setSummary] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [selectedIssue, setSelectedIssue] = useState<IssueRow | null>(issues[0] ?? null);
  const [activeCodeLine, setActiveCodeLine] = useState<number | undefined>(undefined);
  const [flow, setFlow] = useState<Array<{ file: string; line: number; kind: string; detail: string }>>([]);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);

  // Derivação de Delta de Evolução do PR (Novos, Resolvidos, Mantidos)
  const newIssuesCount = issues.filter((i) => i.status === "OPEN" || !i.status).length;
  const resolvedIssuesCount = issues.filter((i) => i.status === "FIXED" || i.status === "FALSE_POSITIVE").length;
  const retainedIssuesCount = issues.filter((i) => i.status === "ACCEPTED_RISK").length;

  const fetchSummary = async (cachedOnly = false) => {
    setLoading(true);
    setErr(null);
    try {
      let issuesPayload = issues;
      if (!issuesPayload || issuesPayload.length === 0) {
        const issuesRes = await fetch("/api/v1/issues?limit=120");
        if (issuesRes.ok) {
          const issuesData = await issuesRes.json();
          issuesPayload = issuesData.issues || [];
        }
      }
      const r = await fetch(`/api/prs/${encodeURIComponent(prKey)}/ai-summary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          issues: (issuesPayload || []).slice(0, 120).map((i) => ({
            issue_id: i.issue_id,
            rule_id: i.rule_id,
            cwe: i.cwe,
            file_path: i.file_path,
            start_line: i.start_line,
            code_snippet: i.snippet,
            severity: i.severity,
            message: i.message,
            status: i.status,
          })),
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setSummary(data);
    } catch (e) {
      if (!cachedOnly) {
        setErr(e instanceof Error ? e.message : "Erro ao carregar resumo da IA");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch(`/api/ai/estimate?target_type=pr&target_id=${encodeURIComponent(prKey)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) {
          setEstimate(d);
          if (d.is_cached) {
            fetchSummary(true);
          }
        }
      })
      .catch(() => {});
  }, [prKey]);

  useEffect(() => {
    if (issues.length > 0 && !selectedIssue) {
      openFinding(issues[0]);
    }
  }, [issues]);

  const estTokens = estimate?.estimated_total_tokens ?? 1350;

  const openFinding = (issue: IssueRow) => {
    setSelectedIssue(issue);
    setActiveCodeLine(issue.start_line);
    setActionMsg(null);
    setActionErr(null);
    setFlow([]);
    fetch(`/api/v1/issues/${issue.issue_id}/flow`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setFlow(d?.flow_steps ?? []))
      .catch(() => setFlow([]));
  };

  const runTriage = async (st: TriageActionStatus) => {
    if (!selectedIssue) return;
    setActionBusy(true);
    setActionErr(null);
    setActionMsg(null);
    try {
      const res = await fetch(`/api/v1/issues/${selectedIssue.issue_id}/transition`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: st }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setActionMsg(`Estado atualizado para ${st}`);
      onMutated?.();
    } catch (e) {
      setActionErr(e instanceof Error ? e.message : "Erro na triagem");
    } finally {
      setActionBusy(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "calc(100vh - 64px)", background: "var(--bg-app)", overflow: "hidden" }}>
      {/* Cabeçalho Editorial do PR */}
      <div
        style={{
          padding: "16px 24px",
          background: "var(--bg-surface)",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: 18, fontWeight: 700, color: "var(--text-primary)" }}>
            Pull Request {prKey}
          </span>
          <Badge tone={issues.some((i) => i.severity === "CRITICAL" || i.severity === "BLOCKER") ? "error" : "success"}>
            {issues.some((i) => i.severity === "CRITICAL" || i.severity === "BLOCKER") ? "GATE FAILED" : "GATE PASSED"}
          </Badge>
          <span style={{ fontSize: 12, color: "var(--text-muted)", fontVariantNumeric: "tabular-nums" }}>
            {issues.length} findings detectados
          </span>
        </div>

        {/* 1 CTA Primário Polar Cyan para Resumo */}
        <div>
          {estimate?.is_cached || summary?.cached ? (
            <Button
              variant="secondary"
              size="sm"
              disabled={loading}
              onClick={() => fetchSummary()}
            >
              {loading ? "Carregando resumo..." : "Atualizar resumo em cache (0 tokens)"}
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              disabled={loading}
              onClick={() => fetchSummary()}
            >
              {loading ? `Gerando resumo (~${estTokens}t)...` : `Gerar resumo (~${estTokens} tokens)`}
            </Button>
          )}
        </div>
      </div>

      {/* Faixa de Comparativo de Evolução (Delta do PR) */}
      <div
        style={{
          padding: "10px 24px",
          background: "var(--bg-elevated)",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex",
          alignItems: "center",
          gap: 24,
          flexWrap: "wrap",
        }}
      >
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", letterSpacing: "0.02em" }}>
          DELTA DO PR (EVOLUÇÃO):
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Badge tone={newIssuesCount > 0 ? "error" : "neutral"}>
            +{newIssuesCount} Novos
          </Badge>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>introduzidos</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Badge tone={resolvedIssuesCount > 0 ? "success" : "neutral"}>
            -{resolvedIssuesCount} Resolvidos
          </Badge>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>desde a última análise</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Badge tone="neutral">
            ={retainedIssuesCount} Mantidos
          </Badge>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>em risco aceito</span>
        </div>
      </div>

      {/* Gráfico FinOps de Comparação Previsto vs Real */}
      <div style={{ padding: "12px 24px", background: "var(--bg-elevated)", borderBottom: "1px solid var(--border-subtle)" }}>
        <FinOpsComparisonChart
          estimatedTokens={summary?.estimated_tokens ?? estTokens}
          actualTokens={summary?.actual_total_tokens ?? summary?.tokens_used ?? 0}
          cached={Boolean(summary?.cached || estimate?.is_cached)}
          actualInputTokens={summary?.actual_input_tokens ?? 0}
          actualOutputTokens={summary?.actual_output_tokens ?? 0}
        />
      </div>

      {err && (
        <div style={{ color: "var(--color-critical)", fontSize: 12, padding: "8px 24px", borderBottom: "1px solid var(--border-subtle)" }}>
          Erro: {err}
        </div>
      )}

      {summary && (
        <div style={{ background: "var(--bg-surface)", borderBottom: "1px solid var(--border-subtle)", padding: "14px 24px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
              Veredito do Pull Request
            </span>
            {summary.verdict && (
              <Badge tone={summary.verdict === "CONFIRMED_EXPLOITABLE" ? "error" : summary.verdict === "LIKELY_FALSE_POSITIVE" ? "success" : "warning"}>
                {summary.verdict}
              </Badge>
            )}
            {summary.cached && (
              <span style={{ fontSize: 11, color: "var(--text-muted)" }}>• Cache persistido</span>
            )}
          </div>
          <p style={{ margin: 0, color: "var(--text-secondary)", lineHeight: 1.5, fontSize: 13, whiteSpace: "pre-wrap" }}>
            {summary.summary || summary.raw_response}
          </p>
        </div>
      )}

      {/* Grade Master-Detail com 1º achado aberto */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <div style={{ flex: 1, minWidth: 0, overflowY: "auto", padding: "16px 24px", borderRight: "1px solid var(--border-subtle)", background: "var(--bg-surface)" }}>
          <DataTable
            rowSelection={(r) => selectedIssue?.issue_id === r.issue_id}
            columns={[
              {
                key: "sev",
                header: "Severidade",
                render: (i) => <TechnicalBadge severity={i.severity} />,
              },
              { key: "rule", header: "Regra", render: (i) => <code>{i.rule_id}</code> },
              {
                key: "status",
                header: "Estado",
                render: (i) => <TriageStatusBadge status={i.status} expiresAt={i.triage_expires_at ?? i.expires_at} />,
              },
              {
                key: "file",
                header: "Arquivo",
                render: (i) => <code>{i.file_path}:{i.start_line ?? 1}</code>,
              },
            ]}
            rows={issues}
            onRowClick={openFinding}
            emptyText="Nenhum finding detectado neste PR."
          />
        </div>

        {selectedIssue && (
          <aside style={{ width: 500, flexShrink: 0, background: "var(--bg-surface)", overflowY: "auto", padding: "16px 20px", display: "flex", flexDirection: "column", gap: 14 }}>
            {actionErr && <ErrorState message={actionErr} />}
            {actionMsg && (
              <div style={{ padding: 10, borderRadius: "var(--radius-md)", background: "var(--color-success-bg)", color: "var(--color-success)", fontSize: 13 }}>
                {actionMsg}
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <TechnicalBadge severity={selectedIssue.severity} />
                <TriageStatusBadge status={selectedIssue.status} expiresAt={selectedIssue.triage_expires_at ?? selectedIssue.expires_at} />
              </div>
              <code style={{ fontSize: 12, color: "var(--text-primary)" }}>{selectedIssue.rule_id}</code>
            </div>

            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", borderTop: "1px solid var(--border-subtle)", borderBottom: "1px solid var(--border-subtle)", padding: "10px 0" }}>
              <Button size="sm" variant="secondary" disabled={actionBusy} onClick={() => runTriage("ACCEPTED_RISK")}>Aceitar Risco</Button>
              <Button size="sm" variant="secondary" disabled={actionBusy} onClick={() => runTriage("FALSE_POSITIVE")}>Falso Positivo</Button>
              <Button size="sm" variant="secondary" disabled={actionBusy} onClick={() => runTriage("FIXED")}>Corrigido</Button>
              <Button size="sm" variant="secondary" disabled={actionBusy} onClick={() => runTriage("OPEN")}>Reabrir</Button>
            </div>

            <div>
              <CodeEvidenceBlock
                filePath={selectedIssue.file_path}
                startLine={selectedIssue.start_line}
                activeLine={activeCodeLine}
                snippet={selectedIssue.snippet}
                language={selectedIssue.language}
              />
            </div>

            <div style={{ fontSize: 13, color: "var(--text-primary)", lineHeight: 1.4 }}>
              {selectedIssue.message}
            </div>

            {/* Análise Sob Demanda com IA Ancorada & Comparativo Antes -> Depois */}
            <IssueAiAssistant issue={selectedIssue} />

            {flow.length > 0 && (
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)", marginBottom: 8 }}>
                  Fluxo Semântico ({flow.length} passos)
                </div>
                <TaintTrail steps={flow} />
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}
