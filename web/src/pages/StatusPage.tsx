import { Card, MetricCard } from "../components/ui";
import { HealthStatus, VersionInfo } from "../api/types";

export function StatusPage({
  live,
  ready,
  version,
}: {
  live: HealthStatus | null;
  ready: HealthStatus | null;
  version: VersionInfo | null;
}) {
  return (
    <div>
      <h1 style={{ margin: "0 0 16px", fontSize: 20, fontWeight: 700 }}>Estado do Sistema</h1>
      <div className="polaris-grid">
        <MetricCard label="Versão" value={version?.version ?? "Indisponível"} subtitle={version?.name} />
        <MetricCard label="Liveness" value={live?.status ?? "Indisponível"} tone={live?.status === "ALIVE" ? "success" : "error"} />
        <MetricCard label="Readiness" value={ready?.status ?? "Indisponível"} tone={ready?.status === "READY" ? "success" : "error"} />
      </div>
      <Card title="Componentes">
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>
          Motor de análise local determinístico (Python, C#, Java, SQL) conectado ao PostgreSQL.
        </p>
      </Card>
    </div>
  );
}
