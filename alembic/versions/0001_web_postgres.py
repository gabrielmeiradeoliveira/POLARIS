"""Create dashboard PostgreSQL tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001_web_postgres"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("path", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("base_revision", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("report_json", sa.JSON()),
    )
    op.create_index("ix_analysis_jobs_project_id", "analysis_jobs", ["project_id"])
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])
    op.create_table(
        "findings",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("analysis_jobs.id"), primary_key=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_index("ix_analysis_jobs_status", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_project_id", table_name="analysis_jobs")
    op.drop_table("findings")
    op.drop_table("analysis_jobs")
    op.drop_table("projects")
