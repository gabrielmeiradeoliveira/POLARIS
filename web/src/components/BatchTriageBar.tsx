import React from "react";
import { Button } from "../components/ui";

export type TriageActionStatus = "OPEN" | "ACCEPTED_RISK" | "FALSE_POSITIVE" | "FIXED";

export interface BatchTriageBarProps {
  selectedCount: number;
  onClear: () => void;
  onAction: (status: TriageActionStatus) => void;
}

export function BatchTriageBar({ selectedCount, onClear, onAction }: BatchTriageBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: 20,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 40,
        maxWidth: "calc(100vw - 32px)",
        width: "max-content",
        background: "var(--bg-surface)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-floating)",
        padding: "10px 14px",
        display: "flex",
        alignItems: "center",
        gap: 10,
        flexWrap: "wrap",
      }}
    >
      {/* 1. Contador de selecionados */}
      <span
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: "var(--text-primary)",
          fontVariantNumeric: "tabular-nums",
          whiteSpace: "nowrap",
        }}
      >
        {selectedCount} {selectedCount === 1 ? "achado selecionado" : "achados selecionados"}
      </span>

      {/* 2. Ação de desmarcar */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onClear}
        style={{ color: "var(--text-muted)", padding: "4px 8px" }}
      >
        Limpar
      </Button>

      {/* 3. Divisor vertical */}
      <div
        style={{
          width: 1,
          height: 20,
          background: "var(--border-subtle)",
          flexShrink: 0,
        }}
      />

      {/* 4. Grupo de ações de triagem */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onAction("OPEN")}
          style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--color-low)",
              flexShrink: 0,
            }}
          />
          Reabrir
        </Button>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => onAction("ACCEPTED_RISK")}
          style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--color-warning)",
              flexShrink: 0,
            }}
          />
          Aceitar Risco
        </Button>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => onAction("FALSE_POSITIVE")}
          style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--text-muted)",
              flexShrink: 0,
            }}
          />
          Falso Positivo
        </Button>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => onAction("FIXED")}
          style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "var(--color-success)",
              flexShrink: 0,
            }}
          />
          Corrigido
        </Button>
      </div>
    </div>
  );
}
