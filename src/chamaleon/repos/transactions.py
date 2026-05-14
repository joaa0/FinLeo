from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from chamaleon.domain.types import TransactionDraft
from chamaleon.infra.models import Transaction, User


class TransactionRepository:
    def create(self, session: Session, user: User, draft: TransactionDraft) -> Transaction:
        transaction = Transaction(
            user_id=user.id,
            transaction_type=draft.transaction_type,
            category=draft.category,
            description=draft.description,
            details=draft.details,
            amount=draft.amount,
            transaction_date=draft.transaction_date,
        )
        session.add(transaction)
        session.flush()
        return transaction

    def list_recent(self, session: Session, user: User, limit: int = 10, offset: int = 0) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(session.scalars(stmt))

    def get_by_id_for_user(self, session: Session, user: User, transaction_id: int) -> Transaction | None:
        stmt = select(Transaction).where(Transaction.user_id == user.id, Transaction.id == transaction_id)
        return session.scalar(stmt)

    def get_latest_for_user(self, session: Session, user: User) -> Transaction | None:
        stmt = (
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())
            .limit(1)
        )
        return session.scalar(stmt)

    def count_for_user(self, session: Session, user: User) -> int:
        stmt = select(func.count(Transaction.id)).where(Transaction.user_id == user.id)
        return int(session.scalar(stmt) or 0)

    def delete_for_user(self, session: Session, user: User, transaction_id: int) -> bool:
        stmt = delete(Transaction).where(Transaction.user_id == user.id, Transaction.id == transaction_id)
        result = session.execute(stmt)
        return result.rowcount > 0

    def update_amount_for_user(self, session: Session, user: User, transaction_id: int, amount: Decimal) -> Transaction | None:
        transaction = self.get_by_id_for_user(session, user, transaction_id)
        if transaction is None:
            return None
        transaction.amount = amount
        session.flush()
        return transaction

    def monthly_category_totals(self, session: Session, user: User, start_date: date, end_date: date) -> list[tuple[str, Decimal]]:
        stmt = (
            select(Transaction.category, func.sum(Transaction.amount))
            .where(
                Transaction.user_id == user.id,
                Transaction.transaction_type == "expense",
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .group_by(Transaction.category)
            .order_by(func.sum(Transaction.amount).desc())
        )
        return [(category, total) for category, total in session.execute(stmt).all()]

    def monthly_totals(self, session: Session, user: User, start_date: date, end_date: date) -> tuple[Decimal, Decimal]:
        stmt = (
            select(Transaction.transaction_type, func.sum(Transaction.amount))
            .where(
                Transaction.user_id == user.id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
            .group_by(Transaction.transaction_type)
        )
        income = Decimal("0.00")
        expense = Decimal("0.00")
        for tx_type, total in session.execute(stmt).all():
            if tx_type == "income":
                income = total or Decimal("0.00")
            elif tx_type == "expense":
                expense = total or Decimal("0.00")
        return income, expense
