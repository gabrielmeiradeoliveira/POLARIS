import React, { useEffect, useMemo, useState } from "react";
import { Button, Drawer, ErrorState, Input, Pagination } from "../components/ui";
import { IssueAiAssistant } from "../components/IssueAiAssistant";
import { TriageStatusBadge } from "../components/TriageStatusBadge";
import { BatchTriageBar, TriageActionStatus } from "../components/BatchTriageBar";
import { BatchTriageModal } from "../components/BatchTriageModal";
import { PolarisCheckbox } from "../components/PolarisCheckbox";
import { TaintTrail } from "../components/TaintTrail";
import { CodeEvidenceBlock } from "../components/CodeEvidenceBlock";
import { TechnicalBadge } from "../components/TechnicalBadge";
import { parseRoute } from "../App";

export interface IssueRow {
  issue_id: string;
  project_key?: string;
  rule_id: string;
  language?: string;
  severity: string;
  status: string;
  file_path: string;
  start_line?: number;
  message: string;
  snippet?: string;
  cwe?: string;
  confidence?: "HIGH" | "MEDIUM" | "LOW";
  assignee?: string;
  triage_expires_at?: string | null;
  expires_at?: string | null;
}

export interface GroupedIssue {
  key: string;
  representative: IssueRow;
  items: IssueRow[];
  count: number;
}

function isVuln(i: IssueRow): boolean {
  return i.rule_id.includes("-SEC-");
}

function isBug(i: IssueRow): boolean {
  return !isVuln(i) && (i.rule_id.includes("-REL-") || i.severity === "BLOCKER" || i.severity === "CRITICAL");
}

