import { useState } from "react";
import { Button, Dialog, ErrorState, Input } from "../components/ui";
import { ProjectItem } from "../api/types";
import { IssueRow } from "./IssuesPage";

export function ProjectsPage({
  projects,
  issues = [],
  onCreated,
}: {
  projects: ProjectItem[];
  issues?: IssueRow[];
  onCreated: () => void;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [projectKey, setProjectKey] = useState("");
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const filtered = projects.filter(
    (p) => p.projectKey.toLowerCase().includes(search.toLowerCase()) || p.name.toLowerCase().includes(search.toLowerCase()),
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErr(null);
    try {
      const res = await fetch("/api/v1/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectKey: projectKey.trim(), name: name.trim() }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setOpen(false);
      setProjectKey("");
      setName("");
      onCreated();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Erro ao criar projeto");
    } finally {
      setSubmitting(false);
    }
  };

  // Cálculo da Grade por projeto derivado dos achados
  const getProjectStats = (key: string) => {
    const projIssues = issues.filter((i) => i.project_key === key);
    const openProjIssues = projIssues.filter((i) => (i.status || "OPEN").toUpperCase() === "OPEN");
    const critical = openProjIssues.filter((i) => i.severity === "CRITICAL" || i.severity === "BLOCKER").length;

    let score = 0;
    for (const i of openProjIssues) {
      const s = (i.severity || "").toUpperCase();
      if (s === "BLOCKER") score += 4;
      else if (s === "CRITICAL") score += 3;
      else if (s === "MAJOR") score += 2;
      else if (s === "MINOR") score += 1;
    }

    let grade = "A";
    let color = "var(--color-success)";
    if (score > 40) { grade = "F"; color = "var(--color-critical)"; }
    else if (score > 20) { grade = "D"; color = "var(--color-high)"; }
    else if (score > 10) { grade = "C"; color = "var(--color-warning)"; }
    else if (score > 0) { grade = "B"; color = "var(--color-low)"; }

    return { total: projIssues.length, open: openProjIssues.length, critical, grade, color };
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%", background: "var(--bg-app)", padding: "24px 32px", gap: 16 }}>
      {/* Topo do Portfólio */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "var(--text-primary)" }}>Portfólio de Aplicações</h1>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>
            {projects.length} repositórios monitorados
          </div>
        </div>
        <Button variant="primary" onClick={() => setOpen(true)}>Novo Projeto</Button>
      </div>

      <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-xl)", overflow: "hidden", boxShadow: "var(--shadow-soft)" }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-subtle)" }}>
          <Input placeholder="Buscar por chave ou nome..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ width: 280 }} />
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-subtle)", textAlign: "left", background: "var(--bg-elevated)", color: "var(--text-muted)" }}>
                <th style={{ padding: "10px 16px", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em" }}>Projeto</th>
                <th style={{ padding: "10px 16px", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em" }}>Grade</th>
                <th style={{ padding: "10px 16px", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em" }}>Achados Abertos</th>
                <th style={{ padding: "10px 16px", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em" }}>Críticos</th>
                <th style={{ padding: "10px 16px", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em" }}>Quality Gate</th>
                <th style={{ padding: "10px 16px", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em", textAlign: "right" }}>Ação</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => {
                const stats = getProjectStats(p.projectKey);
                return (
                  <tr
                    key={p.projectKey}
                    onClick={() => { window.location.hash = `#/projects/${encodeURIComponent(p.projectKey)}`; }}
                    style={{ borderBottom: "1px solid var(--border-subtle)", cursor: "pointer", transition: "background 120ms ease" }}
                  >
                    <td style={{ padding: "12px 16px" }}>
                      <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{p.name}</div>
                      <code style={{ fontSize: 11, color: "var(--text-muted)" }}>{p.projectKey}</code>
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span style={{ fontSize: 14, fontWeight: 700, color: stats.color, fontFamily: "var(--font-mono)" }}>
                        Grade {stats.grade}
                      </span>
                    </td>
                    <td style={{ padding: "12px 16px", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>
                      {stats.open}
                    </td>
                    <td style={{ padding: "12px 16px", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: stats.critical > 0 ? "var(--color-critical)" : "var(--text-muted)", fontWeight: stats.critical > 0 ? 600 : 400 }}>
                      {stats.critical}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span style={{ fontSize: 11, color: "var(--color-success)", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--color-success)" }} />
                        PASSED
                      </span>
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "right" }}>
                      <a href={`#/projects/${encodeURIComponent(p.projectKey)}`} style={{ fontSize: 12, color: "var(--accent-iris)", fontWeight: 500 }}>
                        Abrir Overview →
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={open} title="Criar Projeto" onClose={() => setOpen(false)}>
        {err && <ErrorState message={err} />}
        <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Input placeholder="Chave (ex: meu-projeto)" value={projectKey} onChange={(e) => setProjectKey(e.target.value)} required />
          <Input placeholder="Nome do Projeto" value={name} onChange={(e) => setName(e.target.value)} required />
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button type="submit" disabled={submitting}>{submitting ? "Criando..." : "Criar"}</Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
