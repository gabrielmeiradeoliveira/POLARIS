"""Add continuous GitHub discovery, pull_requests, and sync_settings schema."""

import sqlalchemy as sa
from alembic import op

revision = "0006_continuous_quality_platform"
down_revision = "0005_pat_pr_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("github_language", sa.String(64)))
    op.add_column("projects", sa.Column("github_is_private", sa.Boolean(), server_default=sa.text("false")))
    op.add_column("projects", sa.Column("github_is_archived", sa.Boolean(), server_default=sa.text("false")))
    op.add_column("projects", sa.Column("github_is_fork", sa.Boolean(), server_default=sa.text("false")))
    op.add_column("projects", sa.Column("sync_status", sa.String(32), server_default="active"))
    op.add_column("projects", sa.Column("last_synced_at", sa.DateTime(timezone=True)))
    op.add_column("projects", sa.Column("last_analyzed_sha", sa.String(64)))
    op.add_column("projects", sa.Column("last_successful_analysis_at", sa.DateTime(timezone=True)))
    op.add_column("projects", sa.Column("auto_analyze", sa.Boolean(), server_default=sa.text("true")))

    op.create_table(
        "pull_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("author_login", sa.String(255)),
        sa.Column("head_ref", sa.String(255)),
        sa.Column("base_ref", sa.String(255)),
        sa.Column("head_sha", sa.String(64), nullable=False),
        sa.Column("base_sha", sa.String(64), nullable=False),
        sa.Column("is_fork", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("merged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("html_url", sa.Text()),
        sa.Column("latest_base_job_id", sa.String(36)),
        sa.Column("latest_candidate_job_id", sa.String(36)),
        sa.Column("last_analyzed_head_sha", sa.String(64)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number", name="uq_pull_requests_project_number"),
    )

    op.create_table(
        "sync_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("auto_discover_repos", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_analyze_initial", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_analyze_prs", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_private_repo_analysis", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_fork_pr_analysis", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sync_interval_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_status", sa.String(64)),
        sa.Column("last_sync_error", sa.Text()),
        sa.Column("last_sync_summary_json", sa.JSON()),
    )


def downgrade():
    op.drop_table("sync_settings")
    op.drop_table("pull_requests")
    op.drop_column("projects", "auto_analyze")
    op.drop_column("projects", "last_successful_analysis_at")
    op.drop_column("projects", "last_analyzed_sha")
    op.drop_column("projects", "last_synced_at")
    op.drop_column("projects", "sync_status")
    op.drop_column("projects", "github_is_fork")
    op.drop_column("projects", "github_is_archived")
    op.drop_column("projects", "github_is_private")
    op.drop_column("projects", "github_language")
