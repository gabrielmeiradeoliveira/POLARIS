"""Add Polaris quality engine, quality gate, and PR comparison persistence."""

import sqlalchemy as sa
from alembic import op

revision = "0002_polaris_quality_and_pr"
down_revision = "0001_web_postgres"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("gate_config_json", sa.JSON(), nullable=True))
    op.add_column("analysis_jobs", sa.Column("analysis_mode", sa.String(20), nullable=True))
    op.add_column("analysis_jobs", sa.Column("baseline_job_id", sa.String(36), nullable=True))
    op.add_column("analysis_jobs", sa.Column("quality_json", sa.JSON(), nullable=True))
    op.add_column("analysis_jobs", sa.Column("gate_json", sa.JSON(), nullable=True))
    op.add_column("analysis_jobs", sa.Column("comparison_json", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("analysis_jobs", "comparison_json")
    op.drop_column("analysis_jobs", "gate_json")
    op.drop_column("analysis_jobs", "quality_json")
    op.drop_column("analysis_jobs", "baseline_job_id")
    op.drop_column("analysis_jobs", "analysis_mode")
    op.drop_column("projects", "gate_config_json")
