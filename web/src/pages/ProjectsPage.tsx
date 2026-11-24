import { useState } from "react";
import { Button, Card, DataTable, Dialog, ErrorState, Input } from "../components/ui";
import { ProjectItem } from "../api/types";

export function ProjectsPage({
  projects,
  onCreated,
}: {
  projects: ProjectItem[];
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

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Projetos</h1>
        <Button onClick={() => setOpen(true)}>Novo Projeto</Button>
      </div>
      <Card>
        <div style={{ marginBottom: 12 }}>
          <Input placeholder="Buscar por chave ou nome..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ width: 280 }} />
        </div>
        <DataTable
          columns={[
            { key: "key", header: "Chave", render: (p) => <a href={`#/projects/${encodeURIComponent(p.projectKey)}`}>{p.projectKey}</a> },
            { key: "name", header: "Nome", render: (p) => p.name },
            { key: "action", header: "Ação", render: (p) => <a href={`#/projects/${encodeURIComponent(p.projectKey)}`}>Abrir Overview</a> },
          ]}
          rows={filtered}
          emptyText="Nenhum projeto encontrado."
        />
      </Card>
      <Dialog open={open} title="Criar Projeto" onClose={() => setOpen(false)}>
        {err && <ErrorState message={err} />}
        <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
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
