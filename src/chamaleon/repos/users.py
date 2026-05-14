from __future__ import annotations

import random
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from chamaleon.infra.models import User


class UserRepository:
    def __init__(self, nudge_start_hour: int = 8, nudge_end_hour: int = 20):
        self.nudge_start_hour = nudge_start_hour
        self.nudge_end_hour = nudge_end_hour

    def _random_nudge_slot(self) -> tuple[int, int]:
        hour = random.randint(self.nudge_start_hour, self.nudge_end_hour)
        minute = random.randint(0, 59)
        return hour, minute

    def get_by_telegram_id(self, session: Session, telegram_user_id: str) -> User | None:
        stmt = select(User).where(User.telegram_user_id == telegram_user_id)
        return session.scalar(stmt)

    def list_all_with_nudges(self, session: Session) -> list[User]:
        stmt = select(User).where(User.daily_nudge_enabled.is_(True))
        return list(session.scalars(stmt))

    def create_or_update(self, session: Session, telegram_user_id: str, email: str, monthly_salary: Decimal) -> User:
        user = self.get_by_telegram_id(session, telegram_user_id)
        if user is None:
            nudge_hour, nudge_minute = self._random_nudge_slot()
            user = User(
                telegram_user_id=telegram_user_id,
                email=email,
                monthly_salary=monthly_salary,
                nudge_hour=nudge_hour,
                nudge_minute=nudge_minute,
            )
            session.add(user)
            session.flush()
            return user
        user.email = email
        user.monthly_salary = monthly_salary
        session.flush()
        return user

    def update_salary(self, session: Session, telegram_user_id: str, monthly_salary: Decimal) -> User | None:
        user = self.get_by_telegram_id(session, telegram_user_id)
        if user is None:
            return None
        user.monthly_salary = monthly_salary
        session.flush()
        return user

    def mark_nudge_sent(self, session: Session, user: User, sent_on) -> None:
        user.last_nudge_sent_on = sent_on
        session.flush()
