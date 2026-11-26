import React, { useEffect, useState } from "react";
import { Button, Header, StatusIndicator } from "../components/ui";
import { Icon } from "../components/ui/Icons";
import { PolarisLogo } from "../components/PolarisLogo";

const NAV_GROUPS = [
  {
    title: "WORKSPACE",
    items: [
      { href: "#/", label: "Overview", key: "home", icon: "home" as const },
      { href: "#/projects", label: "Projetos", key: "projects", icon: "folder" as const },
      { href: "#/issues", label: "Findings", key: "issues", icon: "shield" as const },
      { href: "#/pull-requests", label: "Pull Requests", key: "pull-requests", icon: "shield" as const },
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

function SunIcon({ active }: { active: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" style={{ color: active ? "var(--text-primary)" : "var(--text-muted)" }}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

function MoonIcon({ active }: { active: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ color: active ? "var(--text-primary)" : "var(--text-muted)" }}>
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function ThemeToggle({ theme, onToggle }: { theme: "dark" | "light"; onToggle: () => void }) {
  const isDark = theme === "dark";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label={isDark ? "Ativar tema claro" : "Ativar tema escuro"}
      title={isDark ? "Tema claro" : "Tema escuro"}
      onClick={onToggle}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        background: "transparent",
        border: "1px solid var(--border-subtle)",
        borderRadius: 999,
        padding: "3px 7px",
        cursor: "pointer",
        lineHeight: 0,
      }}
    >
      <SunIcon active={!isDark} />
      <span
        aria-hidden="true"
        style={{
          position: "relative",
          display: "inline-block",
          width: 30,
          height: 16,
          borderRadius: 999,
          background: "var(--bg-muted)",
          border: "1px solid var(--border-subtle)",
        }}
      >
        <span
          style={{
            position: "absolute",
            top: 2,
            left: isDark ? 16 : 2,
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: "var(--text-primary)",
            transition: "left 150ms ease",
          }}
        />
      </span>
      <MoonIcon active={isDark} />
    </button>
  );
}

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
              <PolarisLogo size={24} />
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, letterSpacing: "0.02em", color: "var(--text-primary)" }}>POLARIS</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{version ? `AppSec v${version}` : "versão indisponível"}</div>
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
      </aside>
      <div className="polaris-main">
        <Header>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" }}>
            Static Analysis &amp; AppSec Workbench
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {readyStatus && (
              <StatusIndicator
                status={readyStatus === "READY" ? "ok" : "error"}
                label={readyStatus === "READY" ? "PostgreSQL Conectado" : readyStatus}
              />
            )}
            <ThemeToggle theme={theme} onToggle={() => setTheme(theme === "dark" ? "light" : "dark")} />
          </div>
        </Header>
        <main className="polaris-content">{children}</main>
      </div>
    </div>
  );
}
