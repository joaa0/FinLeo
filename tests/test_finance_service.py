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
    from chamaleon.repos.budgets import CategoryBudgetRepository
    from chamaleon.repos.recurring import RecurringRuleRepository
    from chamaleon.repos.transactions import TransactionRepository
    from chamaleon.services.finance import FinanceService
    from chamaleon.services.parser import parse_transaction_text


@unittest.skipIf(create_engine is None, "sqlalchemy nao instalado no ambiente atual")
class FinanceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        self.repo = TransactionRepository()
        self.budgets = CategoryBudgetRepository()
        self.recurring_rules = RecurringRuleRepository()
        self.service = FinanceService(self.repo, self.budgets, self.recurring_rules)

    def test_builds_monthly_summary(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()

            expense = parse_transaction_text("gastei 100 no ifood")
            income = parse_transaction_text("recebi 250 de freelance")
            assert expense is not None and income is not None
            self.repo.create(session, user, expense)
            self.repo.create(session, user, income)
            session.commit()

            summary = self.service.build_monthly_summary(session, user, reference_date=date.today())

        self.assertEqual(summary.salary, Decimal("3000.00"))
        self.assertEqual(summary.expense_total, Decimal("100.00"))
        self.assertEqual(summary.income_total, Decimal("250.00"))
        self.assertEqual(summary.balance, Decimal("3150.00"))
        self.assertTrue(summary.insights)
        self.assertIn("Seu ritmo de gastos", summary.insights[0])

    def test_builds_budget_statuses(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()

            expense = parse_transaction_text("gastei 100 no ifood")
            assert expense is not None
            self.repo.create(session, user, expense)
            self.budgets.upsert(session, user, "Alimentacao", Decimal("300.00"))
            session.commit()

            summary = self.service.build_monthly_summary(session, user, reference_date=date.today())

        self.assertEqual(len(summary.budget_statuses), 1)
        status = summary.budget_statuses[0]
        self.assertEqual(status.category, "Alimentacao")
        self.assertEqual(status.spent, Decimal("100.00"))
        self.assertEqual(status.monthly_limit, Decimal("300.00"))
        self.assertEqual(status.remaining, Decimal("200.00"))
        self.assertIsNone(status.alert_threshold)

    def test_builds_budget_alert_for_70_percent_threshold(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()
            self.budgets.upsert(session, user, "Alimentacao", Decimal("100.00"))

            alert = self.service.build_budget_alert_for_new_expense(
                session=session,
                user=user,
                category="Alimentacao",
                amount=Decimal("70.00"),
                reference_date=date.today(),
            )

        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertIn("70%", alert)

    def test_builds_budget_alert_for_90_percent_threshold(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()
            self.budgets.upsert(session, user, "Alimentacao", Decimal("100.00"))

            first_expense = parse_transaction_text("gastei 75 no ifood")
            assert first_expense is not None
            self.repo.create(session, user, first_expense)

            alert = self.service.build_budget_alert_for_new_expense(
                session=session,
                user=user,
                category="Alimentacao",
                amount=Decimal("15.00"),
                reference_date=date.today(),
            )

        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertIn("Quase no teto", alert)

    def test_builds_budget_alert_for_100_percent_threshold(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()
            self.budgets.upsert(session, user, "Alimentacao", Decimal("100.00"))

            first_expense = parse_transaction_text("gastei 95 no ifood")
            assert first_expense is not None
            self.repo.create(session, user, first_expense)

            alert = self.service.build_budget_alert_for_new_expense(
                session=session,
                user=user,
                category="Alimentacao",
                amount=Decimal("10.00"),
                reference_date=date.today(),
            )

        self.assertIsNotNone(alert)
        assert alert is not None
        self.assertIn("passou do limite", alert)

    def test_can_update_and_delete_latest_transaction(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()

            expense = parse_transaction_text("gastei 100 no ifood")
            assert expense is not None
            transaction = self.repo.create(session, user, expense)
            session.commit()

            latest = self.repo.get_latest_for_user(session, user)
            self.assertIsNotNone(latest)
            assert latest is not None
            self.assertEqual(latest.id, transaction.id)

            updated = self.repo.update_amount_for_user(session, user, latest.id, Decimal("55.00"))
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertEqual(updated.amount, Decimal("55.00"))

            deleted = self.repo.delete_for_user(session, user, latest.id)
            self.assertTrue(deleted)

    def test_builds_weekly_summary_for_previous_week(self) -> None:
        with self.session_factory() as session:
            user = User(telegram_user_id="123", email="test@example.com", monthly_salary=Decimal("3000.00"))
            session.add(user)
            session.flush()

            expense = parse_transaction_text("gastei 148 no ifood")
            income = parse_transaction_text("recebi 500 de freelance")
            assert expense is not None and income is not None
            expense = expense.__class__(**{**expense.__dict__, "transaction_date": date(2026, 5, 6)})
            income = income.__class__(**{**income.__dict__, "transaction_date": date(2026, 5, 8)})
            self.repo.create(session, user, expense)
            self.repo.create(session, user, income)
            self.budgets.upsert(session, user, "Alimentacao", Decimal("180.00"))
            self.recurring_rules.create(
                session,
                user,
                description="academia",
                category="Saude",
                transaction_type="expense",
                amount=Decimal("90.00"),
                day_of_month=None,
                frequency="weekly",
                weekday=0,
                reminder_days_before=1,
            )
            session.commit()

            summary = self.service.build_weekly_summary(session, user, reference_date=date(2026, 5, 15))

        self.assertEqual(summary.week_start, date(2026, 5, 4))
        self.assertEqual(summary.week_end, date(2026, 5, 10))
        self.assertEqual(summary.expense_total, Decimal("148.00"))
        self.assertEqual(summary.income_total, Decimal("500.00"))
        self.assertEqual(summary.balance, Decimal("352.00"))
        self.assertEqual(summary.top_category, ("Alimentacao", Decimal("148.00")))
        self.assertTrue(summary.upcoming_recurring)
        self.assertIsNotNone(summary.main_warning)

    def test_weekly_closure_due_only_once_per_week(self) -> None:
        user = User(
            telegram_user_id="123",
            email="test@example.com",
            monthly_salary=Decimal("3000.00"),
            last_weekly_closure_sent_for=None,
        )
        self.assertTrue(self.service.weekly_closure_due(user, datetime(2026, 5, 18, 9, 15), 9))
        user.last_weekly_closure_sent_for = self.service.weekly_period_label(date(2026, 5, 18))
        self.assertFalse(self.service.weekly_closure_due(user, datetime(2026, 5, 18, 9, 30), 9))


if __name__ == "__main__":
    unittest.main()
