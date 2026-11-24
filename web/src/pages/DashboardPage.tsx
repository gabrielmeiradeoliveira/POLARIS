import { useMemo } from "react";
import { Badge, Card, DataTable, MetricCard } from "../components/ui";
import { ProjectItem } from "../api/types";
import { IssueRow } from "./IssuesPage";
import { summarizeSeverities } from "../utils/severity";

export function DashboardPage({
  projects,
  issues,
  rulesCount,
  gatesCount,
}: {
  projects: ProjectItem[];
  issues: IssueRow[];
  rulesCount: number;
  gatesCount: number;
}) {
  const sevCounts = useMemo(() => summarizeSeverities(issues), [issues]);

  const catCounts = useMemo(() => {
    let sec = 0;
    let rel = 0;
    let mnt = 0;
    for (const i of issues) {
      if (i.rule_id.includes("-SEC-")) sec++;
      else if (i.rule_id.includes("-REL-") || i.severity === "CRITICAL" || i.severity === "BLOCKER") rel++;
      else mnt++;
    }
    return { sec, rel, mnt };
  }, [issues]);

  const langCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const i of issues) {
      const lang = i.language || i.rule_id.split("-")[0]?.toLowerCase() || "other";
      map.set(lang, (map.get(lang) ?? 0) + 1);
    }
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [issues]);

  const totalSev = Math.max(1, issues.length);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>Visão Geral</h1>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Postura de segurança e qualidade de código</div>
        </div>
        <a href="#/projects" style={{ fontSize: 13, fontWeight: 600 }}>Novo Projeto &rarr;</a>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, alignItems: "start" }}>
        <div>
          <Card title={`Distribuição de Riscos (${issues.length} findings)`}>
            <div style={{ display: "flex", height: 12, borderRadius: 6, overflow: "hidden", background: "var(--bg-muted)", marginBottom: 12 }}>
              <div style={{ width: `${(sevCounts.critical / totalSev) * 100}%`, background: "var(--color-critical)" }} title={`Crítico/Blocker: ${sevCounts.critical}`} />
              <div style={{ width: `${(sevCounts.high / totalSev) * 100}%`, background: "var(--color-high)" }} title={`Alto/Major: ${sevCounts.high}`} />
              <div style={{ width: `${(sevCounts.medium / totalSev) * 100}%`, background: "var(--color-warning)" }} title={`Médio/Minor: ${sevCounts.medium}`} />
              <div style={{ width: `${(sevCounts.low / totalSev) * 100}%`, background: "var(--color-low)" }} title={`Baixo/Info: ${sevCounts.low}`} />
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 12 }}>
              <a href="#/issues"><Badge tone="error">Crítico/Blocker: {sevCounts.critical}</Badge></a>
              <a href="#/issues"><Badge tone="warning">Alto/Major: {sevCounts.high}</Badge></a>
              <a href="#/issues"><Badge tone="primary">Médio/Minor: {sevCounts.medium}</Badge></a>
              <a href="#/issues"><Badge>Baixo/Info: {sevCounts.low}</Badge></a>
            </div>
          </Card>

          <Card title="Projetos Prioritários">
            <DataTable
              columns={[
                { key: "key", header: "Projeto", render: (p) => <a href={`#/projects/${encodeURIComponent(p.projectKey)}`}>{p.name}</a> },
                { key: "id", header: "Chave", render: (p) => <code>{p.projectKey}</code> },
                { key: "action", header: "Workspace", render: (p) => <a href={`#/projects/${encodeURIComponent(p.projectKey)}`}>Investigar &rarr;</a> },
              ]}
              rows={projects}
              emptyText="Nenhum projeto cadastrado ainda."
            />
          </Card>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <MetricCard label="Projetos" value={projects.length} />
            <MetricCard label="Findings" value={issues.length} tone={issues.length > 0 ? "warning" : "success"} />
            <MetricCard label="Vulnerabilidades" value={catCounts.sec} tone={catCounts.sec > 0 ? "error" : "success"} />
            <MetricCard label="Bugs" value={catCounts.rel} tone={catCounts.rel > 0 ? "warning" : "success"} />
          </div>

          <Card title="Distribuição por Linguagem">
            {langCounts.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--text-muted)" }}>Sem findings registrados.</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {langCounts.map(([lang, count]) => (
                  <div key={lang} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                    <span>{lang.toUpperCase()}</span>
                    <strong>{count}</strong>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card title="Governança">
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
              <span>Regras no Catálogo</span>
              <a href="#/rules"><strong>{rulesCount}</strong></a>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <span>Quality Gates</span>
              <a href="#/gates"><strong>{gatesCount}</strong></a>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
