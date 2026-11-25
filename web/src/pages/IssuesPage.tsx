import { useMemo, useState } from "react";
import { Badge, Button, Card, DataTable, Drawer, ErrorState, Input, Pagination, Select, Tabs } from "../components/ui";
import { IssueAiAssistant } from "../components/IssueAiAssistant";

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
}

type CategoryTab = "all" | "vuln" | "bug" | "smell";
type GroupBy = "none" | "rule_id" | "severity" | "project_key";

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
  const [tab, setTab] = useState<CategoryTab>("all");
  const [search, setSearch] = useState("");
  const [projectFilter, setProjectFilter] = useState("");
  const [severity, setSeverity] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [confidenceFilter, setConfidenceFilter] = useState("");
  const [groupBy, setGroupBy] = useState<GroupBy>("none");
  const [page, setPage] = useState(1);
  const pageSize = 25;
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

  const clearFilters = () => {
    setSearch("");
    setProjectFilter("");
    setSeverity("");
    setStatusFilter("");
    setConfidenceFilter("");
    setGroupBy("none");
  };

  return (
    <div>
      <h1 style={{ margin: "0 0 12px", fontSize: 24, fontWeight: 600 }}>Findings Workbench</h1>
      <Tabs
        active={tab}
        onChange={(id) => setTab(id as CategoryTab)}
        tabs={[
          { id: "all", label: `Todas (${counts.all})` },
          { id: "vuln", label: `Vulnerabilidades (${counts.vuln})` },
          { id: "bug", label: `Bugs (${counts.bug})` },
          { id: "smell", label: `Code Smells (${counts.smell})` },
        ]}
      />

      <Card>
        <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
          <Input
            placeholder="Buscar regra, arquivo ou mensagem..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 260 }}
          />
          <Select value={projectFilter} onChange={(e) => setProjectFilter(e.target.value)}>
            <option value="">Todos projetos</option>
            {projects.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </Select>
          <Select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="">Todas severidades</option>
            <option value="BLOCKER">BLOCKER</option>
            <option value="CRITICAL">CRITICAL</option>
            <option value="MAJOR">MAJOR</option>
            <option value="MINOR">MINOR</option>
            <option value="INFO">INFO</option>
          </Select>
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Todos estados</option>
            <option value="OPEN">OPEN</option>
            <option value="CONFIRMED">CONFIRMED</option>
            <option value="RESOLVED">RESOLVED</option>
            <option value="FALSE_POSITIVE">FALSE_POSITIVE</option>
            <option value="WONT_FIX">WONT_FIX</option>
          </Select>
          <Select value={confidenceFilter} onChange={(e) => setConfidenceFilter(e.target.value)}>
            <option value="">Todas confianças</option>
            <option value="HIGH">HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="LOW">LOW</option>
          </Select>
          <Select value={groupBy} onChange={(e) => setGroupBy(e.target.value as GroupBy)}>
            <option value="none">Sem agrupamento</option>
            <option value="rule_id">Agrupar por Regra</option>
            <option value="severity">Agrupar por Severidade</option>
            <option value="project_key">Agrupar por Projeto</option>
          </Select>
          <Button variant="secondary" size="sm" onClick={clearFilters}>Limpar filtros</Button>
        </div>

        {grouped.map(([groupName, rows]) => (
          <div key={groupName} style={{ marginBottom: 16 }}>
            {groupBy !== "none" && (
              <div style={{ fontSize: 13, fontWeight: 600, padding: "6px 0", color: "var(--text-secondary)" }}>
                {groupName} ({rows.length})
              </div>
            )}
            <DataTable
              columns={[
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
                { key: "status", header: "Estado", render: (i) => <Badge>{i.status}</Badge> },
                {
                  key: "file",
                  header: "Arquivo",
                  render: (i) => <code>{i.file_path}{i.start_line ? `:${i.start_line}` : ""}</code>,
                },
                { key: "msg", header: "Descrição", render: (i) => i.message },
              ]}
              rows={groupBy === "none" ? rows.slice((page - 1) * pageSize, page * pageSize) : rows}
              onRowClick={openIssue}
              emptyText="Nenhum finding encontrado com os filtros atuais."
            />
            {groupBy === "none" && (
              <Pagination
                page={page}
                totalPages={Math.max(1, Math.ceil(rows.length / pageSize))}
                onPageChange={setPage}
              />
            )}
          </div>
        ))}
      </Card>

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
              <Badge>{selected.status}</Badge>
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
