import { useEffect, useState } from "react";

interface Issue {
  ruleId: string;
  language: string;
  severity: string;
  location: { file: string; startLine: number };
  message: string;
}

interface ProjectIssuesResponse {
  projectKey: string;
  analysisId: string | null;
  status: string;
  totalFiles?: number;
  issues: Issue[];
}

export default function App() {
  const [projectKey, setProjectKey] = useState("demo-r3");
  const [data, setData] = useState<ProjectIssuesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`http://127.0.0.1:8088/api/v1/projects/${encodeURIComponent(projectKey)}/issues`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json: ProjectIssuesResponse) => setData(json))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectKey]);

  return (
    <main style={{ fontFamily: "sans-serif", padding: "1.5rem" }}>
      <h1>POLARIS 2.0 — PoC React + TypeScript</h1>
      <label>
        Projeto:{" "}
        <input value={projectKey} onChange={(e) => setProjectKey(e.target.value)} />
      </label>
      {loading && <p>Carregando análise...</p>}
      {error && <p style={{ color: "red" }}>Erro ao consultar API: {error}</p>}
      {!loading && !error && data && data.issues.length === 0 && (
        <p>Nenhuma issue encontrada para o projeto {data.projectKey}.</p>
      )}
      {!loading && !error && data && data.issues.length > 0 && (
        <div>
          <p>
            Análise: <strong>{data.analysisId}</strong> | Status: <strong>{data.status}</strong>
          </p>
          <table border={1} cellPadding={6}>
            <thead>
              <tr>
                <th>Linguagem</th>
                <th>Regra</th>
                <th>Severidade</th>
                <th>Localização</th>
                <th>Mensagem</th>
              </tr>
            </thead>
            <tbody>
              {data.issues.map((iss, idx) => (
                <tr key={idx}>
                  <td>{iss.language}</td>
                  <td>{iss.ruleId}</td>
                  <td>{iss.severity}</td>
                  <td>{iss.location.file}:{iss.location.startLine}</td>
                  <td>{iss.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
