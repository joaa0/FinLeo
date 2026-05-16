from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class TransactionDraft:
    description: str
    amount: Decimal
    category: str
    transaction_type: str
    transaction_date: date
    details: str = ""
    confidence: float = 0.0
    raw_text: str = ""


@dataclass(frozen=True)
class IntentResult:
    intent: str
    confidence: float
    entities: dict[str, str] = field(default_factory=dict)
    draft: TransactionDraft | None = None
    drafts: list[TransactionDraft] = field(default_factory=list)
    needs_confirmation: bool = False


@dataclass(frozen=True)
class TransactionParseResult:
    confidence: float
    draft: TransactionDraft | None = None
    drafts: list[TransactionDraft] = field(default_factory=list)
    needs_confirmation: bool = True
    should_use_ai_fallback: bool = False
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CategoryBudgetStatus:
    category: str
    monthly_limit: Decimal
    spent: Decimal
    remaining: Decimal
    usage_ratio: Decimal
    alert_threshold: int | None


@dataclass(frozen=True)
class MonthlySummary:
    salary: Decimal
    income_total: Decimal
    expense_total: Decimal
    balance: Decimal
    top_categories: list[tuple[str, Decimal]]
    budget_statuses: list[CategoryBudgetStatus]
    insights: list[str]


@dataclass(frozen=True)
class WeeklySummary:
    week_start: date
    week_end: date
    income_total: Decimal
    expense_total: Decimal
    balance: Decimal
    top_category: tuple[str, Decimal] | None
    budget_statuses: list[CategoryBudgetStatus]
    upcoming_recurring: list[str]
    main_warning: str | None


@dataclass(frozen=True)
class ReportPayload:
    period_label: str
    generated_at: datetime
    summary: MonthlySummary
    recent_transactions: list[dict]
    email: str
