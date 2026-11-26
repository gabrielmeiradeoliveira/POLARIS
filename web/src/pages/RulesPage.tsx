import { useState } from "react";
import { Badge, Card, DataTable, Drawer, Input, Pagination, Select } from "../components/ui";

export interface RuleRow {
  ruleId: string;
  name: string;
  language: string;
  category: string;
  severity: string;
  description?: string;
  implementationStatus?: string;
  validationStatus?: string;
  semanticCapability?: boolean;
}

function severityTone(sev: string): "error" | "warning" | "primary" | "neutral" {
  if (sev === "BLOCKER" || sev === "CRITICAL") return "error";
  if (sev === "MAJOR" || sev === "HIGH") return "warning";
  if (sev === "MINOR" || sev === "LOW") return "primary";
  return "neutral";
}

export function RulesPage({ rules }: { rules: RuleRow[] }) {
  const [search, setSearch] = useState("");
  const [language, setLanguage] = useState("");
  const [severity, setSeverity] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<RuleRow | null>(null);
  const pageSize = 25;

  const filtered = rules.filter((r) => {
    if (language && r.language !== language) return false;
    if (severity && r.severity !== severity) return false;
    if (search) {
      const q = search.toLowerCase();
      return r.ruleId.toLowerCase().includes(q) || r.name.toLowerCase().includes(q) || (r.description ?? "").toLowerCase().includes(q);
    }
    return true;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const slice = filtered.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div style={{ padding: "24px 32px" }}>
      <h1 style={{ margin: "0 0 16px", fontSize: 24, fontWeight: 600 }}>Catálogo de Regras ({filtered.length})</h1>
      <Card>
        <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
          <Input placeholder="Pesquisar regra..." value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} style={{ width: 260 }} />
          <Select value={language} onChange={(e) => { setLanguage(e.target.value); setPage(1); }}>
            <option value="">Todas linguagens</option>
            <option value="python">Python</option>
            <option value="csharp">C#</option>
            <option value="java">Java</option>
            <option value="sql">SQL</option>
          </Select>
          <Select value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }}>
            <option value="">Todas severidades</option>
            <option value="BLOCKER">BLOCKER</option>
            <option value="CRITICAL">CRITICAL</option>
            <option value="MAJOR">MAJOR</option>
            <option value="MINOR">MINOR</option>
            <option value="INFO">INFO</option>
          </Select>
        </div>
        <DataTable
          columns={[
            { key: "id", header: "ID", render: (r) => <code>{r.ruleId}</code> },
            { key: "name", header: "Nome", render: (r) => r.name },
            { key: "lang", header: "Linguagem", render: (r) => r.language },
            { key: "cat", header: "Categoria", render: (r) => r.category },
            { key: "sev", header: "Severidade", render: (r) => <Badge tone={severityTone(r.severity)}>{r.severity}</Badge> },
            { key: "impl", header: "Implementação", render: (r) => <Badge>{r.implementationStatus ?? "IMPLEMENTED"}</Badge> },
            { key: "val", header: "Validação", render: (r) => <Badge tone={r.validationStatus === "VALIDATED" ? "success" : "warning"}>{r.validationStatus ?? "IMPLEMENTED"}</Badge> },
          ]}
          rows={slice}
          onRowClick={setSelected}
          emptyText="Nenhuma regra encontrada."
        />
        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      </Card>

      <Drawer open={Boolean(selected)} title={`Regra ${selected?.ruleId ?? ""}`} onClose={() => setSelected(null)}>
        {selected && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div><strong>Nome:</strong> {selected.name}</div>
            <div><strong>Linguagem:</strong> {selected.language}</div>
            <div><strong>Categoria:</strong> {selected.category}</div>
            <div><strong>Severidade:</strong> <Badge tone={severityTone(selected.severity)}>{selected.severity}</Badge></div>
            <div><strong>Implementação:</strong> <Badge>{selected.implementationStatus ?? "IMPLEMENTED"}</Badge></div>
            <div><strong>Validação:</strong> <Badge tone={selected.validationStatus === "VALIDATED" ? "success" : "warning"}>{selected.validationStatus ?? "IMPLEMENTED"}</Badge></div>
            <div><strong>Capacidade Semântica:</strong> {selected.semanticCapability ? "Sim" : "Sintática"}</div>
            <div><strong>Descrição:</strong> {selected.description ?? selected.name}</div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
