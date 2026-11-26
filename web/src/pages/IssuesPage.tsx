import React, { useMemo, useState } from "react";
import { Badge, Button, Card, DataTable, Drawer, ErrorState, Input, Pagination, Select, Tabs } from "../components/ui";
import { IssueAiAssistant } from "../components/IssueAiAssistant";
import { TriageStatusBadge } from "../components/TriageStatusBadge";
import { BatchTriageBar, TriageActionStatus } from "../components/BatchTriageBar";
import { BatchTriageModal } from "../components/BatchTriageModal";
import { IndeterminateCheckbox } from "../components/IndeterminateCheckbox";

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
  cwe?: string;
  confidence?: "HIGH" | "MEDIUM" | "LOW";
  assignee?: string;
  triage_expires_at?: string | null;
  expires_at?: string | null;
}

type CategoryTab = "all" | "vuln" | "bug" | "smell";
type GroupBy = "none" | "rule_id" | "severity" | "project_key";

function isVuln(i: IssueRow): boolean {
  return i.rule_id.includes("-SEC-");
}

function isBug(i: IssueRow): boolean {
  return !isVuln(i) && (i.rule_id.includes("-REL-") || i.severity === "BLOCKER" || i.severity === "CRITICAL");
}

const STATUS_LABELS: Record<string, string> = {
  OPEN: "Aberto",
  ACCEPTED_RISK: "Risco Aceito",
  FALSE_POSITIVE: "Falso Positivo",
  FIXED: "Corrigido",
};

