import React from "react";

export interface TaintStep {
  file: string;
  line: number;
  kind?: string;
  detail?: string;
}

export function TaintTrail({
  steps,
  currentIdx,
  onSelectStep,
}: {
  steps: TaintStep[];
  currentIdx?: number;
  onSelectStep?: (idx: number) => void;
}) {
  if (!steps || steps.length === 0) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0, position: "relative" }}>
      {steps.map((step, idx) => {
        const isFirst = idx === 0;
        const isLast = idx === steps.length - 1;
        const isSelected = currentIdx === idx;

        let stageLabel = step.kind || (isFirst ? "SOURCE" : isLast ? "SINK" : "PROPAGATION");
        const stageUpper = stageLabel.toUpperCase();

        let markerColor = "var(--text-muted)";
        let badgeBg = "var(--bg-muted)";
        let badgeColor = "var(--text-secondary)";

        if (stageUpper.includes("SOURCE") || isFirst) {
          stageLabel = "SOURCE";
          markerColor = "var(--accent-cyan)";
          badgeBg = "var(--accent-cyan-bg)";
          badgeColor = "var(--accent-cyan)";
        } else if (stageUpper.includes("SINK") || isLast) {
          stageLabel = "SINK";
          markerColor = "var(--color-critical)";
          badgeBg = "var(--color-critical-bg)";
          badgeColor = "var(--color-critical)";
        } else {
          stageLabel = "STEP";
          markerColor = "var(--border-strong)";
          badgeBg = "var(--bg-muted)";
          badgeColor = "var(--text-secondary)";
        }

        return (
          <div
            key={idx}
            onClick={onSelectStep ? () => onSelectStep(idx) : undefined}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
              padding: "6px 8px",
              borderRadius: "var(--radius-sm)",
              cursor: onSelectStep ? "pointer" : "default",
              background: isSelected ? "var(--bg-elevated)" : "transparent",
              position: "relative",
            }}
          >
            {/* Coluna do Trilho SVG com Ponto e Seta Conectora */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                width: 14,
                flexShrink: 0,
                alignSelf: "stretch",
              }}
            >
              <div
                style={{
                  width: stageLabel === "STEP" ? 6 : 8,
                  height: stageLabel === "STEP" ? 6 : 8,
                  borderRadius: "50%",
                  background: markerColor,
                  border: isSelected ? "2px solid var(--text-primary)" : "none",
                  marginTop: 4,
                  flexShrink: 0,
                  zIndex: 2,
                }}
              />
              {!isLast && (
                <div
                  style={{
                    width: 1.5,
                    background: "var(--border-subtle)",
                    flex: 1,
                    marginTop: 2,
                    marginBottom: 2,
                  }}
                />
              )}
            </div>

            {/* Conteúdo do Passo */}
            <div style={{ flex: 1, minWidth: 0, paddingBottom: isLast ? 0 : 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginBottom: 2 }}>
                <span
                  style={{
                    display: "inline-block",
                    padding: "1px 6px",
                    borderRadius: 4,
                    fontSize: 10,
                    fontWeight: 700,
                    fontFamily: "var(--font-mono)",
                    background: badgeBg,
                    color: badgeColor,
                    letterSpacing: 0.5,
                  }}
                >
                  {stageLabel}
                </span>
                <code
                  style={{
                    fontSize: 12,
                    fontFamily: "var(--font-mono)",
                    fontVariantNumeric: "tabular-nums",
                    color: "var(--text-primary)",
                  }}
                >
                  {step.file}:{step.line}
                </code>
              </div>
              {step.detail && (
                <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.4 }}>
                  {step.detail}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
