import React, { useEffect, useState } from "react";
import { Button, Header, StatusIndicator } from "../components/ui";
import { Icon } from "../components/ui/Icons";

const NAV_GROUPS = [
  {
    title: "WORKSPACE",
    items: [
      { href: "#/", label: "Overview", key: "home", icon: "home" as const },
      { href: "#/projects", label: "Projetos", key: "projects", icon: "folder" as const },
      { href: "#/issues", label: "Findings", key: "issues", icon: "shield" as const },
    ],
  },
  {
    title: "QUALITY MANAGEMENT",
    items: [
      { href: "#/rules", label: "Regras", key: "rules", icon: "book" as const },
      { href: "#/profiles", label: "Quality Profiles", key: "profiles", icon: "sliders" as const },
      { href: "#/gates", label: "Quality Gates", key: "gates", icon: "check" as const },
    ],
  },
  {
    title: "SYSTEM",
    items: [
      { href: "#/admin", label: "Administração", key: "admin", icon: "sliders" as const },
      { href: "#/status", label: "Status", key: "status", icon: "activity" as const },
    ],
  },
];

export function AppLayout({
  activeRoute,
  version,
  readyStatus,
  children,
}: {
  activeRoute: string;
  version?: string;
  readyStatus?: string;
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    const saved = localStorage.getItem("polaris-theme");
    return saved === "light" ? "light" : "dark";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("polaris-theme", theme);
  }, [theme]);

  return (
    <div className="polaris-shell">
      <aside className="polaris-sidebar" style={{ width: collapsed ? 64 : 232 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: collapsed ? "center" : "space-between", padding: "8px 6px 16px", borderBottom: "1px solid var(--border-subtle)", marginBottom: 14 }}>
          {!collapsed && (
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <polygon points="12,2 21,7 21,17 12,22 3,17 3,7" stroke="var(--color-primary)" strokeWidth="2" />
                <circle cx="12" cy="12" r="3" fill="var(--color-primary)" />
              </svg>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, letterSpacing: "0.02em", color: "var(--text-primary)" }}>POLARIS</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>AppSec v{version ?? "2.0.0"}</div>
              </div>
            </div>
          )}
          <Button variant="ghost" size="sm" onClick={() => setCollapsed(!collapsed)} aria-label="Alternar barra lateral">
            <Icon name="menu" />
          </Button>
        </div>

        <nav aria-label="Navegação principal" style={{ display: "flex", flexDirection: "column", gap: 16, flex: 1 }}>
          {NAV_GROUPS.map((group) => (
            <div key={group.title}>
              {!collapsed && (
                <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", padding: "0 10px 6px", letterSpacing: "0.04em" }}>
                  {group.title}
                </div>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                {group.items.map((item) => {
                  const active = activeRoute === item.key || (item.key === "projects" && activeRoute === "project-detail");
                  return (
                    <a
                      key={item.key}
                      href={item.href}
                      title={collapsed ? item.label : undefined}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: collapsed ? "center" : "flex-start",
                        gap: 10,
                        padding: "8px 10px",
                        borderRadius: "var(--radius-md)",
                        fontSize: 13,
                        fontWeight: active ? 600 : 500,
                        background: active ? "var(--color-primary-subtle)" : "transparent",
                        color: active ? "var(--color-primary)" : "var(--text-secondary)",
                        textDecoration: "none",
                      }}
                    >
                      <Icon name={item.icon} />
                      {!collapsed && <span>{item.label}</span>}
                    </a>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12, display: "flex", justifyContent: collapsed ? "center" : "space-between", alignItems: "center" }}>
          {!collapsed && <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Tema</span>}
          <Button variant="secondary" size="sm" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? "Claro" : "Escuro"}
          </Button>
        </div>
      </aside>
      <div className="polaris-main">
        <Header>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" }}>
            Static Analysis &amp; AppSec Workbench
          </div>
          <StatusIndicator
            status={readyStatus === "READY" ? "ok" : readyStatus ? "error" : "warn"}
            label={readyStatus === "READY" ? "PostgreSQL Conectado" : readyStatus ?? "Verificando..."}
          />
        </Header>
        <main className="polaris-content">{children}</main>
      </div>
    </div>
  );
}
