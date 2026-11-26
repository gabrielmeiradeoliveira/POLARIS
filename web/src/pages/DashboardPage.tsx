import { useMemo } from "react";
import { DataTable } from "../components/ui";
import { ProjectItem } from "../api/types";
import { IssueRow } from "./IssuesPage";
import { summarizeSeverities } from "../utils/severity";
import { NoiseReductionFunnel } from "../components/NoiseReductionFunnel";

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

  const openIssues = useMemo(() => issues.filter((i) => (i.status || "OPEN").toUpperCase() === "OPEN"), [issues]);
  const triagedIssues = useMemo(() => issues.filter((i) => (i.status || "OPEN").toUpperCase() !== "OPEN"), [issues]);
  const criticalOpen = useMemo(
    () => openIssues.filter((i) => i.severity === "CRITICAL" || i.severity === "BLOCKER").length,
    [openIssues],
  );

  // Security Grade (PSG): 4*BLOCKER + 3*CRITICAL + 2*MAJOR + 1*MINOR
  const { grade, gradeColor, gradeDesc } = useMemo(() => {
    let score = 0;
    let hasBlocker = false;
    for (const i of openIssues) {
      const s = (i.severity || "").toUpperCase();
      if (s === "BLOCKER") {
        score += 4;
        hasBlocker = true;
      } else if (s === "CRITICAL") score += 3;
      else if (s === "MAJOR") score += 2;
      else if (s === "MINOR") score += 1;
    }

    let g = "A";
    let color = "var(--color-success)";
    if (score === 0) {
      g = "A";
      color = "var(--color-success)";
    } else if (score < 10) {
      g = "B";
      color = "var(--color-low)";
    } else if (score < 25) {
      g = "C";
      color = "var(--color-warning)";
    } else if (score < 50) {
      g = "D";
      color = "var(--color-high)";
    } else {
      g = "F";
      color = "var(--color-critical)";
    }

    if (hasBlocker && (g === "A" || g === "B" || g === "C")) {
      g = "D";
      color = "var(--color-high)";
    }

    return {
      grade: g,
      gradeColor: color,
      gradeDesc: `${score} pts ponderados (${openIssues.length} achados abertos)`,
    };
  }, [openIssues]);

  // Mapa de Calor de Risco por Arquivo (Barras Empilhadas)
  const fileHeatmap = useMemo(() => {
    const map = new Map<
      string,
      { file: string; score: number; critical: number; high: number; medium: number; low: number; total: number }
    >();

    for (const i of issues) {
      const file = i.file_path || "unknown";
      const entry = map.get(file) ?? { file, score: 0, critical: 0, high: 0, medium: 0, low: 0, total: 0 };
      entry.total++;

      const s = (i.severity || "").toUpperCase();
      if (s === "BLOCKER" || s === "CRITICAL") {
        entry.score += 4;
        entry.critical++;
      } else if (s === "MAJOR" || s === "HIGH") {
        entry.score += 2;
        entry.high++;
      } else {
        entry.score += 1;
        entry.medium++;
      }
      map.set(file, entry);
    }

    return Array.from(map.values())
      .sort((a, b) => b.score - a.score)
      .slice(0, 12);
  }, [issues]);

  // Fila Acionável (Top 5 achados abertos mais críticos)
  const actionableQueue = useMemo(() => {
    return [...openIssues]
      .sort((a, b) => {
        const order: Record<string, number> = { BLOCKER: 4, CRITICAL: 3, MAJOR: 2, MINOR: 1, INFO: 0 };
        return (order[b.severity] ?? 0) - (order[a.severity] ?? 0);
      })
      .slice(0, 5);
  }, [openIssues]);

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%", background: "var(--bg-app)", padding: "20px 24px", gap: 20 }}>
      {/* 4 Módulos Editoriais de Alta Presença */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        {/* 1. POSTURA */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-xl)", padding: "20px 24px", boxShadow: "var(--shadow-soft)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Postura de Segurança
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, margin: "12px 0 6px" }}>
            <span style={{ fontSize: "clamp(32px, 2.5vw, 36px)", fontWeight: 700, color: gradeColor, lineHeight: 1 }}>
              Grade {grade}
            </span>
            <span style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 500 }}>
              Gate PASSED
            </span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
            {gradeDesc}
          </div>
        </div>

        {/* 2. RUÍDO */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-xl)", padding: "20px 24px", boxShadow: "var(--shadow-soft)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Redução de Ruído
          </div>
          <div style={{ margin: "12px 0 6px" }}>
            <span style={{ fontSize: "clamp(32px, 2.5vw, 36px)", fontWeight: 700, color: "var(--text-primary)", lineHeight: 1 }}>
              {Math.round((triagedIssues.length / Math.max(1, issues.length)) * 100)}%
            </span>
            <span style={{ fontSize: 13, color: "var(--text-secondary)", marginLeft: 8 }}>
              triado / mitigado
            </span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
            {triagedIssues.length} suprimidos de {issues.length} totais
          </div>
        </div>

        {/* 3. SEVERIDADE */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-xl)", padding: "20px 24px", boxShadow: "var(--shadow-soft)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Achados Abertos
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, margin: "12px 0 6px" }}>
            <span style={{ fontSize: "clamp(32px, 2.5vw, 36px)", fontWeight: 700, color: "var(--text-primary)", lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>
              {openIssues.length}
            </span>
            <span style={{ fontSize: 12, color: "var(--color-critical)", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
              {criticalOpen} críticos
            </span>
          </div>
          <div style={{ display: "flex", gap: 8, fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
            <span style={{ color: "var(--color-critical)" }}>C:{sevCounts.critical}</span>
            <span style={{ color: "var(--color-high)" }}>A:{sevCounts.high}</span>
            <span style={{ color: "var(--color-warning)" }}>M:{sevCounts.medium}</span>
            <span style={{ color: "var(--color-low)" }}>B:{sevCounts.low}</span>
          </div>
        </div>

        {/* 4. SUPERFÍCIE */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-xl)", padding: "20px 24px", boxShadow: "var(--shadow-soft)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Superfície Monitorada
          </div>
          <div style={{ margin: "12px 0 6px" }}>
            <span style={{ fontSize: "clamp(32px, 2.5vw, 36px)", fontWeight: 700, color: "var(--text-primary)", lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>
              {projects.length}
            </span>
            <span style={{ fontSize: 13, color: "var(--text-secondary)", marginLeft: 8 }}>
              repositórios
            </span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", display: "flex", gap: 8 }}>
            <span>{rulesCount} regras</span> · <span>{gatesCount} gates</span>
          </div>
        </div>
      </div>

      {/* Funil de Redução de Ruído */}
      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-xl)", padding: "20px 24px", boxShadow: "var(--shadow-soft)" }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)", marginBottom: 16 }}>
          Funil de Triagem &amp; Redução de Ruído Operacional
        </div>
        <NoiseReductionFunnel
          total={issues.length}
          triaged={triagedIssues.length}
          open={openIssues.length}
          criticalOpen={criticalOpen}
          onFilterClick={(filter) => {
            if (filter === "CRITICAL") window.location.hash = "#/issues?severity=CRITICAL";
            else if (filter === "OPEN") window.location.hash = "#/issues?status=OPEN";
            else if (filter === "FALSE_POSITIVE") window.location.hash = "#/issues?status=FALSE_POSITIVE";
          }}
        />
      </div>

      {/* Grade: Mapa de Calor com Barras Empilhadas (65%) e Fila Acionável (35%) */}
      <div style={{ display: "grid", gridTemplateColumns: "65% 35%", gap: 20 }}>
        {/* Mapa de Calor por Arquivo */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-xl)", padding: "20px 24px", boxShadow: "var(--shadow-soft)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
              Mapa de Calor de Risco por Arquivo (Top 12)
            </span>
            <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
              Barras Empilhadas por Severidade
            </span>
          </div>

          {fileHeatmap.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
              Nenhum achado registrado para compor mapa de calor.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {fileHeatmap.map((item) => {
                const total = Math.max(1, item.total);
                const critPct = (item.critical / total) * 100;
                const highPct = (item.high / total) * 100;
                const medPct = (item.medium / total) * 100;
                const lowPct = (item.low / total) * 100;

                return (
                  <a
                    key={item.file}
                    href={`#/issues?file=${encodeURIComponent(item.file)}`}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 10px",
                      borderRadius: "var(--radius-md)",
                      textDecoration: "none",
                      gap: 12,
                      border: "1px solid var(--border-subtle)",
                      background: "var(--bg-app)",
                    }}
                  >
                    <span
                      title={item.file}
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 12,
                        color: "var(--text-primary)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        flex: 1,
                      }}
                    >
                      {item.file}
                    </span>

                    {/* Barra Empilhada Multisseveridade */}
                    <div
                      style={{
                        width: 140,
                        height: 8,
                        background: "var(--bg-muted)",
                        borderRadius: 4,
                        overflow: "hidden",
                        display: "flex",
                        flexShrink: 0,
                        gap: 1,
                      }}
                    >
                      {item.critical > 0 && <div style={{ width: `${critPct}%`, background: "var(--color-critical)" }} />}
                      {item.high > 0 && <div style={{ width: `${highPct}%`, background: "var(--color-high)" }} />}
                      {item.medium > 0 && <div style={{ width: `${medPct}%`, background: "var(--color-warning)" }} />}
                      {item.low > 0 && <div style={{ width: `${lowPct}%`, background: "var(--color-low)" }} />}
                    </div>

                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontVariantNumeric: "tabular-nums", color: "var(--text-secondary)", flexShrink: 0, minWidth: 90, textAlign: "right" }}>
                      <span style={{ color: item.critical > 0 ? "var(--color-critical)" : "var(--text-muted)" }}>C:{item.critical}</span>{" "}
                      <span style={{ color: item.high > 0 ? "var(--color-high)" : "var(--text-muted)" }}>A:{item.high}</span>{" "}
                      <span style={{ color: item.medium > 0 ? "var(--color-warning)" : "var(--text-muted)" }}>M:{item.medium}</span>
                    </div>
                  </a>
                );
              })}
            </div>
          )}
        </div>

        {/* Fila Acionável (Top 5) */}
        <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-xl)", padding: "20px 24px", boxShadow: "var(--shadow-soft)", display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
              Fila Acionável Prioritária
            </span>
            <a href="#/issues?status=OPEN" style={{ fontSize: 12, color: "var(--accent-iris)", fontWeight: 500 }}>
              Ver todas →
            </a>
          </div>

          {actionableQueue.length === 0 ? (
            <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
              Nenhum achado em aberto na fila acionável.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {actionableQueue.map((i) => (
                <a
                  key={i.issue_id}
                  href={`#/issues?finding=${encodeURIComponent(i.issue_id)}`}
                  style={{
                    padding: "10px 12px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--border-subtle)",
                    background: "var(--bg-app)",
                    textDecoration: "none",
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <code style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>{i.rule_id}</code>
                    <span style={{ fontSize: 10, fontWeight: 700, fontFamily: "var(--font-mono)", color: i.severity === "CRITICAL" || i.severity === "BLOCKER" ? "var(--color-critical)" : "var(--color-high)" }}>
                      {i.severity}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {i.file_path}:{i.start_line ?? 1}
                  </div>
                </a>
              ))}
            </div>
          )}

          {/* Projetos Cadastrados Compactos */}
          <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 14, marginTop: "auto" }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 8 }}>
              Projetos Monitorados ({projects.length})
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {projects.slice(0, 4).map((p) => (
                <a
                  key={p.projectKey}
                  href={`#/projects/${encodeURIComponent(p.projectKey)}`}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "6px 8px",
                    fontSize: 12,
                    color: "var(--text-primary)",
                    textDecoration: "none",
                    borderRadius: "var(--radius-sm)",
                  }}
                >
                  <span>{p.name}</span>
                  <code style={{ fontSize: 11, color: "var(--text-muted)" }}>{p.projectKey}</code>
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
