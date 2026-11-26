import { useEffect, useState } from "react";
import { Badge, Button, Card, DataTable, Dialog, ErrorState, Input, Select, Tabs } from "../components/ui";

interface UserRow {
  username: string;
  role: string;
  active: boolean;
  created_at: string;
}

interface TokenRow {
  token_id: string;
  username: string;
  revoked: boolean;
  expires_at: string | null;
  created_at: string;
}

interface AuditRow {
  action?: string;
  actor?: string;
  target?: string;
  created_at?: string;
}

export function AdminPage() {
  const [tab, setTab] = useState<"users" | "tokens" | "audit">("users");
  const [users, setUsers] = useState<UserRow[]>([]);
  const [tokens, setTokens] = useState<TokenRow[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const [openUser, setOpenUser] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("developer");
  const [createdToken, setCreatedToken] = useState<string | null>(null);

  const load = () => {
    setErr(null);
    Promise.all([
      fetch("/api/v1/admin/users").then((r) => (r.ok ? r.json() : { items: [] })),
      fetch("/api/v1/admin/tokens").then((r) => (r.ok ? r.json() : { items: [] })),
      fetch("/api/v1/admin/audit").then((r) => (r.ok ? r.json() : { items: [] })),
    ])
      .then(([u, t, a]) => {
        setUsers(u.items ?? []);
        setTokens(t.items ?? []);
        setAudit(a.items ?? []);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Erro ao carregar administração"));
  };

  useEffect(load, []);

  const createUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    const r = await fetch("/api/v1/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username.trim(), password, role }),
    });
    if (!r.ok) {
      setErr(`HTTP ${r.status}`);
      return;
    }
    setOpenUser(false);
    setUsername("");
    setPassword("");
    load();
  };

  const createToken = async (user: string) => {
    setErr(null);
    setCreatedToken(null);
    const r = await fetch("/api/v1/admin/tokens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user, expires_in_days: 30 }),
    });
    if (!r.ok) {
      setErr(`HTTP ${r.status}`);
      return;
    }
    const d = await r.json();
    setCreatedToken(d.token ?? d.raw_token ?? null);
    load();
  };

  return (
    <div style={{ padding: "24px 32px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>Administração e Segurança</h1>
        <Button onClick={() => setOpenUser(true)}>Novo Usuário</Button>
      </div>
      {err && <ErrorState message={err} onRetry={load} />}
      {createdToken && (
        <div style={{ padding: 12, marginBottom: 16, borderRadius: "var(--radius-md)", background: "var(--color-success-bg)", color: "var(--color-success)", fontSize: 13 }}>
          <strong>Token gerado (copie agora, não será exibido novamente):</strong> <code>{createdToken}</code>
        </div>
      )}

      <Tabs
        active={tab}
        onChange={(id) => setTab(id as "users" | "tokens" | "audit")}
        tabs={[
          { id: "users", label: `Usuários (${users.length})` },
          { id: "tokens", label: `Tokens (${tokens.length})` },
          { id: "audit", label: `Auditoria (${audit.length})` },
        ]}
      />

      {tab === "users" && (
        <Card>
          <DataTable
            columns={[
              { key: "u", header: "Usuário", render: (u) => u.username },
              { key: "r", header: "Papel", render: (u) => <Badge tone="primary">{u.role}</Badge> },
              { key: "a", header: "Estado", render: (u) => <Badge tone={u.active ? "success" : "error"}>{u.active ? "Ativo" : "Inativo"}</Badge> },
              {
                key: "act",
                header: "Ações",
                render: (u) => (
                  <div style={{ display: "flex", gap: 6 }}>
                    <Button size="sm" variant="secondary" onClick={() => createToken(u.username)}>Gerar Token</Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        fetch(`/api/v1/admin/users/${encodeURIComponent(u.username)}/status?active=${!u.active}`, { method: "PATCH" }).then(load);
                      }}
                    >
                      {u.active ? "Desativar" : "Ativar"}
                    </Button>
                  </div>
                ),
              },
            ]}
            rows={users}
            emptyText="Nenhum usuário cadastrado."
          />
        </Card>
      )}

      {tab === "tokens" && (
        <Card>
          <DataTable
            columns={[
              { key: "id", header: "ID", render: (t) => <code>{t.token_id}</code> },
              { key: "u", header: "Usuário", render: (t) => t.username },
              { key: "s", header: "Estado", render: (t) => <Badge tone={t.revoked ? "error" : "success"}>{t.revoked ? "Revogado" : "Ativo"}</Badge> },
              { key: "e", header: "Expira em", render: (t) => t.expires_at ?? "-" },
              {
                key: "act",
                header: "Ação",
                render: (t) =>
                  !t.revoked ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        fetch(`/api/v1/admin/tokens/${encodeURIComponent(t.token_id)}/revoke`, { method: "POST" }).then(load);
                      }}
                    >
                      Revogar
                    </Button>
                  ) : (
                    "-"
                  ),
              },
            ]}
            rows={tokens}
            emptyText="Nenhum token emitido."
          />
        </Card>
      )}

      {tab === "audit" && (
        <Card>
          <DataTable
            columns={[
              { key: "act", header: "Ação", render: (a) => a.action ?? "-" },
              { key: "actor", header: "Ator", render: (a) => a.actor ?? "-" },
              { key: "target", header: "Alvo", render: (a) => a.target ?? "-" },
              { key: "dt", header: "Data", render: (a) => a.created_at ?? "-" },
            ]}
            rows={audit}
            emptyText="Nenhum evento de auditoria registrado."
          />
        </Card>
      )}

      <Dialog open={openUser} title="Criar Usuário" onClose={() => setOpenUser(false)}>
        <form onSubmit={createUser} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Input placeholder="Usuário" value={username} onChange={(e) => setUsername(e.target.value)} required />
          <Input type="password" placeholder="Senha" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <Select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="admin">admin</option>
            <option value="security_analyst">security_analyst</option>
            <option value="developer">developer</option>
            <option value="viewer">viewer</option>
          </Select>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button type="button" variant="secondary" onClick={() => setOpenUser(false)}>Cancelar</Button>
            <Button type="submit">Criar</Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
