import { useState } from "react";
import { Badge, Button, Card, DataTable, Dialog, Drawer, ErrorState, Input, Select } from "../components/ui";

export interface ProfileRow {
  profile_id: string;
  name: string;
  language: string;
  is_default: boolean;
}

export function QualityProfilesPage({
  profiles,
  onMutated,
}: {
  profiles: ProfileRow[];
  onMutated?: () => void;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("python");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [selected, setSelected] = useState<ProfileRow | null>(null);
  const [ruleId, setRuleId] = useState("");
  const [projectKey, setProjectKey] = useState("");
  const [editorMsg, setEditorMsg] = useState<string | null>(null);
  const [editorErr, setEditorErr] = useState<string | null>(null);

  const filtered = profiles.filter(
    (p) => p.name.toLowerCase().includes(search.toLowerCase()) || p.language.toLowerCase().includes(search.toLowerCase()),
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch("/api/v1/quality-profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), language }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setOpen(false);
      setName("");
      onMutated?.();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Erro ao criar profile");
    } finally {
      setBusy(false);
    }
  };

  const runProfileAction = async (url: string, body: Record<string, unknown>, okText: string) => {
    setBusy(true);
    setEditorErr(null);
    setEditorMsg(null);
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setEditorMsg(okText);
      onMutated?.();
    } catch (error) {
      setEditorErr(error instanceof Error ? error.message : "Erro na operação");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>Quality Profiles ({filtered.length})</h1>
        <Button onClick={() => setOpen(true)}>Novo Profile</Button>
      </div>
      <Card>
        <div style={{ marginBottom: 12 }}>
          <Input placeholder="Buscar profile..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ width: 260 }} />
        </div>
        <DataTable
          columns={[
            { key: "id", header: "ID", render: (p) => <code>{p.profile_id}</code> },
            { key: "name", header: "Nome", render: (p) => p.name },
            { key: "lang", header: "Linguagem", render: (p) => p.language },
            { key: "def", header: "Padrão", render: (p) => (p.is_default ? <Badge tone="primary">Default</Badge> : "-") },
          ]}
          rows={filtered}
          onRowClick={(p) => {
            setSelected(p);
            setEditorMsg(null);
            setEditorErr(null);
          }}
          emptyText="Nenhum Quality Profile encontrado."
        />
      </Card>

      <Dialog open={open} title="Criar Quality Profile" onClose={() => setOpen(false)}>
        {err && <ErrorState message={err} />}
        <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Input placeholder="Nome do Profile" value={name} onChange={(e) => setName(e.target.value)} required />
          <Select value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="python">Python</option>
            <option value="csharp">C#</option>
            <option value="java">Java</option>
            <option value="sql">SQL</option>
          </Select>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button type="submit" disabled={busy}>{busy ? "Criando..." : "Criar"}</Button>
          </div>
        </form>
      </Dialog>

      <Drawer open={Boolean(selected)} title={`Editor de Profile — ${selected?.name ?? ""}`} onClose={() => setSelected(null)}>
        {selected && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {editorErr && <ErrorState message={editorErr} />}
            {editorMsg && (
              <div style={{ padding: 10, borderRadius: "var(--radius-md)", background: "var(--color-success-bg)", color: "var(--color-success)", fontSize: 13 }}>
                {editorMsg}
              </div>
            )}
            <div style={{ fontSize: 13 }}>
              <strong>ID:</strong> <code>{selected.profile_id}</code> | <strong>Linguagem:</strong> {selected.language}
            </div>

            <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Ativar / Desativar Regra</div>
              <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                <Input placeholder="Rule ID (ex: PY-SYN-001)" value={ruleId} onChange={(e) => setRuleId(e.target.value)} style={{ flex: 1 }} />
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <Button
                  size="sm"
                  disabled={busy || !ruleId.trim()}
                  onClick={() =>
                    runProfileAction(
                      `/api/v1/quality-profiles/${selected.profile_id}/rules/activate`,
                      { rule_id: ruleId.trim() },
                      `Regra ${ruleId.trim()} ativada`,
                    )
                  }
                >
                  Ativar Regra
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={busy || !ruleId.trim()}
                  onClick={() =>
                    runProfileAction(
                      `/api/v1/quality-profiles/${selected.profile_id}/rules/${encodeURIComponent(ruleId.trim())}/deactivate`,
                      {},
                      `Regra ${ruleId.trim()} desativada`,
                    )
                  }
                >
                  Desativar Regra
                </Button>
              </div>
            </div>

            <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Associar ao Projeto</div>
              <div style={{ display: "flex", gap: 8 }}>
                <Input placeholder="Project Key" value={projectKey} onChange={(e) => setProjectKey(e.target.value)} style={{ flex: 1 }} />
                <Button
                  size="sm"
                  disabled={busy || !projectKey.trim()}
                  onClick={() =>
                    runProfileAction(
                      `/api/v1/quality-profiles/${selected.profile_id}/projects/${encodeURIComponent(projectKey.trim())}`,
                      {},
                      `Profile associado ao projeto ${projectKey.trim()}`,
                    )
                  }
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
