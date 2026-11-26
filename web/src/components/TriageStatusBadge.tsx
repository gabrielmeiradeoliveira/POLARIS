import React from "react";

export interface TriageStatusBadgeProps {
  status: string;
  expiresAt?: string | null;
}

export function TriageStatusBadge({ status, expiresAt }: TriageStatusBadgeProps) {
  const norm = status?.toUpperCase?.() || status;

  // Formatação de data se fornecida
  let formattedDate = "";
  let dateTitle = "";
  if (expiresAt) {
    try {
      const d = new Date(expiresAt);
      if (!isNaN(d.getTime())) {
        const day = String(d.getUTCDate()).padStart(2, "0");
        const month = String(d.getUTCMonth() + 1).padStart(2, "0");
        const year = d.getUTCFullYear();
        formattedDate = `${day}/${month}`;
        dateTitle = `Expira em ${day}/${month}/${year}`;
      }
    } catch {
      // fallback sem data
    }
  }

  // Estilos conforme Seção 5.2 do Blueprint v3.6.0
  let label = norm;
  let bg = "var(--bg-muted)";
  let color = "var(--text-secondary)";
  let dotColor = "var(--text-muted)";
  let border = "1px solid var(--border-subtle)";

  switch (norm) {
    case "OPEN":
      label = "Aberto";
      bg = "rgba(88, 166, 255, 0.14)";
      color = "var(--color-low)";
      dotColor = "var(--color-low)";
      border = "1px solid rgba(88, 166, 255, 0.28)";
      break;
    case "ACCEPTED_RISK":
      label = "Risco Aceito";
      bg = "var(--color-warning-bg)";
      color = "var(--color-warning)";
      dotColor = "var(--color-warning)";
      border = "1px solid rgba(210, 153, 34, 0.28)";
      break;
    case "FALSE_POSITIVE":
      label = "Falso Positivo";
      bg = "var(--bg-muted)";
      color = "var(--text-muted)";
      dotColor = "var(--text-muted)";
      border = "1px solid var(--border-subtle)";
      break;
    case "FIXED":
      label = "Corrigido";
      bg = "var(--color-success-bg)";
      color = "var(--color-success)";
      dotColor = "var(--color-success)";
      border = "1px solid rgba(63, 185, 80, 0.28)";
      break;
    // Fallbacks para estados legados
    case "CONFIRMED":
      label = "Confirmado";
      bg = "rgba(88, 166, 255, 0.14)";
      color = "var(--color-low)";
      dotColor = "var(--color-low)";
      border = "1px solid rgba(88, 166, 255, 0.28)";
      break;
    case "RESOLVED":
      label = "Resolvido";
      bg = "var(--color-success-bg)";
      color = "var(--color-success)";
      dotColor = "var(--color-success)";
      border = "1px solid rgba(63, 185, 80, 0.28)";
      break;
    case "WONT_FIX":
      label = "Não Corrigir";
      bg = "var(--bg-muted)";
      color = "var(--text-muted)";
      dotColor = "var(--text-muted)";
      border = "1px solid var(--border-subtle)";
      break;
    default:
      label = norm || "-";
      break;
  }

  return (
    <span
      title={dateTitle || undefined}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "2px 8px",
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        whiteSpace: "nowrap",
        background: bg,
        color: color,
        border: border,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: dotColor,
          flexShrink: 0,
        }}
      />
      <span>{label}</span>
      {norm === "ACCEPTED_RISK" && formattedDate && (
        <span style={{ fontWeight: 500, opacity: 0.85, marginLeft: 2 }}>
          · até {formattedDate}
        </span>
      )}
    </span>
  );
}
