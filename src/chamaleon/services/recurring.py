from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime

from chamaleon.infra.models import RecurringRule, User


class RecurringService:
    def reminder_due(self, rule: RecurringRule, today: date) -> bool:
        last_day = monthrange(today.year, today.month)[1]
        due_day = min(rule.day_of_month, last_day)
        reminder_day = max(1, due_day - rule.reminder_days_before)
        period_label = today.strftime("%Y-%m")
        return (
            today.day == reminder_day
            and rule.last_reminder_period != period_label
            and rule.enabled
        )

    def build_reminder_text(self, rule: RecurringRule) -> str:
        return (
            "🔔 Lembrete de recorrência\n\n"
            f"Em breve vence este lançamento recorrente:\n"
            f"• {rule.description}\n"
            f"• Valor: R$ {rule.amount:.2f}".replace(".", ",")
            + f"\n• Dia previsto: {rule.day_of_month:02d}\n\n"
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
