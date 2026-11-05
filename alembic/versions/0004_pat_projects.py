"""Add local PAT GitHub repository identity to projects."""

import sqlalchemy as sa
from alembic import op

revision = "0004_pat_projects"
down_revision = "0003_github_app"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("github_repository_id", sa.BigInteger(), unique=True))
    op.add_column("projects", sa.Column("github_owner", sa.String(255)))
    op.add_column("projects", sa.Column("github_name", sa.String(255)))
    op.add_column("projects", sa.Column("github_default_branch", sa.String(255)))


def downgrade():
    op.drop_column("projects", "github_default_branch")
    op.drop_column("projects", "github_name")
    op.drop_column("projects", "github_owner")
    op.drop_column("projects", "github_repository_id")
