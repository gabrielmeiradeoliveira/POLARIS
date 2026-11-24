ALTER TABLE issues ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'OPEN';
ALTER TABLE issues ADD COLUMN IF NOT EXISTS resolution TEXT;
ALTER TABLE issues ADD COLUMN IF NOT EXISTS assignee TEXT;

CREATE TABLE IF NOT EXISTS issue_comments (
    id BIGSERIAL PRIMARY KEY,
    issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    author TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quality_profiles (
    profile_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    language TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    active_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quality_gates (
    gate_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_metrics (
    id BIGSERIAL PRIMARY KEY,
    project_key TEXT NOT NULL REFERENCES projects(project_key) ON DELETE CASCADE,
    analysis_id TEXT REFERENCES analyses(analysis_id) ON DELETE SET NULL,
    metrics JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_branches (
    project_key TEXT NOT NULL REFERENCES projects(project_key) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_main BOOLEAN NOT NULL DEFAULT FALSE,
    last_analysis_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_key, name)
);

CREATE TABLE IF NOT EXISTS project_pull_requests (
    project_key TEXT NOT NULL REFERENCES projects(project_key) ON DELETE CASCADE,
    pr_key TEXT NOT NULL,
    title TEXT NOT NULL,
    source_branch TEXT NOT NULL,
    target_branch TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_key, pr_key)
);

CREATE TABLE IF NOT EXISTS project_webhooks (
    webhook_id TEXT PRIMARY KEY,
    project_key TEXT NOT NULL REFERENCES projects(project_key) ON DELETE CASCADE,
    url TEXT NOT NULL,
    secret TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
