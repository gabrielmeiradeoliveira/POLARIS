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

export type Route = "home" | "status" | "admin" | "projects" | "project-detail" | "issues" | "pull-requests" | "cockpit" | "rules" | "profiles" | "gates" | "not-found";

export function parseRoute(hash: string): { route: Route; projectKey: string | null; query: URLSearchParams } {
  const clean = hash.replace(/^#/, "") || "/";
  const [pathPart, queryPart] = clean.split("?");
  const query = new URLSearchParams(queryPart || "");

  if (pathPart === "/") return { route: "home", projectKey: null, query };
  if (pathPart === "/status") return { route: "status", projectKey: null, query };
  if (pathPart === "/admin") return { route: "admin", projectKey: null, query };
  if (pathPart === "/projects") return { route: "projects", projectKey: null, query };
  if (pathPart.startsWith("/projects/")) {
    const key = decodeURIComponent(pathPart.slice("/projects/".length));
    if (key) return { route: "project-detail", projectKey: key, query };
  }
  if (pathPart === "/issues") return { route: "issues", projectKey: null, query };
  if (pathPart === "/pull-requests") return { route: "pull-requests", projectKey: null, query };
  if (pathPart === "/cockpit") return { route: "cockpit", projectKey: null, query };
  if (pathPart === "/rules") return { route: "rules", projectKey: null, query };
  if (pathPart === "/profiles") return { route: "profiles", projectKey: null, query };
  if (pathPart === "/gates") return { route: "gates", projectKey: null, query };
  return { route: "not-found", projectKey: null, query };
}

export function App() {
  const [nav, setNav] = useState<{ route: Route; projectKey: string | null; query: URLSearchParams }>(() => parseRoute(window.location.hash));
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

  const handleTriageCockpit = async (issueId: string, status: string) => {
    try {
      await fetch(`/api/v1/issues/${issueId}/transition`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      await loadData();
    } catch {
      // ignore
    }
  };

  // Cálculo de Grade e Gate Status contextual para sincronização da Topbar
  const hasBlockerOrCritical = issues.some(
    (i) => (i.severity === "BLOCKER" || i.severity === "CRITICAL") && i.status !== "FIXED" && i.status !== "FALSE_POSITIVE"
  );
  const openCount = issues.filter((i) => i.status !== "FIXED" && i.status !== "FALSE_POSITIVE").length;
  
  let contextualGrade: "A" | "B" | "C" | "D" | "E" | "F" = "A";
  if (hasBlockerOrCritical) {
    contextualGrade = "F";
  } else if (openCount > 20) {
    contextualGrade = "D";
  } else if (openCount > 10) {
    contextualGrade = "C";
  } else if (openCount > 0) {
    contextualGrade = "B";
  }

  const contextualGateStatus: "PASSED" | "FAILED" = hasBlockerOrCritical ? "FAILED" : "PASSED";

  const contextInfo = {
    grade: contextualGrade,
    gateStatus: contextualGateStatus,
    workspaceName: nav.projectKey ?? (nav.route === "pull-requests" ? (nav.query.get("pr") || "Pull Request") : "Workspace Geral"),
    branch: nav.route === "pull-requests" ? "pr/review" : "main",
  };

  return (
    <AuthProvider>
      <AppLayout
        activeRoute={nav.route}
        version={version?.version}
        readyStatus={ready?.status === "READY" ? undefined : ready?.status}
        contextInfo={contextInfo}
      >
        {error && <ErrorState message={error} onRetry={loadData} />}
        {loading ? (
          <div style={{ padding: 16 }}>
            <Skeleton height={32} />
            <Skeleton height={120} />
          </div>
        ) : (
          <>
            {nav.route === "home" && (
              <DashboardPage projects={projects} issues={issues} rulesCount={rules.length} gatesCount={gates.length} />
            )}
            {nav.route === "projects" && <ProjectsPage projects={projects} issues={issues} onCreated={loadData} />}
            {nav.route === "project-detail" && nav.projectKey && <ProjectOverviewPage projectKey={nav.projectKey} />}
            {nav.route === "issues" && <IssuesPage issues={issues} onMutated={loadData} />}
            {nav.route === "pull-requests" && <PullRequestsPage issues={issues} onMutated={loadData} />}
            {nav.route === "cockpit" && (
              <CockpitPage
                repos={projects.map((p) => ({
                  project_key: p.projectKey,
                  name: p.name,
                  default_branch: "main",
                  languages: ["Python", "TypeScript"],
                  gate_status: "PASSED",
                }))}
                issues={issues}
                onTriage={handleTriageCockpit}
              />
            )}
            {nav.route === "rules" && <RulesPage rules={rules} />}
            {nav.route === "profiles" && <QualityProfilesPage profiles={profiles} onMutated={loadData} />}
            {nav.route === "gates" && <QualityGatesPage gates={gates} onMutated={loadData} />}
            {nav.route === "admin" && <AdminPage />}
            {nav.route === "status" && <StatusPage live={live} ready={ready} version={version} />}
            {nav.route === "not-found" && <p style={{ padding: 16 }}>404 — Página não encontrada.</p>}
          </>
        )}
      </AppLayout>
    </AuthProvider>
  );
}

export default App;
