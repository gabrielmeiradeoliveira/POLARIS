import { useEffect, useState } from "react";
import { polarisApi } from "../api/client";
import { IssueItem, ProjectOverview } from "../api/types";
import { Badge, Breadcrumb, Button, Card, DataTable, Drawer, EmptyState, ErrorState, MetricCard, Select, Skeleton, Tabs } from "../components/ui";
import { severityTone } from "../utils/severity";

type WorkspaceTab = "overview" | "findings" | "code" | "metrics" | "branches" | "history" | "settings";

export function ProjectOverviewPage({ projectKey }: { projectKey: string }) {
  const [tab, setTab] = useState<WorkspaceTab>("overview");
  const [data, setData] = useState<ProjectOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<IssueItem | null>(null);
  const [history, setHistory] = useState<Array<{ analysis_id?: string; analysisId?: string; branch?: string; status?: string; created_at?: string }>>([]);
  const [branches, setBranches] = useState<Array<{ branch_name?: string; is_main?: boolean; last_commit?: string }>>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>("");
  const [baseId, setBaseId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [compareRes, setCompareRes] = useState<Record<string, unknown> | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      polarisApi.getProjectOverview(projectKey),
      fetch(`/api/v1/projects/${encodeURIComponent(projectKey)}/history`).then((r) => (r.ok ? r.json() : { items: [] })).catch(() => ({ items: [] })),
      fetch(`/api/v1/projects/${encodeURIComponent(projectKey)}/branches`).then((r) => (r.ok ? r.json() : { items: [] })).catch(() => ({ items: [] })),
    ])
      .then(([ov, hist, br]) => {
        setData(ov);
        setHistory(Array.isArray(hist) ? hist : (hist.items ?? []));
        setBranches(Array.isArray(br) ? br : (br.items ?? []));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Erro ao carregar projeto"))
      .finally(() => setLoading(false));
  };

  useEffect(load, [projectKey]);

  return (
    <div>
      <Breadcrumb items={[{ label: "Projetos", href: "#/projects" }, { label: projectKey }]} />
      {loading && (
        <div>
          <Skeleton height={32} />
          <Skeleton height={120} />
        </div>
      )}
      {error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && data && (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
            <div>
              <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>{data.name}</h1>
              <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                Chave: <code>{data.projectKey}</code>
                {data.latestAnalysis ? ` | Branch: ${data.latestAnalysis.branch} | Análise: ${data.latestAnalysis.analysisId}` : ""}
              </div>
            </div>
            <Badge tone={data.qualityGate.status === "PASSED" ? "success" : data.qualityGate.status === "FAILED" ? "error" : "neutral"}>
              Quality Gate: {data.qualityGate.status}
            </Badge>
          </div>

          <Tabs
            active={tab}
            onChange={(id) => setTab(id as WorkspaceTab)}
            tabs={[
              { id: "overview", label: "Overview" },
              { id: "findings", label: `Findings (${data.issues.length})` },
              { id: "code", label: "Code Explorer" },
              { id: "metrics", label: "Métricas" },
              { id: "branches", label: `Branches (${branches.length})` },
              { id: "history", label: `Histórico (${history.length})` },
              { id: "settings", label: "Configurações" },
            ]}
          />

          {!data.latestAnalysis ? (
            <EmptyState message="Nenhuma análise executada para este projeto ainda. Execute o scanner independente para enviar os resultados." />
          ) : (
            <>
              {tab === "overview" && (
                <>
                  <div className="polaris-grid">
                    <MetricCard label="Última Análise" value={data.latestAnalysis.analysisId} subtitle={`Estado: ${data.latestAnalysis.status}`} />
                    <MetricCard label="Arquivos Analisados" value={data.totalFiles} />
                    <MetricCard label="Bugs" value={data.bugs} tone={data.bugs > 0 ? "error" : "success"} />
                    <MetricCard label="Vulnerabilidades" value={data.vulnerabilities} tone={data.vulnerabilities > 0 ? "error" : "success"} />
                    <MetricCard label="Code Smells" value={data.codeSmells} tone={data.codeSmells > 0 ? "warning" : "success"} />
                    <MetricCard label="Cobertura" value={null} subtitle="Não calculada" />
                  </div>

                  <Card title="Condições do Quality Gate">
                    <DataTable
                      columns={[
                        { key: "metric", header: "Métrica", render: (c) => c.metric },
                        { key: "cond", header: "Condição", render: (c) => `${c.operator} ${c.threshold}` },
                        { key: "actual", header: "Valor Atual", render: (c) => c.actual },
                        { key: "status", header: "Estado", render: (c) => <Badge tone={c.status === "OK" ? "success" : "error"}>{c.status}</Badge> },
                      ]}
                      rows={data.qualityGate.conditions}
                    />
                  </Card>
                </>
              )}

              {tab === "findings" && (
                <Card title={`Findings (${data.issues.length})`}>
                  <DataTable
                    columns={[
                      { key: "sev", header: "Severidade", render: (i) => <Badge tone={severityTone(i.severity)}>{i.severity}</Badge> },
                      { key: "rule", header: "Regra", render: (i) => <code>{i.ruleId}</code> },
                      { key: "lang", header: "Linguagem", render: (i) => i.language },
                      { key: "loc", header: "Localização", render: (i) => <code>{i.location.file}:{i.location.startLine}</code> },
                      { key: "msg", header: "Mensagem", render: (i) => i.message },
                    ]}
                    rows={data.issues}
                    onRowClick={setSelectedIssue}
                    emptyText="Nenhuma issue encontrada nesta análise."
                  />
                </Card>
              )}

              {tab === "code" && (
                <Card title="Code Explorer (Manifesto de Arquivos com Findings)">
                  <DataTable
                    columns={[
                      { key: "file", header: "Arquivo", render: (i) => <code>{i.location.file}</code> },
                      { key: "line", header: "Linha", render: (i) => i.location.startLine },
                      { key: "rule", header: "Regra", render: (i) => <code>{i.ruleId}</code> },
                      { key: "sev", header: "Severidade", render: (i) => <Badge tone={severityTone(i.severity)}>{i.severity}</Badge> },
                    ]}
                    rows={data.issues}
                    onRowClick={setSelectedIssue}
                    emptyText="Nenhum arquivo com findings registrado nesta análise."
                  />
                </Card>
              )}

              {tab === "metrics" && (
                <Card title="Métricas da Análise">
                  <DataTable
                    columns={[
                      { key: "k", header: "Métrica", render: ([k]) => k },
                      { key: "v", header: "Valor", render: ([, v]) => String(v) },
                    ]}
                    rows={Object.entries(data.metrics)}
                    emptyText="Nenhuma métrica calculada."
                  />
                </Card>
              )}

              {tab === "branches" && (
                <Card title={`Branches (${branches.length})`}>
                  <div style={{ marginBottom: 12 }}>
                    <Select value={selectedBranch} onChange={(e) => setSelectedBranch(e.target.value)}>
                      <option value="">Todas as branches</option>
                      {branches.map((b) => (
                        <option key={b.branch_name} value={b.branch_name ?? ""}>{b.branch_name}</option>
                      ))}
                    </Select>
                  </div>
                  <DataTable
                    columns={[
                      { key: "name", header: "Branch", render: (b) => <code>{b.branch_name ?? "-"}</code> },
                      { key: "main", header: "Principal", render: (b) => (b.is_main ? <Badge tone="primary">Main</Badge> : "-") },
                      { key: "commit", header: "Último Commit", render: (b) => <code>{b.last_commit ?? "-"}</code> },
                    ]}
                    rows={selectedBranch ? branches.filter((b) => b.branch_name === selectedBranch) : branches}
                    emptyText="Nenhuma branch registrada."
                  />
                </Card>
              )}

              {tab === "history" && (
                <Card title={`Histórico de Análises (${history.length})`}>
                  {history.length >= 2 && (
                    <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
                      <Select value={baseId} onChange={(e) => setBaseId(e.target.value)}>
                        <option value="">Análise Base...</option>
                        {history.map((h) => {
                          const id = h.analysis_id ?? h.analysisId ?? "";
                          return <option key={id} value={id}>{id}</option>;
                        })}
                      </Select>
                      <Select value={targetId} onChange={(e) => setTargetId(e.target.value)}>
                        <option value="">Análise Alvo...</option>
                        {history.map((h) => {
                          const id = h.analysis_id ?? h.analysisId ?? "";
                          return <option key={id} value={id}>{id}</option>;
                        })}
                      </Select>
                      <Button
                        size="sm"
                        disabled={!baseId || !targetId || baseId === targetId}
                        onClick={() => {
                          fetch(`/api/v1/projects/${encodeURIComponent(projectKey)}/compare?base=${encodeURIComponent(baseId)}&target=${encodeURIComponent(targetId)}`)
                            .then((r) => (r.ok ? r.json() : null))
                            .then(setCompareRes)
                            .catch(() => setCompareRes(null));
                        }}
                      >
                        Comparar
                      </Button>
                    </div>
                  )}
                  {compareRes && (
                    <div style={{ padding: 12, marginBottom: 12, borderRadius: "var(--radius-md)", background: "var(--bg-elevated)", fontSize: 13 }}>
                      <strong>Comparação:</strong> <code>{JSON.stringify(compareRes)}</code>
                    </div>
                  )}
                  <DataTable
                    columns={[
                      { key: "id", header: "Análise", render: (h) => <code>{h.analysis_id ?? h.analysisId ?? "-"}</code> },
                      { key: "branch", header: "Branch", render: (h) => h.branch ?? "main" },
                      { key: "status", header: "Estado", render: (h) => <Badge>{h.status ?? "COMPLETED"}</Badge> },
                      { key: "date", header: "Data", render: (h) => h.created_at ?? "-" },
                    ]}
                    rows={history}
                    emptyText="Nenhuma análise histórica registrada."
                  />
                </Card>
              )}

              {tab === "settings" && (
                <Card title="Configurações do Projeto e Scanner">
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}>
                    <div><strong>Nome:</strong> {data.name}</div>
                    <div><strong>Chave:</strong> <code>{data.projectKey}</code></div>
                    <div><strong>Branch Principal:</strong> {data.latestAnalysis.branch}</div>
                    <div><strong>Quality Gate:</strong> {data.qualityGate.status}</div>
                    <div style={{ marginTop: 8 }}>
                      <strong>Comando do Scanner Independente:</strong>
                      <pre style={{ padding: 10, borderRadius: "var(--radius-md)", background: "var(--bg-elevated)", overflowX: "auto" }}>
                        {`python -m polaris_scanner.cli analyze --target <REPO_DIR> --project ${data.projectKey} --server http://127.0.0.1:8001 --output report.json`}
                      </pre>
                    </div>
                  </div>
                </Card>
              )}
            </>
          )}
        </>
      )}

      <Drawer open={Boolean(selectedIssue)} title="Detalhes da Issue" onClose={() => setSelectedIssue(null)}>
        {selectedIssue && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div><strong>Regra:</strong> <code>{selectedIssue.ruleId}</code></div>
            <div><strong>Severidade:</strong> <Badge tone={severityTone(selectedIssue.severity)}>{selectedIssue.severity}</Badge></div>
            <div><strong>Linguagem:</strong> {selectedIssue.language}</div>
            <div><strong>Arquivo:</strong> <code>{selectedIssue.location.file}:{selectedIssue.location.startLine}</code></div>
            <div><strong>Mensagem:</strong> {selectedIssue.message}</div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
