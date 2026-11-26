import React from "react";

export function Button({
  children,
  variant = "primary",
  size = "md",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
}) {
  const bg =
    variant === "primary"
      ? "var(--btn-primary-bg)"
      : variant === "secondary"
        ? "var(--bg-surface)"
        : "transparent";
  const color =
    variant === "primary"
      ? "var(--btn-primary-text)"
      : "var(--text-primary)";
  const border =
    variant === "secondary"
      ? "1px solid var(--border-subtle)"
      : "1px solid transparent";
  const pad = size === "sm" ? "6px 12px" : "8px 16px";
  return (
    <button
      {...props}
      style={{
        background: bg,
        color,
        border,
        borderRadius: "var(--radius-md)",
        padding: pad,
        fontSize: size === "sm" ? 12 : 13,
        fontWeight: 500,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        lineHeight: 1.25,
        transition: "all 0.15s ease",
        cursor: props.disabled ? "not-allowed" : "pointer",
        opacity: props.disabled ? 0.6 : 1,
        ...props.style,
      }}
    >
      {children}
    </button>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      style={{
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-md)",
        padding: "7px 10px",
        fontSize: 13,
        background: "var(--bg-surface)",
        color: "var(--text-primary)",
        ...props.style,
      }}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      style={{
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-md)",
        padding: "7px 10px",
        fontSize: 13,
        background: "var(--bg-surface)",
        color: "var(--text-primary)",
        ...props.style,
      }}
    />
  );
}

export function Checkbox({ label, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
      <input type="checkbox" {...props} />
      <span>{label}</span>
    </label>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: "neutral" | "primary" | "success" | "warning" | "error";
}) {
  const map = {
    neutral: { bg: "var(--bg-muted)", color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" },
    primary: { bg: "var(--color-info-bg)", color: "var(--accent-cyan)", border: "1px solid var(--color-info-border)" },
    success: { bg: "var(--color-success-bg)", color: "var(--color-success)", border: "1px solid rgba(63, 185, 80, 0.28)" },
    warning: { bg: "var(--color-warning-bg)", color: "var(--color-warning)", border: "1px solid rgba(210, 153, 34, 0.28)" },
    error: { bg: "var(--color-error-bg)", color: "var(--color-error)", border: "1px solid rgba(248, 81, 73, 0.28)" },
  }[tone];
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 600,
        background: map.bg,
        color: map.color,
        border: map.border,
      }}
    >
      {children}
    </span>
  );
}

