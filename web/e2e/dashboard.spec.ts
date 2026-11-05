import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

function createSyntheticRepo(prefix: string): string {
  const repoDir = mkdtempSync(join(tmpdir(), `polaris-${prefix}-`));
  execFileSync("git", ["init"], { cwd: repoDir });
  execFileSync("git", ["config", "user.email", "polaris@example.com"], { cwd: repoDir });
  execFileSync("git", ["config", "user.name", "Polaris Test"], { cwd: repoDir });
  mkdirSync(join(repoDir, "src"), { recursive: true });
  writeFileSync(
    join(repoDir, "src", "calc.py"),
    "def compute(a: int, b: int) -> int:\n    return a + b\n",
    "utf-8"
  );
  execFileSync("git", ["add", "."], { cwd: repoDir });
  execFileSync("git", ["commit", "-m", "initial clean commit"], { cwd: repoDir });
  return repoDir;
}

test("Polaris E2E Journey 1: GitHub connection -> repository list -> project details -> PR list -> PR details -> findings & isolation", async ({
  page,
}, testInfo) => {
  test.setTimeout(90_000);
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(err.message));

  const mockProjects = [
    {
      id: "proj-billing",
      name: "gabrielmeiradeoliveira/BillingCore",
      path: "github://gabrielmeiradeoliveira/BillingCore",
      github_repository_id: 201,
      github_owner: "gabrielmeiradeoliveira",
      github_name: "BillingCore",
      github_default_branch: "main",
      owner: "gabrielmeiradeoliveira",
      repository_name: "BillingCore",
      full_name: "gabrielmeiradeoliveira/BillingCore",
      language: "Python",
      default_branch: "main",
      is_private: false,
      is_archived: false,
      is_fork: false,
      sync_status: "active",
      auto_analyze: true,
      last_synced_at: "2026-11-03T00:00:00Z",
      last_analyzed_sha: "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4",
      last_successful_analysis_at: "2026-11-03T00:01:00Z",
      created_at: "2026-11-03T00:00:00Z",
      analysis_count: 2,
      project_analysis_count: 1,
      open_pr_count: 1,
      latest_job_id: "job-billing-base",
      latest_status: "completed",
      analysis_status: "completed",
      latest_grade: "B",
      latest_score: 78.0,
      latest_gate_status: "FAILED",
      vulnerability_count: 1,
      bug_count: 0,
      findings_count: 1,
      severity_counts: { critical: 0, high: 1, medium: 0, low: 0, info: 0 },
    },
    {
      id: "proj-auth",
      name: "gabrielmeiradeoliveira/AuthAPI",
      path: "github://gabrielmeiradeoliveira/AuthAPI",
      github_repository_id: 202,
      github_owner: "gabrielmeiradeoliveira",
      github_name: "AuthAPI",
      github_default_branch: "main",
      owner: "gabrielmeiradeoliveira",
      repository_name: "AuthAPI",
      full_name: "gabrielmeiradeoliveira/AuthAPI",
      language: "Python",
      default_branch: "main",
      is_private: false,
      is_archived: false,
      is_fork: false,
      sync_status: "active",
      auto_analyze: true,
      last_synced_at: "2026-11-03T00:00:00Z",
      last_analyzed_sha: null,
      last_successful_analysis_at: null,
      created_at: "2026-11-03T00:00:00Z",
      analysis_count: 0,
      project_analysis_count: 0,
      open_pr_count: 0,
      latest_job_id: null,
      latest_status: null,
      analysis_status: "NOT_ANALYZED",
      latest_grade: null,
      latest_score: null,
      latest_gate_status: null,
      vulnerability_count: null,
      bug_count: null,
      findings_count: null,
      severity_counts: null,
    },
  ];

  const billingFinding = {
    id: "dcd-sql-001",
    module_id: "code_review",
    severity: "high",
    confidence: "high",
    category: "correctness",
    file_path: "src/billing/db.py",
    line_range: { start_line: 24, end_line: 24 },
    title: "[DET-SQL-INTERPOLATION] Unparameterized SQL string interpolation",
    description: "Dynamic values are interpolated into a SQL string before execution.",
    evidence: 'cursor.execute(f"SELECT * FROM invoices WHERE acct = \'{account_id}\'")',
    suggested_remediation: "Pass SQL parameters separately from the query text.",
    is_vulnerability: true,
    finding_type: "vulnerability",
    addressed_gate_conditions: ["max_high_findings"],
    github_blob_url:
      "https://github.com/gabrielmeiradeoliveira/BillingCore/blob/a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4/src/billing/db.py#L24",
    safe_code_example: "cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))",
    project_id: "proj-billing",
    project_name: "gabrielmeiradeoliveira/BillingCore",
    commit_sha: "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4",
  };

  const prNewFinding = {
    id: "dcd-div-042",
    module_id: "code_review",
    severity: "critical",
    confidence: "high",
    category: "correctness",
    file_path: "src/billing/settlement.py",
    line_range: { start_line: 42, end_line: 42 },
    title: "[DET-DIV-ZERO] Division or modulo by zero",
    description: "An arithmetic operation divides by literal zero.",
    evidence: "return net_amount / 0",
    suggested_remediation: "Validate that the divisor is non-zero before dividing.",
    is_vulnerability: false,
    finding_type: "bug",
    addressed_gate_conditions: ["minimum_grade", "max_new_critical_findings"],
    github_blob_url:
      "https://github.com/gabrielmeiradeoliveira/BillingCore/blob/f9e8d7c6b5a4f9e8d7c6b5a4f9e8d7c6b5a4f9e8/src/billing/settlement.py#L42",
    safe_code_example: "return net_amount / divisor if divisor != 0 else 0",
  };

  const mockPr42 = {
    id: "pr-uuid-42",
    project_id: "proj-billing",
    project_name: "gabrielmeiradeoliveira/BillingCore",
    github_owner: "gabrielmeiradeoliveira",
    github_name: "BillingCore",
    number: 42,
    title: "Add instant settlement calculation",
    state: "open",
    author_login: "gabrielmeiradeoliveira",
    head_ref: "feat/instant-settlement",
    base_ref: "main",
    head_sha: "f9e8d7c6b5a4f9e8d7c6b5a4f9e8d7c6b5a4f9e8",
    base_sha: "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4",
    is_fork: false,
    merged: false,
    html_url: "https://github.com/gabrielmeiradeoliveira/BillingCore/pull/42",
    diff_url: "https://github.com/gabrielmeiradeoliveira/BillingCore/pull/42/files",
    analysis_status: "completed",
    latest_base_job_id: "job-billing-base",
    latest_candidate_job_id: "job-billing-pr42",
    last_analyzed_sha: "f9e8d7c6b5a4f9e8d7c6b5a4f9e8d7c6b5a4f9e8",
    last_analyzed_at: "2026-11-03T00:02:00Z",
    base_grade: "B",
    base_score: 78.0,
    head_grade: "F",
    head_score: 55.0,
    grade_delta: "B -> F",
    score_delta: -23.0,
    new_critical_count: 1,
    new_high_count: 0,
    counts: { new: 1, existing: 1, resolved: 0, uncertain: 0 },
    quality_gate_status: "FAILED",
    quality_gate: {
      gate_version: "polaris-gate-v1",
      status: "FAILED",
      passed: false,
      reasons: [
        "Quality grade F is below minimum required grade C.",
        "Introduced 1 new critical finding(s) (maximum allowed: 0).",
      ],
      conditions: [
        {
          criterion: "minimum_grade",
          passed: false,
          actual: "F",
          threshold: ">= C",
          reason: "Quality grade F is below minimum required grade C.",
        },
        {
          criterion: "max_new_critical_findings",
          passed: false,
          actual: "1",
          threshold: "<= 0",
          reason: "Introduced 1 new critical finding(s) (maximum allowed: 0).",
        },
      ],
    },
    error: null,
    comparison: {
      comparison_version: "polaris-pr-v1",
      base_revision: "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4",
      head_revision: "f9e8d7c6b5a4f9e8d7c6b5a4f9e8d7c6b5a4f9e8",
      base_evaluation: {
        formula_version: "polaris-quality-v1",
        grade: "B",
        score: 78.0,
        total_penalty: 22.0,
        not_rated_reason: null,
        explanation: "Grade B (78.0/100)",
        severity_counts: { critical: 0, high: 1, medium: 0, low: 0, info: 0 },
        confidence_counts: { high: 1, medium: 0, low: 0 },
        scope: {
          operational_status: "completed",
          files_analyzed_count: 2,
          files_analyzed: ["src/billing/db.py", "src/billing/settlement.py"],
          modules_executed: ["code_review"],
          is_complete: true,
          has_sufficient_evidence: true,
          truncation_warnings: [],
          warning_count: 0,
        },
      },
      pr_evaluation: {
        formula_version: "polaris-quality-v1",
        grade: "F",
        score: 55.0,
        total_penalty: 45.0,
        not_rated_reason: null,
        explanation: "Grade F (55.0/100)",
        severity_counts: { critical: 1, high: 0, medium: 0, low: 0, info: 0 },
        confidence_counts: { high: 1, medium: 0, low: 0 },
        scope: {
          operational_status: "completed",
          files_analyzed_count: 2,
          files_analyzed: ["src/billing/db.py", "src/billing/settlement.py"],
          modules_executed: ["code_review"],
          is_complete: true,
          has_sufficient_evidence: true,
          truncation_warnings: [],
          warning_count: 0,
        },
      },
      quality_gate: {
        gate_version: "polaris-gate-v1",
        status: "FAILED",
        passed: false,
        reasons: [
          "Quality grade F is below minimum required grade C.",
          "Introduced 1 new critical finding(s) (maximum allowed: 0).",
        ],
        conditions: [],
      },
      grade_delta: "B -> F",
      score_delta: -23.0,
      counts: { new: 1, existing: 1, resolved: 0, uncertain: 0 },
      new_findings: [
        {
          classification: "new",
          finding: prNewFinding,
          stable_fingerprint: "pol-9988776655443322",
          matched_baseline_finding_id: null,
          similarity_score: 0.0,
          reason: "no_matching_baseline_finding",
          is_vulnerability: false,
          addressed_gate_conditions: ["minimum_grade", "max_new_critical_findings"],
          github_blob_url: prNewFinding.github_blob_url,
          safe_code_example: prNewFinding.safe_code_example,
        },
      ],
      existing_findings: [
        {
          classification: "existing",
          finding: billingFinding,
          stable_fingerprint: "pol-1122334455667788",
          matched_baseline_finding_id: "dcd-sql-001",
          similarity_score: 1.0,
          reason: "identical_finding_id",
          is_vulnerability: true,
          addressed_gate_conditions: [],
          github_blob_url: billingFinding.github_blob_url,
          safe_code_example: billingFinding.safe_code_example,
        },
      ],
      resolved_findings: [],
      uncertain_findings: [],
      summary: "Quality Gate FAILED (B -> F): Introduced 1 new critical finding(s) (maximum allowed: 0).",
    },
  };

  await page.route("**/api/github/pat/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ configured: true, login: "gabrielmeiradeoliveira", id: 42 }),
    });
  });

  await page.route("**/api/projects", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockProjects),
    });
  });

  await page.route("**/api/projects/proj-auth", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...mockProjects[1],
        analyses: [],
        pull_requests: [],
        latest_analysis: null,
        quality_trend: [],
      }),
    });
  });

  await page.route("**/api/projects/proj-billing", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...mockProjects[0],
        analyses: [
          {
            id: "job-billing-base",
            project_id: "proj-billing",
            project_name: "gabrielmeiradeoliveira/BillingCore",
            commit_sha: "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4",
            analysis_mode: "project",
            status: "completed",
            created_at: "2026-11-03T00:01:00Z",
            finished_at: "2026-11-03T00:01:05Z",
            findings_count: 1,
            vulnerability_count: 1,
            bug_count: 0,
            quality: mockPr42.comparison.base_evaluation,
            quality_gate: {
              gate_version: "polaris-gate-v1",
              status: "FAILED",
              passed: false,
              reasons: ["Detected 1 high finding(s) (maximum allowed: 0)."],
              conditions: [
                {
                  criterion: "max_high_findings",
                  passed: false,
                  actual: "1",
                  threshold: "<= 0",
                  reason: "Detected 1 high finding(s) (maximum allowed: 0).",
                },
              ],
            },
            findings: [billingFinding],
          },
        ],
        pull_requests: [mockPr42],
        latest_analysis: {
          id: "job-billing-base",
          project_id: "proj-billing",
          project_name: "gabrielmeiradeoliveira/BillingCore",
          commit_sha: "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4",
          analysis_mode: "project",
          status: "completed",
          created_at: "2026-11-03T00:01:00Z",
          finished_at: "2026-11-03T00:01:05Z",
          findings_count: 1,
          vulnerability_count: 1,
          bug_count: 0,
          quality: mockPr42.comparison.base_evaluation,
          quality_gate: {
            gate_version: "polaris-gate-v1",
            status: "FAILED",
            passed: false,
            reasons: ["Detected 1 high finding(s) (maximum allowed: 0)."],
            conditions: [
              {
                criterion: "max_high_findings",
                passed: false,
                actual: "1",
                threshold: "<= 0",
                reason: "Detected 1 high finding(s) (maximum allowed: 0).",
              },
            ],
          },
          findings: [billingFinding],
        },
        quality_trend: [
          {
            job_id: "job-billing-base",
            commit_sha: "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4",
            status: "completed",
            grade: "B",
            score: 78.0,
            findings_count: 1,
            vulnerability_count: 1,
            bug_count: 0,
            created_at: "2026-11-03T00:01:00Z",
          },
        ],
      }),
    });
  });

  await page.route("**/api/pull-requests", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([mockPr42]),
    });
  });

  await page.route("**/api/pull-requests/pr-uuid-42", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockPr42),
    });
  });

  await page.route("**/api/analytics", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        total_repositories: 2,
        analyzed_repositories: 1,
        not_analyzed_repositories: 1,
        average_score: 78.0,
        grade_distribution: { A: 0, B: 1, C: 0, D: 0, F: 0, NOT_RATED: 1 },
        status_distribution: { NOT_ANALYZED: 1, completed: 1 },
        gate_distribution: { PASSED: 0, FAILED: 1, INCONCLUSIVE: 1 },
        total_vulnerabilities: 1,
        total_bugs: 0,
        severity_totals: { critical: 0, high: 1, medium: 0, low: 0, info: 0 },
        total_pull_requests: 1,
        open_pull_requests: 1,
        blocked_pull_requests: 1,
        passed_pull_requests: 0,
      }),
    });
  });

  await page.route("**/api/settings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        auto_discover_repos: true,
        auto_analyze_initial: true,
        auto_analyze_prs: true,
        allow_private_repo_analysis: false,
        allow_fork_pr_analysis: false,
        sync_interval_seconds: 300,
        last_sync_at: "2026-11-03T00:00:00Z",
        last_sync_status: "completed",
        last_sync_error: null,
        pat_configured: true,
        sync_mode: "pat_polling",
        realtime_webhooks: false,
        pat_local_only: true,
      }),
    });
  });

  await page.route("**/api/findings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([billingFinding]),
    });
  });

  // 1. Open Polaris & verify GitHub PAT Polling indicator + Repository Table
  await page.goto("/");
  await expect(page.getByTestId("sync-mode-indicator")).toContainText(
    "GitHub PAT Polling (@gabrielmeiradeoliveira)"
  );
  await expect(page.getByTestId("repositories-table")).toBeVisible();
  await expect(page.getByTestId("repo-grade-BillingCore")).toHaveText("B");
  await expect(page.getByTestId("repo-vuln-BillingCore")).toHaveText("1");
  await expect(page.getByTestId("repo-status-AuthAPI")).toHaveText("NOT_ANALYZED");
  await expect(page.getByTestId("repo-vuln-AuthAPI")).toHaveText("—");
  await page.screenshot({ path: testInfo.outputPath("goal51-repositories-dashboard.png"), fullPage: true });

  // 2. Verify strict isolation: click AuthAPI (NOT_ANALYZED) -> must NOT leak BillingCore's findings!
  await page.getByTestId("repo-row-AuthAPI").click();
  await expect(page.getByTestId("project-header-title")).toHaveText("gabrielmeiradeoliveira/AuthAPI");
  await expect(page.getByTestId("not-analyzed-banner")).toBeVisible();
  await page.getByTestId("project-tab-findings").click();
  await expect(page.getByTestId("empty-findings")).toContainText("NOT_ANALYZED");

  // 3. Navigate back to Repositories -> click BillingCore -> inspect Project Details
  await page.getByTestId("nav-repositories").click();
  await page.getByTestId("repo-row-BillingCore").click();
  await expect(page.getByTestId("grade-hero-badge")).toHaveText("B");
  await expect(page.getByTestId("overview-vuln-count")).toHaveText("1");
  await expect(page.getByTestId("high-priority-issues")).toContainText("Unparameterized SQL string interpolation");
  await page.screenshot({ path: testInfo.outputPath("goal51-project-overview.png"), fullPage: true });

  // 4. Project PR Tab: verify PR grade B -> F is visible BEFORE opening PR details
  await page.getByTestId("project-tab-pull-requests").click();
  await expect(page.getByTestId("pr-row-base-grade-42")).toHaveText("B");
  await expect(page.getByTestId("pr-row-head-grade-42")).toHaveText("F");
  await expect(page.getByTestId("pr-row-delta-42")).toHaveText("B -> F");
  await expect(page.getByTestId("pr-row-gate-42")).toHaveText("FAILED");
  await page.screenshot({ path: testInfo.outputPath("goal51-pr-list.png"), fullPage: true });

  // 5. Open PR #42 Details: verify Base -> Head grade, Gate reasons, remediation, safe example, addressed conditions, GitHub links
  await page.getByTestId("pr-row-42").click();
  await expect(page.getByTestId("pr-detail-page")).toBeVisible();
  await expect(page.getByTestId("pr-base-grade")).toHaveText("B");
  await expect(page.getByTestId("pr-candidate-grade")).toHaveText("F");
  await expect(page.getByTestId("pr-gate-reasons")).toContainText("Introduced 1 new critical finding(s)");
  await expect(page.getByTestId("pr-fix-recommendation").first()).toContainText(
    "Validate that the divisor is non-zero"
  );
  await expect(page.getByTestId("pr-safe-code-example").first()).toContainText("divisor != 0");
  await expect(page.getByTestId("pr-addressed-gate-conditions").first()).toContainText(
    "max_new_critical_findings"
  );
  await expect(page.getByTestId("pr-github-diff-link")).toHaveAttribute(
    "href",
    "https://github.com/gabrielmeiradeoliveira/BillingCore/pull/42/files"
  );
  await page.screenshot({ path: testInfo.outputPath("goal51-pr-details.png"), fullPage: true });

  // 6. Global Findings & Theme Toggle
  await page.getByTestId("nav-findings").click();
  await expect(page.getByTestId("findings-table")).toContainText("Unparameterized SQL string interpolation");
  await page.getByTestId("theme-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.screenshot({ path: testInfo.outputPath("goal51-findings-light-mode.png"), fullPage: true });

  expect(consoleErrors).toEqual([]);
});

