"""weekly closure tracking"""

from alembic import op
import sqlalchemy as sa


revision = "20260515_0005"
down_revision = "20260515_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_weekly_closure_sent_for", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_weekly_closure_sent_for")