export function Card({ title, children, actions }: { title?: string; children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-lg)",
        padding: 16,
        marginBottom: 16,
      }}
    >
      {(title || actions) && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          {title && <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}

export function MetricCard({
  label,
  value,
  subtitle,
  tone = "neutral",
}: {
  label: string;
  value: string | number | null | undefined;
  subtitle?: string;
  tone?: "neutral" | "success" | "warning" | "error";
}) {
  const color =
    tone === "success"
      ? "var(--color-success)"
      : tone === "warning"
        ? "var(--color-warning)"
        : tone === "error"
          ? "var(--color-error)"
          : "var(--text-primary)";
  const display = value === null || value === undefined ? "Indisponível" : value;
  return (
    <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", padding: 14 }}>
      <div style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 4, fontVariantNumeric: "tabular-nums" }}>{display}</div>
      {subtitle && <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>{subtitle}</div>}
    </div>
  );
}

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  width?: string | number;
  render: (row: T) => React.ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  emptyText = "Nenhum registro encontrado.",
  onRowClick,
  rowSelection,
  rowOpacity,
}: {
  columns: Column<T>[];
  rows: T[];
  emptyText?: string;
  onRowClick?: (row: T) => void;
  rowSelection?: (row: T) => boolean;
  rowOpacity?: (row: T) => number | undefined;
}) {
  if (rows.length === 0) return <EmptyState message={emptyText} />;
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border-subtle)", textAlign: "left", color: "var(--text-secondary)" }}>
            {columns.map((c) => (
              <th
                key={c.key}
                style={{
                  padding: "7px 10px",
                  fontWeight: 600,
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                  background: "var(--bg-surface)",
                  width: c.width,
                }}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => {
            const isSelected = rowSelection ? rowSelection(row) : false;
            const customOpacity = rowOpacity ? rowOpacity(row) : undefined;
            const rowBg = isSelected ? "var(--bg-row-selected)" : "transparent";
            return (
              <tr
                key={idx}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                style={{
                  borderBottom: "1px solid var(--border-subtle)",
                  cursor: onRowClick ? "pointer" : "default",
                  background: rowBg,
                  opacity: isSelected ? 1 : customOpacity,
                }}
              >
                {columns.map((c) => (
                  <td key={c.key} style={{ padding: "7px 10px", width: c.width, fontSize: 13 }}>{c.render(row)}</td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({
  page,
  totalPages,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  onPageChange: (p: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, justifyContent: "flex-end" }}>
      <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Anterior</Button>
      <span style={{ fontSize: 12, color: "var(--text-secondary)", fontVariantNumeric: "tabular-nums" }}>Página {page} de {totalPages}</span>
      <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>Próxima</Button>
    </div>
  );
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: Array<{ id: string; label: string }>;
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border-subtle)", marginBottom: 16 }}>
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          style={{
            background: "transparent",
            border: "none",
            borderBottom: active === t.id ? "2px solid var(--accent-cyan)" : "2px solid transparent",
            padding: "8px 12px",
            fontSize: 13,
            fontWeight: active === t.id ? 600 : 500,
            color: active === t.id ? "var(--text-primary)" : "var(--text-secondary)",
            cursor: "pointer",
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Dialog({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: React.ReactNode }) {
  if (!open) return null;
  return (
    <div style={{ position: "fixed", inset: 0, background: "var(--bg-backdrop)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
      <div style={{ background: "var(--bg-surface)", borderRadius: "var(--radius-lg)", padding: 20, width: "100%", maxWidth: 480, border: "1px solid var(--border-subtle)", boxShadow: "var(--shadow-floating)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>{title}</h3>
          <Button variant="ghost" size="sm" onClick={onClose}>Fechar</Button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Drawer({
  open,
  title,
  onClose,
  children,
  nonBlocking = false,
}: {
  open: boolean;
  title: string | React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
  nonBlocking?: boolean;
}) {
  if (!open) return null;

  if (nonBlocking) {
    return (
      <div
        style={{
          width: 460,
          flexShrink: 0,
          background: "var(--bg-surface)",
          borderLeft: "1px solid var(--border-subtle)",
          padding: 20,
          overflowY: "auto",
          height: "calc(100vh - 120px)",
          position: "sticky",
          top: 76,
          borderRadius: "var(--radius-lg)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, borderBottom: "1px solid var(--border-subtle)", paddingBottom: 10 }}>
          <div style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>{title}</div>
          <Button variant="secondary" size="sm" onClick={onClose}>Fechar</Button>
        </div>
        {children}
      </div>
    );
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "var(--bg-backdrop)", display: "flex", justifyContent: "flex-end", zIndex: 50 }}>
      <div style={{ background: "var(--bg-surface)", width: "100%", maxWidth: 520, height: "100%", padding: 20, overflowY: "auto", borderLeft: "1px solid var(--border-subtle)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, borderBottom: "1px solid var(--border-subtle)", paddingBottom: 10 }}>
          <div style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{title}</div>
          <Button variant="secondary" size="sm" onClick={onClose}>Fechar</Button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  return <span title={text}>{children}</span>;
}

export function Breadcrumb({ items }: { items: Array<{ label: string; href?: string }> }) {
  return (
    <nav aria-label="Breadcrumb" style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 12 }}>
      {items.map((item, idx) => (
        <span key={idx}>
          {idx > 0 && " / "}
          {item.href ? <a href={item.href}>{item.label}</a> : <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{item.label}</span>}
        </span>
      ))}
    </nav>
  );
}

export function Skeleton({ height = 20 }: { height?: number }) {
  return <div style={{ height, background: "var(--bg-muted)", borderRadius: "var(--radius-sm)", marginBottom: 8 }} />;
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div style={{ padding: 24, textAlign: "center", color: "var(--text-secondary)", border: "1px dashed var(--border-subtle)", borderRadius: "var(--radius-md)" }}>
      {message}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" style={{ padding: 16, background: "var(--color-error-bg)", color: "var(--color-error)", borderRadius: "var(--radius-md)", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
      <span>Erro: {message}</span>
      {onRetry && <Button variant="secondary" size="sm" onClick={onRetry}>Tentar novamente</Button>}
    </div>
  );
}

export function StatusIndicator({ status, label }: { status: "ok" | "warn" | "error"; label: string }) {
  const color = status === "ok" ? "var(--color-success)" : status === "warn" ? "var(--color-warning)" : "var(--color-error)";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 500 }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />
      {label}
    </span>
  );
}

export function Sidebar({ children }: { children: React.ReactNode }) {
  return <aside className="polaris-sidebar">{children}</aside>;
}

export function Header({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return <header className="polaris-header" style={style}>{children}</header>;
}
