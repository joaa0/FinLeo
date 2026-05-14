from __future__ import annotations

from calendar import monthrange
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from chamaleon.domain.types import MonthlySummary, ReportPayload
from chamaleon.infra.models import User
from chamaleon.repos.transactions import TransactionRepository


class FinanceService:
    def __init__(self, transactions: TransactionRepository):
        self.transactions = transactions

    def _build_monthly_insights(
        self,
        salary: Decimal,
        income_total: Decimal,
        expense_total: Decimal,
        balance: Decimal,
        top_categories: list[tuple[str, Decimal]],
    ) -> list[str]:
        insights: list[str] = []
        available_income = salary + income_total

        if available_income > 0:
            expense_ratio = (expense_total / available_income) * Decimal("100")
            if expense_ratio >= Decimal("90"):
                insights.append("Seu mês está bem pressionado: você já comprometeu mais de 90% do que entrou.")
            elif expense_ratio >= Decimal("70"):
                insights.append("Seu ritmo de gastos está alto: mais de 70% do que entrou no mês já foi consumido.")
            else:
                insights.append("Seu ritmo de gastos está sob controle até aqui.")

        if top_categories:
            top_category, top_amount = top_categories[0]
            insights.append(f"Sua categoria mais pesada no mês foi {top_category}, com {_format_decimal(top_amount)}.")

        if balance < 0:
            insights.append("Seu saldo do mês está negativo. Vale desacelerar os gastos variáveis agora.")
        elif balance == 0:
            insights.append("Seu saldo do mês está no limite. Qualquer novo gasto merece revisão.")
        else:
            insights.append(f"Você ainda tem {_format_decimal(balance)} de fôlego estimado no mês.")

        if income_total > 0:
            insights.append(f"Entradas extras somaram {_format_decimal(income_total)} e ajudaram seu caixa no período.")

        return insights[:4]

    def build_monthly_summary(self, session: Session, user: User, reference_date: date | None = None) -> MonthlySummary:
        today = reference_date or date.today()
        start_date = today.replace(day=1)
        end_date = today.replace(day=monthrange(today.year, today.month)[1])
        income_total, expense_total = self.transactions.monthly_totals(session, user, start_date, end_date)
        balance = Decimal(user.monthly_salary) + income_total - expense_total
        top_categories = self.transactions.monthly_category_totals(session, user, start_date, end_date)
        salary = Decimal(user.monthly_salary)
        return MonthlySummary(
            salary=salary,
            income_total=income_total,
            expense_total=expense_total,
            balance=balance,
            top_categories=top_categories[:5],
            insights=self._build_monthly_insights(salary, income_total, expense_total, balance, top_categories[:5]),
        )

    def build_report_payload(self, session: Session, user: User, reference_date: date | None = None) -> ReportPayload:
        today = reference_date or date.today()
        summary = self.build_monthly_summary(session, user, today)
        recent_transactions = []
        for transaction in self.transactions.list_recent(session, user, limit=8):
            recent_transactions.append(
                {
                    "id": transaction.id,
                    "date": transaction.transaction_date.isoformat(),
                    "type": transaction.transaction_type,
                    "category": transaction.category,
                    "description": transaction.description,
                    "details": transaction.details,
                    "amount": f"{transaction.amount:.2f}",
                }
            )
        return ReportPayload(
            period_label=today.strftime("%Y-%m"),
            generated_at=datetime.utcnow(),
            summary=summary,
            recent_transactions=recent_transactions,
            email=user.email,
        )


def _format_decimal(value: Decimal) -> str:
    return f"R$ {value:.2f}".replace(".", ",")