export function IssuesPage({
  issues,
  onMutated,
}: {
  issues: IssueRow[];
  onMutated?: () => void;
}) {
  // Leitura inicial de deep links
  const initialNav = useMemo(() => parseRoute(window.location.hash), []);
  const initialQuery = initialNav.query;

  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [search, setSearch] = useState<string>(initialQuery.get("q") || initialQuery.get("search") || "");
  const [projectFilter, setProjectFilter] = useState<string>(initialQuery.get("project") || "");
  const [severityFilter, setSeverityFilter] = useState<string>(initialQuery.get("severity") || "");
  const [statusFilter, setStatusFilter] = useState<string>(initialQuery.get("status") || "");
  const [fileFilter, setFileFilter] = useState<string>(initialQuery.get("file") || "");
  const [confidenceFilter, setConfidenceFilter] = useState<string>("");

  // Decisão 3: persistir o agrupamento ×N em sessionStorage, ligado por padrão
  const [isGrouped, setIsGrouped] = useState<boolean>(() => {
    const saved = sessionStorage.getItem("polaris-findings-group");
    return saved !== null ? saved === "1" : true;
  });

  const [page, setPage] = useState(1);
  const pageSize = 25;

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [triageModalOpen, setTriageModalOpen] = useState(false);
  const [targetTriageStatus, setTargetTriageStatus] = useState<TriageActionStatus>("OPEN");
  const [batchSuccessMsg, setBatchSuccessMsg] = useState<string | null>(null);

  // Decisão 5: 1º achado sempre aberto
  const [selected, setSelected] = useState<IssueRow | null>(null);
  const [activeCodeLine, setActiveCodeLine] = useState<number | undefined>(undefined);
  const [flow, setFlow] = useState<Array<{ file: string; line: number; kind: string; detail: string }>>([]);
  const [assigneeInput, setAssigneeInput] = useState("");
  const [commentInput, setCommentInput] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);

  // Salvar toggle no sessionStorage
  useEffect(() => {
    sessionStorage.setItem("polaris-findings-group", isGrouped ? "1" : "0");
  }, [isGrouped]);

  const projects = useMemo(
    () => Array.from(new Set(issues.map((i) => i.project_key).filter(Boolean) as string[])).sort(),
    [issues],
  );

  const counts = useMemo(() => {
    let vuln = 0;
    let bug = 0;
    let smell = 0;
    for (const i of issues) {
      if (isVuln(i)) vuln++;
      else if (isBug(i)) bug++;
      else smell++;
    }
    return { all: issues.length, vuln, bug, smell };
  }, [issues]);

  // Filtragem plana
  const filtered = useMemo(() => {
    return issues.filter((i) => {
      if (categoryFilter === "vuln" && !isVuln(i)) return false;
      if (categoryFilter === "bug" && !isBug(i)) return false;
      if (categoryFilter === "smell" && (isVuln(i) || isBug(i))) return false;
      if (projectFilter && i.project_key !== projectFilter) return false;
      if (severityFilter && i.severity !== severityFilter) return false;
      if (statusFilter && i.status !== statusFilter) return false;
      if (fileFilter && i.file_path !== fileFilter) return false;
      if (confidenceFilter && (i.confidence ?? "HIGH") !== confidenceFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (
          !i.rule_id.toLowerCase().includes(q) &&
          !i.file_path.toLowerCase().includes(q) &&
          !i.message.toLowerCase().includes(q)
        ) {
          return false;
        }
      }
      return true;
    });
  }, [issues, categoryFilter, projectFilter, severityFilter, statusFilter, fileFilter, confidenceFilter, search]);

  // Agrupamento ×N (rule_id | file_path | severity | status)
  const groupedData = useMemo(() => {
    if (!isGrouped) {
      return filtered.map((item) => ({
        key: item.issue_id,
        representative: item,
        items: [item],
        count: 1,
      }));
    }

    const map = new Map<string, IssueRow[]>();
    for (const item of filtered) {
      const gKey = `${item.rule_id}::${item.file_path}::${item.severity}::${item.status}`;
      const arr = map.get(gKey) ?? [];
      arr.push(item);
      map.set(gKey, arr);
    }

    const res: GroupedIssue[] = [];
    for (const [key, arr] of map.entries()) {
      arr.sort((a, b) => (a.start_line ?? 1) - (b.start_line ?? 1));
      res.push({
        key,
        representative: arr[0],
        items: arr,
        count: arr.length,
      });
    }

    return res;
  }, [filtered, isGrouped]);

  const pagedGroups = useMemo(() => {
    const start = (page - 1) * pageSize;
    return groupedData.slice(start, start + pageSize);
  }, [groupedData, page, pageSize]);

  // Garante que o 1º achado sempre abre selecionado ao carregar ou mudar filtro
  useEffect(() => {
    const targetFindingId = initialQuery.get("finding");
    if (targetFindingId) {
      const match = issues.find((i) => i.issue_id === targetFindingId);
      if (match) {
        openIssue(match);
        return;
      }
    }

    if (groupedData.length > 0) {
      // Se o selecionado atual não estiver mais no resultado, seleciona o 1º
      const isCurrentVisible = selected && filtered.some((i) => i.issue_id === selected.issue_id);
      if (!isCurrentVisible) {
        openIssue(groupedData[0].representative);
      }
    } else {
      setSelected(null);
    }
  }, [groupedData]);

  const openIssue = (issue: IssueRow) => {
    setSelected(issue);
    setActiveCodeLine(issue.start_line);
    setAssigneeInput(issue.assignee ?? "");
    setCommentInput("");
    setActionMsg(null);
    setActionErr(null);
    setFlow([]);
    fetch(`/api/v1/issues/${issue.issue_id}/flow`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setFlow(d?.flow_steps ?? []))
      .catch(() => setFlow([]));
  };

  const selectedIndex = useMemo(() => {
    if (!selected) return -1;
    return filtered.findIndex((i) => i.issue_id === selected.issue_id);
  }, [filtered, selected]);

  const navigateItem = (dir: -1 | 1) => {
    const nextIdx = selectedIndex + dir;
    if (nextIdx >= 0 && nextIdx < filtered.length) {
      openIssue(filtered[nextIdx]);
    }
  };

  // Atalhos de teclado
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!selected) return;
      const tag = (document.activeElement?.tagName || "").toUpperCase();
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (document.activeElement as HTMLElement)?.isContentEditable) {
        return;
      }

      if (e.key === "Escape") {
        setSelected(null);
        return;
      }
      if (e.key === "j" || e.key === "J" || e.key === "ArrowDown") {
        e.preventDefault();
        navigateItem(1);
        return;
      }
      if (e.key === "k" || e.key === "K" || e.key === "ArrowUp") {
        e.preventDefault();
        navigateItem(-1);
        return;
      }
      if (e.key === "f" || e.key === "F") {
        e.preventDefault();
        handleSingleTriage("FALSE_POSITIVE");
        return;
      }
      if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        handleSingleTriage("ACCEPTED_RISK");
        return;
      }
      if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        handleSingleTriage("OPEN");
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selected, selectedIndex, filtered]);

  const toggleSelectRow = (issueId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(issueId)) next.delete(issueId);
      else next.add(issueId);
      return next;
    });
  };

  const toggleSelectGroup = (items: IssueRow[]) => {
    const allIn = items.every((i) => selectedIds.has(i.issue_id));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allIn) {
        items.forEach((i) => next.delete(i.issue_id));
      } else {
        items.forEach((i) => next.add(i.issue_id));
      }
      return next;
    });
  };

  const handleBatchTriageSubmit = async (reason: string, expiresAt?: string) => {
    const findingIds = Array.from(selectedIds);
    const body: Record<string, unknown> = {
      finding_ids: findingIds,
      action: targetTriageStatus,
      status: targetTriageStatus,
      reason,
      expires_at: expiresAt || null,
    };

    const res = await fetch("/api/findings/batch-triage", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      let errMsg = `Falha na requisição (HTTP ${res.status})`;
      try {
        const data = await res.json();
        if (data?.detail) errMsg = data.detail;
        else if (data?.message) errMsg = data.message;
      } catch {
        // use default
      }
      throw new Error(errMsg);
    }

    let updatedCount = findingIds.length;
    try {
      const data = await res.json();
      if (typeof data?.updated_count === "number") updatedCount = data.updated_count;
    } catch {
      // fallback
    }

    setBatchSuccessMsg(`${updatedCount} achado(s) atualizado(s) com sucesso.`);
    setTriageModalOpen(false);
    setSelectedIds(new Set());
    onMutated?.();
  };

  const handleSingleTriage = async (st: TriageActionStatus) => {
    if (!selected) return;
    setActionBusy(true);
    setActionErr(null);
    setActionMsg(null);
    try {
      const res = await fetch(`/api/v1/issues/${selected.issue_id}/transition`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: st }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setActionMsg(`Estado atualizado para ${st}`);
      onMutated?.();
    } catch (err) {
      setActionErr(err instanceof Error ? err.message : "Erro ao alterar estado");
    } finally {
      setActionBusy(false);
    }
  };

  const clearAllFilters = () => {
    setCategoryFilter("all");
    setSearch("");
    setProjectFilter("");
    setSeverityFilter("");
    setStatusFilter("");
    setFileFilter("");
    setConfidenceFilter("");
    setPage(1);
    setSelectedIds(new Set());
    window.location.hash = "#/issues";
  };

  return (
    <div style={{ display: "flex", width: "100%", height: "calc(100vh - 64px)", background: "var(--bg-app)", overflow: "hidden" }}>
      {/* 1. Rail Lateral de Filtros (220px) — Sem Abas */}
      <aside
        style={{
          width: 220,
          flexShrink: 0,
          background: "var(--bg-sidebar)",
          borderRight: "1px solid var(--border-subtle)",
          padding: "16px 14px",
          display: "flex",
          flexDirection: "column",
          gap: 16,
          overflowY: "auto",
        }}
      >
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>
            Categoria
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {[
              { id: "all", label: `Todas (${counts.all})` },
              { id: "vuln", label: `Vulnerabilidades (${counts.vuln})` },
              { id: "bug", label: `Bugs (${counts.bug})` },
              { id: "smell", label: `Code Smells (${counts.smell})` },
            ].map((c) => (
              <button
                key={c.id}
                onClick={() => { setCategoryFilter(c.id); setPage(1); }}
                style={{
                  textAlign: "left",
                  padding: "6px 12px",
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  background: categoryFilter === c.id ? "var(--accent-iris-soft)" : "transparent",
                  color: categoryFilter === c.id ? "var(--text-primary)" : "var(--text-secondary)",
                  fontSize: 12,
                  fontWeight: categoryFilter === c.id ? 600 : 400,
                  cursor: "pointer",
                  transition: "background 0.12s ease",
                }}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>
            Severidade
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {["", "BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"].map((s) => (
              <button
                key={s}
                onClick={() => { setSeverityFilter(s); setPage(1); }}
                style={{
                  textAlign: "left",
                  padding: "6px 12px",
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  background: severityFilter === s ? "var(--accent-iris-soft)" : "transparent",
                  color: severityFilter === s ? "var(--text-primary)" : "var(--text-secondary)",
                  fontSize: 12,
                  fontWeight: severityFilter === s ? 600 : 400,
                  cursor: "pointer",
                  transition: "background 0.12s ease",
                }}
              >
                {s || "Todas as severidades"}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 6 }}>
            Estado
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {["", "OPEN", "ACCEPTED_RISK", "FALSE_POSITIVE", "FIXED"].map((st) => (
              <button
                key={st}
                onClick={() => { setStatusFilter(st); setPage(1); }}
                style={{
                  textAlign: "left",
                  padding: "6px 12px",
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  background: statusFilter === st ? "var(--accent-iris-soft)" : "transparent",
                  color: statusFilter === st ? "var(--text-primary)" : "var(--text-secondary)",
                  fontSize: 12,
                  fontWeight: statusFilter === st ? 600 : 400,
                  cursor: "pointer",
                  transition: "background 0.12s ease",
                }}
              >
                {st || "Todos os estados"}
              </button>
            ))}
          </div>
        </div>

        {fileFilter && (
          <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted)", marginBottom: 4 }}>Arquivo Ativo</div>
            <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--accent-cyan)", wordBreak: "break-all" }}>
              {fileFilter}
            </div>
            <Button variant="ghost" size="sm" onClick={() => setFileFilter("")} style={{ padding: "2px 0", fontSize: 11 }}>
              Remover filtro
            </Button>
          </div>
        )}

        <Button variant="ghost" size="sm" onClick={clearAllFilters} style={{ marginTop: "auto", border: "1px solid var(--border-subtle)" }}>
          Limpar filtros
        </Button>
      </aside>

      {/* 2. Área Central: Lista Minimalista de 4 Sinais + Controles de Topo */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", borderRight: "1px solid var(--border-subtle)", background: "var(--bg-surface)" }}>
        {/* Controles no Topo da Lista */}
        <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <Input
            placeholder="Buscar por regra, arquivo ou descrição..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            style={{ width: 280 }}
          />

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer", color: "var(--text-secondary)", userSelect: "none" }}>
              <PolarisCheckbox checked={isGrouped} onChange={(e) => setIsGrouped(e.target.checked)} />
              <span>Agrupar ocorrências (×N)</span>
            </label>
            <span style={{ fontSize: 12, color: "var(--text-muted)", fontVariantNumeric: "tabular-nums" }}>
              {filtered.length} findings
            </span>
          </div>
        </div>

        {/* Lista Minimalista (Attio-like) */}
        <div style={{ flex: 1, overflowY: "auto", padding: 0 }}>
          {pagedGroups.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
              Nenhum finding encontrado com os filtros aplicados.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column" }}>
              {pagedGroups.map((group) => {
                const rep = group.representative;
                const isSelected = selected?.issue_id === rep.issue_id || group.items.some((i) => i.issue_id === selected?.issue_id);
                const isChecked = group.items.every((i) => selectedIds.has(i.issue_id));

                return (
                  <div
                    key={group.key}
                    onClick={() => openIssue(rep)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "10px 16px",
                      borderBottom: "1px solid var(--border-subtle)",
                      background: isSelected ? "var(--accent-iris-soft)" : "transparent",
                      borderLeft: isSelected ? "2px solid var(--accent-iris)" : "2px solid transparent",
                      cursor: "pointer",
                      gap: 12,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0, flex: 1 }}>
                      <div onClick={(e) => { e.stopPropagation(); toggleSelectGroup(group.items); }}>
                        <PolarisCheckbox checked={isChecked} onChange={() => {}} />
                      </div>
                      <TechnicalBadge severity={rep.severity} />
                      <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <code style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>{rep.rule_id}</code>
                          {group.count > 1 && (
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 700,
                                fontFamily: "var(--font-mono)",
                                fontVariantNumeric: "tabular-nums",
                                background: "var(--bg-muted)",
                                color: "var(--text-secondary)",
                                padding: "1px 6px",
                                borderRadius: 4,
                                border: "1px solid var(--border-subtle)",
                              }}
                            >
                              ×{group.count}
                            </span>
                          )}
                        </div>
                        <div
                          title={`${rep.file_path}:${rep.start_line ?? 1}`}
                          style={{
                            fontSize: 11,
                            fontFamily: "var(--font-mono)",
                            color: "var(--text-muted)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {rep.file_path}:{rep.start_line ?? 1}
                        </div>
                      </div>
                    </div>

                    <div style={{ flexShrink: 0 }}>
                      <TriageStatusBadge status={rep.status} expiresAt={rep.triage_expires_at ?? rep.expires_at} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Paginação */}
        <div style={{ padding: "8px 16px", borderTop: "1px solid var(--border-subtle)" }}>
          <Pagination
            page={page}
            totalPages={Math.max(1, Math.ceil(groupedData.length / pageSize))}
            onPageChange={setPage}
          />
        </div>
      </div>

      {/* 3. Painel de Inspeção com Divulgação Progressiva (480–560px) */}
      <aside
        style={{
          width: 520,
          flexShrink: 0,
          background: "var(--bg-surface)",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
        }}
      >
        {selected ? (
          <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 14 }}>
            {actionErr && <ErrorState message={actionErr} />}
            {actionMsg && (
              <div style={{ padding: 10, borderRadius: "var(--radius-md)", background: "var(--color-success-bg)", color: "var(--color-success)", fontSize: 13 }}>
                {actionMsg}
              </div>
            )}

            {/* Cabeçalho do Painel: Regra, Severidade e Navegação */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <TechnicalBadge severity={selected.severity} />
                <TriageStatusBadge status={selected.status} expiresAt={selected.triage_expires_at ?? selected.expires_at} />
              </div>

              <div style={{ display: "flex", gap: 4 }}>
                <Button variant="secondary" size="sm" disabled={selectedIndex <= 0} onClick={() => navigateItem(-1)}>
                  ← Anterior
                </Button>
                <Button variant="secondary" size="sm" disabled={selectedIndex < 0 || selectedIndex >= filtered.length - 1} onClick={() => navigateItem(1)}>
                  Próximo →
                </Button>
              </div>
            </div>

            {/* Ações Rápidas de Triagem Direta */}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", borderTop: "1px solid var(--border-subtle)", borderBottom: "1px solid var(--border-subtle)", padding: "10px 0" }}>
              <Button size="sm" variant="secondary" disabled={actionBusy} onClick={() => handleSingleTriage("ACCEPTED_RISK")}>
                Aceitar Risco
              </Button>
              <Button size="sm" variant="secondary" disabled={actionBusy} onClick={() => handleSingleTriage("FALSE_POSITIVE")}>
                Falso Positivo
              </Button>
              <Button size="sm" variant="secondary" disabled={actionBusy} onClick={() => handleSingleTriage("FIXED")}>
                Corrigido
              </Button>
              <Button size="sm" variant="secondary" disabled={actionBusy} onClick={() => handleSingleTriage("OPEN")}>
                Reabrir
              </Button>
            </div>

            {/* Descrição Concisa */}
            <div style={{ fontSize: 13, color: "var(--text-primary)", lineHeight: 1.4 }}>
              {selected.message}
            </div>

            {/* Protagonismo do Código: CodeEvidenceBlock */}
            <div>
              <CodeEvidenceBlock
                filePath={selected.file_path}
                startLine={selected.start_line}
                activeLine={activeCodeLine}
                snippet={selected.snippet}
                language={selected.language}
              />
            </div>

            {/* TaintTrail (SOURCE → SINK) */}
            {flow.length > 0 && (
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)", marginBottom: 8 }}>
                  Fluxo Semântico ({flow.length} passos)
                </div>
                <TaintTrail
                  steps={flow}
                  onSelectStep={(idx) => {
                    const step = flow[idx];
                    if (step && step.file === selected.file_path) {
                      setActiveCodeLine(step.line);
                    }
                  }}
                />
              </div>
            )}

            {/* Divulgação Progressiva: Detalhes, Auditoria e Atribuição */}
            <details style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 10, cursor: "pointer" }}>
              <summary style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 10 }}>
                ▸ Metadados &amp; Auditoria
              </summary>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, paddingLeft: 4 }}>
                <div style={{ fontSize: 12 }}>
                  <span style={{ color: "var(--text-muted)" }}>ID:</span> <code>{selected.issue_id}</code>
                </div>
                {selected.cwe && (
                  <div style={{ fontSize: 12 }}>
                    <span style={{ color: "var(--text-muted)" }}>CWE:</span> <code>{selected.cwe}</code>
                  </div>
                )}
                <div style={{ fontSize: 12 }}>
                  <span style={{ color: "var(--text-muted)" }}>Confiança:</span> <code>{selected.confidence ?? "HIGH"}</code>
                </div>
                <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                  <Input placeholder="Atribuir usuário..." value={assigneeInput} onChange={(e) => setAssigneeInput(e.target.value)} style={{ flex: 1 }} />
                  <Button size="sm" variant="secondary" onClick={() => {}}>Atribuir</Button>
                </div>
              </div>
            </details>

            {/* Divulgação Progressiva: IA Editorial sob demanda */}
            <details style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 10, cursor: "pointer" }}>
              <summary style={{ fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 10 }}>
                ▸ Análise de IA Sob Demanda
              </summary>
              <IssueAiAssistant issue={selected} />
            </details>

            {/* Dicas de Teclado no Rodapé */}
            <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 8, marginTop: "auto", display: "flex", gap: 8, fontSize: 11, color: "var(--text-muted)", flexWrap: "wrap" }}>
              <span><kbd>J</kbd>/<kbd>K</kbd> navegar</span>
              <span>·</span>
              <span><kbd>F</kbd> falso positivo</span>
              <span>·</span>
              <span><kbd>A</kbd> aceitar</span>
              <span>·</span>
              <span><kbd>R</kbd> reabrir</span>
              <span>·</span>
              <span><kbd>Esc</kbd> fechar</span>
            </div>
          </div>
        ) : (
          <div style={{ padding: 32, textAlign: "center", color: "var(--text-muted)", fontSize: 13, margin: "auto" }}>
            Nenhum achado selecionado.
          </div>
        )}
      </aside>

      {/* Barra de Ação Flutuante */}
      <BatchTriageBar
        selectedCount={selectedIds.size}
        onClear={() => setSelectedIds(new Set())}
        onAction={(st) => { setTargetTriageStatus(st); setTriageModalOpen(true); }}
      />

      {/* Modal de Justificativa de Lote */}
      <BatchTriageModal
        open={triageModalOpen}
        targetStatus={targetTriageStatus}
        selectedCount={selectedIds.size}
        onClose={() => setTriageModalOpen(false)}
        onSubmit={handleBatchTriageSubmit}
      />
    </div>
  );
}
