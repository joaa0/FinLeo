from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta

from chamaleon.infra.models import RecurringRule, User

WEEKDAY_LABELS = {
    0: "segunda",
    1: "terca",
    2: "quarta",
    3: "quinta",
    4: "sexta",
    5: "sabado",
    6: "domingo",
}


class RecurringService:
    def reminder_due(self, rule: RecurringRule, today: date) -> bool:
        occurrence_date = self._next_occurrence_on_or_after(rule, today)
        if occurrence_date is None:
            return False
        reminder_date = occurrence_date - timedelta(days=rule.reminder_days_before)
        reminder_key = occurrence_date.isoformat()
        return today == reminder_date and rule.last_reminder_period != reminder_key and rule.enabled

    def build_reminder_text(self, rule: RecurringRule) -> str:
        return (
            "🔔 Lembrete de recorrência\n\n"
            f"Em breve vence este lançamento recorrente:\n"
            f"• {rule.description}\n"
            f"• Valor: R$ {rule.amount:.2f}".replace(".", ",")
            + f"\n• Frequência: {self.describe_schedule(rule)}\n\n"
            "Se quiser, você já pode se planejar com base nisso."
        )

    def nudge_due(self, user: User, now: datetime) -> bool:
        if not user.daily_nudge_enabled:
            return False
        if user.last_nudge_sent_on == now.date():
            return False
        return now.hour == user.nudge_hour and now.minute >= user.nudge_minute

    def build_nudge_text(self) -> str:
        return (
            "🦎 Passando para te lembrar de usar o ChamaLeon hoje.\n\n"
            "Se rolou algum gasto, entrada ou ajuste no seu mês, me manda por aqui.\n\n"
            "Exemplos:\n"
            "• gastei 28 no almoço\n"
            "• recebi 500 de freelance\n"
            "• quanto ainda posso gastar esse mês?"
        )

    def describe_schedule(self, rule: RecurringRule) -> str:
        if rule.frequency == "weekly":
            return f"toda {WEEKDAY_LABELS.get(rule.weekday or 0, 'semana')}"
        if rule.frequency == "biweekly":
            return f"a cada 2 semanas na {WEEKDAY_LABELS.get(rule.weekday or 0, 'semana')}"
        day = rule.day_of_month or 1
        return f"todo dia {day:02d}"

    def next_schedule_start(self, frequency: str, weekday: int | None, today: date | None = None) -> date | None:
        if frequency not in {"weekly", "biweekly"} or weekday is None:
            return None
        reference = today or date.today()
        delta = (weekday - reference.weekday()) % 7
        return reference + timedelta(days=delta)

    def _next_occurrence_on_or_after(self, rule: RecurringRule, reference: date) -> date | None:
        if rule.frequency == "weekly":
            weekday = rule.weekday if rule.weekday is not None else 0
            delta = (weekday - reference.weekday()) % 7
            return reference + timedelta(days=delta)

        if rule.frequency == "biweekly":
            weekday = rule.weekday if rule.weekday is not None else 0
            anchor = rule.start_date or self.next_schedule_start("biweekly", weekday, reference)
            if anchor is None:
                return None
            aligned_anchor = anchor + timedelta(days=(weekday - anchor.weekday()) % 7)
            if reference <= aligned_anchor:
                return aligned_anchor
            days_since = (reference - aligned_anchor).days
            step_count = days_since // 14
            candidate = aligned_anchor + timedelta(days=step_count * 14)
            if candidate < reference:
                candidate += timedelta(days=14)
            return candidate

        last_day = monthrange(reference.year, reference.month)[1]
        due_day = min(rule.day_of_month or 1, last_day)
        return date(reference.year, reference.month, due_day)
