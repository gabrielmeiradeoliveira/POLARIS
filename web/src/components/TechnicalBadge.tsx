import React from "react";

export function TechnicalBadge({
  severity,
}: {
  severity: string;
}) {
  const norm = (severity || "").toUpperCase();

  let borderColor = "var(--text-muted)";
  let bg = "var(--bg-muted)";
  let color = "var(--text-secondary)";

  if (norm === "BLOCKER" || norm === "CRITICAL") {
    borderColor = "var(--color-critical)";
    bg = "var(--color-critical-bg)";
    color = "var(--color-critical)";
  } else if (norm === "MAJOR" || norm === "HIGH") {
    borderColor = "var(--color-high)";
    bg = "var(--color-high-bg)";
    color = "var(--color-high)";
  } else if (norm === "MINOR" || norm === "MEDIUM") {
    borderColor = "var(--color-warning)";
    bg = "var(--color-warning-bg)";
    color = "var(--color-warning)";
  } else {
    borderColor = "var(--color-low)";
    bg = "var(--color-low-bg)";
    color = "var(--color-low)";
  }

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "2px 6px",
        borderRadius: "var(--radius-sm)",
        border: "1px solid var(--border-subtle)",
        borderLeft: `3px solid ${borderColor}`,
        background: bg,
        color: color,
        fontFamily: "var(--font-mono)",
        fontSize: 11,
        fontWeight: 600,
        fontVariantNumeric: "tabular-nums",
        minWidth: 78,
        textAlign: "center",
        lineHeight: 1.2,
      }}
    >
      {norm}
    </span>
  );
}
