import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type QualityGrade = "A" | "B" | "C" | "D" | "F" | "NOT_RATED";
type QualityGateStatus = "PASSED" | "FAILED" | "INCONCLUSIVE";
type TopNavPage =
  | "dashboard"
  | "repositories"
  | "pull-requests"
  | "findings"
  | "analytics"
  | "settings"
  | "project-detail"
  | "pr-detail";
type ProjectTab = "overview" | "pull-requests" | "findings" | "history" | "settings";

interface QualityGateCondition {
  criterion: string;
  passed: boolean;
  actual: string;
  threshold: string;
  reason: string;
}

interface QualityGateResult {
  gate_version: string;
  status: QualityGateStatus;
  passed: boolean;
  reasons: string[];
  conditions: QualityGateCondition[];
}

interface AnalysisScopeSummary {
  operational_status: string;
  files_analyzed_count: number;
  files_analyzed: string[];
  modules_executed: string[];
  is_complete: boolean;
  has_sufficient_evidence: boolean;
  truncation_warnings: string[];
  warning_count: number;
}

interface QualityEvaluation {
  formula_version: string;
  grade: QualityGrade;
  score: number | null;
  total_penalty: number;
  not_rated_reason: string | null;
  explanation: string;
  severity_counts: Record<string, number>;
  confidence_counts: Record<string, number>;
  vulnerability_count?: number;
  bug_count?: number;
  scope: AnalysisScopeSummary;
}

interface Finding {
  id: string;
  module_id?: string;
  severity: string;
  confidence: string;
  category: string;
  file_path: string;
  line_range?: { start_line: number; end_line: number };
  title: string;
  description: string;
  evidence: string;
  suggested_remediation?: string | null;
  is_vulnerability?: boolean;
  finding_type?: "vulnerability" | "bug";
  addressed_gate_conditions?: string[];
  github_blob_url?: string | null;
  safe_code_example?: string | null;
  project_id?: string;
  project_name?: string;
  commit_sha?: string;
}

interface ComparedFindingItem {
  classification: "new" | "existing" | "resolved" | "uncertain";
  finding: Finding;
  stable_fingerprint: string;
  matched_baseline_finding_id: string | null;
  similarity_score: number;
  reason: string;
  is_vulnerability?: boolean;
  addressed_gate_conditions?: string[];
  github_blob_url?: string | null;
  safe_code_example?: string | null;
}

interface PullRequestComparison {
  comparison_version: string;
  base_revision: string | null;
  head_revision: string | null;
  base_evaluation: QualityEvaluation;
  pr_evaluation: QualityEvaluation;
  quality_gate: QualityGateResult;
  grade_delta: string;
  score_delta: number | null;
  counts: { new: number; existing: number; resolved: number; uncertain: number };
  new_findings: ComparedFindingItem[];
  existing_findings: ComparedFindingItem[];
  resolved_findings: ComparedFindingItem[];
  uncertain_findings: ComparedFindingItem[];
  summary: string;
  baseline_job_id?: string;
  candidate_job_id?: string;
}

interface Job {
  id: string;
  project_id: string;
  project_name: string;
  project_path?: string;
  github_owner?: string | null;
  github_name?: string | null;
  base_revision: string | null;
  head_sha?: string | null;
  commit_sha?: string | null;
  analysis_mode: "project" | "pr";
  baseline_job_id: string | null;
  pull_request_number?: number | null;
  status: string;
  created_at: string;
  finished_at: string | null;
  error: string | null;
  findings_count: number;
  vulnerability_count?: number;
  bug_count?: number;
  quality?: QualityEvaluation;
  quality_gate?: QualityGateResult;
  comparison?: PullRequestComparison | null;
  warnings?: Array<{ code: string; message: string }>;
  files_analyzed?: string[];
  findings?: Finding[];
}

interface PullRequestItem {
  id: string;
  project_id: string;
  project_name: string;
  github_owner: string | null;
  github_name: string | null;
  number: number;
  title: string;
  state: string;
  author_login: string;
  head_ref: string;
  base_ref: string;
  head_sha: string;
  base_sha: string;
  is_fork: boolean;
  merged: boolean;
  html_url: string | null;
  diff_url: string | null;
  analysis_status: string;
  is_stale_sha?: boolean;
  latest_base_job_id: string | null;
  latest_candidate_job_id: string | null;
  last_analyzed_sha: string | null;
  last_analyzed_at: string | null;
  base_grade: QualityGrade;
  base_score: number | null;
  head_grade: QualityGrade;
  head_score: number | null;
  grade_delta: string;
  score_delta: number | null;
  new_critical_count: number;
  new_high_count: number;
  counts: { new: number; existing: number; resolved: number; uncertain: number };
  quality_gate_status: QualityGateStatus;
  quality_gate: QualityGateResult | null;
  error: string | null;
  comparison?: PullRequestComparison | null;
  candidate_job?: Job | null;
  base_job?: Job | null;
}

interface QualityTrendPoint {
  job_id: string;
  commit_sha: string | null;
  status: string;
  grade: QualityGrade;
  score: number | null;
  findings_count: number;
  vulnerability_count: number;
  bug_count: number;
  created_at: string;
}

interface Project {
  id: string;
  name: string;
  path: string;
  github_repository_id?: number | null;
  github_owner?: string | null;
  github_name?: string | null;
  github_default_branch?: string | null;
  owner: string;
  repository_name: string;
  full_name: string;
  language: string | null;
  default_branch: string;
  is_private: boolean;
  is_archived: boolean;
  is_fork: boolean;
  sync_status: string;
  auto_analyze: boolean;
  last_synced_at: string | null;
  last_analyzed_sha: string | null;
  last_successful_analysis_at: string | null;
  created_at: string;
  analysis_count: number;
  project_analysis_count?: number;
  open_pr_count: number;
  latest_job_id: string | null;
  latest_status: string | null;
  analysis_status: string;
  latest_grade: QualityGrade | null;
  latest_score: number | null;
  latest_gate_status: QualityGateStatus | null;
  vulnerability_count: number | null;
  bug_count: number | null;
  findings_count: number | null;
  severity_counts: Record<string, number> | null;
  gate_config?: {
    min_grade: "A" | "B" | "C" | "D";
    max_critical_findings: number;
    max_high_findings: number;
    max_new_critical_findings: number;
    max_new_high_findings: number;
    max_total_new_findings: number;
    require_complete_analysis: boolean;
  };
  analyses?: Job[];
  pull_requests?: PullRequestItem[];
  latest_analysis?: Job | null;
  quality_trend?: QualityTrendPoint[];
}

interface SyncSettings {
  auto_discover_repos: boolean;
  auto_analyze_initial: boolean;
  auto_analyze_prs: boolean;
  allow_private_repo_analysis: boolean;
  allow_fork_pr_analysis: boolean;
  sync_interval_seconds: number;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
  pat_configured?: boolean;
  github_app_webhook_configured?: boolean;
  sync_mode?: "pat_polling" | "github_app_webhook" | "offline";
  realtime_webhooks?: boolean;
  pat_local_only?: boolean;
}

interface AnalyticsSummary {
  total_repositories: number;
  analyzed_repositories: number;
  not_analyzed_repositories: number;
  average_score: number | null;
  grade_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  gate_distribution: Record<string, number>;
  total_vulnerabilities: number;
  total_bugs: number;
  severity_totals: Record<string, number>;
  total_pull_requests: number;
  open_pull_requests: number;
  blocked_pull_requests: number;
  passed_pull_requests: number;
}

const API_BASE = import.meta.env.VITE_API_BASE || "";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || "Request failed.");
  }
  return response.json() as Promise<T>;
}

function PolarisLogo() {
  return (
    <svg
      className="brand-logo"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Polaris Logo"
    >
      <circle cx="32" cy="32" r="24" stroke="url(#polaris-ring)" strokeWidth="2" strokeDasharray="6 4" />
      <path d="M32 10 A22 22 0 0 1 54 32" stroke="#38BDF8" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M32 54 A22 22 0 0 1 10 32" stroke="#6366F1" strokeWidth="2.5" strokeLinecap="round" />
      <path
        d="M23 23 L32 27.5 L41 23 L36.5 32 L41 41 L32 36.5 L23 41 L27.5 32 Z"
        fill="#1E293B"
        stroke="#6366F1"
        strokeWidth="1.5"
      />
      <path d="M32 4 L36.2 26.2 L58 32 L36.2 37.8 L32 60 L27.8 37.8 L6 32 L27.8 26.2 Z" fill="url(#polaris-star)" />
      <circle cx="32" cy="32" r="3.5" fill="#F8FAFC" />
      <defs>
        <linearGradient id="polaris-star" x1="6" y1="4" x2="58" y2="60" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#E0F2FE" />
          <stop offset="45%" stopColor="#38BDF8" />
          <stop offset="100%" stopColor="#6366F1" />
        </linearGradient>
        <linearGradient id="polaris-ring" x1="8" y1="8" x2="56" y2="56" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.65" />
          <stop offset="100%" stopColor="#6366F1" stopOpacity="0.25" />
        </linearGradient>
      </defs>
    </svg>
  );
}

function GradeBadge({
  grade,
  size = "md",
  testId,
}: {
  grade?: QualityGrade | string | null;
  size?: "sm" | "md" | "lg";
  testId?: string;
}) {
  const normalized = (grade || "NOT_RATED") as QualityGrade;
  const label = normalized === "NOT_RATED" ? "N/R" : normalized;
  return (
    <span
      className={`grade-badge ${size} grade-${normalized}`}
      title={normalized === "NOT_RATED" ? "NOT_RATED (Insufficient or unanalyzed scope)" : `Quality Grade ${normalized}`}
      data-testid={testId}
    >
      {label}
    </span>
  );
}

function formatShortSha(sha?: string | null): string {
  if (!sha) return "—";
  return sha.length > 8 ? sha.slice(0, 7) : sha;
}

