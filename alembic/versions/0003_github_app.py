"""Add GitHub App installations, repositories, webhook deliveries and policies."""

import sqlalchemy as sa
from alembic import op

revision = "0003_github_app"
down_revision = "0002_polaris_quality_and_pr"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("github_installations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("github_installation_id", sa.BigInteger(), nullable=False, unique=True), sa.Column("github_account_id", sa.BigInteger(), nullable=False), sa.Column("account_login", sa.String(255), nullable=False), sa.Column("account_type", sa.String(32), nullable=False), sa.Column("repository_selection", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("synced_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("github_repositories", sa.Column("id", sa.String(36), primary_key=True), sa.Column("installation_id", sa.String(36), sa.ForeignKey("github_installations.id"), nullable=False), sa.Column("github_repository_id", sa.BigInteger(), nullable=False), sa.Column("owner_login", sa.String(255), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("full_name", sa.String(512), nullable=False), sa.Column("default_branch", sa.String(255)), sa.Column("is_active", sa.Boolean(), nullable=False), sa.UniqueConstraint("installation_id", "github_repository_id"))
    op.create_table("github_webhook_deliveries", sa.Column("delivery_id", sa.String(128), primary_key=True), sa.Column("event", sa.String(64), nullable=False), sa.Column("installation_id", sa.String(36)), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False), sa.Column("processed_at", sa.DateTime(timezone=True)), sa.Column("status", sa.String(32), nullable=False), sa.Column("error", sa.Text()))
    op.create_table("polaris_policies", sa.Column("id", sa.String(36), primary_key=True), sa.Column("installation_id", sa.String(36), sa.ForeignKey("github_installations.id"), nullable=False), sa.Column("repository_id", sa.String(36), sa.ForeignKey("github_repositories.id")), sa.Column("version", sa.Integer(), nullable=False), sa.Column("policy_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_by", sa.String(64), nullable=False))
    op.create_table("polaris_audit_logs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("installation_id", sa.String(36), nullable=False), sa.Column("action", sa.String(128), nullable=False), sa.Column("actor", sa.String(64), nullable=False), sa.Column("payload_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("polaris_audit_logs")
    op.drop_table("polaris_policies")
    op.drop_table("github_webhook_deliveries")
    op.drop_table("github_repositories")
    op.drop_table("github_installations")