test("Polaris E2E Journey 2: Live backend static analysis B -> F regression, clean PR, incomplete & failed states", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(err.message));

  const repoPath = createSyntheticRepo("live-b-to-f");
  writeFileSync(
    join(repoPath, "src", "calc.py"),
    "def compute(a: int, b: int, cache=[]) -> int:\n    cache.append(a + b)\n    return a + b\n",
    "utf-8"
  );

  await page.goto("/");
  await page.getByTestId("toggle-local-repo-btn").click();
  await page.getByPlaceholder("Repository display name").fill("Polaris Live Repo");
  await page.getByPlaceholder("Absolute local path").fill(repoPath);
  await page.getByRole("button", { name: "Register", exact: true }).click();

  await expect(page.getByTestId("project-detail-page")).toBeVisible();
  await expect(page.getByTestId("not-analyzed-banner")).toBeVisible();

  // 1. Run baseline analysis -> Grade B
  await page.getByTestId("run-project-analysis-btn").click();
  await expect(page.getByTestId("grade-hero-badge")).toHaveText("B");
  await expect(page.getByTestId("quality-score-value")).toContainText("78.0 / 100");

  // 2. Introduce critical division-by-zero defect and run second analysis -> Grade F
  writeFileSync(
    join(repoPath, "src", "calc.py"),
    "def compute(a: int, b: int, cache=[]) -> int:\n    cache.append(a + b)\n    return (a + b) / 0\n",
    "utf-8"
  );
  await page.getByTestId("run-project-analysis-btn").click();
  await expect(page.getByTestId("grade-hero-badge")).toHaveText("F");

  // 3. Go to History tab and evaluate baseline (Grade B) vs candidate (Grade F) -> B -> F, Gate FAILED
  await page.getByTestId("project-tab-history").click();
  await page.getByTestId("run-comparison-btn").click();
  await expect(page.getByTestId("pr-comparison-result")).toContainText("B -> F");
  await expect(page.getByTestId("pr-gate-verdict")).toContainText("FAILED");

  // 4. Test Incomplete analysis (budget exceeded) -> NOT_RATED (N/R)
  const largeLines = Array.from(
    { length: 160 },
    (_, idx) => `def helper_${idx}(x: int, y: int) -> int:\n    return (x * ${idx}) + y\n`
  ).join("\n");
  writeFileSync(join(repoPath, "src", "calc.py"), largeLines, "utf-8");
  await page.getByTestId("run-project-analysis-btn").click();
  await page.getByTestId("project-tab-overview").click();
  await expect(page.getByTestId("incomplete-banner")).toBeVisible();
  await expect(page.getByTestId("grade-hero-badge")).toHaveText("N/R");

  // 5. Test Failed analysis (invalid revision) -> NOT_RATED (N/R)
  await page.getByPlaceholder("Optional revision / SHA").fill("invalid-sha-999999");
  await page.getByTestId("run-project-analysis-btn").click();
  await expect(page.getByTestId("failed-banner")).toBeVisible();
  await expect(page.getByTestId("grade-hero-badge")).toHaveText("N/R");

  expect(consoleErrors).toEqual([]);
});