export function IssuesPage({
  issues,
  onMutated,
}: {
  issues: IssueRow[];
  onMutated?: () => void;
}) {
  const [tab, setTab] = useState<CategoryTab>("all");
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [severity, setSeverity] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [confidenceFilter, setConfidenceFilter] = useState("");
  const [groupBy, setGroupBy] = useState<GroupBy>("none");
  const [page, setPage] = useState(1);
  const pageSize = 25;

  // Seleção múltipla para triagem em lote
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [triageModalOpen, setTriageModalOpen] = useState(false);
  const [targetTriageStatus, setTargetTriageStatus] = useState<TriageActionStatus>("OPEN");
  const [batchSuccessMsg, setBatchSuccessMsg] = useState<string | null>(null);

  const [selected, setSelected] = useState<IssueRow | null>(null);
  const [flow, setFlow] = useState<Array<{ file: string; line: number; kind: string; detail: string }>>([]);
  const [assigneeInput, setAssigneeInput] = useState("");
  const [commentInput, setCommentInput] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);

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

  const filtered = useMemo(() => {
    return issues.filter((i) => {
      if (tab === "vuln" && !isVuln(i)) return false;
      if (tab === "bug" && !isBug(i)) return false;
      if (tab === "smell" && (isVuln(i) || isBug(i))) return false;
      if (projectFilter && i.project_key !== projectFilter) return false;
      if (severity && i.severity !== severity) return false;
      if (statusFilter && i.status !== statusFilter) return false;
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
  }, [issues, tab, projectFilter, severity, statusFilter, confidenceFilter, search]);

  const grouped = useMemo(() => {
    if (groupBy === "none") return [["Todos os Findings", filtered] as const];
    const map = new Map<string, IssueRow[]>();
    for (const item of filtered) {
      const key = (item[groupBy] as string | undefined) || "Sem valor";
      const arr = map.get(key) ?? [];
      arr.push(item);
      map.set(key, arr);
    }
    return Array.from(map.entries());
  }, [filtered, groupBy]);

  // Função para limpar filtros e seleção
  const clearFilters = () => {
    setSearch("");
    setProjectFilter("");
    setSeverity("");
    setStatusFilter("");
    setConfidenceFilter("");
    setGroupBy("none");
    setPage(1);
    setSelectedIds(new Set());
  };

  // Handlers de alteração de filtros com reset de página e seleção conforme especificação (Seção 2.2)
  const handleTabChange = (newTab: CategoryTab) => {
    setTab(newTab);
    setPage(1);
    setSelectedIds(new Set());
  };

  const handleSearchChange = (val: string) => {
    setSearch(val);
    setPage(1);
    setSelectedIds(new Set());
  };

  const handleProjectFilterChange = (val: string) => {
    setProjectFilter(val);
    setPage(1);
    setSelectedIds(new Set());
  };

  const handleSeverityChange = (val: string) => {
    setSeverity(val);
    setPage(1);
    setSelectedIds(new Set());
  };

  const handleStatusFilterChange = (val: string) => {
    setStatusFilter(val);
    setPage(1);
    setSelectedIds(new Set());
  };

  const handleConfidenceFilterChange = (val: string) => {
    setConfidenceFilter(val);
    setPage(1);
    setSelectedIds(new Set());
  };

  // Toggle de seleção de um único achado
  const toggleSelectRow = (issueId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(issueId)) {
        next.delete(issueId);
      } else {
        next.add(issueId);
      }
      return next;
    });
  };

  // Toggle de seleção de todos os itens visíveis
  const toggleSelectAllVisible = (visibleRows: IssueRow[]) => {
    if (visibleRows.length === 0) return;
    const allSelected = visibleRows.every((r) => selectedIds.has(r.issue_id));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allSelected) {
        visibleRows.forEach((r) => next.delete(r.issue_id));
      } else {
        visibleRows.forEach((r) => next.add(r.issue_id));
      }
      return next;
    });
  };

  // Abertura do modal de triagem
  const handleTriageAction = (st: TriageActionStatus) => {
    setTargetTriageStatus(st);
    setTriageModalOpen(true);
  };

  // Execução do PATCH /api/findings/batch-triage
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
      if (typeof data?.updated_count === "number") {
        updatedCount = data.updated_count;
      }
    } catch {
      // fallback
    }

    const label = STATUS_LABELS[targetTriageStatus] || targetTriageStatus;
    setBatchSuccessMsg(`${updatedCount} achado(s) atualizado(s) para ${label}.`);
    setTriageModalOpen(false);
    setSelectedIds(new Set());
    onMutated?.();
  };

  const openIssue = (issue: IssueRow) => {
    setSelected(issue);
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

  const runAction = async (url: string, body: Record<string, unknown>, successText: string) => {
    if (!selected) return;
    setActionBusy(true);
    setActionErr(null);
    setActionMsg(null);
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setActionMsg(successText);
      onMutated?.();
    } catch (err) {
      setActionErr(err instanceof Error ? err.message : "Erro ao executar ação");
    } finally {
      setActionBusy(false);
    }
  };

  return (
    <div>
      <h1 style={{ margin: "0 0 12px", fontSize: 24, fontWeight: 600 }}>Findings Workbench</h1>
      <Tabs
        active={tab}
        onChange={(id) => handleTabChange(id as CategoryTab)}
        tabs={[
          { id: "all", label: `Todas (${counts.all})` },
          { id: "vuln", label: `Vulnerabilidades (${counts.vuln})` },
          { id: "bug", label: `Bugs (${counts.bug})` },
          { id: "smell", label: `Code Smells (${counts.smell})` },
        ]}
      />

      <Card>
        {/* Banner inline de sucesso de triagem */}
        {batchSuccessMsg && (
          <div
            style={{
              background: "var(--color-success-bg)",
              color: "var(--color-success)",
              padding: "10px 12px",
              borderRadius: "var(--radius-md)",
              fontSize: 13,
              marginBottom: 12,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>{batchSuccessMsg}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setBatchSuccessMsg(null)}
              style={{ color: "var(--color-success)", padding: "2px 6px" }}
            >
              Fechar
            </Button>
          </div>
        )}

        <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
          <Input
            placeholder="Buscar regra, arquivo ou mensagem..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            style={{ width: 260 }}
          />
          <Select value={projectFilter} onChange={(e) => handleProjectFilterChange(e.target.value)}>
            <option value="">Todos projetos</option>
            {projects.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </Select>
          <Select value={severity} onChange={(e) => handleSeverityChange(e.target.value)}>
            <option value="">Todas severidades</option>
            <option value="BLOCKER">BLOCKER</option>
            <option value="CRITICAL">CRITICAL</option>
            <option value="MAJOR">MAJOR</option>
            <option value="MINOR">MINOR</option>
            <option value="INFO">INFO</option>
          </Select>
          <Select value={statusFilter} onChange={(e) => handleStatusFilterChange(e.target.value)}>
            <option value="">Todos os estados</option>
            <option value="OPEN">Aberto (OPEN)</option>
            <option value="ACCEPTED_RISK">Risco Aceito (ACCEPTED_RISK)</option>
            <option value="FALSE_POSITIVE">Falso Positivo (FALSE_POSITIVE)</option>
            <option value="FIXED">Corrigido (FIXED)</option>
          </Select>
          <Select value={confidenceFilter} onChange={(e) => handleConfidenceFilterChange(e.target.value)}>
            <option value="">Todas confianças</option>
            <option value="HIGH">HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="LOW">LOW</option>
          </Select>
          <Select value={groupBy} onChange={(e) => { setGroupBy(e.target.value as GroupBy); setPage(1); setSelectedIds(new Set()); }}>
            <option value="none">Sem agrupamento</option>
            <option value="rule_id">Agrupar por Regra</option>
            <option value="severity">Agrupar por Severidade</option>
            <option value="project_key">Agrupar por Projeto</option>
          </Select>
          <Button variant="secondary" size="sm" onClick={clearFilters}>Limpar filtros</Button>
        </div>

        {grouped.map(([groupName, rows]) => {
          const visibleRows = groupBy === "none" ? rows.slice((page - 1) * pageSize, page * pageSize) : rows;
          const allVisibleSelected = visibleRows.length > 0 && visibleRows.every((r) => selectedIds.has(r.issue_id));
          const someVisibleSelected = visibleRows.some((r) => selectedIds.has(r.issue_id));
          const isIndeterminate = someVisibleSelected && !allVisibleSelected;

          return (
            <div key={groupName} style={{ marginBottom: 16 }}>
              {groupBy !== "none" && (
                <div style={{ fontSize: 13, fontWeight: 600, padding: "6px 0", color: "var(--text-secondary)" }}>
                  {groupName} ({rows.length})
                </div>
              )}
              <DataTable
                rowSelection={(r) => selectedIds.has(r.issue_id)}
                rowOpacity={(r) => {
                  const s = r.status?.toUpperCase?.();
                  if (s === "FALSE_POSITIVE" || s === "FIXED") return 0.78;
                  return undefined;
                }}
                columns={[
                  {
                    key: "selection",
                    header: (
                      <div style={{ textAlign: "center", width: 40, padding: "2px 0" }}>
                        <IndeterminateCheckbox
                          checked={allVisibleSelected}
                          indeterminate={isIndeterminate}
                          aria-label="Selecionar todos os achados visíveis nesta página"
                          onChange={() => toggleSelectAllVisible(visibleRows)}
                        />
                      </div>
                    ),
                    width: "40px",
                    render: (i) => (
                      <div
                        style={{ textAlign: "center", width: 40, padding: "2px 0" }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <IndeterminateCheckbox
                          checked={selectedIds.has(i.issue_id)}
                          aria-label={`Selecionar achado ${i.rule_id} em ${i.file_path}`}
                          onChange={() => toggleSelectRow(i.issue_id)}
                        />
                      </div>
                    ),
                  },
                  {
                    key: "sev",
                    header: "Severidade",
                    render: (i) => (
                      <Badge tone={i.severity === "CRITICAL" || i.severity === "BLOCKER" ? "error" : "warning"}>
                        {i.severity}
                      </Badge>
                    ),
                  },
                  { key: "rule", header: "Regra", render: (i) => <code>{i.rule_id}</code> },
                  {
                    key: "proj",
                    header: "Projeto",
                    render: (i) =>
                      i.project_key ? (
                        <a href={`#/projects/${encodeURIComponent(i.project_key)}`} onClick={(e) => e.stopPropagation()}>
                          {i.project_key}
                        </a>
                      ) : (
                        "-"
                      ),
                  },
                  {
                    key: "status",
                    header: "Estado",
                    render: (i) => (
                      <TriageStatusBadge
                        status={i.status}
                        expiresAt={i.triage_expires_at ?? i.expires_at}
                      />
                    ),
                  },
                  {
                    key: "file",
                    header: "Arquivo",
                    render: (i) => <code>{i.file_path}{i.start_line ? `:${i.start_line}` : ""}</code>,
                  },
                  { key: "msg", header: "Descrição", render: (i) => i.message },
                ]}
                rows={visibleRows}
                onRowClick={openIssue}
                emptyText="Nenhum finding encontrado com os filtros atuais."
              />
              {groupBy === "none" && (
                <Pagination
                  page={page}
                  totalPages={Math.max(1, Math.ceil(rows.length / pageSize))}
                  onPageChange={(p) => {
                    setPage(p);
                    setSelectedIds(new Set());
                  }}
                />
              )}
            </div>
          );
        })}
      </Card>

      {/* Barra de ação flutuante de triagem em lote */}
      <BatchTriageBar
        selectedCount={selectedIds.size}
        onClear={() => setSelectedIds(new Set())}
        onAction={handleTriageAction}
      />

      {/* Modal de justificativa de triagem em lote */}
      <BatchTriageModal
        open={triageModalOpen}
        targetStatus={targetTriageStatus}
        selectedCount={selectedIds.size}
        onClose={() => setTriageModalOpen(false)}
        onSubmit={handleBatchTriageSubmit}
      />

      <Drawer open={Boolean(selected)} title={`Investigação — ${selected?.rule_id ?? ""}`} onClose={() => setSelected(null)}>
        {selected && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {actionErr && <ErrorState message={actionErr} />}
            {actionMsg && (
              <div style={{ padding: 10, borderRadius: "var(--radius-md)", background: "var(--color-success-bg)", color: "var(--color-success)", fontSize: 13 }}>
                {actionMsg}
              </div>
            )}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <Badge tone={selected.severity === "CRITICAL" || selected.severity === "BLOCKER" ? "error" : "warning"}>{selected.severity}</Badge>
              <TriageStatusBadge status={selected.status} expiresAt={selected.triage_expires_at ?? selected.expires_at} />
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, padding: "2px 6px", borderRadius: 4, border: "1px solid var(--border-subtle)" }}>
                CONF:{selected.confidence ?? "HIGH"}
              </span>
              {selected.cwe && <Badge tone="primary">{selected.cwe}</Badge>}
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Localização</div>
              <code>{selected.file_path}{selected.start_line ? `:${selected.start_line}` : ""}</code>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Descrição</div>
              <div>{selected.message}</div>
            </div>

            <IssueAiAssistant issue={selected} />

            {flow.length > 0 && (
              <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Fluxo Semântico ({flow.length} passos)</div>
                <ol style={{ margin: 0, paddingLeft: 18 }}>
                  {flow.map((s, idx) => (
                    <li key={idx} style={{ marginBottom: 4 }}>
                      <Badge tone="primary">{s.kind}</Badge> <code>{s.file}:{s.line}</code> — {s.detail}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Alterar Estado</div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {(["CONFIRMED", "RESOLVED", "FALSE_POSITIVE", "WONT_FIX"] as const).map((st) => (
                  <Button
                    key={st}
                    size="sm"
                    variant="secondary"
                    disabled={actionBusy}
                    onClick={() => runAction(`/api/v1/issues/${selected.issue_id}/transition`, { status: st }, `Estado atualizado para ${st}`)}
                  >
                    {st}
                  </Button>
                ))}
              </div>
            </div>

            <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Atribuir Responsável</div>
              <div style={{ display: "flex", gap: 8 }}>
                <Input placeholder="Usuário..." value={assigneeInput} onChange={(e) => setAssigneeInput(e.target.value)} style={{ flex: 1 }} />
                <Button
                  size="sm"
                  disabled={actionBusy || !assigneeInput.trim()}
                  onClick={() => runAction(`/api/v1/issues/${selected.issue_id}/assign`, { assignee: assigneeInput.trim() }, "Responsável atribuído")}
                >
                  Atribuir
                </Button>
              </div>
            </div>

            <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Adicionar Comentário</div>
              <div style={{ display: "flex", gap: 8 }}>
                <Input placeholder="Comentário..." value={commentInput} onChange={(e) => setCommentInput(e.target.value)} style={{ flex: 1 }} />
                <Button
                  size="sm"
                  disabled={actionBusy || !commentInput.trim()}
                  onClick={() => runAction(`/api/v1/issues/${selected.issue_id}/comments`, { comment: commentInput.trim() }, "Comentário registrado")}
                >
                  Comentar
                </Button>
              </div>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
