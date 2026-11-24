import { useState } from "react";
import { Badge, Button, Card, DataTable, Dialog, Drawer, ErrorState, Input, Select } from "../components/ui";

export interface GateRow {
  gate_id: string;
  name: string;
  is_default: boolean;
}

export function QualityGatesPage({
  gates,
  onMutated,
}: {
  gates: GateRow[];
  onMutated?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [metric, setMetric] = useState("bugs");
  const [operator, setOperator] = useState("GT");
  const [threshold, setThreshold] = useState("0");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [selected, setSelected] = useState<GateRow | null>(null);
  const [projectKey, setProjectKey] = useState("");
  const [assignMsg, setAssignMsg] = useState<string | null>(null);
  const [evalBugs, setEvalBugs] = useState("0");
  const [evalVulns, setEvalVulns] = useState("0");
  const [evalResult, setEvalResult] = useState<string | null>(null);
  const [evalErr, setEvalErr] = useState<string | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch("/api/v1/quality-gates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          conditions: [{ metric, operator, threshold: Number(threshold) }],
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setOpen(false);
      setName("");
      onMutated?.();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Erro ao criar gate");
    } finally {
      setBusy(false);
    }
  };

  const handleEvaluate = async () => {
    if (!selected) return;
    setBusy(true);
    setEvalErr(null);
    setEvalResult(null);
    try {
      const res = await fetch(`/api/v1/quality-gates/${selected.gate_id}/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metrics: { bugs: Number(evalBugs), vulnerabilities: Number(evalVulns) },
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEvalResult(data.status ?? JSON.stringify(data));
    } catch (error) {
      setEvalErr(error instanceof Error ? error.message : "Erro ao avaliar gate");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>Quality Gates ({gates.length})</h1>
        <Button onClick={() => setOpen(true)}>Novo Quality Gate</Button>
      </div>
      <Card>
        <DataTable
          columns={[
            { key: "id", header: "ID", render: (g) => <code>{g.gate_id}</code> },
            { key: "name", header: "Nome", render: (g) => g.name },
            { key: "def", header: "Padrão", render: (g) => (g.is_default ? <Badge tone="primary">Default</Badge> : "-") },
          ]}
          rows={gates}
          onRowClick={(g) => {
            setSelected(g);
            setEvalResult(null);
            setEvalErr(null);
          }}
          emptyText="Nenhum Quality Gate encontrado."
        />
      </Card>

      <Dialog open={open} title="Criar Quality Gate" onClose={() => setOpen(false)}>
        {err && <ErrorState message={err} />}
        <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Input placeholder="Nome do Quality Gate" value={name} onChange={(e) => setName(e.target.value)} required />
          <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Condição inicial</div>
          <div style={{ display: "flex", gap: 8 }}>
            <Select value={metric} onChange={(e) => setMetric(e.target.value)}>
              <option value="bugs">bugs</option>
              <option value="vulnerabilities">vulnerabilities</option>
              <option value="code_smells">code_smells</option>
            </Select>
            <Select value={operator} onChange={(e) => setOperator(e.target.value)}>
              <option value="GT">GT (&gt;)</option>
              <option value="LT">LT (&lt;)</option>
              <option value="EQ">EQ (=)</option>
            </Select>
            <Input type="number" value={threshold} onChange={(e) => setThreshold(e.target.value)} style={{ width: 80 }} />
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button type="submit" disabled={busy}>{busy ? "Criando..." : "Criar"}</Button>
          </div>
        </form>
      </Dialog>

      <Drawer open={Boolean(selected)} title={`Avaliar Quality Gate — ${selected?.name ?? ""}`} onClose={() => setSelected(null)}>
        {selected && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {evalErr && <ErrorState message={evalErr} />}
            {evalResult && (
              <Badge tone={evalResult === "PASSED" ? "success" : evalResult === "FAILED" ? "error" : "warning"}>
                Resultado: {evalResult}
              </Badge>
            )}
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <label style={{ fontSize: 13 }}>Bugs: <Input type="number" value={evalBugs} onChange={(e) => setEvalBugs(e.target.value)} style={{ width: 80 }} /></label>
              <label style={{ fontSize: 13 }}>Vulnerabilidades: <Input type="number" value={evalVulns} onChange={(e) => setEvalVulns(e.target.value)} style={{ width: 80 }} /></label>
            </div>
            <Button onClick={handleEvaluate} disabled={busy}>{busy ? "Avaliando..." : "Avaliar Gate"}</Button>
            <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12, marginTop: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Associar ao Projeto</div>
              {assignMsg && <div style={{ fontSize: 12, color: "var(--color-success)", marginBottom: 6 }}>{assignMsg}</div>}
              <div style={{ display: "flex", gap: 8 }}>
                <Input placeholder="Project Key" value={projectKey} onChange={(e) => setProjectKey(e.target.value)} style={{ flex: 1 }} />
                <Button
                  size="sm"
                  disabled={busy || !projectKey.trim()}
                  onClick={async () => {
                    setBusy(true);
                    setEvalErr(null);
                    setAssignMsg(null);
                    try {
                      const r = await fetch(`/api/v1/quality-gates/${selected.gate_id}/projects/${encodeURIComponent(projectKey.trim())}`, { method: "POST" });
                      if (!r.ok) throw new Error(`HTTP ${r.status}`);
                      setAssignMsg(`Gate associado ao projeto ${projectKey.trim()}`);
                      onMutated?.();
                    } catch (e) {
                      setEvalErr(e instanceof Error ? e.message : "Erro ao associar gate");
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Associar
                </Button>
              </div>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
