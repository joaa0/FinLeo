from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from chamaleon.infra.models import RecurringRule, User


class RecurringRuleRepository:
    def create(
        self,
        session: Session,
        user: User,
        description: str,
        category: str,
        transaction_type: str,
        amount,
        day_of_month: int,
        reminder_days_before: int = 1,
    ) -> RecurringRule:
        rule = RecurringRule(
            user_id=user.id,
            description=description,
            category=category,
            transaction_type=transaction_type,
            amount=amount,
            day_of_month=day_of_month,
            reminder_days_before=reminder_days_before,
        )
        session.add(rule)
        session.flush()
        return rule

    def list_for_user(self, session: Session, user: User) -> list[RecurringRule]:
        stmt = select(RecurringRule).where(RecurringRule.user_id == user.id).order_by(RecurringRule.day_of_month.asc(), RecurringRule.id.asc())
        return list(session.scalars(stmt))

    def list_enabled(self, session: Session) -> list[RecurringRule]:
        stmt = select(RecurringRule).where(RecurringRule.enabled.is_(True))
        return list(session.scalars(stmt))

    def get_by_id_for_user(self, session: Session, user: User, rule_id: int) -> RecurringRule | None:
        stmt = select(RecurringRule).where(RecurringRule.user_id == user.id, RecurringRule.id == rule_id)
        return session.scalar(stmt)

    def update_for_user(
        self,
        session: Session,
        user: User,
        rule_id: int,
        *,
        description: str | None = None,
        category: str | None = None,
        transaction_type: str | None = None,
        amount=None,
        day_of_month: int | None = None,
    ) -> RecurringRule | None:
        rule = self.get_by_id_for_user(session, user, rule_id)
        if rule is None:
            return None
        if description is not None:
            rule.description = description
        if category is not None:
            rule.category = category
        if transaction_type is not None:
            rule.transaction_type = transaction_type
        if amount is not None:
            rule.amount = amount
        if day_of_month is not None:
            rule.day_of_month = day_of_month
        session.flush()
        return rule

    def set_enabled_for_user(self, session: Session, user: User, rule_id: int, enabled: bool) -> RecurringRule | None:
        rule = self.get_by_id_for_user(session, user, rule_id)
        if rule is None:
            return None
        rule.enabled = enabled
        session.flush()
        return rule

    def delete_for_user(self, session: Session, user: User, rule_id: int) -> bool:
        rule = self.get_by_id_for_user(session, user, rule_id)
        if rule is None:
            return False
        session.delete(rule)
        session.flush()
        return True

    def mark_reminder_sent(self, session: Session, rule: RecurringRule, period_label: str) -> None:
        rule.last_reminder_period = period_label
        session.flush()
