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


@dataclass(frozen=True)
class MonthlySummary:
    salary: Decimal
    income_total: Decimal
    expense_total: Decimal
    balance: Decimal
    top_categories: list[tuple[str, Decimal]]
    insights: list[str]


@dataclass(frozen=True)
class ReportPayload:
    period_label: str
    generated_at: datetime
    summary: MonthlySummary
    recent_transactions: list[dict]
    email: str
