import { useEffect, useState } from "react";
import { HealthStatus, VersionInfo } from "../api/types";
import { Badge, Card } from "../components/ui";

interface AnalyzerMeta {
  language: string;
  id: string;
  version: string;
  capabilities: string[];
}

export function StatusPage({
  live,
  ready,
  version,
}: {
  live: HealthStatus | null;
  ready: HealthStatus | null;
  version: VersionInfo | null;
}) {
  const [analyzers, setAnalyzers] = useState<AnalyzerMeta[]>([]);
  const [aiStatus, setAiStatus] = useState<{ enabled?: boolean; model?: string; daily_budget?: number } | null>(null);

  useEffect(() => {
    fetch("/api/meta")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.analyzers) setAnalyzers(d.analyzers);
        if (d?.ai) setAiStatus(d.ai);
      })
      .catch(() => {});
  }, []);

  return (
    <div style={{ padding: "24px 32px" }}>
      <h1 style={{ margin: "0 0 16px", fontSize: 24, fontWeight: 600 }}>Estado do Sistema</h1>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
        <Card title="API Liveness">
          <Badge tone={live?.status === "OK" || live?.status === "ALIVE" ? "success" : "error"}>{live?.status ?? "DESCONHECIDO"}</Badge>
        </Card>
        <Card title="PostgreSQL Readiness">
          <Badge tone={ready?.status === "READY" ? "success" : "error"}>{ready?.status === "READY" ? "Conectado (READY)" : (ready?.status ?? "DESCONHECIDO")}</Badge>
        </Card>
        <Card title="Versão & Contrato">
          <div>Serviço: <code>polaris-server</code></div>
          <div>Versão: <code>{version?.version ?? "-"}</code></div>
          <div>Contrato: <code>1.0.0</code></div>
        </Card>
        <Card title="Camada de IA Sob Demanda">
          <Badge tone={aiStatus?.enabled ? "success" : "warning"}>
            {aiStatus?.enabled ? `Ativa (${aiStatus.model ?? "LLM"})` : "Determinístico"}
          </Badge>
          {aiStatus?.daily_budget && (
            <div style={{ marginTop: 6, fontSize: 12, color: "var(--text-muted)" }}>
              Orçamento diário: <code>{aiStatus.daily_budget}</code> tokens
            </div>
          )}
        </Card>
      </div>
      <div style={{ marginTop: 16 }}>
        <Card title={`Motores de Análise por Linguagem (${analyzers.length})`}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border-subtle)" }}>
                <th style={{ padding: "6px 8px" }}>Linguagem</th>
                <th style={{ padding: "6px 8px" }}>Analyzer</th>
                <th style={{ padding: "6px 8px" }}>Versão</th>
                <th style={{ padding: "6px 8px" }}>Capacidades</th>
              </tr>
            </thead>
            <tbody>
              {analyzers.map((a) => (
                <tr key={a.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                  <td style={{ padding: "6px 8px", fontWeight: 600 }}>{a.language}</td>
                  <td style={{ padding: "6px 8px" }}><code>{a.id}</code></td>
                  <td style={{ padding: "6px 8px" }}><code>{a.version}</code></td>
                  <td style={{ padding: "6px 8px" }}>{a.capabilities.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
