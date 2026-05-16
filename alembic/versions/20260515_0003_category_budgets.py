"""category budgets"""

from alembic import op
import sqlalchemy as sa


revision = "20260515_0003"
down_revision = "20260514_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "category_budgets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("monthly_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "category", name="uq_category_budgets_user_category"),
    )
    op.create_index("ix_category_budgets_user_id", "category_budgets", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_category_budgets_user_id", table_name="category_budgets")
    op.drop_table("category_budgets")
