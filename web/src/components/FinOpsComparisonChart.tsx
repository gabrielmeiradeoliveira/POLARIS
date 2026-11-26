import React from "react";

export interface FinOpsComparisonChartProps {
  estimatedTokens: number;
  actualTokens: number;
  cached?: boolean;
  actualInputTokens?: number;
  actualOutputTokens?: number;
}

export function FinOpsComparisonChart({
  estimatedTokens,
  actualTokens,
  cached = false,
  actualInputTokens = 0,
  actualOutputTokens = 0,
}: FinOpsComparisonChartProps) {
  const maxTokens = Math.max(1, estimatedTokens, actualTokens);
  const estWidth = Math.max(8, (estimatedTokens / maxTokens) * 100);
  const actWidth = cached ? 0 : Math.max(8, (actualTokens / maxTokens) * 100);

  const savedTokens = cached ? estimatedTokens : Math.max(0, estimatedTokens - actualTokens);
  const savedPct = Math.round((savedTokens / Math.max(1, estimatedTokens)) * 100);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        width: "100%",
        fontFamily: "var(--font-mono)",
        fontSize: 12,
      }}
      role="img"
      aria-label={`Comparação FinOps: Previsto ${estimatedTokens}t, Real ${actualTokens}t, Economia ${savedPct}%`}
    >
      {/* Barra de Previsto */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 64, color: "var(--text-muted)", fontSize: 11, flexShrink: 0 }}>Previsto</span>
        <div style={{ flex: 1, height: 10, background: "var(--bg-muted)", borderRadius: 3, overflow: "hidden" }}>
          <div style={{ width: `${estWidth}%`, height: "100%", background: "var(--border-strong)" }} />
        </div>
        <span style={{ minWidth: 60, textAlign: "right", fontVariantNumeric: "tabular-nums", color: "var(--text-secondary)" }}>
          ~{estimatedTokens}t
        </span>
      </div>

      {/* Barra de Real */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 64, color: "var(--text-muted)", fontSize: 11, flexShrink: 0 }}>Real</span>
        <div style={{ flex: 1, height: 10, background: "var(--bg-muted)", borderRadius: 3, overflow: "hidden" }}>
          <div
            style={{
              width: `${actWidth}%`,
              height: "100%",
              background: cached ? "var(--color-success)" : "var(--accent-iris)",
            }}
          />
        </div>
        <span style={{ minWidth: 60, textAlign: "right", fontVariantNumeric: "tabular-nums", color: cached ? "var(--color-success)" : "var(--text-primary)", fontWeight: 600 }}>
          {cached ? "0t (Hit)" : `${actualTokens}t`}
        </span>
      </div>

      {/* Detalhes de Telemetria */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
        <span>
          {cached
            ? "100% dos tokens economizados via Cache Persistente"
            : `${actualInputTokens} in + ${actualOutputTokens} out (${savedPct > 0 ? `-${savedPct}% tokens` : "consumo nominal"})`}
        </span>
        {savedTokens > 0 && (
          <span style={{ color: "var(--color-success)", fontWeight: 600 }}>
            +{savedTokens}t economizados
          </span>
        )}
      </div>
    </div>
  );
}
