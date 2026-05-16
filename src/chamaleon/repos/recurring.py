from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from chamaleon.infra.models import RecurringRule, User

_UNSET = object()


class RecurringRuleRepository:
    def create(
        self,
        session: Session,
        user: User,
        description: str,
        category: str,
        transaction_type: str,
        amount,
        day_of_month: int | None,
        frequency: str = "monthly",
        weekday: int | None = None,
        start_date: date | None = None,
        reminder_days_before: int = 1,
    ) -> RecurringRule:
        rule = RecurringRule(
            user_id=user.id,
            description=description,
            category=category,
            transaction_type=transaction_type,
            amount=amount,
            frequency=frequency,
            day_of_month=day_of_month,
            weekday=weekday,
            start_date=start_date,
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
        frequency: str | None = None,
        day_of_month: int | None | object = _UNSET,
        weekday: int | None | object = _UNSET,
        start_date: date | None | object = _UNSET,
        reminder_days_before: int | None = None,
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
        if frequency is not None:
            rule.frequency = frequency
        if day_of_month is not _UNSET:
            rule.day_of_month = day_of_month
        if weekday is not _UNSET:
            rule.weekday = weekday
        if start_date is not _UNSET:
            rule.start_date = start_date
        if reminder_days_before is not None:
            rule.reminder_days_before = reminder_days_before
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
