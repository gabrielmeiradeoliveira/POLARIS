import React from "react";

export interface NoiseReductionFunnelProps {
  total: number;
  triaged: number;
  open: number;
  criticalOpen: number;
  onFilterClick?: (statusOrSeverity: string) => void;
}

export function NoiseReductionFunnel({
  total,
  triaged,
  open,
  criticalOpen,
  onFilterClick,
}: NoiseReductionFunnelProps) {
  const safeTotal = Math.max(1, total);
  const triagedPct = Math.round((triaged / safeTotal) * 100);
  const openPct = Math.round((open / safeTotal) * 100);
  const criticalPct = Math.round((criticalOpen / safeTotal) * 100);

  const stages = [
    {
      id: "total",
      label: "Detectados",
      count: total,
      pct: "100%",
      bg: "var(--bg-muted)",
      color: "var(--text-primary)",
      filter: "",
    },
    {
      id: "triaged",
      label: "Suprimidos / Triados",
      count: triaged,
      pct: `${triagedPct}%`,
      bg: "var(--color-success-bg)",
      color: "var(--color-success)",
      filter: "FALSE_POSITIVE",
    },
    {
      id: "open",
      label: "Fila Acionável",
      count: open,
      pct: `${openPct}%`,
      bg: "var(--accent-iris-soft)",
      color: "var(--accent-iris)",
      filter: "OPEN",
    },
    {
      id: "critical",
      label: "Crítico Acionável",
      count: criticalOpen,
      pct: `${criticalPct}%`,
      bg: "var(--color-critical-bg)",
      color: "var(--color-critical)",
      filter: "CRITICAL",
    },
  ];

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 12,
        width: "100%",
      }}
      role="img"
      aria-label={`Funil de redução de ruído: ${total} detectados, ${triaged} triados (${triagedPct}%), ${open} acionáveis (${openPct}%), ${criticalOpen} críticos (${criticalPct}%).`}
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
        {stages.map((stage) => {
          const isClickable = Boolean(onFilterClick && stage.filter);
          return (
            <div
              key={stage.id}
              onClick={() => isClickable && onFilterClick?.(stage.filter)}
              style={{
                background: stage.bg,
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "10px 12px",
                cursor: isClickable ? "pointer" : "default",
                display: "flex",
                flexDirection: "column",
                gap: 2,
                transition: "transform 120ms ease, box-shadow 120ms ease",
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                }}
              >
                {stage.label}
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 2 }}>
                <span
                  style={{
                    fontSize: 22,
                    fontWeight: 700,
                    fontFamily: "var(--font-mono)",
                    fontVariantNumeric: "tabular-nums",
                    color: stage.color,
                  }}
                >
                  {stage.count}
                </span>
                <span
                  style={{
                    fontSize: 11,
                    fontFamily: "var(--font-mono)",
                    fontVariantNumeric: "tabular-nums",
                    color: "var(--text-muted)",
                  }}
                >
                  {stage.pct}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ fontSize: 12, color: "var(--text-secondary)", display: "flex", justifyContent: "space-between" }}>
        <span>
          <strong>{triagedPct}% do ruído bruto foi triado</strong> ou mitigado.
        </span>
        <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
          Restam {criticalOpen} críticos que impedem conformidade
        </span>
      </div>
    </div>
  );
}
