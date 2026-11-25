import { useEffect, useMemo, useState } from "react";

export interface CockpitRepo {
  project_key: string;
  name: string;
  default_branch?: string;
  languages?: string[];
  gate_status?: "PASSED" | "FAILED";
  severities?: { BLOCKER?: number; CRITICAL?: number; MAJOR?: number; MINOR?: number };
  trend?: number[];
}

export interface CockpitIssue {
  issue_id: string;
  rule_id: string;
  severity: string;
  confidence?: string;
  cwe?: string;
  file_path: string;
  start_line?: number;
  message: string;
  snippet?: string;
  status: string;
  flowSteps?: Array<{ file: string; line: number; kind: string; detail: string }>;
}

export function CockpitPage({
  repos,
  issues,
  onTriage,
}: {
  repos: CockpitRepo[];
  issues: CockpitIssue[];
  onTriage?: (issueId: string, status: string) => void;
}) {
  const [selectedRepo, setSelectedRepo] = useState<CockpitRepo | null>(null);
  const [gateFilter, setGateFilter] = useState<"ALL" | "FAILED" | "PASSED">("ALL");
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<"NEW_CODE" | "BASELINE">("NEW_CODE");
  const [selectedIssue, setSelectedIssue] = useState<CockpitIssue | null>(issues[0] ?? null);
  const [stepIdx, setStepIdx] = useState(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!selectedRepo || !selectedIssue) return;
      if (e.key === "ArrowLeft") setStepIdx((s) => Math.max(0, s - 1));
      if (e.key === "ArrowRight") setStepIdx((s) => Math.min((selectedIssue.flowSteps?.length ?? 1) - 1, s + 1));
      if (e.key.toLowerCase() === "f") onTriage?.(selectedIssue.issue_id, "FALSE_POSITIVE");
      if (e.key.toLowerCase() === "r") onTriage?.(selectedIssue.issue_id, "OPEN");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedRepo, selectedIssue, onTriage]);

  const filteredRepos = useMemo(
    () =>
      repos.filter((r) => {
        if (gateFilter !== "ALL" && r.gate_status !== gateFilter) return false;
        if (search && !r.name.toLowerCase().includes(search.toLowerCase())) return false;
        return true;
      }),
    [repos, gateFilter, search],
  );

  const kpis = useMemo(() => {
    const failed = repos.filter((r) => r.gate_status === "FAILED").length;
    const crit = issues.filter((i) => i.severity === "CRITICAL" || i.severity === "BLOCKER").length;
    return { total: repos.length, failed, crit, blockedPrs: failed };
  }, [repos, issues]);

  return (
    <div style={{ background: "#090C10", color: "#E6EDF3", minHeight: "100vh", fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 16px", background: "#11161D", borderBottom: "1px solid #21262D" }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <strong style={{ letterSpacing: 1 }}>POLARIS</strong>
          <span style={{ color: "#8B949E", cursor: "pointer" }} onClick={() => setSelectedRepo(null)}>
            Organização {selectedRepo ? `/ ${selectedRepo.name}` : ""}
          </span>
        </div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: "#8B949E" }}>
          GitHub App Connected · Runtime OK
        </div>
      </header>

      {!selectedRepo ? (
        <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
            {[
              ["Repositórios Monitorados", kpis.total],
              ["Quality Gates Reprovados", kpis.failed],
              ["Vulnerabilidades Críticas", kpis.crit],
              ["Branches/PRs Bloqueados", kpis.blockedPrs],
            ].map(([label, val]) => (
              <div key={String(label)} style={{ background: "#11161D", border: "1px solid #21262D", borderRadius: 6, padding: 12 }}>
                <div style={{ fontSize: 12, color: "#8B949E" }}>{label}</div>
                <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>{val}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            {(["ALL", "FAILED", "PASSED"] as const).map((g) => (
              <button key={g} onClick={() => setGateFilter(g)} style={{ background: gateFilter === g ? "#21262D" : "#11161D", color: "#E6EDF3", border: "1px solid #21262D", padding: "6px 12px", borderRadius: 4, cursor: "pointer" }}>
                {g === "ALL" ? "Todos" : g === "FAILED" ? "Gate Reprovado" : "Gate Aprovado"}
              </button>
            ))}
            <input placeholder="Buscar repositório..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ background: "#11161D", color: "#E6EDF3", border: "1px solid #21262D", padding: "6px 10px", borderRadius: 4, flex: 1 }} />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {filteredRepos.map((r) => (
              <div key={r.project_key} onClick={() => setSelectedRepo(r)} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "#11161D", border: "1px solid #21262D", borderRadius: 6, padding: 12, cursor: "pointer" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{r.name}</div>
                  <div style={{ fontSize: 12, color: "#8B949E", fontFamily: "'JetBrains Mono', monospace" }}>
                    {r.default_branch ?? "main"} · {(r.languages ?? []).join(", ")}
                  </div>
                </div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: r.gate_status === "FAILED" ? "#F85149" : "#3FB950" }}>
                  {r.gate_status ?? "PASSED"}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 45px)" }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", padding: "8px 16px", background: "#11161D", borderBottom: "1px solid #21262D" }}>
            <button onClick={() => setSelectedRepo(null)} style={{ background: "#21262D", color: "#E6EDF3", border: "none", padding: "4px 10px", borderRadius: 4, cursor: "pointer" }}>
              ← Todas as Aplicações
            </button>
            <button onClick={() => setMode(mode === "NEW_CODE" ? "BASELINE" : "NEW_CODE")} style={{ background: "#11161D", color: "#E6EDF3", border: "1px solid #21262D", padding: "4px 10px", borderRadius: 4, cursor: "pointer" }}>
              {mode === "NEW_CODE" ? "New Code" : "Baseline"}
            </button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "240px 1fr 320px", flex: 1, overflow: "hidden" }}>
            <aside style={{ borderRight: "1px solid #21262D", padding: 10, overflowY: "auto" }}>
              {issues.map((i) => (
                <div key={i.issue_id} onClick={() => { setSelectedIssue(i); setStepIdx(0); }} style={{ padding: 6, borderRadius: 4, cursor: "pointer", background: selectedIssue?.issue_id === i.issue_id ? "#21262D" : "transparent", fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>
                  {i.file_path}:{i.start_line ?? 1}
                </div>
              ))}
            </aside>
            <main style={{ padding: 16, overflowY: "auto", fontFamily: "'JetBrains Mono', monospace", fontSize: 13 }}>
              {selectedIssue ? (
                <>
                  <div style={{ background: "#11161D", border: "1px solid #21262D", padding: 12, borderRadius: 6, marginBottom: 12 }}>
                    <strong>{selectedIssue.rule_id}</strong> ({selectedIssue.severity}) {selectedIssue.cwe ?? ""}
                    <div style={{ color: "#8B949E", marginTop: 4 }}>{selectedIssue.message}</div>
                  </div>
                  <pre style={{ background: "#11161D", border: "1px solid #21262D", padding: 12, borderRadius: 6, overflowX: "auto" }}>
                    {selectedIssue.snippet ?? `// ${selectedIssue.file_path}:${selectedIssue.start_line ?? 1}`}
                  </pre>
                </>
              ) : (
                <div>Selecione uma issue.</div>
              )}
            </main>
            <aside style={{ borderLeft: "1px solid #21262D", padding: 12, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Taint Path Stepper</div>
                {(selectedIssue?.flowSteps ?? []).map((s, idx) => (
                  <div key={idx} style={{ padding: 6, background: idx === stepIdx ? "#21262D" : "transparent", fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}>
                    {s.kind}: {s.file}:{s.line}
                  </div>
                ))}
              </div>
              {selectedIssue && (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button onClick={() => onTriage?.(selectedIssue.issue_id, "FALSE_POSITIVE")}>False Positive (F)</button>
                    <button onClick={() => onTriage?.(selectedIssue.issue_id, "ACCEPTED_RISK")}>Accept Risk</button>
                    <button onClick={() => onTriage?.(selectedIssue.issue_id, "OPEN")}>Reopen (R)</button>
                  </div>
                  <button
                    onClick={() => fetch(`/api/issues/${selectedIssue.issue_id}/ai-analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(selectedIssue) })}
                    style={{ background: "#1F6FEB", color: "#FFFFFF", border: "none", padding: "6px 10px", borderRadius: 4, cursor: "pointer" }}
                  >
                    ✦ Explicar &amp; Sugerir Ajuste
                  </button>
                  <button
                    onClick={() => navigator.clipboard?.writeText(`${selectedIssue.rule_id} (${selectedIssue.cwe ?? "N/A"})\n${selectedIssue.snippet ?? ""}`)}
                    style={{ background: "#21262D", color: "#E6EDF3", border: "1px solid #30363D", padding: "6px 10px", borderRadius: 4, cursor: "pointer" }}
                  >
                    Copiar Prompt Cirúrgico
                  </button>
                </div>
              )}
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
