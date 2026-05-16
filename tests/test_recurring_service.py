from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
except ModuleNotFoundError:  # pragma: no cover - depende do ambiente
    create_engine = None
    sessionmaker = None

if create_engine is not None:
    from chamaleon.infra.models import Base, User
    from chamaleon.repos.recurring import RecurringRuleRepository
    from chamaleon.repos.users import UserRepository
    from chamaleon.services.parser import detect_category
    from chamaleon.services.recurring import RecurringService


@unittest.skipIf(create_engine is None, "sqlalchemy nao instalado no ambiente atual")
class RecurringServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        self.repo = RecurringRuleRepository()
        self.users = UserRepository(nudge_start_hour=8, nudge_end_hour=20)
        self.service = RecurringService()

    def test_creates_rule_and_detects_due_reminder(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()

            rule = self.repo.create(
                session=session,
                user=user,
                description="aluguel",
                category="Moradia",
                transaction_type="expense",
                amount=Decimal("1200.00"),
                day_of_month=10,
                reminder_days_before=1,
            )
            session.commit()

            self.assertTrue(self.service.reminder_due(rule, date(2026, 5, 9)))
            self.assertFalse(self.service.reminder_due(rule, date(2026, 5, 10)))

    def test_does_not_repeat_reminder_in_same_period(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()

            rule = self.repo.create(
                session=session,
                user=user,
                description="netflix",
                category="Entretenimento",
                transaction_type="expense",
                amount=Decimal("39.90"),
                day_of_month=15,
                reminder_days_before=1,
            )
            self.repo.mark_reminder_sent(session, rule, "2026-05")
            session.commit()

            self.assertFalse(self.service.reminder_due(rule, date(2026, 5, 14)))

    def test_detects_daily_nudge_only_once(self) -> None:
        user = User(
            telegram_user_id="123",
            email="test@example.com",
            monthly_salary=Decimal("3000.00"),
            daily_nudge_enabled=True,
            nudge_hour=10,
            nudge_minute=15,
            last_nudge_sent_on=None,
        )
        self.assertTrue(self.service.nudge_due(user, datetime(2026, 5, 14, 10, 15)))

        user.last_nudge_sent_on = date(2026, 5, 14)
        self.assertFalse(self.service.nudge_due(user, datetime(2026, 5, 14, 10, 30)))

    def test_can_toggle_and_reroll_daily_nudge(self) -> None:
        with self.session_factory() as session:
            user = User(
                telegram_user_id="123",
                email="test@example.com",
                monthly_salary=Decimal("3000.00"),
                daily_nudge_enabled=True,
                nudge_hour=10,
                nudge_minute=15,
            )
            session.add(user)
            session.flush()

            updated = self.users.set_daily_nudge_enabled(session, user, False)
            self.assertFalse(updated.daily_nudge_enabled)

            rerolled = self.users.reroll_nudge_slot(session, user)
            self.assertGreaterEqual(rerolled.nudge_hour, 8)
            self.assertLessEqual(rerolled.nudge_hour, 20)
            self.assertGreaterEqual(rerolled.nudge_minute, 0)
            self.assertLessEqual(rerolled.nudge_minute, 59)

    def test_detects_due_reminder_for_weekly_rule(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()

            rule = self.repo.create(
                session=session,
                user=user,
                description="academia",
                category="Saude",
                transaction_type="expense",
                amount=Decimal("80.00"),
                day_of_month=None,
                frequency="weekly",
                weekday=2,
                reminder_days_before=1,
            )
            session.commit()

            self.assertTrue(self.service.reminder_due(rule, date(2026, 5, 12)))
            self.assertFalse(self.service.reminder_due(rule, date(2026, 5, 13)))

    def test_detects_due_reminder_for_biweekly_rule(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()

            rule = self.repo.create(
                session=session,
                user=user,
                description="faxina",
                category="Moradia",
                transaction_type="expense",
                amount=Decimal("150.00"),
                day_of_month=None,
                frequency="biweekly",
                weekday=4,
                start_date=date(2026, 5, 15),
                reminder_days_before=2,
            )
            session.commit()

            self.assertTrue(self.service.reminder_due(rule, date(2026, 5, 13)))
            self.assertFalse(self.service.reminder_due(rule, date(2026, 5, 20)))

    def test_can_edit_pause_and_delete_rule(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()

            category, tx_type = detect_category("spotify")
            rule = self.repo.create(
                session=session,
                user=user,
                description="spotify",
                category=category,
                transaction_type=tx_type,
                amount=Decimal("21.90"),
                day_of_month=12,
                reminder_days_before=1,
            )
            session.commit()

            updated = self.repo.update_for_user(
                session=session,
                user=user,
                rule_id=rule.id,
                description="netflix",
                category="Entretenimento",
                transaction_type="expense",
                amount=Decimal("39.90"),
                frequency="weekly",
                day_of_month=None,
                weekday=2,
                start_date=None,
                reminder_days_before=3,
            )
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertEqual(updated.description, "netflix")
            self.assertEqual(updated.amount, Decimal("39.90"))
            self.assertEqual(updated.frequency, "weekly")
            self.assertIsNone(updated.day_of_month)
            self.assertEqual(updated.weekday, 2)
            self.assertEqual(updated.reminder_days_before, 3)

            paused = self.repo.set_enabled_for_user(session, user, rule.id, False)
            self.assertIsNotNone(paused)
            assert paused is not None
            self.assertFalse(paused.enabled)

            resumed = self.repo.set_enabled_for_user(session, user, rule.id, True)
            self.assertIsNotNone(resumed)
            assert resumed is not None
            self.assertTrue(resumed.enabled)

            deleted = self.repo.delete_for_user(session, user, rule.id)
            self.assertTrue(deleted)
            self.assertIsNone(self.repo.get_by_id_for_user(session, user, rule.id))


if __name__ == "__main__":
    unittest.main()
