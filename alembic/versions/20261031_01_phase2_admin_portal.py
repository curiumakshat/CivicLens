"""Phase 2 admin lifecycle, wards, severity, and status audit."""

from alembic import op
import sqlalchemy as sa


revision = "20261031_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("population", sa.Integer(), nullable=True),
        sa.Column("population_source", sa.String(length=255), nullable=True),
        sa.Column("boundary_geojson", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_wards_name"),
        sa.CheckConstraint("population IS NULL OR population >= 0", name="wards_population_nonnegative"),
    )
    op.create_index("ix_wards_name", "wards", ["name"], unique=False)

    op.add_column("reports", sa.Column("status", sa.String(length=30), nullable=True))
    op.execute(sa.text("UPDATE reports SET status = 'pending' WHERE status IS NULL"))
    op.alter_column("reports", "status", nullable=False, server_default=sa.text("'pending'"))
    op.create_index("ix_reports_status", "reports", ["status"], unique=False)
    op.create_check_constraint("reports_status_check", "reports", "status IN ('pending', 'in_progress', 'resolved')")

    op.add_column("reports", sa.Column("severity", sa.Integer(), nullable=True))
    op.create_index("ix_reports_severity", "reports", ["severity"], unique=False)
    op.create_check_constraint("reports_severity_check", "reports", "severity IS NULL OR severity BETWEEN 1 AND 5")

    op.add_column("reports", sa.Column("ward_id", sa.Integer(), nullable=True))
    op.create_index("ix_reports_ward_id", "reports", ["ward_id"], unique=False)
    op.create_foreign_key("reports_ward_id_fkey", "reports", "wards", ["ward_id"], ["id"])

    op.create_table(
        "report_status_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], name="report_status_log_report_id_fkey", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], name="report_status_log_changed_by_id_fkey"),
        sa.CheckConstraint("to_status IN ('pending', 'in_progress', 'resolved')", name="report_status_log_to_status_check"),
    )
    op.create_index("ix_report_status_log_report_id", "report_status_log", ["report_id"], unique=False)
    op.create_index("ix_report_status_log_changed_by_id", "report_status_log", ["changed_by_id"], unique=False)
    op.create_index("ix_report_status_log_report_created", "report_status_log", ["report_id", "created_at"], unique=False)

    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION civiclens_log_report_status_change()
        RETURNS trigger AS $$
        DECLARE
            actor_id INTEGER;
            status_note TEXT;
        BEGIN
            IF NEW.status IS DISTINCT FROM OLD.status THEN
                actor_id := NULLIF(current_setting('civiclens.changed_by_id', true), '')::INTEGER;
                IF actor_id IS NULL THEN
                    RAISE EXCEPTION 'Report status changes must include a CivicLens actor';
                END IF;
                status_note := NULLIF(current_setting('civiclens.status_note', true), '');
                INSERT INTO report_status_log(report_id, changed_by_id, from_status, to_status, note)
                VALUES (OLD.id, actor_id, OLD.status, NEW.status, status_note);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))
    op.execute(sa.text("""
        CREATE TRIGGER civiclens_report_status_history
        BEFORE UPDATE OF status ON reports
        FOR EACH ROW EXECUTE FUNCTION civiclens_log_report_status_change();
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS civiclens_report_status_history ON reports"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS civiclens_log_report_status_change()"))
    op.drop_index("ix_report_status_log_report_created", table_name="report_status_log")
    op.drop_index("ix_report_status_log_changed_by_id", table_name="report_status_log")
    op.drop_index("ix_report_status_log_report_id", table_name="report_status_log")
    op.drop_table("report_status_log")
    op.drop_constraint("reports_ward_id_fkey", "reports", type_="foreignkey")
    op.drop_index("ix_reports_ward_id", table_name="reports")
    op.drop_column("reports", "ward_id")
    op.drop_constraint("reports_severity_check", "reports", type_="check")
    op.drop_index("ix_reports_severity", table_name="reports")
    op.drop_column("reports", "severity")
    op.drop_constraint("reports_status_check", "reports", type_="check")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_column("reports", "status")
    op.drop_index("ix_wards_name", table_name="wards")
    op.drop_table("wards")
