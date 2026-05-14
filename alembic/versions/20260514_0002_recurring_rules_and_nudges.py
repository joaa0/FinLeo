"""recurring rules and nudges"""

from alembic import op
import sqlalchemy as sa


revision = "20260514_0002"
down_revision = "20260514_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("daily_nudge_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("nudge_hour", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("users", sa.Column("nudge_minute", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("last_nudge_sent_on", sa.Date(), nullable=True))

    op.create_table(
        "recurring_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("description", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("transaction_type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("day_of_month", sa.Integer(), nullable=False),
        sa.Column("reminder_days_before", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_reminder_period", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recurring_rules_user_id", "recurring_rules", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recurring_rules_user_id", table_name="recurring_rules")
    op.drop_table("recurring_rules")
    op.drop_column("users", "last_nudge_sent_on")
    op.drop_column("users", "nudge_minute")
    op.drop_column("users", "nudge_hour")
    op.drop_column("users", "daily_nudge_enabled")
