from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from chamaleon.domain.types import CategoryBudgetStatus, MonthlySummary, ReportPayload, WeeklySummary
from chamaleon.infra.models import User
from chamaleon.repos.budgets import CategoryBudgetRepository
from chamaleon.repos.recurring import RecurringRuleRepository
from chamaleon.repos.transactions import TransactionRepository
from chamaleon.services.recurring import RecurringService


class FinanceService:
    def __init__(
        self,
        transactions: TransactionRepository,
        budgets: CategoryBudgetRepository | None = None,
        recurring_rules: RecurringRuleRepository | None = None,
        recurring_service: RecurringService | None = None,
    ):
        self.transactions = transactions
        self.budgets = budgets or CategoryBudgetRepository()
        self.recurring_rules = recurring_rules or RecurringRuleRepository()
        self.recurring_service = recurring_service or RecurringService()

    def _build_monthly_insights(
        self,
        salary: Decimal,
        income_total: Decimal,
        expense_total: Decimal,
        balance: Decimal,
        top_categories: list[tuple[str, Decimal]],
        budget_statuses: list[CategoryBudgetStatus],
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

        stressed_budget = next((item for item in budget_statuses if item.alert_threshold is not None), None)
        if stressed_budget is not None:
            if stressed_budget.alert_threshold >= 100:
                insights.append(
                    f"{stressed_budget.category} já passou do limite planejado e merece atenção imediata."
                )
            elif stressed_budget.alert_threshold >= 90:
                insights.append(
                    f"{stressed_budget.category} está muito perto de estourar o teto definido para o mês."
                )
            else:
                insights.append(
                    f"{stressed_budget.category} já entrou na faixa de atenção do orçamento."
                )

        return insights[:4]

    def build_monthly_summary(self, session: Session, user: User, reference_date: date | None = None) -> MonthlySummary:
        today = reference_date or date.today()
        start_date = today.replace(day=1)
        end_date = today.replace(day=monthrange(today.year, today.month)[1])
        income_total, expense_total = self.transactions.monthly_totals(session, user, start_date, end_date)
        balance = Decimal(user.monthly_salary) + income_total - expense_total
        top_categories = self.transactions.monthly_category_totals(session, user, start_date, end_date)
        salary = Decimal(user.monthly_salary)
        budget_statuses = self._build_budget_statuses(session, user, start_date, end_date)
        return MonthlySummary(
            salary=salary,
            income_total=income_total,
            expense_total=expense_total,
            balance=balance,
            top_categories=top_categories[:5],
            budget_statuses=budget_statuses,
            insights=self._build_monthly_insights(salary, income_total, expense_total, balance, top_categories[:5], budget_statuses),
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

    def build_weekly_summary(self, session: Session, user: User, reference_date: date | None = None) -> WeeklySummary:
        today = reference_date or date.today()
        week_start, week_end = self.previous_week_range(today)
        income_total, expense_total = self.transactions.totals_for_period(session, user, week_start, week_end)
        balance = income_total - expense_total
        top_categories = self.transactions.category_totals_for_period(session, user, week_start, week_end)
        top_category = top_categories[0] if top_categories else None
        month_start = week_end.replace(day=1)
        month_end = week_end.replace(day=monthrange(week_end.year, week_end.month)[1])
        budget_statuses = self._build_budget_statuses(session, user, month_start, month_end)
        upcoming_recurring = self._build_upcoming_recurring_labels(session, user, week_end + timedelta(days=1), week_end + timedelta(days=7))
        main_warning = self._build_weekly_warning(balance, budget_statuses, top_category)
        return WeeklySummary(
            week_start=week_start,
            week_end=week_end,
            income_total=income_total,
            expense_total=expense_total,
            balance=balance,
            top_category=top_category,
            budget_statuses=budget_statuses,
            upcoming_recurring=upcoming_recurring,
            main_warning=main_warning,
        )

    def build_weekly_closure_text(self, summary: WeeklySummary) -> str:
        lines = [
            "📊 Fechamento da semana",
            "",
            f"Período: {summary.week_start.strftime('%d/%m')} a {summary.week_end.strftime('%d/%m')}",
            f"Você gastou {_format_decimal(summary.expense_total)} nesta semana.",
            f"Entradas da semana: {_format_decimal(summary.income_total)}.",
            f"Saldo da semana: {_format_decimal(summary.balance)}.",
        ]

        if summary.top_category is not None:
            category, amount = summary.top_category
            lines.append(f"Sua maior categoria foi {category}, com {_format_decimal(amount)}.")

        watched_budgets = [item for item in summary.budget_statuses if item.alert_threshold is not None][:2]
        if watched_budgets:
            lines.append("")
            lines.append("Orçamentos:")
            for budget in watched_budgets:
                lines.append(
                    f"{budget.category} está em {int(budget.usage_ratio)}% do limite mensal."
                )

        if summary.upcoming_recurring:
            lines.append("")
            lines.append("Próximas recorrências:")
            for item in summary.upcoming_recurring[:2]:
                lines.append(f"• {item}")

        if summary.main_warning:
            lines.append("")
            lines.append("Ponto de atenção:")
            lines.append(summary.main_warning)

        return "\n".join(lines)

    def weekly_period_label(self, reference_date: date | None = None) -> str:
        week_start, _ = self.previous_week_range(reference_date or date.today())
        iso_year, iso_week, _ = week_start.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

    def weekly_closure_due(self, user: User, now: datetime, weekly_closure_hour: int) -> bool:
        if now.weekday() != 0 or now.hour < weekly_closure_hour:
            return False
        return user.last_weekly_closure_sent_for != self.weekly_period_label(now.date())

    def previous_week_range(self, reference_date: date) -> tuple[date, date]:
        week_end = reference_date - timedelta(days=reference_date.weekday() + 1)
        week_start = week_end - timedelta(days=6)
        return week_start, week_end

    def _build_budget_statuses(self, session: Session, user: User, start_date: date, end_date: date) -> list[CategoryBudgetStatus]:
        category_totals = {
            category: Decimal(total or Decimal("0.00"))
            for category, total in self.transactions.monthly_category_totals(session, user, start_date, end_date)
        }
        statuses: list[CategoryBudgetStatus] = []
        for budget in self.budgets.list_for_user(session, user):
            spent = category_totals.get(budget.category, Decimal("0.00"))
            monthly_limit = Decimal(budget.monthly_limit)
            remaining = monthly_limit - spent
            usage_ratio = Decimal("0.00")
            if monthly_limit > 0:
                usage_ratio = (spent / monthly_limit) * Decimal("100")
            alert_threshold = self._threshold_for_ratio(usage_ratio)
            statuses.append(
                CategoryBudgetStatus(
                    category=budget.category,
                    monthly_limit=monthly_limit,
                    spent=spent,
                    remaining=remaining,
                    usage_ratio=usage_ratio.quantize(Decimal("0.01")),
                    alert_threshold=alert_threshold,
                )
            )
        return sorted(statuses, key=lambda item: (item.usage_ratio, item.spent), reverse=True)

    def build_budget_alert_for_new_expense(
        self,
        session: Session,
        user: User,
        category: str,
        amount: Decimal,
        reference_date: date,
    ) -> str | None:
        budget = self.budgets.get_for_user_category(session, user, category)
        if budget is None or amount <= 0:
            return None

        start_date = reference_date.replace(day=1)
        end_date = reference_date.replace(day=monthrange(reference_date.year, reference_date.month)[1])
        spent_before = self.transactions.monthly_spent_for_category(session, user, category, start_date, end_date)
        spent_after = spent_before + amount
        monthly_limit = Decimal(budget.monthly_limit)
        if monthly_limit <= 0:
            return None

        before_ratio = (spent_before / monthly_limit) * Decimal("100") if spent_before > 0 else Decimal("0.00")
        after_ratio = (spent_after / monthly_limit) * Decimal("100")
        threshold = self._crossed_threshold(before_ratio, after_ratio)
        if threshold is None:
            return None

        remaining = monthly_limit - spent_after
        if threshold >= 100:
            return (
                f"🚨 Atenção em {category}: você passou do limite mensal.\n"
                f"• Planejado: {_format_decimal(monthly_limit)}\n"
                f"• Gasto atual: {_format_decimal(spent_after)}\n"
                f"• Excedente: {_format_decimal(abs(remaining))}"
            )
        if threshold >= 90:
            return (
                f"🟠 Quase no teto de {category}.\n"
                f"• Planejado: {_format_decimal(monthly_limit)}\n"
                f"• Gasto atual: {_format_decimal(spent_after)}\n"
                f"• Restante: {_format_decimal(max(remaining, Decimal('0.00')))}"
            )
        return (
            f"🟡 Atenção em {category}: você chegou a 70% do orçamento.\n"
            f"• Planejado: {_format_decimal(monthly_limit)}\n"
            f"• Gasto atual: {_format_decimal(spent_after)}\n"
            f"• Restante: {_format_decimal(max(remaining, Decimal('0.00')))}"
        )

    def _threshold_for_ratio(self, ratio: Decimal) -> int | None:
        if ratio >= Decimal("100"):
            return 100
        if ratio >= Decimal("90"):
            return 90
        if ratio >= Decimal("70"):
            return 70
        return None

    def _crossed_threshold(self, before_ratio: Decimal, after_ratio: Decimal) -> int | None:
        for threshold in (100, 90, 70):
            threshold_decimal = Decimal(str(threshold))
            if before_ratio < threshold_decimal <= after_ratio:
                return threshold
        return None

    def _build_upcoming_recurring_labels(
        self,
        session: Session,
        user: User,
        start_date: date,
        end_date: date,
    ) -> list[str]:
        labels: list[str] = []
        for rule in self.recurring_rules.list_for_user(session, user):
            if not rule.enabled:
                continue
            occurrence = self.recurring_service._next_occurrence_on_or_after(rule, start_date)
            if occurrence is None or occurrence > end_date:
                continue
            labels.append(
                f"{rule.description} em {occurrence.strftime('%d/%m')} ({_format_decimal(Decimal(rule.amount))})"
            )
        return labels

    def _build_weekly_warning(
        self,
        balance: Decimal,
        budget_statuses: list[CategoryBudgetStatus],
        top_category: tuple[str, Decimal] | None,
    ) -> str | None:
        critical_budget = next((item for item in budget_statuses if item.alert_threshold and item.alert_threshold >= 100), None)
        if critical_budget is not None:
            return f"{critical_budget.category} já passou do limite mensal e merece atenção imediata."

        near_budget = next((item for item in budget_statuses if item.alert_threshold and item.alert_threshold >= 90), None)
        if near_budget is not None:
            return f"Se continuar nesse ritmo, {near_budget.category} pode estourar o orçamento antes do fim do mês."

        if balance < 0:
            return "Nesta semana você gastou mais do que entrou. Vale revisar os gastos variáveis primeiro."

        if top_category is not None:
            return f"{top_category[0]} foi sua categoria dominante na semana. Vale acompanhar esse ritmo nos próximos dias."

        return None


def _format_decimal(value: Decimal) -> str:
    return f"R$ {value:.2f}".replace(".", ",")
