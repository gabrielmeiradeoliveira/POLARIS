-- Migration 006: Finding Triages, Audit and Issues Fingerprint
-- POLARIS v3.6.0

ALTER TABLE issues ADD COLUMN IF NOT EXISTS fingerprint TEXT;

-- Backfill existing issues deterministically
UPDATE issues 
SET fingerprint = encode(sha256((trim(rule_id) || '|' || regexp_replace(replace(file_path, '\', '/'), ':\d+(:\d+)?$', '') || '|NOFLOW:')::bytea), 'hex')
WHERE fingerprint IS NULL OR fingerprint = '';

CREATE INDEX IF NOT EXISTS idx_issues_fingerprint ON issues (fingerprint);
CREATE INDEX IF NOT EXISTS idx_issues_project_fingerprint ON issues (project_key, fingerprint);

CREATE TABLE IF NOT EXISTS finding_triages (
    fingerprint TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'ACCEPTED_RISK', 'FALSE_POSITIVE', 'FIXED')),
    justification TEXT NOT NULL CHECK (length(trim(justification)) >= 1),
    actor TEXT NOT NULL DEFAULT 'local-user',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_finding_triages_expires_at CHECK (
        (status = 'ACCEPTED_RISK') OR (expires_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_finding_triages_status_expires ON finding_triages (status, expires_at);

CREATE TABLE IF NOT EXISTS finding_triage_audit (
    id BIGSERIAL PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'ACCEPTED_RISK', 'FALSE_POSITIVE', 'FIXED')),
    justification TEXT NOT NULL,
    actor TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_finding_triage_audit_fingerprint ON finding_triage_audit (fingerprint, recorded_at DESC);
