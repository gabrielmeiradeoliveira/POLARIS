import React, { useState } from "react";
import { Button, Dialog, ErrorState, Input } from "../components/ui";
import { TriageStatusBadge } from "./TriageStatusBadge";

export interface BatchTriageModalProps {
  open: boolean;
  targetStatus: "OPEN" | "ACCEPTED_RISK" | "FALSE_POSITIVE" | "FIXED";
  selectedCount: number;
  onClose: () => void;
  onSubmit: (reason: string, expiresAt?: string) => Promise<void>;
}

const STATUS_LABELS: Record<string, string> = {
  OPEN: "Reabrir",
  ACCEPTED_RISK: "Aceitar Risco",
  FALSE_POSITIVE: "Falso Positivo",
  FIXED: "Corrigido",
};

export function BatchTriageModal({
  open,
  targetStatus,
  selectedCount,
  onClose,
  onSubmit,
}: BatchTriageModalProps) {
  const [reason, setReason] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [touched, setTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const todayYYYYMMDD = new Date().toISOString().split("T")[0];
  const isValid = reason.trim().length >= 3;
  const statusLabel = STATUS_LABELS[targetStatus] || targetStatus;

  const handleClose = () => {
    if (submitting) return;
    setReason("");
    setExpiresAt("");
    setTouched(false);
    setSubmitError(null);
    onClose();
  };

  const handleSubmit = async () => {
    setTouched(true);
    if (!isValid) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      await onSubmit(reason.trim(), targetStatus === "ACCEPTED_RISK" && expiresAt ? expiresAt : undefined);
      setReason("");
      setExpiresAt("");
      setTouched(false);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Erro ao aplicar triagem em lote");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} title={`Triagem em lote — ${statusLabel}`} onClose={handleClose}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {submitError && <ErrorState message={submitError} />}

        {/* Resumo de escopo */}
        <div
          style={{
            background: "var(--bg-muted)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "10px 12px",
            fontSize: 13,
            color: "var(--text-secondary)",
            display: "flex",
            alignItems: "center",
            gap: 6,
            flexWrap: "wrap",
          }}
        >
          <span>Você está atualizando {selectedCount} achado(s) para o status</span>
          <TriageStatusBadge status={targetStatus} />.
        </div>

        {/* Campo Justificativa */}
        <div>
          <label
            htmlFor="batch-triage-reason"
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: "var(--text-secondary)",
              marginBottom: 6,
              display: "block",
            }}
          >
            Justificativa *
          </label>
          <textarea
            id="batch-triage-reason"
            disabled={submitting}
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              if (!touched) setTouched(true);
            }}
            placeholder="Descreva o motivo técnico ou decisão de negócio para trilha de auditoria..."
            style={{
              width: "100%",
              minHeight: 88,
              resize: "vertical",
              padding: "8px 10px",
              fontSize: 13,
              fontFamily: "var(--font-sans)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              background: "var(--bg-surface)",
              color: "var(--text-primary)",
              boxSizing: "border-box",
            }}
          />
          {touched && !isValid && (
            <div style={{ color: "var(--color-error)", fontSize: 12, margin: "4px 0 0" }}>
              Informe uma justificativa com pelo menos 3 caracteres.
            </div>
          )}
        </div>

        {/* Campo Expiração condicional */}
        {targetStatus === "ACCEPTED_RISK" && (
          <div>
            <label
              htmlFor="batch-triage-expires"
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--text-secondary)",
                marginBottom: 6,
                display: "block",
              }}
            >
              Expira em (opcional)
            </label>
            <Input
              id="batch-triage-expires"
              type="date"
              disabled={submitting}
              min={todayYYYYMMDD}
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              style={{ width: "100%", boxSizing: "border-box" }}
            />
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
              Opcional. Após esta data, o risco aceito volta a requerer revisão.
            </div>
          </div>
        )}

        {/* Rodapé de Ações */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
          <Button variant="secondary" disabled={submitting} onClick={handleClose}>
            Cancelar
          </Button>
          <Button
            variant="primary"
            disabled={submitting || !isValid}
            onClick={handleSubmit}
          >
            {submitting ? "Aplicando..." : "Confirmar triagem"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
