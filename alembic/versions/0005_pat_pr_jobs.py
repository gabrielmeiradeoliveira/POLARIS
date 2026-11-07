"""Persist pinned local PAT pull request analysis metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0005_pat_pr_jobs"
down_revision = "0004_pat_projects"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analysis_jobs", sa.Column("pull_request_number", sa.Integer()))
    op.add_column("analysis_jobs", sa.Column("head_sha", sa.String(64)))


def downgrade():
    op.drop_column("analysis_jobs", "head_sha")
    op.drop_column("analysis_jobs", "pull_request_number")
