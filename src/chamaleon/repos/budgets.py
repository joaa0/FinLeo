from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from chamaleon.infra.models import CategoryBudget, User


class CategoryBudgetRepository:
    def list_for_user(self, session: Session, user: User) -> list[CategoryBudget]:
        stmt = select(CategoryBudget).where(CategoryBudget.user_id == user.id).order_by(CategoryBudget.category.asc())
        return list(session.scalars(stmt))

    def get_for_user_category(self, session: Session, user: User, category: str) -> CategoryBudget | None:
        stmt = select(CategoryBudget).where(CategoryBudget.user_id == user.id, CategoryBudget.category == category)
        return session.scalar(stmt)

    def upsert(self, session: Session, user: User, category: str, monthly_limit: Decimal) -> CategoryBudget:
        budget = self.get_for_user_category(session, user, category)
        if budget is None:
            budget = CategoryBudget(user_id=user.id, category=category, monthly_limit=monthly_limit)
            session.add(budget)
            session.flush()
            return budget
        budget.monthly_limit = monthly_limit
        session.flush()
        return budget

    def delete_for_user_category(self, session: Session, user: User, category: str) -> bool:
        stmt = delete(CategoryBudget).where(CategoryBudget.user_id == user.id, CategoryBudget.category == category)
        result = session.execute(stmt)
        return result.rowcount > 0
