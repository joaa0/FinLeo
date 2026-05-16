"""recurring frequency and schedule"""

from alembic import op
import sqlalchemy as sa


revision = "20260515_0004"
down_revision = "20260515_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recurring_rules", sa.Column("frequency", sa.String(length=16), nullable=False, server_default="monthly"))
    op.add_column("recurring_rules", sa.Column("weekday", sa.Integer(), nullable=True))
    op.add_column("recurring_rules", sa.Column("start_date", sa.Date(), nullable=True))
    op.alter_column("recurring_rules", "day_of_month", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("recurring_rules", "day_of_month", existing_type=sa.Integer(), nullable=False)
    op.drop_column("recurring_rules", "start_date")
    op.drop_column("recurring_rules", "weekday")
    op.drop_column("recurring_rules", "frequency")
