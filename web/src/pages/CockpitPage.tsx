import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Input } from "../components/ui";
import { TaintTrail } from "../components/TaintTrail";
import { CodeEvidenceBlock } from "../components/CodeEvidenceBlock";

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
  const [activeCodeLine, setActiveCodeLine] = useState<number | undefined>(undefined);
  const [stepIdx, setStepIdx] = useState(0);
  const [aiResult, setAiResult] = useState<Record<string, any> | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [copiedSnippet, setCopiedSnippet] = useState(false);

  const selectedIndex = useMemo(() => {
    if (!selectedIssue) return -1;
    return issues.findIndex((i) => i.issue_id === selectedIssue.issue_id);
  }, [issues, selectedIssue]);

  const selectByIndex = (idx: number) => {
    if (idx >= 0 && idx < issues.length) {
      const target = issues[idx];
      setSelectedIssue(target);
      setActiveCodeLine(target.start_line);
      setStepIdx(0);
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!selectedRepo || !selectedIssue) return;
      const tag = (document.activeElement?.tagName || "").toUpperCase();
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (document.activeElement as HTMLElement)?.isContentEditable) {
        return;
      }

      if (e.key === "Escape") {
        setSelectedRepo(null);
        return;
      }
      if (e.key === "j" || e.key === "J" || e.key === "ArrowDown") {
        e.preventDefault();
        selectByIndex(selectedIndex + 1);
        return;
      }
      if (e.key === "k" || e.key === "K" || e.key === "ArrowUp") {
        e.preventDefault();
        selectByIndex(selectedIndex - 1);
        return;
      }
      if (e.key === "f" || e.key === "F") {
        e.preventDefault();
        onTriage?.(selectedIssue.issue_id, "FALSE_POSITIVE");
        return;
      }
      if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        onTriage?.(selectedIssue.issue_id, "ACCEPTED_RISK");
        return;
      }
      if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        onTriage?.(selectedIssue.issue_id, "OPEN");
        return;
      }
      if (e.key === "ArrowLeft") {
        setStepIdx((s) => Math.max(0, s - 1));
      }
      if (e.key === "ArrowRight") {
        setStepIdx((s) => Math.min((selectedIssue.flowSteps?.length ?? 1) - 1, s + 1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedRepo, selectedIssue, selectedIndex, issues, onTriage]);

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
    <div style={{ background: "var(--bg-app)", color: "var(--text-primary)", minHeight: "100vh", fontFamily: "var(--font-sans)" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 16px", background: "var(--bg-surface)", borderBottom: "1px solid var(--border-subtle)" }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <strong style={{ letterSpacing: 1, color: "var(--text-primary)" }}>POLARIS</strong>
          <span style={{ color: "var(--text-muted)", cursor: "pointer" }} onClick={() => setSelectedRepo(null)}>
            Organização {selectedRepo ? `/ ${selectedRepo.name}` : ""}
          </span>
        </div>
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-muted)" }}>
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
              <div key={String(label)} style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: 12 }}>
                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{label}</div>
                <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--text-primary)", marginTop: 4 }}>{val}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            {(["ALL", "FAILED", "PASSED"] as const).map((g) => (
              <Button
                key={g}
                variant={gateFilter === g ? "primary" : "secondary"}
                size="sm"
                onClick={() => setGateFilter(g)}
              >
                {g === "ALL" ? "Todos" : g === "FAILED" ? "Gate Reprovado" : "Gate Aprovado"}
              </Button>
            ))}
            <Input
              placeholder="Buscar repositório..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ flex: 1 }}
            />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {filteredRepos.map((r) => (
              <div
                key={r.project_key}
                onClick={() => { setSelectedRepo(r); setSelectedIssue(issues[0] ?? null); }}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "var(--radius-md)",
                  padding: 12,
                  cursor: "pointer",
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{r.name}</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", marginTop: 2 }}>
                    {r.default_branch ?? "main"} · {(r.languages ?? []).join(", ")}
                  </div>
                </div>
                <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontVariantNumeric: "tabular-nums", color: r.gate_status === "FAILED" ? "var(--color-critical)" : "var(--color-success)" }}>
                  {r.gate_status ?? "PASSED"}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 45px)" }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", padding: "8px 16px", background: "var(--bg-surface)", borderBottom: "1px solid var(--border-subtle)" }}>
            <Button variant="secondary" size="sm" onClick={() => setSelectedRepo(null)}>
              ← Todas as Aplicações
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setMode(mode === "NEW_CODE" ? "BASELINE" : "NEW_CODE")}>
              {mode === "NEW_CODE" ? "New Code" : "Baseline"}
            </Button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "260px 1fr 340px", flex: 1, overflow: "hidden" }}>
            <aside style={{ borderRight: "1px solid var(--border-subtle)", padding: 10, overflowY: "auto", background: "var(--bg-surface)" }}>
              {issues.map((i) => (
                <div
                  key={i.issue_id}
                  onClick={() => { setSelectedIssue(i); setActiveCodeLine(i.start_line); setStepIdx(0); }}
                  style={{
                    padding: 8,
                    borderRadius: "var(--radius-sm)",
                    cursor: "pointer",
                    background: selectedIssue?.issue_id === i.issue_id ? "var(--bg-row-selected)" : "transparent",
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    fontVariantNumeric: "tabular-nums",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 6,
                    marginBottom: 4,
                  }}
                >
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {i.file_path}:{i.start_line ?? 1}
                  </span>
                  <Badge tone={i.severity === "CRITICAL" || i.severity === "BLOCKER" ? "error" : "warning"}>
                    {i.severity}
                  </Badge>
                </div>
              ))}
            </aside>
            <main style={{ padding: 16, overflowY: "auto", background: "var(--bg-app)" }}>
              {selectedIssue ? (
                <>
                  <div style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: 12, borderRadius: "var(--radius-md)", marginBottom: 12 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                      <strong style={{ color: "var(--text-primary)" }}>{selectedIssue.rule_id}</strong>
                      <Badge tone={selectedIssue.severity === "CRITICAL" || selectedIssue.severity === "BLOCKER" ? "error" : "warning"}>
                        {selectedIssue.severity}
                      </Badge>
                      {selectedIssue.cwe && <Badge tone="primary">{selectedIssue.cwe}</Badge>}
                    </div>
                    <div style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)", fontSize: 13, lineHeight: 1.4 }}>
                      {selectedIssue.message}
                    </div>
                  </div>

                  {/* Protagonismo do Código via CodeEvidenceBlock */}
                  <CodeEvidenceBlock
                    filePath={selectedIssue.file_path}
                    startLine={selectedIssue.start_line}
                    activeLine={activeCodeLine}
                    snippet={selectedIssue.snippet}
                  />
                </>
              ) : (
                <div style={{ color: "var(--text-muted)" }}>Selecione uma issue.</div>
              )}
            </main>
            <aside style={{ borderLeft: "1px solid var(--border-subtle)", padding: 12, display: "flex", flexDirection: "column", gap: 12, background: "var(--bg-surface)", overflowY: "auto" }}>
              {selectedIssue ? (
                <>
                  {/* Topo Fixo com Ações de Triagem + Botão da IA */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 10, borderBottom: "1px solid var(--border-subtle)", paddingBottom: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                      Triagem Imediata
                    </div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <Button size="sm" variant="secondary" onClick={() => onTriage?.(selectedIssue.issue_id, "OPEN")}>Reabrir</Button>
                      <Button size="sm" variant="secondary" onClick={() => onTriage?.(selectedIssue.issue_id, "ACCEPTED_RISK")}>Aceitar Risco</Button>
                      <Button size="sm" variant="secondary" onClick={() => onTriage?.(selectedIssue.issue_id, "FALSE_POSITIVE")}>Falso Positivo</Button>
                      <Button size="sm" variant="secondary" onClick={() => onTriage?.(selectedIssue.issue_id, "FIXED")}>Corrigido</Button>
                    </div>

                    <Button
                      variant="primary"
                      size="sm"
                      disabled={aiLoading}
                      onClick={async () => {
                        setAiLoading(true);
                        try {
                          const r = await fetch(`/api/issues/${selectedIssue.issue_id}/ai-analyze`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                              issue_id: selectedIssue.issue_id,
                              rule_id: selectedIssue.rule_id,
                              cwe: selectedIssue.cwe,
                              file_path: selectedIssue.file_path,
                              start_line: selectedIssue.start_line,
                              code_snippet: selectedIssue.snippet,
                              severity: selectedIssue.severity,
                              message: selectedIssue.message,
                            }),
                          });
                          setAiResult(await r.json());
                        } finally {
                          setAiLoading(false);
                        }
                      }}
                    >
                      {aiLoading ? "Analisando..." : "Explicar e sugerir ajuste"}
                    </Button>

                    {aiResult && (
                      <div style={{ background: "var(--bg-muted)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: 10, fontSize: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                          <Badge tone={aiResult.verdict === "CONFIRMED_EXPLOITABLE" ? "error" : aiResult.verdict === "LIKELY_FALSE_POSITIVE" ? "success" : "warning"}>
                            {aiResult.verdict ?? "NEEDS_REVIEW"}
                          </Badge>
                          <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>
                            {aiResult.max_tokens_applied >= 1000 ? "Legado 1200t" : "Moderno 500t"}
                          </span>
                          {aiResult.cached && <span style={{ color: "var(--color-success)", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>Em cache</span>}
                        </div>
                        <p style={{ margin: 0, color: "var(--text-primary)", lineHeight: 1.4 }}>{aiResult.summary || aiResult.raw_response}</p>
                        
                        {/* Comparativo Visual Antes (Vulnerável) -> Depois (Corrigido) */}
                        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 4 }}>
                          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-critical)" }}>
                            Antes (Linha {selectedIssue.start_line ?? 1}):
                          </div>
                          <pre style={{ margin: 0, background: "rgba(248, 81, 73, 0.08)", border: "1px solid rgba(248, 81, 73, 0.25)", color: "var(--color-critical)", padding: "6px 8px", borderRadius: "var(--radius-sm)", overflowX: "auto", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                            {selectedIssue.snippet || `Linha ${selectedIssue.start_line ?? 1}: Código vulnerável detectado`}
                          </pre>

                          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--color-success)", marginTop: 4 }}>
                            Depois (Sugestão Corrigida):
                          </div>
                          <pre style={{ margin: 0, background: "rgba(63, 185, 80, 0.08)", border: "1px solid rgba(63, 185, 80, 0.25)", color: "var(--color-success)", padding: "6px 8px", borderRadius: "var(--radius-sm)", overflowX: "auto", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                            {aiResult.suggested_snippet || "// Correção recomendada: sanitizar ou parametrizar entrada"}
                          </pre>
                        </div>

                        {aiResult.suggested_snippet && (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => {
                              navigator.clipboard?.writeText(aiResult.suggested_snippet);
                              setCopiedSnippet(true);
                              setTimeout(() => setCopiedSnippet(false), 1500);
                            }}
                            style={{ alignSelf: "flex-start", marginTop: 4 }}
                          >
                            {copiedSnippet ? "Copiado!" : "Copiar Correção"}
                          </Button>
                        )}
                      </div>
                    )}

                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigator.clipboard?.writeText(`${selectedIssue.rule_id} (${selectedIssue.cwe ?? "N/A"})\n${selectedIssue.snippet ?? ""}`)}
                        style={{ border: "1px solid var(--border-subtle)", color: "var(--text-secondary)", flex: 1 }}
                      >
                        Copiar prompt
                      </Button>
                    </div>

                    <div style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 10, color: "var(--text-muted)", flexWrap: "wrap" }}>
                      <span><kbd>J</kbd>/<kbd>K</kbd> navegar</span>
                      <span>·</span>
                      <span><kbd>F</kbd> falso positivo</span>
                      <span>·</span>
                      <span><kbd>A</kbd> aceitar</span>
                    </div>
                  </div>

                  {/* Fluxo Semântico SOURCE -> SINK Compacto e Colapsável */}
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--text-primary)", fontSize: 13, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span>SOURCE → SINK</span>
                      {selectedIssue?.flowSteps && selectedIssue.flowSteps.length > 0 && (
                        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{selectedIssue.flowSteps.length} passos</span>
                      )}
                    </div>
                    {selectedIssue?.flowSteps && selectedIssue.flowSteps.length > 0 ? (
                      <TaintTrail
                        steps={selectedIssue.flowSteps}
                        currentIdx={stepIdx}
                        onSelectStep={(idx) => {
                          setStepIdx(idx);
                          const step = selectedIssue.flowSteps?.[idx];
                          if (step && step.file === selectedIssue.file_path) {
                            setActiveCodeLine(step.line);
                          }
                        }}
                      />
                    ) : (
                      <div style={{ fontSize: 11, color: "var(--text-muted)", fontStyle: "italic", padding: "4px 0" }}>
                        Fluxo intra-procedural direto (sem propagação cross-file).
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div style={{ color: "var(--text-muted)", fontSize: 12 }}>Selecione uma issue para inspecionar.</div>
              )}
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
