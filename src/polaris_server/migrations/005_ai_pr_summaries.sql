CREATE TABLE IF NOT EXISTS ai_pr_summaries (
    pr_key TEXT NOT NULL,
    model TEXT NOT NULL,
    snippet_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    estimated_tokens INTEGER NOT NULL DEFAULT 0 CHECK (estimated_tokens >= 0),
    actual_input_tokens INTEGER NOT NULL DEFAULT 0 CHECK (actual_input_tokens >= 0),
    actual_output_tokens INTEGER NOT NULL DEFAULT 0 CHECK (actual_output_tokens >= 0),
    actual_total_tokens INTEGER NOT NULL DEFAULT 0 CHECK (actual_total_tokens >= 0),
    saved_tokens INTEGER NOT NULL DEFAULT 0 CHECK (saved_tokens >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (pr_key, model, snippet_hash)
);

CREATE INDEX IF NOT EXISTS idx_ai_pr_summaries_pr_key ON ai_pr_summaries (pr_key, updated_at DESC);
