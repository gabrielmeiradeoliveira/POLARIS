import { useEffect, useState } from "react";
import { polarisApi } from "./api/client";
import { HealthStatus, ProjectItem, VersionInfo } from "./api/types";
import { ErrorState, Skeleton } from "./components/ui";
import { AuthProvider } from "./features/auth/AuthContext";
import { AppLayout } from "./layouts/AppLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { IssuesPage, IssueRow } from "./pages/IssuesPage";
import { ProjectOverviewPage } from "./pages/ProjectOverviewPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { GateRow, QualityGatesPage } from "./pages/QualityGatesPage";
import { ProfileRow, QualityProfilesPage } from "./pages/QualityProfilesPage";
import { RuleRow, RulesPage } from "./pages/RulesPage";
import { StatusPage } from "./pages/StatusPage";
import { AdminPage } from "./pages/AdminPage";
import { CockpitPage } from "./pages/CockpitPage";
import { PullRequestsPage } from "./pages/PullRequestsPage";

type Route = "home" | "status" | "admin" | "projects" | "project-detail" | "issues" | "pull-requests" | "rules" | "profiles" | "gates" | "not-found";

function parseRoute(hash: string): { route: Route; projectKey: string | null } {
  const clean = hash.replace(/^#/, "") || "/";
  if (clean === "/") return { route: "home", projectKey: null };
  if (clean === "/status") return { route: "status", projectKey: null };
  if (clean === "/admin") return { route: "admin", projectKey: null };
  if (clean === "/projects") return { route: "projects", projectKey: null };
  if (clean.startsWith("/projects/")) {
    const key = decodeURIComponent(clean.slice("/projects/".length));
    if (key) return { route: "project-detail", projectKey: key };
  }
  if (clean === "/issues") return { route: "issues", projectKey: null };
  if (clean === "/pull-requests") return { route: "pull-requests", projectKey: null };
  if (clean === "/rules") return { route: "rules", projectKey: null };
  if (clean === "/profiles") return { route: "profiles", projectKey: null };
  if (clean === "/gates") return { route: "gates", projectKey: null };
  return { route: "not-found", projectKey: null };
}

export function App() {
  const [nav, setNav] = useState<{ route: Route; projectKey: string | null }>(() => parseRoute(window.location.hash));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<HealthStatus | null>(null);
  const [ready, setReady] = useState<HealthStatus | null>(null);
  const [version, setVersion] = useState<VersionInfo | null>(null);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [issues, setIssues] = useState<IssueRow[]>([]);
  const [rules, setRules] = useState<RuleRow[]>([]);
  const [profiles, setProfiles] = useState<ProfileRow[]>([]);
  const [gates, setGates] = useState<GateRow[]>([]);

  useEffect(() => {
    const onHashChange = () => setNav(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [liveRes, readyRes, verRes, projRes, issRes, rulRes, profRes, gateRes] = await Promise.all([
        polarisApi.getLive(),
        polarisApi.getReady(),
        polarisApi.getVersion(),
        polarisApi.getProjects(),
        fetch("/api/v1/issues").then((r) => (r.ok ? r.json() : { items: [] })),
        fetch("/api/v1/rules?limit=250").then((r) => (r.ok ? r.json() : { items: [] })),
        fetch("/api/v1/quality-profiles").then((r) => (r.ok ? r.json() : { items: [] })),
        fetch("/api/v1/quality-gates").then((r) => (r.ok ? r.json() : { items: [] })),
      ]);
      setLive(liveRes);
      setReady(readyRes);
      setVersion(verRes);
      setProjects(Array.isArray(projRes) ? projRes : []);
      setIssues(issRes.items ?? []);
      setRules(rulRes.items ?? []);
      setProfiles(profRes.items ?? []);
      setGates(gateRes.items ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar dados");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  return (
    <AuthProvider>
    <AppLayout activeRoute={nav.route} version={version?.version} readyStatus={ready?.status}>
      {error && <ErrorState message={error} onRetry={loadData} />}
      {loading ? (
        <div>
          <Skeleton height={32} />
          <Skeleton height={120} />
        </div>
      ) : (
        <>
          {nav.route === "home" && (
            <DashboardPage projects={projects} issues={issues} rulesCount={rules.length} gatesCount={gates.length} />
          )}
          {nav.route === "projects" && <ProjectsPage projects={projects} onCreated={loadData} />}
          {nav.route === "project-detail" && nav.projectKey && <ProjectOverviewPage projectKey={nav.projectKey} />}
          {nav.route === "issues" && <IssuesPage issues={issues} onMutated={loadData} />}
          {nav.route === "rules" && <RulesPage rules={rules} />}
          {nav.route === "profiles" && <QualityProfilesPage profiles={profiles} onMutated={loadData} />}
          {nav.route === "gates" && <QualityGatesPage gates={gates} onMutated={loadData} />}
          {nav.route === "admin" && <AdminPage />}
          {nav.route === "status" && <StatusPage live={live} ready={ready} version={version} />}
          {nav.route === "not-found" && <p>404 — Página não encontrada.</p>}
        </>
      )}
    </AppLayout>
    </AuthProvider>
  );
}

export default App;
