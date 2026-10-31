"""Add the stable Supabase Auth identity to CivicLens users."""

from alembic import op
import sqlalchemy as sa


revision = "20261031_02"
down_revision = "20261031_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("supabase_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_supabase_id", "users", ["supabase_id"])
    op.create_index("ix_users_supabase_id", "users", ["supabase_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_supabase_id", table_name="users")
    op.drop_constraint("uq_users_supabase_id", "users", type_="unique")
    op.drop_column("users", "supabase_id")