function formatTimestamp(iso?: string | null): string {
  if (!iso) return "Never";
  try {
    const dt = new Date(iso);
    return dt.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function App() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [activePage, setActivePage] = useState<TopNavPage>("repositories");
  const [projectTab, setProjectTab] = useState<ProjectTab>("overview");

  const [projects, setProjects] = useState<Project[]>([]);
  const [pullRequests, setPullRequests] = useState<PullRequestItem[]>([]);
  const [globalFindings, setGlobalFindings] = useState<Finding[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [settings, setSettings] = useState<SyncSettings | null>(null);
  const [gitHubUser, setGitHubUser] = useState<string | null>(null);

  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [projectDetail, setProjectDetail] = useState<Project | null>(null);
  const [selectedHistoricalJob, setSelectedHistoricalJob] = useState<Job | null>(null);

  const [selectedPrId, setSelectedPrId] = useState<string | null>(null);
  const [prDetail, setPrDetail] = useState<PullRequestItem | null>(null);

  // Comparison state for manual baseline vs candidate comparison in History tab
  const [baseJobId, setBaseJobId] = useState<string>("");
  const [candidateJobId, setCandidateJobId] = useState<string>("");
  const [manualComparison, setManualComparison] = useState<PullRequestComparison | null>(null);

  // Repository Table Filters & Pagination
  const [repoSearch, setRepoSearch] = useState("");
  const [repoGradeFilter, setRepoGradeFilter] = useState("ALL");
  const [repoStatusFilter, setRepoStatusFilter] = useState("ALL");
  const [repoSyncFilter, setRepoSyncFilter] = useState("ALL");
  const [repoSortBy, setRepoSortBy] = useState("created_at");
  const [repoSortDir, setRepoSortDir] = useState<"asc" | "desc">("desc");
  const [repoPage, setRepoPage] = useState(1);
  const repoPerPage = 15;

  // Local repository registration drawer
  const [showLocalForm, setShowLocalForm] = useState(false);
  const [localName, setLocalName] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [manualRevision, setManualRevision] = useState("");
  const [manualPrNumber, setManualPrNumber] = useState("");

  // Findings Filters
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [findingSearch, setFindingSearch] = useState("");
  const [findingSort, setFindingSort] = useState<"severity" | "file" | "category">("severity");

  // PR Details Delta Filter
  const [prDeltaFilter, setPrDeltaFilter] = useState<"all" | "new" | "existing" | "resolved" | "uncertain">("all");

  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [busyAction, setBusyAction] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncNotice, setSyncNotice] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const loadProjectDetail = useCallback(async (projId: string) => {
    const detail = await apiFetch<Project>(`/api/projects/${projId}`);
    setProjectDetail(detail);
    // Strict repository isolation: only set historical job if it belongs to this project
    if (detail.latest_analysis && detail.latest_analysis.project_id === projId) {
      setSelectedHistoricalJob(detail.latest_analysis);
    } else {
      setSelectedHistoricalJob(null);
    }
    const projAnalyses = detail.analyses || [];
    if (projAnalyses.length >= 2) {
      setCandidateJobId(projAnalyses[0].id);
      setBaseJobId(projAnalyses[1].id);
    } else if (projAnalyses.length === 1) {
      setCandidateJobId(projAnalyses[0].id);
      setBaseJobId(projAnalyses[0].id);
    } else {
      setCandidateJobId("");
      setBaseJobId("");
    }
    return detail;
  }, []);

  const loadPrDetail = useCallback(async (prId: string) => {
    const detail = await apiFetch<PullRequestItem>(`/api/pull-requests/${prId}`);
    setPrDetail(detail);
    return detail;
  }, []);

  const refreshPlatform = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        const [projList, prList, analyticsData, settingsData] = await Promise.all([
          apiFetch<Project[]>("/api/projects"),
          apiFetch<PullRequestItem[]>("/api/pull-requests"),
          apiFetch<AnalyticsSummary>("/api/analytics"),
          apiFetch<SyncSettings>("/api/settings"),
        ]);
        setProjects(projList);
        setPullRequests(prList);
        setAnalytics(analyticsData);
        setSettings(settingsData);

        if (selectedProjectId) {
          await loadProjectDetail(selectedProjectId);
        }
        if (selectedPrId) {
          await loadPrDetail(selectedPrId);
        }
        if (activePage === "findings") {
          const gf = await apiFetch<Finding[]>("/api/findings");
          setGlobalFindings(gf);
        }
        setError(null);
        return { projList, settingsData };
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load platform state.");
        return null;
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [selectedProjectId, selectedPrId, activePage, loadProjectDetail, loadPrDetail]
  );

  const triggerGitHubSync = useCallback(
    async (projectId?: string, silent = false) => {
      if (!silent) setSyncing(true);
      try {
        const res = await apiFetch<{
          discovered_count: number;
          new_count: number;
          prs_synced: number;
          jobs_enqueued: number;
        }>("/api/github/sync", {
          method: "POST",
          body: JSON.stringify({
            sync_prs: true,
            enqueue_jobs: true,
            project_id: projectId || null,
          }),
        });
        if (!silent) {
          setSyncNotice(
            `Synchronized ${res.discovered_count} repositories (${res.new_count} new), ${res.prs_synced} open PRs, ${res.jobs_enqueued} analysis job(s) scheduled.`
          );
        }
        await refreshPlatform(true);
      } catch (err) {
        if (!silent) {
          setError(err instanceof Error ? err.message : "GitHub synchronization failed.");
        }
      } finally {
        if (!silent) setSyncing(false);
      }
    },
    [refreshPlatform]
  );

  // Initial load & automatic GitHub discovery when PAT is configured
  useEffect(() => {
    let mounted = true;
    (async () => {
      const initial = await refreshPlatform(false);
      if (!initial?.settingsData?.pat_configured) {
        if (mounted) setGitHubUser(null);
        return;
      }
      try {
        const pat = await apiFetch<{ configured: boolean; login: string }>("/api/github/pat/status");
        if (mounted && pat.configured) {
          setGitHubUser(pat.login);
          const hasGitHubRepos = initial?.projList.some((p) => Boolean(p.github_repository_id));
          if (initial?.settingsData?.auto_discover_repos && !hasGitHubRepos) {
            await triggerGitHubSync(undefined, true);
          }
        }
      } catch {
        if (mounted) setGitHubUser(null);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  // Poll when any job is queued or running
  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshPlatform(true);
    }, 3500);
    return () => window.clearInterval(timer);
  }, [refreshPlatform]);

  // Load global findings when switching to Global Findings page
  useEffect(() => {
    if (activePage === "findings") {
      void apiFetch<Finding[]>("/api/findings")
        .then(setGlobalFindings)
        .catch(() => {});
    }
  }, [activePage]);

  async function openProject(proj: Project, initialTab: ProjectTab = "overview") {
    setSelectedProjectId(proj.id);
    setProjectTab(initialTab);
    setManualComparison(null);
    setActivePage("project-detail");
    await loadProjectDetail(proj.id);
  }

  async function openPullRequest(pr: PullRequestItem) {
    setSelectedPrId(pr.id);
    setPrDeltaFilter("all");
    setActivePage("pr-detail");
    await loadPrDetail(pr.id);
  }

  async function handleCreateLocalProject(event: FormEvent) {
    event.preventDefault();
    if (!localName.trim() || !localPath.trim()) return;
    setBusyAction(true);
    setError(null);
    try {
      const created = await apiFetch<Project>("/api/projects", {
        method: "POST",
        body: JSON.stringify({ name: localName.trim(), path: localPath.trim() }),
      });
      setLocalName("");
      setLocalPath("");
      setShowLocalForm(false);
      await refreshPlatform(true);
      await openProject(created, "overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to register local repository.");
    } finally {
      setBusyAction(false);
    }
  }

  async function handleStartBranchAnalysis(projId: string) {
    setBusyAction(true);
    setError(null);
    try {
      const createdJob = await apiFetch<Job>(`/api/projects/${projId}/analyses`, {
        method: "POST",
        body: JSON.stringify({
          base_revision: manualRevision.trim() || null,
          analysis_mode: "project",
        }),
      });
      await loadProjectDetail(projId);
      setSelectedHistoricalJob(createdJob);
      await refreshPlatform(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start branch analysis.");
    } finally {
      setBusyAction(false);
    }
  }

  async function handleManualGitHubPrAnalysis(projId: string) {
    const num = Number(manualPrNumber);
    if (!Number.isInteger(num) || num <= 0) return;
    setBusyAction(true);
    setError(null);
    try {
      await apiFetch(`/api/projects/${projId}/github/pull-requests`, {
        method: "POST",
        body: JSON.stringify({ number: num }),
      });
      setManualPrNumber("");
      await loadProjectDetail(projId);
      await refreshPlatform(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to analyze GitHub pull request.");
    } finally {
      setBusyAction(false);
    }
  }

  async function handleRunManualComparison() {
    if (!baseJobId || !candidateJobId) return;
    setBusyAction(true);
    setError(null);
    try {
      const result = await apiFetch<PullRequestComparison>("/api/comparisons", {
        method: "POST",
        body: JSON.stringify({
          baseline_job_id: baseJobId,
          candidate_job_id: candidateJobId,
        }),
      });
      setManualComparison(result);
      if (selectedProjectId) {
        await loadProjectDetail(selectedProjectId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to compare runs.");
    } finally {
      setBusyAction(false);
    }
  }

  async function handleToggleSetting(key: keyof SyncSettings, val: boolean) {
    try {
      const updated = await apiFetch<SyncSettings>("/api/settings", {
        method: "PUT",
        body: JSON.stringify({ [key]: val }),
      });
      setSettings(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update setting.");
    }
  }

  // Filtered & sorted repositories for the Global Repository Dashboard
  const filteredRepositories = useMemo(() => {
    let list = [...projects];
    if (repoSearch.trim()) {
      const q = repoSearch.trim().toLowerCase();
      list = list.filter(
        (p) =>
          p.full_name.toLowerCase().includes(q) ||
          p.owner.toLowerCase().includes(q) ||
          (p.language || "").toLowerCase().includes(q) ||
          (p.last_analyzed_sha || "").toLowerCase().includes(q)
      );
    }
    if (repoGradeFilter !== "ALL") {
      list = list.filter((p) => (p.latest_grade || "NOT_RATED") === repoGradeFilter);
    }
    if (repoStatusFilter !== "ALL") {
      list = list.filter((p) => p.analysis_status === repoStatusFilter);
    }
    if (repoSyncFilter !== "ALL") {
      list = list.filter((p) => p.sync_status === repoSyncFilter);
    }
    const gradeOrder: Record<string, number> = { A: 5, B: 4, C: 3, D: 2, F: 1, NOT_RATED: 0 };
    const dir = repoSortDir === "asc" ? 1 : -1;
    list.sort((a, b) => {
      if (repoSortBy === "name") {
        return a.full_name.localeCompare(b.full_name) * dir;
      }
      if (repoSortBy === "grade") {
        return ((gradeOrder[a.latest_grade || "NOT_RATED"] || 0) - (gradeOrder[b.latest_grade || "NOT_RATED"] || 0)) * dir;
      }
      if (repoSortBy === "score") {
        return ((a.latest_score ?? -1) - (b.latest_score ?? -1)) * dir;
      }
      if (repoSortBy === "vulnerabilities") {
        return ((a.vulnerability_count ?? -1) - (b.vulnerability_count ?? -1)) * dir;
      }
      if (repoSortBy === "findings") {
        return ((a.findings_count ?? -1) - (b.findings_count ?? -1)) * dir;
      }
      return (a.created_at || "").localeCompare(b.created_at || "") * dir;
    });
    return list;
  }, [projects, repoSearch, repoGradeFilter, repoStatusFilter, repoSyncFilter, repoSortBy, repoSortDir]);

  const totalRepoPages = Math.max(1, Math.ceil(filteredRepositories.length / repoPerPage));
  const paginatedRepositories = useMemo(() => {
    const start = (repoPage - 1) * repoPerPage;
    return filteredRepositories.slice(start, start + repoPerPage);
  }, [filteredRepositories, repoPage]);

  // Strictly scoped active findings for the currently viewed project or global findings view
  const activeProjectJob: Job | null = useMemo(() => {
    if (!projectDetail) return null;
    if (
      selectedHistoricalJob &&
      selectedHistoricalJob.project_id === projectDetail.id
    ) {
      return selectedHistoricalJob;
    }
    if (
      projectDetail.latest_analysis &&
      projectDetail.latest_analysis.project_id === projectDetail.id
    ) {
      return projectDetail.latest_analysis;
    }
    return null;
  }, [projectDetail, selectedHistoricalJob]);

  const filteredFindings = useMemo(() => {
    const rawSource: Finding[] =
      activePage === "project-detail"
        ? activeProjectJob?.findings || []
        : globalFindings;

    const sevRank: Record<string, number> = { critical: 5, high: 4, medium: 3, low: 2, info: 1 };
    return rawSource
      .filter((f) => {
        if (severityFilter !== "ALL" && f.severity !== severityFilter) return false;
        if (categoryFilter !== "ALL" && f.category !== categoryFilter) return false;
        if (typeFilter !== "ALL" && (f.finding_type || (f.is_vulnerability ? "vulnerability" : "bug")) !== typeFilter) {
          return false;
        }
        if (findingSearch.trim()) {
          const q = findingSearch.trim().toLowerCase();
          const match =
            f.file_path.toLowerCase().includes(q) ||
            f.title.toLowerCase().includes(q) ||
            f.description.toLowerCase().includes(q) ||
            f.evidence.toLowerCase().includes(q) ||
            (f.project_name || "").toLowerCase().includes(q);
          if (!match) return false;
        }
        return true;
      })
      .sort((a, b) => {
        if (findingSort === "file") {
          return a.file_path.localeCompare(b.file_path);
        }
        if (findingSort === "category") {
          return a.category.localeCompare(b.category);
        }
        return (sevRank[b.severity] || 0) - (sevRank[a.severity] || 0);
      });
  }, [activePage, activeProjectJob, globalFindings, severityFilter, categoryFilter, typeFilter, findingSearch, findingSort]);

  const findingCategories = useMemo(() => {
    const rawSource: Finding[] =
      activePage === "project-detail"
        ? activeProjectJob?.findings || []
        : globalFindings;
    return Array.from(new Set(rawSource.map((f) => f.category))).sort();
  }, [activePage, activeProjectJob, globalFindings]);

  function renderRepositoriesTable(items: Project[]) {
    if (items.length === 0) {
      return (
        <div className="empty-state" data-testid="empty-repositories">
          <h3>No repositories match the current filters</h3>
          <p>Sync with GitHub or register a local repository to begin continuous code-quality tracking.</p>
        </div>
      );
    }
    return (
      <div className="table-container" data-testid="repositories-table">
        <table className="data-table">
          <thead>
            <tr>
              <th>Repository</th>
              <th>Language</th>
              <th>Branch</th>
              <th>Quality Grade</th>
              <th>Score</th>
              <th>Vulnerabilities</th>
              <th>Findings (C / H / M / L)</th>
              <th>Quality Gate</th>
              <th>Last Commit</th>
              <th>Last Analyzed</th>
              <th>Analysis Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((repo) => {
              const isAnalyzed =
                repo.analysis_status === "completed" || repo.analysis_status === "incomplete";
              const sev = repo.severity_counts;
              return (
                <tr
                  key={repo.id}
                  className="clickable-row"
                  data-testid={`repo-row-${repo.repository_name}`}
                  onClick={() => void openProject(repo, "overview")}
                >
                  <td>
                    <div style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                      <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>
                        {repo.owner} /{" "}
                      </span>
                      {repo.repository_name}
                    </div>
                    <div style={{ display: "flex", gap: 6, marginTop: 3 }}>
                      <span className="sha-chip" style={{ fontSize: 10 }}>
                        {repo.sync_status.toUpperCase()}
                      </span>
                      {repo.is_private && (
                        <span className="sha-chip" style={{ fontSize: 10 }}>
                          PRIVATE
                        </span>
                      )}
                      {repo.is_archived && (
                        <span className="sha-chip" style={{ fontSize: 10 }}>
                          ARCHIVED
                        </span>
                      )}
                    </div>
                  </td>
                  <td>{repo.language || "—"}</td>
                  <td>
                    <span className="sha-chip">{repo.default_branch}</span>
                  </td>
                  <td>
                    <GradeBadge
                      grade={repo.latest_grade}
                      size="sm"
                      testId={`repo-grade-${repo.repository_name}`}
                    />
                  </td>
                  <td className="mono">
                    {repo.latest_score !== null && repo.latest_score !== undefined
                      ? `${repo.latest_score.toFixed(1)}`
                      : "—"}
                  </td>
                  <td className="mono" data-testid={`repo-vuln-${repo.repository_name}`}>
                    {isAnalyzed && repo.vulnerability_count !== null ? (
                      <span
                        style={{
                          fontWeight: 700,
                          color:
                            repo.vulnerability_count > 0
                              ? "var(--grade-f-fg)"
                              : "var(--grade-a-fg)",
                        }}
                      >
                        {repo.vulnerability_count}
                      </span>
                    ) : (
                      <span style={{ color: "var(--text-muted)" }}>—</span>
                    )}
                  </td>
                  <td>
                    {isAnalyzed && sev ? (
                      <div className="sev-mini-row">
                        <span
                          className="sev-mini-item"
                          style={{ color: sev.critical > 0 ? "var(--grade-f-fg)" : undefined }}
                        >
                          C:{sev.critical}
                        </span>
                        <span
                          className="sev-mini-item"
                          style={{ color: sev.high > 0 ? "var(--grade-d-fg)" : undefined }}
                        >
                          H:{sev.high}
                        </span>
                        <span className="sev-mini-item">M:{sev.medium}</span>
                        <span className="sev-mini-item">L:{sev.low}</span>
                      </div>
                    ) : (
                      <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
                        {repo.analysis_status === "NOT_ANALYZED"
                          ? "Not analyzed"
                          : repo.analysis_status}
                      </span>
                    )}
                  </td>
                  <td>
                    {repo.latest_gate_status ? (
                      <span className={`gate-pill gate-${repo.latest_gate_status}`}>
                        {repo.latest_gate_status}
                      </span>
                    ) : (
                      <span className="status-pill status-NOT_ANALYZED">N/A</span>
                    )}
                  </td>
                  <td>
                    <span className="sha-chip">{formatShortSha(repo.last_analyzed_sha)}</span>
                  </td>
                  <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    {formatTimestamp(repo.last_successful_analysis_at)}
                  </td>
                  <td>
                    <span
                      className={`status-pill status-${repo.analysis_status}`}
                      data-testid={`repo-status-${repo.repository_name}`}
                    >
                      {repo.analysis_status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  function renderPullRequestsTable(items: PullRequestItem[], showRepoColumn = true) {
    if (items.length === 0) {
      return (
        <div className="empty-state" data-testid="empty-prs">
          <h3>No pull requests discovered</h3>
          <p>Open pull requests on synchronized repositories are discovered and evaluated automatically.</p>
        </div>
      );
    }
    return (
      <div className="table-container" data-testid="pr-table">
        <table className="data-table">
          <thead>
            <tr>
              {showRepoColumn && <th>Repository</th>}
              <th>Pull Request</th>
              <th>Branches</th>
              <th>Author</th>
              <th>Analysis Status</th>
              <th>Base Grade</th>
              <th>Proposed Head Grade</th>
              <th>Grade Change</th>
              <th>New Crit / High</th>
              <th>Quality Gate</th>
              <th>Last Analyzed SHA / Time</th>
            </tr>
          </thead>
          <tbody>
            {items.map((pr) => (
              <tr
                key={pr.id}
                className="clickable-row"
                data-testid={`pr-row-${pr.number}`}
                onClick={() => void openPullRequest(pr)}
              >
                {showRepoColumn && (
                  <td style={{ fontWeight: 600 }}>{pr.project_name}</td>
                )}
                <td>
                  <div style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                    #{pr.number} · {pr.title}
                  </div>
                  <div style={{ display: "flex", gap: 6, marginTop: 3 }}>
                    <span className="sha-chip" style={{ fontSize: 10 }}>
                      {pr.state.toUpperCase()}
                    </span>
                    {pr.is_fork && (
                      <span className="sha-chip" style={{ fontSize: 10 }}>
                        FORK
                      </span>
                    )}
                  </div>
                </td>
                <td>
                  <span className="sha-chip">
                    {pr.head_ref} → {pr.base_ref}
                  </span>
                </td>
                <td className="mono">@{pr.author_login}</td>
                <td>
                  <span className={`status-pill status-${pr.analysis_status}`}>
                    {pr.analysis_status}
                  </span>
                </td>
                <td>
                  <GradeBadge
                    grade={pr.base_grade}
                    size="sm"
                    testId={`pr-row-base-grade-${pr.number}`}
                  />
                </td>
                <td>
                  <GradeBadge
                    grade={pr.head_grade}
                    size="sm"
                    testId={`pr-row-head-grade-${pr.number}`}
                  />
                </td>
                <td>
                  <span
                    className="mono"
                    style={{ fontWeight: 700 }}
                    data-testid={`pr-row-delta-${pr.number}`}
                  >
                    {pr.grade_delta}
                  </span>
                </td>
                <td className="mono">
                  <span
                    style={{
                      color: pr.new_critical_count > 0 ? "var(--grade-f-fg)" : undefined,
                      fontWeight: pr.new_critical_count > 0 ? 700 : 400,
                    }}
                  >
                    {pr.new_critical_count} crit
                  </span>{" "}
                  /{" "}
                  <span
                    style={{
                      color: pr.new_high_count > 0 ? "var(--grade-d-fg)" : undefined,
                      fontWeight: pr.new_high_count > 0 ? 700 : 400,
                    }}
                  >
                    {pr.new_high_count} high
                  </span>
                </td>
                <td>
                  <span
                    className={`gate-pill gate-${pr.quality_gate_status}`}
                    data-testid={`pr-row-gate-${pr.number}`}
                  >
                    {pr.quality_gate_status}
                  </span>
                </td>
                <td>
                  <div>
                    <span className="sha-chip">
                      {formatShortSha(pr.last_analyzed_sha || pr.head_sha)}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
                    {formatTimestamp(pr.last_analyzed_at)}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  function renderFindingsView(showProjectColumn: boolean) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="filter-toolbar" data-testid="findings-filter-bar">
          <div className="filter-group">
            <input
              className="input-field"
              placeholder="Search file, rule, evidence..."
              value={findingSearch}
              onChange={(e) => setFindingSearch(e.target.value)}
              data-testid="finding-search"
              style={{ minWidth: 240 }}
            />
            <select
              className="select-field"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              data-testid="severity-filter"
            >
              <option value="ALL">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="info">Info</option>
            </select>
            <select
              className="select-field"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              data-testid="type-filter"
            >
              <option value="ALL">All Types (Vuln + Bug)</option>
              <option value="vulnerability">Vulnerabilities Only</option>
              <option value="bug">Correctness Bugs Only</option>
            </select>
            <select
              className="select-field"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              data-testid="category-filter"
            >
              <option value="ALL">All Categories</option>
              {findingCategories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-group">
            <label style={{ fontSize: 12, color: "var(--text-secondary)" }}>Sort:</label>
            <select
              className="select-field"
              value={findingSort}
              onChange={(e) => setFindingSort(e.target.value as "severity" | "file" | "category")}
            >
              <option value="severity">Severity</option>
              <option value="file">File Path</option>
              <option value="category">Category</option>
            </select>
          </div>
        </div>

        {filteredFindings.length === 0 ? (
          <div className="empty-state" data-testid="empty-findings">
            <h3>No findings match the current scope</h3>
            <p>
              {activePage === "project-detail" && projectDetail?.analysis_status === "NOT_ANALYZED"
                ? "This repository has not been analyzed yet (NOT_ANALYZED)."
                : "Zero findings detected for the active filter criteria."}
            </p>
          </div>
        ) : (
          <div className="table-container" data-testid="findings-table">
            <table className="data-table">
              <thead>
                <tr>
                  {showProjectColumn && <th>Repository / SHA</th>}
                  <th>Severity / Type</th>
                  <th>Category</th>
                  <th>Location</th>
                  <th>Finding, Evidence & Remediation</th>
                </tr>
              </thead>
              <tbody>
                {filteredFindings.map((f) => {
                  const isVuln = f.is_vulnerability || f.finding_type === "vulnerability";
                  const startLine = f.line_range?.start_line || 1;
                  const endLine = f.line_range?.end_line || startLine;
                  return (
                    <tr key={`${f.project_id || "proj"}-${f.id}`} data-testid="finding-row">
                      {showProjectColumn && (
                        <td>
                          <div style={{ fontWeight: 600 }}>{f.project_name}</div>
                          <span className="sha-chip">{formatShortSha(f.commit_sha)}</span>
                        </td>
                      )}
                      <td>
                        <div style={{ display: "flex", flexDirection: "column", gap: 5, alignItems: "flex-start" }}>
                          <span className={`sev-pill sev-${f.severity}`}>{f.severity}</span>
                          <span className={`type-pill type-${isVuln ? "vulnerability" : "bug"}`}>
                            {isVuln ? "VULNERABILITY" : "BUG"}
                          </span>
                        </div>
                      </td>
                      <td className="mono" style={{ fontSize: 12 }}>
                        {f.category}
                      </td>
                      <td className="mono" style={{ fontSize: 12 }}>
                        <div>
                          {f.file_path}:{startLine}
                          {endLine > startLine ? `-${endLine}` : ""}
                        </div>
                        {f.github_blob_url && (
                          <a
                            href={f.github_blob_url}
                            target="_blank"
                            rel="noreferrer"
                            style={{ fontSize: 11, display: "inline-block", marginTop: 4 }}
                            data-testid="finding-github-link"
                          >
                            View on GitHub ↗
                          </a>
                        )}
                      </td>
                      <td>
                        <div style={{ fontWeight: 700, color: "var(--text-primary)" }}>{f.title}</div>
                        <div style={{ color: "var(--text-secondary)", fontSize: 12, marginTop: 3 }}>
                          {f.description}
                        </div>
                        <pre className="code-evidence">{f.evidence}</pre>
                        {f.suggested_remediation && (
                          <div className="remediation-box">
                            <strong style={{ color: "var(--text-primary)" }}>Suggested Correction: </strong>
                            {f.suggested_remediation}
                          </div>
                        )}
                        {f.safe_code_example && (
                          <div className="code-example-box">
                            <strong>Safe Pattern: </strong>
                            <code>{f.safe_code_example}</code>
                          </div>
                        )}
                        {f.addressed_gate_conditions && f.addressed_gate_conditions.length > 0 && (
                          <div className="gate-impact-tags">
                            {f.addressed_gate_conditions.map((cond) => (
                              <span key={cond} className="gate-impact-tag">
                                Addresses gate: {cond}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="polaris-platform">
      {/* Top Modular Navigation Bar */}
      <header className="top-navbar">
        <div className="navbar-left">
          <button
            type="button"
            className="brand-link"
            onClick={() => setActivePage("repositories")}
          >
            <PolarisLogo />
            <div>
              <span className="brand-title">POLARIS</span>
              <span className="brand-subtitle">CONTINUOUS QUALITY PLATFORM</span>
            </div>
          </button>

          <nav className="top-nav-links" aria-label="Main Navigation">
            <button
              type="button"
              className={`top-nav-btn ${activePage === "dashboard" ? "active" : ""}`}
              onClick={() => setActivePage("dashboard")}
              data-testid="nav-dashboard"
            >
              Dashboard
            </button>
            <button
              type="button"
              className={`top-nav-btn ${
                activePage === "repositories" || activePage === "project-detail" ? "active" : ""
              }`}
              onClick={() => setActivePage("repositories")}
              data-testid="nav-repositories"
            >
              Repositories
              <span className="nav-count-pill">{projects.length}</span>
            </button>
            <button
              type="button"
              className={`top-nav-btn ${
                activePage === "pull-requests" || activePage === "pr-detail" ? "active" : ""
              }`}
              onClick={() => setActivePage("pull-requests")}
              data-testid="nav-pull-requests"
            >
              Pull Requests
              <span className="nav-count-pill">{pullRequests.length}</span>
            </button>
            <button
              type="button"
              className={`top-nav-btn ${activePage === "findings" ? "active" : ""}`}
              onClick={() => setActivePage("findings")}
              data-testid="nav-findings"
            >
              Findings
            </button>
            <button
              type="button"
              className={`top-nav-btn ${activePage === "analytics" ? "active" : ""}`}
              onClick={() => setActivePage("analytics")}
              data-testid="nav-analytics"
            >
              Analytics
            </button>
            <button
              type="button"
              className={`top-nav-btn ${activePage === "settings" ? "active" : ""}`}
              onClick={() => setActivePage("settings")}
              data-testid="nav-settings"
            >
              Settings
            </button>
          </nav>
        </div>

        <div className="navbar-right">
          <span
            className="sync-mode-pill"
            data-testid="sync-mode-indicator"
            title="PAT mode uses local-only polling and never publishes GitHub Checks or misrepresents polling as real-time webhooks."
          >
            <span className={`sync-dot ${gitHubUser ? "" : "offline"}`} />
            {gitHubUser
              ? `GitHub PAT Polling (@${gitHubUser})`
              : settings?.github_app_webhook_configured
                ? "GitHub App Webhooks"
                : "Offline Local Mode"}
          </span>

          <button
            type="button"
            className="btn-secondary"
            onClick={() => void triggerGitHubSync()}
            disabled={syncing}
            data-testid="sync-github-btn"
          >
            {syncing ? "Syncing..." : "Sync GitHub"}
          </button>

          <button
            type="button"
            className="btn-ghost"
            onClick={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
            data-testid="theme-toggle"
            aria-label="Toggle Light/Dark Theme"
          >
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </button>
        </div>
      </header>

      <main className="platform-container">
        {error && (
          <div className="alert-banner error" role="alert" data-testid="error-banner">
            <span>{error}</span>
            <button type="button" className="btn-ghost" onClick={() => setError(null)}>
              Dismiss
            </button>
          </div>
        )}

        {syncNotice && (
          <div className="alert-banner info" data-testid="sync-notice">
            <span>{syncNotice}</span>
            <button type="button" className="btn-ghost" onClick={() => setSyncNotice(null)}>
              Dismiss
            </button>
          </div>
        )}

        {/* PAGE 1: GLOBAL DASHBOARD */}
        {activePage === "dashboard" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }} data-testid="dashboard-page">
            <div className="page-header">
              <div>
                <h1 className="page-title">Continuous Quality Overview</h1>
                <p className="page-subtitle">
                  Deterministic A–F repository quality, vulnerability tracking, and Pull Request Quality Gates.
                </p>
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => setActivePage("repositories")}
                >
                  View All Repositories
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setActivePage("pull-requests")}
                >
                  Inspect Pull Requests
                </button>
              </div>
            </div>

            <div className="kpi-strip">
              <div className="kpi-card">
                <span className="kpi-label">Synchronized Repositories</span>
                <span className="kpi-value">{analytics?.total_repositories ?? projects.length}</span>
                <span className="kpi-sub">
                  {analytics?.analyzed_repositories ?? 0} analyzed · {analytics?.not_analyzed_repositories ?? 0} not analyzed
                </span>
              </div>
              <div className="kpi-card">
                <span className="kpi-label">Portfolio Avg Score</span>
                <span className="kpi-value">
                  {analytics?.average_score !== null && analytics?.average_score !== undefined
                    ? `${analytics.average_score.toFixed(1)}`
                    : "—"}
                </span>
                <span className="kpi-sub">Across completed repository baselines</span>
              </div>
              <div className="kpi-card">
                <span className="kpi-label">Active Vulnerabilities</span>
                <span
                  className="kpi-value"
                  style={{
                    color:
                      (analytics?.total_vulnerabilities ?? 0) > 0
                        ? "var(--grade-f-fg)"
                        : "var(--grade-a-fg)",
                  }}
                >
                  {analytics?.total_vulnerabilities ?? 0}
                </span>
                <span className="kpi-sub">
                  Separated from {analytics?.total_bugs ?? 0} correctness bugs
                </span>
              </div>
              <div className="kpi-card">
                <span className="kpi-label">Open Pull Requests</span>
                <span className="kpi-value">{analytics?.open_pull_requests ?? 0}</span>
                <span className="kpi-sub">
                  {analytics?.blocked_pull_requests ?? 0} blocked by Quality Gate
                </span>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h2 className="panel-title">Repositories</h2>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => setActivePage("repositories")}
                >
                  Open Full Repository Table →
                </button>
              </div>
              {renderRepositoriesTable(projects.slice(0, 8))}
            </div>

            <div className="panel">
              <div className="panel-header">
                <h2 className="panel-title">Recent Pull Requests</h2>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => setActivePage("pull-requests")}
                >
                  Open Pull Requests →
                </button>
              </div>
              {renderPullRequestsTable(pullRequests.slice(0, 6), true)}
            </div>
          </div>
        )}

        {/* PAGE 2: GLOBAL REPOSITORIES TABLE */}
        {activePage === "repositories" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }} data-testid="repositories-page">
            <div className="page-header">
              <div>
                <h1 className="page-title">Repositories</h1>
                <p className="page-subtitle">
                  Automatically synchronized GitHub repositories and registered local workspaces.
                </p>
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => setShowLocalForm((prev) => !prev)}
                  data-testid="toggle-local-repo-btn"
                >
                  {showLocalForm ? "Close Local Form" : "+ Register Local Repo"}
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => void triggerGitHubSync()}
                  disabled={syncing}
                >
                  {syncing ? "Reconciling..." : "Reconcile GitHub Repositories"}
                </button>
              </div>
            </div>

            {showLocalForm && (
              <form className="panel" onSubmit={handleCreateLocalProject} data-testid="local-repo-form">
                <div className="panel-header">
                  <h2 className="panel-title">Register Local Git Repository</h2>
                </div>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <input
                    className="input-field"
                    placeholder="Repository display name"
                    value={localName}
                    onChange={(e) => setLocalName(e.target.value)}
                    required
                    style={{ flex: 1, minWidth: 200 }}
                  />
                  <input
                    className="input-field"
                    placeholder="Absolute local path"
                    value={localPath}
                    onChange={(e) => setLocalPath(e.target.value)}
                    required
                    style={{ flex: 2, minWidth: 280 }}
                  />
                  <button type="submit" className="btn-primary" disabled={busyAction}>
                    Register
                  </button>
                </div>
              </form>
            )}

            <div className="filter-toolbar">
              <div className="filter-group">
                <input
                  className="input-field"
                  placeholder="Search owner, repository, language, SHA..."
                  value={repoSearch}
                  onChange={(e) => {
                    setRepoSearch(e.target.value);
                    setRepoPage(1);
                  }}
                  data-testid="repo-search-input"
                  style={{ minWidth: 260 }}
                />
                <select
                  className="select-field"
                  value={repoGradeFilter}
                  onChange={(e) => {
                    setRepoGradeFilter(e.target.value);
                    setRepoPage(1);
                  }}
                  data-testid="repo-grade-filter"
                >
                  <option value="ALL">All Grades</option>
                  <option value="A">Grade A</option>
                  <option value="B">Grade B</option>
                  <option value="C">Grade C</option>
                  <option value="D">Grade D</option>
                  <option value="F">Grade F</option>
                  <option value="NOT_RATED">NOT_RATED</option>
                </select>
                <select
                  className="select-field"
                  value={repoStatusFilter}
                  onChange={(e) => {
                    setRepoStatusFilter(e.target.value);
                    setRepoPage(1);
                  }}
                  data-testid="repo-status-filter"
                >
                  <option value="ALL">All Analysis States</option>
                  <option value="NOT_ANALYZED">NOT_ANALYZED</option>
                  <option value="completed">Completed</option>
                  <option value="incomplete">Incomplete</option>
                  <option value="failed">Failed</option>
                  <option value="queued">Queued</option>
                </select>
                <select
                  className="select-field"
                  value={repoSyncFilter}
                  onChange={(e) => {
                    setRepoSyncFilter(e.target.value);
                    setRepoPage(1);
                  }}
                  data-testid="repo-sync-filter"
                >
                  <option value="ALL">All Sync States</option>
                  <option value="active">Active</option>
                  <option value="archived">Archived</option>
                  <option value="inaccessible">Inaccessible</option>
                  <option value="local">Local</option>
                </select>
              </div>

              <div className="filter-group">
                <label style={{ fontSize: 12, color: "var(--text-secondary)" }}>Sort by:</label>
                <select
                  className="select-field"
                  value={repoSortBy}
                  onChange={(e) => setRepoSortBy(e.target.value)}
                  data-testid="repo-sort-select"
                >
                  <option value="created_at">Discovered Time</option>
                  <option value="name">Repository Name</option>
                  <option value="grade">Quality Grade</option>
                  <option value="score">Quality Score</option>
                  <option value="vulnerabilities">Vulnerabilities</option>
                  <option value="findings">Total Findings</option>
                </select>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => setRepoSortDir((d) => (d === "asc" ? "desc" : "asc"))}
                >
                  {repoSortDir === "asc" ? "↑ ASC" : "↓ DESC"}
                </button>
              </div>
            </div>

            {loading ? (
              <div className="empty-state">Loading synchronized repositories...</div>
            ) : (
              renderRepositoriesTable(paginatedRepositories)
            )}

            {filteredRepositories.length > repoPerPage && (
              <div className="pagination-bar" data-testid="repo-pagination">
                <span>
                  Showing {(repoPage - 1) * repoPerPage + 1}–
                  {Math.min(repoPage * repoPerPage, filteredRepositories.length)} of{" "}
                  {filteredRepositories.length} repositories
                </span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={repoPage <= 1}
                    onClick={() => setRepoPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </button>
                  <span style={{ alignSelf: "center" }}>
                    Page {repoPage} of {totalRepoPages}
                  </span>
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={repoPage >= totalRepoPages}
                    onClick={() => setRepoPage((p) => Math.min(totalRepoPages, p + 1))}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* PAGE 3: PROJECT DETAILS */}
        {activePage === "project-detail" && projectDetail && (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }} data-testid="project-detail-page">
            <div>
              <div className="breadcrumb-bar">
                <button
                  type="button"
                  className="breadcrumb-btn"
                  onClick={() => setActivePage("repositories")}
                >
                  Repositories
                </button>
                <span>/</span>
                <span>{projectDetail.owner}</span>
                <span>/</span>
                <strong style={{ color: "var(--text-primary)" }}>{projectDetail.repository_name}</strong>
              </div>

              <div className="page-header">
                <div>
                  <h1 className="page-title" data-testid="project-header-title">
                    {projectDetail.full_name}
                  </h1>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6, flexWrap: "wrap" }}>
                    <span className="sha-chip">Branch: {projectDetail.default_branch}</span>
                    {projectDetail.language && (
                      <span className="sha-chip">Language: {projectDetail.language}</span>
                    )}
                    <span className="sha-chip">
                      Last SHA: {formatShortSha(projectDetail.last_analyzed_sha)}
                    </span>
                    <span className={`status-pill status-${projectDetail.analysis_status}`}>
                      {projectDetail.analysis_status}
                    </span>
                    <span className="sha-chip">Sync: {projectDetail.sync_status}</span>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <input
                    className="input-field"
                    placeholder="Optional revision / SHA"
                    value={manualRevision}
                    onChange={(e) => setManualRevision(e.target.value)}
                    style={{ width: 170 }}
                  />
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={busyAction}
                    onClick={() => void handleStartBranchAnalysis(projectDetail.id)}
                    data-testid="run-project-analysis-btn"
                  >
                    Run Branch Analysis
                  </button>
                  {projectDetail.github_repository_id && (
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={syncing}
                      onClick={() => void triggerGitHubSync(projectDetail.id)}
                      data-testid="sync-project-btn"
                    >
                      Sync Repository & PRs
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Project Detail Sub-Tabs */}
            <div className="sub-tabs" role="tablist">
              {(["overview", "pull-requests", "findings", "history", "settings"] as ProjectTab[]).map(
                (tab) => (
                  <button
                    key={tab}
                    type="button"
                    role="tab"
                    aria-selected={projectTab === tab}
                    className={`sub-tab-btn ${projectTab === tab ? "active" : ""}`}
                    onClick={() => setProjectTab(tab)}
                    data-testid={`project-tab-${tab}`}
                  >
                    {tab === "overview" && "Overview"}
                    {tab === "pull-requests" &&
                      `Pull Requests (${projectDetail.pull_requests?.length || 0})`}
                    {tab === "findings" &&
                      `Findings (${
                        activeProjectJob?.findings?.length ??
                        (projectDetail.findings_count !== null ? projectDetail.findings_count : 0)
                      })`}
                    {tab === "history" && `History (${projectDetail.analyses?.length || 0})`}
                    {tab === "settings" && "Settings"}
                  </button>
                )
              )}
            </div>

            {/* PROJECT TAB 1: OVERVIEW */}
            {projectTab === "overview" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 18 }} data-testid="project-overview-tab">
                {projectDetail.analysis_status === "NOT_ANALYZED" || !activeProjectJob ? (
                  <div className="alert-banner info" data-testid="not-analyzed-banner">
                    <div>
                      <strong>NOT_ANALYZED — Repository Awaiting Analysis</strong>
                      <div style={{ marginTop: 4 }}>
                        No branch analysis has completed for {projectDetail.full_name} yet. Polaris never fabricates scores or zero-finding metrics for unanalyzed repositories.
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => void handleStartBranchAnalysis(projectDetail.id)}
                    >
                      Analyze Default Branch Now
                    </button>
                  </div>
                ) : null}

                {activeProjectJob?.status === "failed" && (
                  <div className="alert-banner error" data-testid="failed-banner">
                    <div>
                      <strong>Analysis Failed:</strong>{" "}
                      {activeProjectJob.error || "Execution terminated before report generation."}
                    </div>
                  </div>
                )}

                {activeProjectJob?.status === "incomplete" && (
                  <div className="alert-banner warning" data-testid="incomplete-banner">
                    <div>
                      <strong>Incomplete Analysis (Partial Scope):</strong>{" "}
                      {activeProjectJob.quality?.not_rated_reason ||
                        "Quality grade is withheld when scope is truncated."}
                    </div>
                  </div>
                )}

                <div className="overview-grid">
                  {/* Card 1: Quality Grade & Score */}
                  <div className="panel">
                    <div className="panel-header">
                      <h3 className="panel-title">Quality Rating</h3>
                      <span className="sha-chip">
                        {activeProjectJob?.quality?.formula_version || "polaris-quality-v1"}
                      </span>
                    </div>
                    <div className="hero-score-row">
                      <GradeBadge
                        grade={activeProjectJob?.quality?.grade || projectDetail.latest_grade}
                        size="lg"
                        testId="grade-hero-badge"
                      />
                      <div>
                        <div className="kpi-value" data-testid="quality-score-value">
                          {activeProjectJob?.quality?.score !== null &&
                          activeProjectJob?.quality?.score !== undefined
                            ? `${activeProjectJob.quality.score.toFixed(1)} / 100`
                            : "NOT RATED"}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }}>
                          {activeProjectJob
                            ? activeProjectJob.quality?.not_rated_reason ||
                              activeProjectJob.quality?.explanation
                            : "No completed analysis run."}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Card 2: Quality Gate Status */}
                  <div className="panel">
                    <div className="panel-header">
                      <h3 className="panel-title">Quality Gate</h3>
                      <span
                        className={`gate-pill gate-${
                          activeProjectJob?.quality_gate?.status || "INCONCLUSIVE"
                        }`}
                        data-testid="gate-status-badge"
                      >
                        {activeProjectJob?.quality_gate?.status || "NOT_EVALUATED"}
                      </span>
                    </div>
                    {activeProjectJob?.quality_gate?.conditions ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        {activeProjectJob.quality_gate.conditions.map((c) => (
                          <div
                            key={c.criterion}
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              fontSize: 12,
                              color: c.passed ? "var(--text-secondary)" : "var(--grade-f-fg)",
                              fontWeight: c.passed ? 400 : 700,
                            }}
                          >
                            <span>
                              {c.passed ? "✓" : "✗"} {c.criterion}
                            </span>
                            <span className="mono">
                              {c.actual} (req {c.threshold})
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>
                        Quality Gate will evaluate once an analysis run completes.
                      </p>
                    )}
                  </div>

                  {/* Card 3: Vulnerabilities, Bugs & Analysis Scope */}
                  <div className="panel">
                    <div className="panel-header">
                      <h3 className="panel-title">Scope & Defect Breakdown</h3>
                      <span className="sha-chip">
                        SHA: {formatShortSha(activeProjectJob?.commit_sha || projectDetail.last_analyzed_sha)}
                      </span>
                    </div>
                    {activeProjectJob &&
                    (activeProjectJob.status === "completed" ||
                      activeProjectJob.status === "incomplete") ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                          <span>Vulnerabilities:</span>
                          <strong
                            className="mono"
                            style={{
                              color:
                                (activeProjectJob.vulnerability_count || 0) > 0
                                  ? "var(--grade-f-fg)"
                                  : "var(--grade-a-fg)",
                            }}
                            data-testid="overview-vuln-count"
                          >
                            {activeProjectJob.vulnerability_count ?? 0}
                          </strong>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                          <span>Correctness Bugs:</span>
                          <strong className="mono">{activeProjectJob.bug_count ?? 0}</strong>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                          <span>Files Analyzed:</span>
                          <strong className="mono">
                            {activeProjectJob.quality?.scope.files_analyzed_count ?? 0}
                          </strong>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                          <span>Modules Executed:</span>
                          <span className="mono">
                            {(activeProjectJob.quality?.scope.modules_executed || []).join(", ") || "—"}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>
                        Scope metrics are unavailable until analysis runs.
                      </p>
                    )}
                  </div>
                </div>

                {/* Actionable High-Priority Issues */}
                {activeProjectJob?.findings && activeProjectJob.findings.length > 0 && (
                  <div className="panel" data-testid="high-priority-issues">
                    <div className="panel-header">
                      <h3 className="panel-title">Actionable High-Priority Issues</h3>
                      <button
                        type="button"
                        className="btn-ghost"
                        onClick={() => setProjectTab("findings")}
                      >
                        Explore All Findings ({activeProjectJob.findings.length}) →
                      </button>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      {activeProjectJob.findings.slice(0, 4).map((f) => (
                        <div
                          key={f.id}
                          style={{
                            padding: 12,
                            borderRadius: 6,
                            background: "var(--bg-elevated)",
                            border: "1px solid var(--border-subtle)",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                            <div>
                              <span className={`sev-pill sev-${f.severity}`} style={{ marginRight: 8 }}>
                                {f.severity}
                              </span>
                              <span
                                className={`type-pill type-${
                                  f.is_vulnerability ? "vulnerability" : "bug"
                                }`}
                                style={{ marginRight: 8 }}
                              >
                                {f.is_vulnerability ? "VULNERABILITY" : "BUG"}
                              </span>
                              <strong>{f.title}</strong>
                            </div>
                            <span className="mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                              {f.file_path}:{f.line_range?.start_line || 1}
                            </span>
                          </div>
                          {f.suggested_remediation && (
                            <div className="remediation-box">
                              <strong>Fix: </strong>
                              {f.suggested_remediation}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Quality Trend Over Runs */}
                {projectDetail.quality_trend && projectDetail.quality_trend.length > 0 && (
                  <div className="panel" data-testid="quality-trend-panel">
                    <div className="panel-header">
                      <h3 className="panel-title">Quality Trend</h3>
                    </div>
                    <div className="table-container">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Timestamp</th>
                            <th>Commit SHA</th>
                            <th>Status</th>
                            <th>Grade</th>
                            <th>Score</th>
                            <th>Vulnerabilities</th>
                            <th>Bugs</th>
                          </tr>
                        </thead>
                        <tbody>
                          {projectDetail.quality_trend.map((pt) => (
                            <tr key={pt.job_id}>
                              <td>{formatTimestamp(pt.created_at)}</td>
                              <td>
                                <span className="sha-chip">{formatShortSha(pt.commit_sha)}</span>
                              </td>
                              <td>
                                <span className={`status-pill status-${pt.status}`}>{pt.status}</span>
                              </td>
                              <td>
                                <GradeBadge grade={pt.grade} size="sm" />
                              </td>
                              <td className="mono">
                                {pt.score !== null && pt.score !== undefined ? pt.score.toFixed(1) : "—"}
                              </td>
                              <td className="mono">{pt.vulnerability_count}</td>
                              <td className="mono">{pt.bug_count}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* PROJECT TAB 2: PULL REQUESTS */}
            {projectTab === "pull-requests" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }} data-testid="project-prs-tab">
                {projectDetail.github_repository_id && (
                  <div className="filter-toolbar">
                    <div className="filter-group">
                      <strong>Analyze Specific Pull Request:</strong>
                      <input
                        className="input-field"
                        type="number"
                        min={1}
                        placeholder="PR # (e.g. 12)"
                        value={manualPrNumber}
                        onChange={(e) => setManualPrNumber(e.target.value)}
                        style={{ width: 150 }}
                      />
                      <button
                        type="button"
                        className="btn-primary"
                        disabled={busyAction || !manualPrNumber}
                        onClick={() => void handleManualGitHubPrAnalysis(projectDetail.id)}
                      >
                        Analyze PR
                      </button>
                    </div>
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={syncing}
                      onClick={() => void triggerGitHubSync(projectDetail.id)}
                    >
                      Refresh Open PRs
                    </button>
                  </div>
                )}
                {renderPullRequestsTable(projectDetail.pull_requests || [], false)}
              </div>
            )}

            {/* PROJECT TAB 3: FINDINGS */}
            {projectTab === "findings" && renderFindingsView(false)}

            {/* PROJECT TAB 4: HISTORY & MANUAL COMPARISON */}
            {projectTab === "history" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 18 }} data-testid="project-history-tab">
                <div className="panel">
                  <div className="panel-header">
                    <h3 className="panel-title">Compare Baseline Run vs Candidate / PR Run</h3>
                  </div>
                  <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
                    <div style={{ flex: 1, minWidth: 220 }}>
                      <label style={{ display: "block", fontSize: 12, marginBottom: 4 }}>
                        Baseline Analysis Run
                      </label>
                      <select
                        className="select-field"
                        style={{ width: "100%" }}
                        value={baseJobId}
                        onChange={(e) => setBaseJobId(e.target.value)}
                        data-testid="baseline-job-select"
                      >
                        <option value="">Select baseline run...</option>
                        {(projectDetail.analyses || []).map((j) => (
                          <option key={j.id} value={j.id}>
                            [{j.quality?.grade || "N/R"}] {j.id.slice(0, 8)} ·{" "}
                            {formatShortSha(j.commit_sha || j.base_revision)} · {j.status}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div style={{ flex: 1, minWidth: 220 }}>
                      <label style={{ display: "block", fontSize: 12, marginBottom: 4 }}>
                        Candidate / PR Run
                      </label>
                      <select
                        className="select-field"
                        style={{ width: "100%" }}
                        value={candidateJobId}
                        onChange={(e) => setCandidateJobId(e.target.value)}
                        data-testid="candidate-job-select"
                      >
                        <option value="">Select candidate run...</option>
                        {(projectDetail.analyses || []).map((j) => (
                          <option key={j.id} value={j.id}>
                            [{j.quality?.grade || "N/R"}] {j.id.slice(0, 8)} ·{" "}
                            {formatShortSha(j.commit_sha || j.base_revision)} · {j.status}
                          </option>
                        ))}
                      </select>
                    </div>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={busyAction || !baseJobId || !candidateJobId}
                      onClick={() => void handleRunManualComparison()}
                      data-testid="run-comparison-btn"
                    >
                      Evaluate PR Quality Gate
                    </button>
                  </div>

                  {manualComparison && (
                    <div style={{ marginTop: 16 }} data-testid="pr-comparison-result">
                      <div className="pr-delta-banner">
                        <div className="pr-grade-flow">
                          <div>
                            <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>BASE</div>
                            <GradeBadge
                              grade={manualComparison.base_evaluation.grade}
                              size="md"
                              testId="pr-base-grade"
                            />
                          </div>
                          <span className="pr-arrow">→</span>
                          <div>
                            <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>PROPOSED</div>
                            <GradeBadge
                              grade={manualComparison.pr_evaluation.grade}
                              size="md"
                              testId="pr-candidate-grade"
                            />
                          </div>
                          <div>
                            <div style={{ fontWeight: 700 }}>{manualComparison.grade_delta}</div>
                            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                              {manualComparison.summary}
                            </div>
                          </div>
                        </div>
                        <span
                          className={`gate-pill gate-${manualComparison.quality_gate.status}`}
                          data-testid="pr-gate-verdict"
                        >
                          GATE {manualComparison.quality_gate.status}
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                <div className="table-container" data-testid="history-table">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Run ID</th>
                        <th>Mode</th>
                        <th>Commit SHA</th>
                        <th>Execution Status</th>
                        <th>Quality Grade</th>
                        <th>Score</th>
                        <th>Vulnerabilities</th>
                        <th>Bugs</th>
                        <th>Quality Gate</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(projectDetail.analyses || []).map((j) => (
                        <tr
                          key={j.id}
                          className="clickable-row"
                          onClick={async () => {
                            const fullJob = await apiFetch<Job>(`/api/analyses/${j.id}`);
                            setSelectedHistoricalJob(fullJob);
                            setProjectTab("overview");
                          }}
                          data-testid="history-row"
                        >
                          <td className="mono">{j.id.slice(0, 8)}</td>
                          <td>
                            <span className="sha-chip">
                              {j.pull_request_number ? `PR #${j.pull_request_number}` : j.analysis_mode}
                            </span>
                          </td>
                          <td>
                            <span className="sha-chip">
                              {formatShortSha(j.commit_sha || j.head_sha || j.base_revision)}
                            </span>
                          </td>
                          <td>
                            <span className={`status-pill status-${j.status}`}>{j.status}</span>
                          </td>
                          <td>
                            <GradeBadge grade={j.quality?.grade} size="sm" />
                          </td>
                          <td className="mono">
                            {j.quality?.score !== null && j.quality?.score !== undefined
                              ? j.quality.score.toFixed(1)
                              : "—"}
                          </td>
                          <td className="mono">{j.vulnerability_count ?? 0}</td>
                          <td className="mono">{j.bug_count ?? 0}</td>
                          <td>
                            <span
                              className={`gate-pill gate-${j.quality_gate?.status || "INCONCLUSIVE"}`}
                            >
                              {j.quality_gate?.status || "N/A"}
                            </span>
                          </td>
                          <td>{formatTimestamp(j.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* PROJECT TAB 5: SETTINGS */}
            {projectTab === "settings" && (
              <div className="panel" data-testid="project-settings-tab">
                <div className="panel-header">
                  <h3 className="panel-title">Repository Quality Gate & Synchronization Policy</h3>
                </div>
                <div className="conditions-grid">
                  <div className="condition-item">
                    <strong>Minimum Required Grade:</strong> {projectDetail.gate_config?.min_grade || "C"}
                  </div>
                  <div className="condition-item">
                    <strong>Max New Critical Findings (PR):</strong>{" "}
                    {projectDetail.gate_config?.max_new_critical_findings ?? 0}
                  </div>
                  <div className="condition-item">
                    <strong>Max New High Findings (PR):</strong>{" "}
                    {projectDetail.gate_config?.max_new_high_findings ?? 0}
                  </div>
                  <div className="condition-item">
                    <strong>Max Total New Findings (PR):</strong>{" "}
                    {projectDetail.gate_config?.max_total_new_findings ?? 3}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* PAGE 4: GLOBAL PULL REQUESTS LIST */}
        {activePage === "pull-requests" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }} data-testid="pull-requests-page">
            <div className="page-header">
              <div>
                <h1 className="page-title">Pull Requests</h1>
                <p className="page-subtitle">
                  Automatically discovered Pull Requests with Base Grade → Proposed Head Grade and Quality Gate decisions visible before opening details.
                </p>
              </div>
              <button
                type="button"
                className="btn-primary"
                disabled={syncing}
                onClick={() => void triggerGitHubSync()}
              >
                {syncing ? "Syncing PRs..." : "Sync Open Pull Requests"}
              </button>
            </div>
            {renderPullRequestsTable(pullRequests, true)}
          </div>
        )}

        {/* PAGE 5: PR DETAILS AND FIX RECOMMENDATIONS */}
        {activePage === "pr-detail" && prDetail && (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }} data-testid="pr-detail-page">
            <div>
              <div className="breadcrumb-bar">
                <button
                  type="button"
                  className="breadcrumb-btn"
                  onClick={() => setActivePage("pull-requests")}
                >
                  Pull Requests
                </button>
                <span>/</span>
                <span>{prDetail.project_name}</span>
                <span>/</span>
                <strong style={{ color: "var(--text-primary)" }}>PR #{prDetail.number}</strong>
              </div>

              <div className="page-header">
                <div>
                  <h1 className="page-title" data-testid="pr-detail-title">
                    #{prDetail.number} · {prDetail.title}
                  </h1>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6, flexWrap: "wrap" }}>
                    <span className="sha-chip">
                      {prDetail.head_ref} → {prDetail.base_ref}
                    </span>
                    <span className="sha-chip">Author: @{prDetail.author_login}</span>
                    <span className="sha-chip">Base SHA: {formatShortSha(prDetail.base_sha)}</span>
                    <span className="sha-chip">Head SHA: {formatShortSha(prDetail.head_sha)}</span>
                    <span className={`status-pill status-${prDetail.analysis_status}`}>
                      {prDetail.analysis_status}
                    </span>
                    {prDetail.diff_url && (
                      <a
                        href={prDetail.diff_url}
                        target="_blank"
                        rel="noreferrer"
                        style={{ fontSize: 12, fontWeight: 600 }}
                        data-testid="pr-github-diff-link"
                      >
                        View GitHub Diff ↗
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Base Grade -> Head Grade & Quality Gate Banner */}
            <div className="pr-delta-banner" data-testid="pr-comparison-result">
              <div className="pr-grade-flow">
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 }}>
                    BASE GRADE
                  </div>
                  <GradeBadge grade={prDetail.base_grade} size="lg" testId="pr-base-grade" />
                  <div className="mono" style={{ fontSize: 12, marginTop: 4 }}>
                    {prDetail.base_score !== null && prDetail.base_score !== undefined
                      ? `${prDetail.base_score.toFixed(1)}/100`
                      : "N/R"}
                  </div>
                </div>

                <span className="pr-arrow">→</span>

                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 11, color: "var(--text-secondary)", marginBottom: 4 }}>
                    PROPOSED HEAD GRADE
                  </div>
                  <GradeBadge grade={prDetail.head_grade} size="lg" testId="pr-candidate-grade" />
                  <div className="mono" style={{ fontSize: 12, marginTop: 4 }}>
                    {prDetail.head_score !== null && prDetail.head_score !== undefined
                      ? `${prDetail.head_score.toFixed(1)}/100`
                      : "N/R"}
                  </div>
                </div>

                <div style={{ marginLeft: 12 }}>
                  <div style={{ fontSize: 16, fontWeight: 800 }} data-testid="pr-grade-delta-text">
                    Grade Change: {prDetail.grade_delta}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>
                    {prDetail.comparison?.summary ||
                      `New: ${prDetail.counts.new} · Existing: ${prDetail.counts.existing} · Resolved: ${prDetail.counts.resolved} · Uncertain: ${prDetail.counts.uncertain}`}
                  </div>
                </div>
              </div>

              <div>
                <span
                  className={`gate-pill gate-${prDetail.quality_gate_status}`}
                  style={{ fontSize: 13, padding: "6px 14px" }}
                  data-testid="pr-gate-verdict"
                >
                  QUALITY GATE: {prDetail.quality_gate_status}
                </span>
              </div>
            </div>

            {/* Quality Gate Conditions & Failed Reasons */}
            {prDetail.quality_gate && (
              <div className="panel" data-testid="pr-gate-reasons">
                <div className="panel-header">
                  <h3 className="panel-title">Quality Gate Evaluation & Failed Conditions</h3>
                </div>
                <div style={{ marginBottom: 10 }}>
                  {prDetail.quality_gate.reasons.map((r, idx) => (
                    <div
                      key={idx}
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: prDetail.quality_gate?.passed
                          ? "var(--grade-a-fg)"
                          : "var(--grade-f-fg)",
                      }}
                    >
                      • {r}
                    </div>
                  ))}
                </div>
                <div className="conditions-grid">
                  {prDetail.quality_gate.conditions.map((c) => (
                    <div
                      key={c.criterion}
                      className={`condition-item ${c.passed ? "" : "failed"}`}
                    >
                      <div style={{ fontWeight: 700 }}>
                        {c.passed ? "✓ PASSED" : "✗ FAILED"} · {c.criterion}
                      </div>
                      <div className="mono" style={{ marginTop: 4 }}>
                        Actual: {c.actual} | Required: {c.threshold}
                      </div>
                      <div style={{ color: "var(--text-secondary)", marginTop: 3 }}>{c.reason}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* PR Findings Classification Tabs & Fix Recommendations */}
            <div className="panel">
              <div className="panel-header">
                <h3 className="panel-title">PR Findings & Actionable Fix Recommendations</h3>
                <div className="filter-group">
                  {(
                    [
                      ["all", "All Delta"],
                      ["new", `New (${prDetail.counts.new})`],
                      ["existing", `Existing (${prDetail.counts.existing})`],
                      ["resolved", `Resolved (${prDetail.counts.resolved})`],
                      ["uncertain", `Uncertain (${prDetail.counts.uncertain})`],
                    ] as const
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      className={prDeltaFilter === key ? "btn-primary" : "btn-ghost"}
                      onClick={() => setPrDeltaFilter(key)}
                      data-testid={`pr-filter-${key}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {(() => {
                const comp = prDetail.comparison;
                if (!comp) {
                  return (
                    <div className="empty-state">
                      No PR comparison findings available ({prDetail.analysis_status}).
                    </div>
                  );
                }
                const allItems: ComparedFindingItem[] = [
                  ...(comp.new_findings || []),
                  ...(comp.uncertain_findings || []),
                  ...(comp.existing_findings || []),
                  ...(comp.resolved_findings || []),
                ].filter((item) => prDeltaFilter === "all" || item.classification === prDeltaFilter);

                if (allItems.length === 0) {
                  return (
                    <div className="empty-state">
                      Zero findings in the "{prDeltaFilter}" classification for this Pull Request.
                    </div>
                  );
                }

                return (
                  <div className="table-container" data-testid="pr-delta-table">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Delta Status</th>
                          <th>Severity / Type</th>
                          <th>Affected File & Lines</th>
                          <th>Problem Description, Evidence & Remediation</th>
                        </tr>
                      </thead>
                      <tbody>
                        {allItems.map((item) => {
                          const f = item.finding;
                          const isVuln = item.is_vulnerability || f.is_vulnerability;
                          const startL = f.line_range?.start_line || 1;
                          const endL = f.line_range?.end_line || startL;
                          const blobUrl = item.github_blob_url || f.github_blob_url;
                          const safeEx = item.safe_code_example || f.safe_code_example;
                          const addressed =
                            item.addressed_gate_conditions || f.addressed_gate_conditions || [];
                          return (
                            <tr
                              key={`${item.classification}-${f.id}`}
                              data-testid={`pr-delta-row-${item.classification}`}
                            >
                              <td>
                                <span
                                  className={`status-pill ${
                                    item.classification === "new"
                                      ? "gate-FAILED"
                                      : item.classification === "resolved"
                                        ? "gate-PASSED"
                                        : "gate-INCONCLUSIVE"
                                  }`}
                                >
                                  {item.classification.toUpperCase()}
                                </span>
                                <div
                                  className="mono"
                                  style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4 }}
                                >
                                  {item.stable_fingerprint}
                                </div>
                              </td>
                              <td>
                                <div
                                  style={{
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: 5,
                                    alignItems: "flex-start",
                                  }}
                                >
                                  <span className={`sev-pill sev-${f.severity}`}>{f.severity}</span>
                                  <span
                                    className={`type-pill type-${isVuln ? "vulnerability" : "bug"}`}
                                  >
                                    {isVuln ? "VULNERABILITY" : "BUG"}
                                  </span>
                                </div>
                              </td>
                              <td className="mono" style={{ fontSize: 12 }}>
                                <div>
                                  {f.file_path}:{startL}
                                  {endL > startL ? `-${endL}` : ""}
                                </div>
                                {blobUrl && (
                                  <a
                                    href={blobUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    style={{ fontSize: 11, display: "inline-block", marginTop: 4 }}
                                    data-testid="pr-finding-github-link"
                                  >
                                    GitHub File @ Line ↗
                                  </a>
                                )}
                              </td>
                              <td>
                                <div style={{ fontWeight: 700, color: "var(--text-primary)" }}>
                                  {f.title}
                                </div>
                                <div
                                  style={{
                                    color: "var(--text-secondary)",
                                    fontSize: 12,
                                    marginTop: 3,
                                  }}
                                >
                                  {f.description}
                                </div>
                                <pre className="code-evidence">{f.evidence}</pre>
                                {f.suggested_remediation && (
                                  <div className="remediation-box" data-testid="pr-fix-recommendation">
                                    <strong style={{ color: "var(--text-primary)" }}>
                                      Recommended Fix:{" "}
                                    </strong>
                                    {f.suggested_remediation}
                                  </div>
                                )}
                                {safeEx && (
                                  <div className="code-example-box" data-testid="pr-safe-code-example">
                                    <strong>Context-Supported Safe Example: </strong>
                                    <code>{safeEx}</code>
                                  </div>
                                )}
                                {addressed.length > 0 && (
                                  <div
                                    className="gate-impact-tags"
                                    data-testid="pr-addressed-gate-conditions"
                                  >
                                    {addressed.map((cond) => (
                                      <span key={cond} className="gate-impact-tag">
                                        Fixing addresses Quality Gate condition: {cond}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                );
              })()}
            </div>
          </div>
        )}

        {/* PAGE 6: GLOBAL FINDINGS */}
        {activePage === "findings" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }} data-testid="global-findings-page">
            <div className="page-header">
              <div>
                <h1 className="page-title">Global Findings</h1>
                <p className="page-subtitle">
                  Evidence-backed vulnerabilities and correctness bugs strictly scoped to each repository’s latest analyzed commit.
                </p>
              </div>
            </div>
            {renderFindingsView(true)}
          </div>
        )}

        {/* PAGE 7: ANALYTICS */}
        {activePage === "analytics" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }} data-testid="analytics-page">
            <div className="page-header">
              <div>
                <h1 className="page-title">Portfolio Quality Analytics</h1>
                <p className="page-subtitle">
                  Aggregated strictly from persisted deterministic evaluations — zero fabricated metrics.
                </p>
              </div>
            </div>

            <div className="overview-grid">
              <div className="panel">
                <div className="panel-header">
                  <h3 className="panel-title">Grade Distribution</h3>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {(["A", "B", "C", "D", "F", "NOT_RATED"] as QualityGrade[]).map((g) => (
                    <div
                      key={g}
                      style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
                    >
                      <GradeBadge grade={g} size="sm" />
                      <strong className="mono">{analytics?.grade_distribution?.[g] ?? 0} repo(s)</strong>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel">
                <div className="panel-header">
                  <h3 className="panel-title">Severity Breakdown</h3>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {(["critical", "high", "medium", "low", "info"] as const).map((sev) => (
                    <div
                      key={sev}
                      style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
                    >
                      <span className={`sev-pill sev-${sev}`}>{sev}</span>
                      <strong className="mono">{analytics?.severity_totals?.[sev] ?? 0}</strong>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel">
                <div className="panel-header">
                  <h3 className="panel-title">Quality Gate & PR Health</h3>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Repositories Passing Gate:</span>
                    <strong className="mono">{analytics?.gate_distribution?.PASSED ?? 0}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Repositories Failing Gate:</span>
                    <strong className="mono">{analytics?.gate_distribution?.FAILED ?? 0}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Open PRs Passing Gate:</span>
                    <strong className="mono">{analytics?.passed_pull_requests ?? 0}</strong>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Open PRs Blocked by Gate:</span>
                    <strong className="mono" style={{ color: "var(--grade-f-fg)" }}>
                      {analytics?.blocked_pull_requests ?? 0}
                    </strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* PAGE 8: SETTINGS */}
        {activePage === "settings" && settings && (
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }} data-testid="settings-page">
            <div className="page-header">
              <div>
                <h1 className="page-title">Platform Synchronization & Security Settings</h1>
                <p className="page-subtitle">
                  Configure continuous GitHub discovery, initial analysis policies, and repository privacy guardrails.
                </p>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h3 className="panel-title">GitHub Connection & Synchronization Mode</h3>
              </div>
              <div className="conditions-grid">
                <div className="condition-item">
                  <strong>Active Mode:</strong>{" "}
                  <span className="mono">{settings.sync_mode || "pat_polling"}</span>
                </div>
                <div className="condition-item">
                  <strong>PAT Local-Only Enforcement:</strong>{" "}
                  <span className="mono">{settings.pat_local_only ? "Enabled (No Checks Published)" : "Disabled"}</span>
                </div>
                <div className="condition-item">
                  <strong>Real-Time Webhooks Active:</strong>{" "}
                  <span className="mono">{settings.realtime_webhooks ? "Yes (GitHub App)" : "No (Periodic Polling)"}</span>
                </div>
                <div className="condition-item">
                  <strong>Last Reconciliation:</strong>{" "}
                  <span>{formatTimestamp(settings.last_sync_at)}</span>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h3 className="panel-title">Automatic Discovery & Analysis Policies</h3>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {(
                  [
                    [
                      "auto_discover_repos",
                      "Automatic Repository Discovery",
                      "Automatically discover and reconcile accessible GitHub repositories on sync.",
                    ],
                    [
                      "auto_analyze_initial",
                      "Automatic Initial Branch Analysis",
                      "Automatically enqueue initial static analysis for newly discovered eligible repositories.",
                    ],
                    [
                      "auto_analyze_prs",
                      "Automatic Open PR Discovery & Analysis",
                      "Automatically enqueue analysis when open PRs are discovered or their head SHA changes.",
                    ],
                    [
                      "allow_private_repo_analysis",
                      "Authorize Private Repository Analysis",
                      "Disabled by default so private company repositories are never analyzed without explicit authorization.",
                    ],
                    [
                      "allow_fork_pr_analysis",
                      "Authorize Fork Pull Request Analysis",
                      "Disabled by default to prevent automatic checkout of untrusted forked pull requests.",
                    ],
                  ] as const
                ).map(([key, title, desc]) => (
                  <label
                    key={key}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: 12,
                      borderRadius: 6,
                      background: "var(--bg-elevated)",
                      border: "1px solid var(--border-subtle)",
                      cursor: "pointer",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700 }}>{title}</div>
                      <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{desc}</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={Boolean(settings[key])}
                      onChange={(e) => void handleToggleSetting(key, e.target.checked)}
                      data-testid={`setting-toggle-${key}`}
                    />
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;

