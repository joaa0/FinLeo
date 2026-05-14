from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import datetime
from decimal import Decimal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from chamaleon.config import Settings
from chamaleon.domain.types import TransactionDraft
from chamaleon.infra.ai import ReportAIClient
from chamaleon.infra.audio import AudioTranscriptionClient, AudioTranscriptionError
from chamaleon.infra.db import Database
from chamaleon.infra.email import EmailClient, EmailDeliveryError
from chamaleon.infra.logging import configure_logging
from chamaleon.repos.reports import ReportRepository
from chamaleon.repos.recurring import RecurringRuleRepository
from chamaleon.repos.transactions import TransactionRepository
from chamaleon.repos.users import UserRepository
from chamaleon.services.finance import FinanceService
from chamaleon.services.parser import detect_category, detect_intent, normalize_amount, parse_transaction_text
from chamaleon.services.recurring import RecurringService
from chamaleon.services.reports import ReportService


logger = logging.getLogger(__name__)

STATE_AWAITING_EMAIL = "awaiting_email"
STATE_AWAITING_ONBOARDING_SALARY = "awaiting_onboarding_salary"
STATE_AWAITING_SALARY_UPDATE = "awaiting_salary_update"
STATE_AWAITING_TRANSACTION = "awaiting_transaction"
STATE_AWAITING_TRANSACTION_CONFIRM = "awaiting_transaction_confirm"
STATE_AWAITING_EDIT_LAST_AMOUNT = "awaiting_edit_last_amount"
STATE_AWAITING_RECURRING_DESCRIPTION = "awaiting_recurring_description"
STATE_AWAITING_RECURRING_AMOUNT = "awaiting_recurring_amount"
STATE_AWAITING_RECURRING_DAY = "awaiting_recurring_day"
STATE_AWAITING_RECURRING_EDIT_DESCRIPTION = "awaiting_recurring_edit_description"
STATE_AWAITING_RECURRING_EDIT_AMOUNT = "awaiting_recurring_edit_amount"
STATE_AWAITING_RECURRING_EDIT_DAY = "awaiting_recurring_edit_day"


class BotRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings)
        self.users = UserRepository(
            nudge_start_hour=settings.daily_nudge_start_hour,
            nudge_end_hour=settings.daily_nudge_end_hour,
        )
        self.transactions = TransactionRepository()
        self.reports = ReportRepository()
        self.recurring_rules = RecurringRuleRepository()
        self.finance = FinanceService(self.transactions)
        self.recurring = RecurringService()
        self.audio = AudioTranscriptionClient(settings)
        self.report_service = ReportService(
            settings=settings,
            finance_service=self.finance,
            report_repository=self.reports,
            ai_client=ReportAIClient(settings),
            email_client=EmailClient(settings),
        )

    def get_user(self, session, update: Update):
        return self.users.get_by_telegram_id(session, str(update.effective_user.id))


def _menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⚡ Novo registro", callback_data="menu:new")],
            [InlineKeyboardButton("📜 Histórico", callback_data="menu:history")],
            [InlineKeyboardButton("💰 Meu dinheiro", callback_data="menu:summary")],
            [InlineKeyboardButton("📩 Relatório", callback_data="menu:report")],
            [InlineKeyboardButton("🔁 Recorrências", callback_data="menu:recurring")],
            [InlineKeyboardButton("✏️ Corrigir último", callback_data="menu:edit_last")],
            [InlineKeyboardButton("🗑️ Excluir transação", callback_data="menu:delete")],
        ]
    )


def _format_amount(amount: Decimal) -> str:
    return f"R$ {amount:.2f}".replace(".", ",")


def _format_date_br(value) -> str:
    return value.strftime("%d/%m/%Y")


def _type_emoji(transaction_type: str) -> str:
    return "🟢" if transaction_type == "income" else "🔴"


def _category_emoji(category: str) -> str:
    return {
        "Alimentacao": "🍽️",
        "Compras": "🛍️",
        "Transporte": "🚕",
        "Moradia": "🏠",
        "Entretenimento": "🎬",
        "Saude": "💊",
        "Educacao": "📚",
        "Trabalho": "💼",
        "Outros": "📌",
    }.get(category, "📌")


def _format_transaction_card(transaction) -> str:
    return (
        f"{_type_emoji(transaction.transaction_type)} {transaction.description}\n"
        f"   {_format_date_br(transaction.transaction_date)} • {_category_emoji(transaction.category)} {transaction.category}\n"
        f"   ID {transaction.id} • {_format_amount(transaction.amount)}"
    )


def _format_recurring_card(rule) -> str:
    tx_type = "Receita" if rule.transaction_type == "income" else "Gasto"
    status = "Ativa" if rule.enabled else "Pausada"
    return (
        f"{_category_emoji(rule.category)} {rule.description}\n"
        f"   Todo dia {rule.day_of_month:02d} • {tx_type} • {status}\n"
        f"   {_format_amount(rule.amount)} • lembrete {rule.reminder_days_before} dia antes"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            context.user_data["state"] = STATE_AWAITING_EMAIL
            await update.message.reply_text(
                "🦎 Oi, eu sou o ChamaLeon.\n\n"
                "Vou te ajudar a cuidar do seu dinheiro com mais clareza, sem complicar o processo.\n\n"
                "📧 Para começar com segurança, me envie seu melhor e-mail."
            )
            return
    await update.message.reply_text(
        "✅ Tudo certo por aqui.\n\n"
        "Pode contar comigo para registrar movimentações, acompanhar seu mês e organizar melhor sua rotina financeira.\n\n"
        "Exemplos:\n"
        "• gastei 39 no ifood\n"
        "• recebi 1200 de freelance\n"
        "• quanto ainda posso gastar esse mês?",
        reply_markup=_menu_markup(),
    )


async def command_registro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        raw_text = " ".join(context.args)
        await _handle_transaction_candidate(update, context, raw_text)
        return
    context.user_data["state"] = STATE_AWAITING_TRANSACTION
    await update.message.reply_text(
        "✍️ Me diga a movimentação do seu jeito.\n\n"
        "Pode escrever de forma natural. Eu organizo para você.\n\n"
        "Exemplos rápidos:\n"
        "• gastei 39 no ifood\n"
        "• recebi 1200 de freelance\n"
        "• paguei 90 na farmácia"
    )


async def command_historico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _show_history(update, context, as_edit=False)


async def command_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _show_summary(update, context, as_edit=False)


async def command_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_report(update, context, as_edit=False)


async def command_recurring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _show_recurring_menu(update, context, as_edit=False)


async def _prompt_edit_last_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE, as_edit: bool = True) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            message = "⚠️ Antes de editar qualquer lançamento, preciso que você comece com /start."
            if as_edit:
                await update.callback_query.edit_message_text(message)
            else:
                await update.effective_message.reply_text(message)
            return
        transaction = runtime.transactions.get_latest_for_user(session, user)

    if transaction is None:
        message = "📭 Ainda não encontrei nenhuma transação para corrigir."
        if as_edit:
            await update.callback_query.edit_message_text(message, reply_markup=_menu_markup())
        else:
            await update.effective_message.reply_text(message, reply_markup=_menu_markup())
        return

    context.user_data["state"] = STATE_AWAITING_EDIT_LAST_AMOUNT
    message = (
        "✏️ Vamos corrigir o seu último lançamento.\n\n"
        f"{_format_transaction_card(transaction)}\n\n"
        "Me envie apenas o novo valor.\n"
        "Exemplos:\n"
        "• 52\n"
        "• 52,90"
    )
    if as_edit:
        await update.callback_query.edit_message_text(message)
    else:
        await update.effective_message.reply_text(message)


async def _undo_last_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE, as_edit: bool = False) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            message = "⚠️ Antes de desfazer qualquer lançamento, preciso que você comece com /start."
            if as_edit:
                await update.callback_query.edit_message_text(message)
            else:
                await update.effective_message.reply_text(message)
            return
        transaction = runtime.transactions.get_latest_for_user(session, user)
        if transaction is None:
            message = "📭 Ainda não há nenhuma transação para desfazer."
            if as_edit:
                await update.callback_query.edit_message_text(message, reply_markup=_menu_markup())
            else:
                await update.effective_message.reply_text(message, reply_markup=_menu_markup())
            return
        deleted = runtime.transactions.delete_for_user(session, user, transaction.id)

    message = (
        "↩️ Último lançamento desfeito com sucesso.\n\n"
        f"{_format_transaction_card(transaction)}"
        if deleted
        else "⚠️ Não consegui desfazer o último lançamento."
    )
    if as_edit:
        await update.callback_query.edit_message_text(message, reply_markup=_menu_markup())
    else:
        await update.effective_message.reply_text(message, reply_markup=_menu_markup())


async def _update_last_transaction_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, amount_text: str) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    amount = normalize_amount(amount_text)
    if amount is None or amount < 0:
        await update.effective_message.reply_text("⚠️ Não consegui entender esse valor. Envie apenas o novo valor da transação.")
        return

    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            await update.effective_message.reply_text("⚠️ Antes de editar qualquer lançamento, preciso que você comece com /start.")
            return
        transaction = runtime.transactions.get_latest_for_user(session, user)
        if transaction is None:
            await update.effective_message.reply_text("📭 Ainda não encontrei nenhuma transação para corrigir.", reply_markup=_menu_markup())
            return
        updated = runtime.transactions.update_amount_for_user(session, user, transaction.id, amount)

    context.user_data.pop("state", None)
    if updated is None:
        await update.effective_message.reply_text("⚠️ Não consegui atualizar o último lançamento.", reply_markup=_menu_markup())
        return

    await update.effective_message.reply_text(
        "✅ Pronto, corrigi o valor do seu último lançamento.\n\n"
        f"{_format_transaction_card(updated)}",
        reply_markup=_menu_markup(),
    )


async def _show_recurring_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, as_edit: bool = True) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            message = "Use /start para concluir seu cadastro primeiro."
            if as_edit:
                await update.callback_query.edit_message_text(message)
            else:
                await update.effective_message.reply_text(message)
            return
        rules = runtime.recurring_rules.list_for_user(session, user)

    if not rules:
        message = (
            "🔁 Você ainda não cadastrou recorrências.\n\n"
            "Use isso para contas fixas, assinaturas ou entradas que se repetem todo mês.\n\n"
            "Exemplos:\n"
            "• aluguel\n"
            "• netflix\n"
            "• salário"
        )
    else:
        lines = ["🔁 Suas recorrências ativas", ""]
        rows = []
        for rule in rules[:6]:
            lines.append(_format_recurring_card(rule))
            lines.append("")
            rows.append([InlineKeyboardButton(f"⚙️ {rule.description[:40]}", callback_data=f"recurring:open:{rule.id}")])
        message = "\n".join(lines).strip()
    if not rules:
        rows = []

    rows.append([InlineKeyboardButton("➕ Nova recorrência", callback_data="recurring:new")])
    rows.append([InlineKeyboardButton("🏠 Menu", callback_data="menu:home")])
    markup = InlineKeyboardMarkup(rows)
    if as_edit:
        await update.callback_query.edit_message_text(message, reply_markup=markup)
    else:
        await update.effective_message.reply_text(message, reply_markup=markup)


async def _show_recurring_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, rule_id: int, as_edit: bool = True) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            message = "Use /start para concluir seu cadastro primeiro."
            if as_edit:
                await update.callback_query.edit_message_text(message)
            else:
                await update.effective_message.reply_text(message)
            return
        rule = runtime.recurring_rules.get_by_id_for_user(session, user, rule_id)

    if rule is None:
        message = "⚠️ Não encontrei essa recorrência no seu cadastro."
        if as_edit:
            await update.callback_query.edit_message_text(message, reply_markup=_menu_markup())
        else:
            await update.effective_message.reply_text(message, reply_markup=_menu_markup())
        return

    toggle_label = "⏸️ Pausar" if rule.enabled else "▶️ Reativar"
    message = (
        "🔁 Gerenciar recorrência\n\n"
        f"{_format_recurring_card(rule)}\n\n"
        "Escolha o que você quer ajustar:"
    )
    markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ Nome", callback_data=f"recurring:edit:description:{rule.id}")],
            [InlineKeyboardButton("💸 Valor", callback_data=f"recurring:edit:amount:{rule.id}")],
            [InlineKeyboardButton("📅 Dia", callback_data=f"recurring:edit:day:{rule.id}")],
            [InlineKeyboardButton(toggle_label, callback_data=f"recurring:toggle:{rule.id}")],
            [InlineKeyboardButton("🗑️ Excluir", callback_data=f"recurring:delete:{rule.id}")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="menu:recurring")],
        ]
    )
    if as_edit:
        await update.callback_query.edit_message_text(message, reply_markup=markup)
    else:
        await update.effective_message.reply_text(message, reply_markup=markup)


async def _prompt_recurring_description(update: Update, context: ContextTypes.DEFAULT_TYPE, as_edit: bool = True) -> None:
    context.user_data["state"] = STATE_AWAITING_RECURRING_DESCRIPTION
    context.user_data.pop("recurring_draft", None)
    message = (
        "🔁 Vamos cadastrar uma recorrência.\n\n"
        "Me diga o nome dela do jeito que faz sentido para você.\n\n"
        "Exemplos:\n"
        "• aluguel\n"
        "• netflix\n"
        "• salário"
    )
    if as_edit:
        await update.callback_query.edit_message_text(message)
    else:
        await update.effective_message.reply_text(message)


async def _save_recurring_rule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    recurring_data = context.user_data.get("recurring_draft") or {}
    description = str(recurring_data.get("description") or "").strip()
    amount = recurring_data.get("amount")
    day_of_month = recurring_data.get("day_of_month")

    if not description or amount is None or day_of_month is None:
        context.user_data.pop("state", None)
        context.user_data.pop("recurring_draft", None)
        await update.effective_message.reply_text(
            "⚠️ Perdi o contexto dessa recorrência. Vamos começar de novo quando você quiser.",
            reply_markup=_menu_markup(),
        )
        return

    category, transaction_type = detect_category(description)
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            await update.effective_message.reply_text("⚠️ Antes de cadastrar recorrências, preciso que você comece com /start.")
            return
        rule = runtime.recurring_rules.create(
            session=session,
            user=user,
            description=description[:120],
            category=category,
            transaction_type=transaction_type,
            amount=amount,
            day_of_month=day_of_month,
            reminder_days_before=1,
        )

    context.user_data.pop("state", None)
    context.user_data.pop("recurring_draft", None)
    await update.effective_message.reply_text(
        "✅ Recorrência salva.\n\n"
        f"{_format_recurring_card(rule)}\n\n"
        "Vou te lembrar perto da data para você não perder o controle.",
        reply_markup=_menu_markup(),
    )


async def _prompt_recurring_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, rule_id: int, field: str) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            await update.callback_query.edit_message_text("Use /start para concluir seu cadastro primeiro.")
            return
        rule = runtime.recurring_rules.get_by_id_for_user(session, user, rule_id)

    if rule is None:
        await update.callback_query.edit_message_text("⚠️ Não encontrei essa recorrência.", reply_markup=_menu_markup())
        return

    context.user_data["editing_recurring_id"] = rule_id
    if field == "description":
        context.user_data["state"] = STATE_AWAITING_RECURRING_EDIT_DESCRIPTION
        message = (
            "✏️ Me mande o novo nome dessa recorrência.\n\n"
            f"Atual: {rule.description}"
        )
    elif field == "amount":
        context.user_data["state"] = STATE_AWAITING_RECURRING_EDIT_AMOUNT
        message = (
            "💸 Me mande o novo valor dessa recorrência.\n\n"
            f"Atual: {_format_amount(rule.amount)}"
        )
    else:
        context.user_data["state"] = STATE_AWAITING_RECURRING_EDIT_DAY
        message = (
            "📅 Me mande o novo dia do mês dessa recorrência.\n\n"
            f"Atual: {rule.day_of_month:02d}"
        )
    await update.callback_query.edit_message_text(message)


async def _toggle_recurring_rule(update: Update, context: ContextTypes.DEFAULT_TYPE, rule_id: int) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            await update.callback_query.edit_message_text("Use /start para concluir seu cadastro primeiro.")
            return
        rule = runtime.recurring_rules.get_by_id_for_user(session, user, rule_id)
        if rule is None:
            await update.callback_query.edit_message_text("⚠️ Não encontrei essa recorrência.", reply_markup=_menu_markup())
            return
        updated = runtime.recurring_rules.set_enabled_for_user(session, user, rule_id, not rule.enabled)

    if updated is None:
        await update.callback_query.edit_message_text("⚠️ Não consegui atualizar essa recorrência.", reply_markup=_menu_markup())
        return
    action = "reativada" if updated.enabled else "pausada"
    await update.callback_query.edit_message_text(
        f"✅ Recorrência {action}.\n\n{_format_recurring_card(updated)}",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅️ Voltar para recorrências", callback_data="menu:recurring")],
                [InlineKeyboardButton("🏠 Menu", callback_data="menu:home")],
            ]
        ),
    )


async def _delete_recurring_rule(update: Update, context: ContextTypes.DEFAULT_TYPE, rule_id: int) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            await update.callback_query.edit_message_text("Use /start para concluir seu cadastro primeiro.")
            return
        rule = runtime.recurring_rules.get_by_id_for_user(session, user, rule_id)
        if rule is None:
            await update.callback_query.edit_message_text("⚠️ Não encontrei essa recorrência.", reply_markup=_menu_markup())
            return
        summary = _format_recurring_card(rule)
        deleted = runtime.recurring_rules.delete_for_user(session, user, rule_id)

    message = (
        f"🗑️ Recorrência excluída com sucesso.\n\n{summary}"
        if deleted
        else "⚠️ Não consegui excluir essa recorrência."
    )
    await update.callback_query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅️ Voltar para recorrências", callback_data="menu:recurring")],
                [InlineKeyboardButton("🏠 Menu", callback_data="menu:home")],
            ]
        ),
    )


async def _apply_recurring_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, field: str, value: str) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    rule_id = context.user_data.get("editing_recurring_id")
    if rule_id is None:
        context.user_data.pop("state", None)
        await update.effective_message.reply_text(
            "⚠️ Perdi o contexto dessa edição. Abra a recorrência de novo e tente mais uma vez.",
            reply_markup=_menu_markup(),
        )
        return

    update_kwargs: dict[str, object] = {}
    if field == "description":
        description = value.strip()
        if len(description) < 2:
            await update.effective_message.reply_text("⚠️ Me mande um nome um pouco mais claro para essa recorrência.")
            return
        category, transaction_type = detect_category(description)
        update_kwargs = {
            "description": description[:120],
            "category": category,
            "transaction_type": transaction_type,
        }
    elif field == "amount":
        amount = normalize_amount(value)
        if amount is None or amount < 0:
            await update.effective_message.reply_text("⚠️ Não consegui entender esse valor. Me envie apenas o novo valor.")
            return
        update_kwargs = {"amount": amount}
    else:
        try:
            day_of_month = int(value)
        except ValueError:
            await update.effective_message.reply_text("⚠️ Me envie apenas um número entre 1 e 31.")
            return
        if not 1 <= day_of_month <= 31:
            await update.effective_message.reply_text("⚠️ O dia precisa estar entre 1 e 31.")
            return
        update_kwargs = {"day_of_month": day_of_month}

    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            await update.effective_message.reply_text("⚠️ Antes de editar recorrências, preciso que você comece com /start.")
            return
        rule = runtime.recurring_rules.update_for_user(session, user, int(rule_id), **update_kwargs)

    context.user_data.pop("state", None)
    context.user_data.pop("editing_recurring_id", None)
    if rule is None:
        await update.effective_message.reply_text("⚠️ Não consegui atualizar essa recorrência.", reply_markup=_menu_markup())
        return
    await update.effective_message.reply_text(
        "✅ Recorrência atualizada.\n\n"
        f"{_format_recurring_card(rule)}",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⚙️ Continuar gerenciando", callback_data=f"recurring:open:{rule.id}")],
                [InlineKeyboardButton("🏠 Menu", callback_data="menu:home")],
            ]
        ),
    )


async def _dispatch_scheduled_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    now = datetime.now()
    today = now.date()

    with runtime.db.session() as session:
        rules = runtime.recurring_rules.list_enabled(session)
        for rule in rules:
            if not runtime.recurring.reminder_due(rule, today):
                continue
            user = rule.user
            try:
                await context.bot.send_message(
                    chat_id=int(user.telegram_user_id),
                    text=runtime.recurring.build_reminder_text(rule),
                    reply_markup=_menu_markup(),
                )
            except Exception:
                logger.exception("Falha ao enviar lembrete de recorrencia", extra={"user_id": user.id, "rule_id": rule.id})
                continue
            runtime.recurring_rules.mark_reminder_sent(session, rule, today.strftime("%Y-%m"))

        users = runtime.users.list_all_with_nudges(session)
        for user in users:
            if not runtime.recurring.nudge_due(user, now):
                continue
            try:
                await context.bot.send_message(
                    chat_id=int(user.telegram_user_id),
                    text=runtime.recurring.build_nudge_text(),
                    reply_markup=_menu_markup(),
                )
            except Exception:
                logger.exception("Falha ao enviar lembrete diario", extra={"user_id": user.id})
                continue
            runtime.users.mark_nudge_sent(session, user, today)


async def _handle_audio_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    message = update.effective_message
    voice = getattr(message, "voice", None)
    audio = getattr(message, "audio", None)
    media = voice or audio
    if media is None:
        return

    try:
        tg_file = await context.bot.get_file(media.file_id)
        suffix = ".ogg" if voice else os.path.splitext(getattr(audio, "file_name", "") or "")[1] or ".mp3"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
        try:
            await tg_file.download_to_drive(custom_path=temp_path)
            transcript = await asyncio.to_thread(runtime.audio.transcribe_file, temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except AudioTranscriptionError as exc:
        await message.reply_text(
            f"🎙️ Eu recebi seu áudio, mas não consegui transcrever com segurança.\n\nDetalhe: {exc}"
        )
        return
    except Exception as exc:
        logger.exception("Erro ao processar audio")
        await message.reply_text(
            f"🎙️ Eu recebi seu áudio, mas algo falhou na transcrição.\n\nDetalhe: {exc}"
        )
        return

    await message.reply_text(
        "🎙️ Áudio entendido.\n\n"
        f"Transcrição capturada:\n"
        f"“{transcript}”\n\n"
        "Vou interpretar isso como uma movimentação para você."
    )
    await _handle_transaction_candidate(update, context, transcript)


async def _handle_transaction_candidate(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    draft = parse_transaction_text(text)
    if draft is None:
        await update.effective_message.reply_text(
            "⚠️ Não consegui confirmar essa movimentação com segurança.\n\n"
            "Para eu não registrar nada errado, prefiro que você envie uma movimentação por vez.\n\n"
            "Melhor formato:\n"
            "• gastei 42 no ifood\n\n"
            "Se preferir, você também pode mandar outro áudio mais direto."
        )
        return
    context.user_data["pending_transaction"] = draft
    context.user_data["state"] = STATE_AWAITING_TRANSACTION_CONFIRM
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="tx:confirm"),
                InlineKeyboardButton("↩️ Cancelar", callback_data="tx:cancel"),
            ]
        ]
    )
    await update.effective_message.reply_text(_format_draft_preview(draft), reply_markup=keyboard)


def _format_draft_preview(draft: TransactionDraft) -> str:
    tx_type = "Receita" if draft.transaction_type == "income" else "Gasto"
    details = f"\nObs: {draft.details}" if draft.details else ""
    return (
        "🧾 Revise com calma antes de salvar\n\n"
        f"Descrição: {draft.description}\n"
        f"Valor: {_format_amount(draft.amount)}\n"
        f"Categoria: {_category_emoji(draft.category)} {draft.category}\n"
        f"Tipo: {tx_type}\n"
        f"Data: {_format_date_br(draft.transaction_date)}{details}\n\n"
        "Se estiver tudo certo, confirme abaixo."
    )


async def _confirm_pending_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE, as_edit: bool = True) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    draft: TransactionDraft | None = context.user_data.get("pending_transaction")
    if draft is None:
        if as_edit:
            await update.callback_query.edit_message_text("Nenhuma transacao pendente.")
        else:
            await update.message.reply_text("Nenhuma transacao pendente.")
        return

    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            message = "Finalize o onboarding com /start antes de registrar transacoes."
            if as_edit:
                await update.callback_query.edit_message_text(message)
            else:
                await update.message.reply_text(message)
            return
        transaction = runtime.transactions.create(session, user, draft)

    context.user_data.pop("pending_transaction", None)
    context.user_data.pop("state", None)
    message = (
        "✅ Pronto, movimento salvo.\n\n"
        f"ID: {transaction.id}\n"
        f"Descrição: {draft.description}\n"
        f"Valor: {_format_amount(draft.amount)}"
    )
    if as_edit:
        await update.callback_query.edit_message_text(message, reply_markup=_menu_markup())
    else:
        await update.message.reply_text(message, reply_markup=_menu_markup())


async def _show_history(update: Update, context: ContextTypes.DEFAULT_TYPE, as_edit: bool = True, page: int = 1) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            message = "Use /start para finalizar seu cadastro antes de consultar historico."
            if as_edit:
                await update.callback_query.edit_message_text(message)
            else:
                await update.message.reply_text(message)
            return
        page_size = 5
        total = runtime.transactions.count_for_user(session, user)
        offset = max(page - 1, 0) * page_size
        items = runtime.transactions.list_recent(session, user, limit=page_size, offset=offset)
    total_pages = max((total + 4) // 5, 1)

    if not items:
        message = (
            "📭 Seu histórico ainda está vazio.\n\n"
            "Quando você fizer o primeiro registro, eu começo a organizar tudo por aqui."
        )
    else:
        lines = [f"📜 Histórico • página {page}/{total_pages}", ""]
        for item in items:
            emoji = _type_emoji(item.transaction_type)
            category_emoji = _category_emoji(item.category)
            lines.append(
                f"{emoji} {item.description}"
            )
            lines.append(
                f"   {_format_date_br(item.transaction_date)} • {category_emoji} {item.category}"
            )
            lines.append(
                f"   ID {item.id} • {_format_amount(item.amount)}"
            )
            lines.append("")
        message = "\n".join(lines)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"history:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️ Próxima", callback_data=f"history:{page + 1}"))
    keyboard_rows = [nav] if nav else []
    keyboard_rows.append([InlineKeyboardButton("🏠 Menu", callback_data="menu:home")])
    markup = InlineKeyboardMarkup(keyboard_rows)
    if as_edit:
        await update.callback_query.edit_message_text(message, reply_markup=markup)
    else:
        await update.message.reply_text(message, reply_markup=markup)


async def _show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, as_edit: bool = True) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            message = "Use /start para concluir seu cadastro primeiro."
            if as_edit:
                await update.callback_query.edit_message_text(message)
            else:
                await update.message.reply_text(message)
            return
        summary = runtime.finance.build_monthly_summary(session, user)

    top_categories = "\n".join(
        [f"- {category}: {_format_amount(amount)}" for category, amount in summary.top_categories[:3]]
    ) or "- Sem gastos no periodo"
    monthly_insights = "\n".join([f"• {insight}" for insight in summary.insights]) or "• Ainda não há dados suficientes para gerar leitura do mês."
    message = (
        "💰 Resumo do mês\n\n"
        f"Salário base: {_format_amount(summary.salary)}\n"
        f"Entradas: {_format_amount(summary.income_total)}\n"
        f"Gastos: {_format_amount(summary.expense_total)}\n"
        f"Saldo atual: {_format_amount(summary.balance)}\n\n"
        "📌 Onde seu dinheiro mais está pesando:\n"
        f"{top_categories}\n\n"
        "🧠 Leitura do mês:\n"
        f"{monthly_insights}"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ Atualizar salário", callback_data="menu:set_salary")],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu:home")],
        ]
    )
    if as_edit:
        await update.callback_query.edit_message_text(message, reply_markup=keyboard)
    else:
        await update.message.reply_text(message, reply_markup=keyboard)


async def _prompt_salary(update: Update, context: ContextTypes.DEFAULT_TYPE, onboarding: bool = False, as_edit: bool = True) -> None:
    context.user_data["state"] = STATE_AWAITING_ONBOARDING_SALARY if onboarding else STATE_AWAITING_SALARY_UPDATE
    message = (
        "💵 Qual é o seu salário mensal?\n\n"
        "Me envie apenas o valor, sem texto extra.\n"
        "Exemplos:\n"
        "• 3500\n"
        "• 4500,00"
    )
    if as_edit:
        await update.callback_query.edit_message_text(message)
    else:
        await update.effective_message.reply_text(message)


async def _send_report(update: Update, context: ContextTypes.DEFAULT_TYPE, as_edit: bool = True) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    try:
        with runtime.db.session() as session:
            user = runtime.get_user(session, update)
            if user is None:
                message = "Use /start para concluir seu cadastro primeiro."
                if as_edit:
                    await update.callback_query.edit_message_text(message)
                else:
                    await update.message.reply_text(message)
                return
            runtime.report_service.generate_and_send(session, user)
    except EmailDeliveryError as exc:
        message = f"⚠️ Eu consegui gerar o relatório, mas o envio por e-mail falhou.\n\nDetalhe: {exc}"
    except Exception as exc:
        logger.exception("Erro ao gerar relatorio")
        message = f"❌ Não consegui gerar o relatório agora.\n\nTente novamente em instantes.\n\nDetalhe: {exc}"
    else:
        message = (
            "📩 Relatório pronto.\n\n"
            "Enviei a análise para o e-mail cadastrado.\n"
            "Se ela não aparecer logo, vale checar spam ou promoções."
        )

    if as_edit:
        await update.callback_query.edit_message_text(message, reply_markup=_menu_markup())
    else:
        await update.message.reply_text(message, reply_markup=_menu_markup())


async def _show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, as_edit: bool = True) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        if user is None:
            message = "Use /start para concluir seu cadastro primeiro."
            if as_edit:
                await update.callback_query.edit_message_text(message)
            else:
                await update.message.reply_text(message)
            return
        items = runtime.transactions.list_recent(session, user, limit=5)

    if not items:
        text = "📭 Não há transações para excluir no momento."
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data="menu:home")]])
    else:
        rows = []
        for item in items:
            label = f"{_type_emoji(item.transaction_type)} {item.description} • {_format_amount(item.amount)}"
            rows.append([InlineKeyboardButton(label[:64], callback_data=f"delete:{item.id}")])
        rows.append([InlineKeyboardButton("🏠 Menu", callback_data="menu:home")])
        text = "🗑️ Escolha com cuidado a transação que deseja remover."
        markup = InlineKeyboardMarkup(rows)

    if as_edit:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def _delete_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE, transaction_id: int) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    with runtime.db.session() as session:
        user = runtime.get_user(session, update)
        deleted = False
        if user is not None:
            deleted = runtime.transactions.delete_for_user(session, user, transaction_id)
    message = (
        "🗑️ Transação excluída com sucesso."
        if deleted
        else "⚠️ Não encontrei essa transação vinculada ao seu histórico."
    )
    await update.callback_query.edit_message_text(message, reply_markup=_menu_markup())


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "menu:home":
        await query.edit_message_text("🏠 Menu principal\n\nMe diga para onde você quer ir agora:", reply_markup=_menu_markup())
    elif data == "menu:new":
        context.user_data["state"] = STATE_AWAITING_TRANSACTION
        await query.edit_message_text(
            "⚡ Me mande a movimentação do seu jeito.\n\n"
            "Exemplo:\n"
            "• gastei 39 no ifood\n\n"
            "Se quiser, pode mandar por áudio também."
        )
    elif data == "menu:history":
        await _show_history(update, context, as_edit=True)
    elif data.startswith("history:"):
        await _show_history(update, context, as_edit=True, page=int(data.split(":")[1]))
    elif data == "menu:summary":
        await _show_summary(update, context, as_edit=True)
    elif data == "menu:set_salary":
        await _prompt_salary(update, context, onboarding=False, as_edit=True)
    elif data == "menu:recurring":
        await _show_recurring_menu(update, context, as_edit=True)
    elif data == "recurring:new":
        await _prompt_recurring_description(update, context, as_edit=True)
    elif data.startswith("recurring:open:"):
        await _show_recurring_detail(update, context, int(data.split(":")[2]), as_edit=True)
    elif data.startswith("recurring:edit:"):
        _, _, field, rule_id = data.split(":")
        await _prompt_recurring_edit(update, context, int(rule_id), field)
    elif data.startswith("recurring:toggle:"):
        await _toggle_recurring_rule(update, context, int(data.split(":")[2]))
    elif data.startswith("recurring:delete:"):
        await _delete_recurring_rule(update, context, int(data.split(":")[2]))
    elif data == "menu:edit_last":
        await _prompt_edit_last_transaction(update, context, as_edit=True)
    elif data == "menu:report":
        await _send_report(update, context, as_edit=True)
    elif data == "menu:delete":
        await _show_delete_menu(update, context, as_edit=True)
    elif data.startswith("delete:"):
        await _delete_transaction(update, context, int(data.split(":")[1]))
    elif data == "tx:confirm":
        await _confirm_pending_transaction(update, context, as_edit=True)
    elif data == "tx:cancel":
        context.user_data.pop("pending_transaction", None)
        context.user_data.pop("state", None)
        await query.edit_message_text("↩️ Tudo bem, cancelei por aqui. Quando quiser, é só tentar de novo.", reply_markup=_menu_markup())


async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    runtime: BotRuntime = context.application.bot_data["runtime"]
    text = (update.message.text or "").strip()
    state = context.user_data.get("state")

    if state == STATE_AWAITING_EMAIL:
        context.user_data["onboarding_email"] = text
        await _prompt_salary(update, context, onboarding=True, as_edit=False)
        return

    if state == STATE_AWAITING_EDIT_LAST_AMOUNT:
        await _update_last_transaction_amount(update, context, text)
        return

    if state == STATE_AWAITING_RECURRING_DESCRIPTION:
        description = text.strip()
        if len(description) < 2:
            await update.message.reply_text("⚠️ Me mande um nome um pouco mais claro para essa recorrência.")
            return
        context.user_data["recurring_draft"] = {"description": description}
        context.user_data["state"] = STATE_AWAITING_RECURRING_AMOUNT
        await update.message.reply_text(
            "💸 Qual é o valor dessa recorrência?\n\n"
            "Me envie apenas o valor.\n"
            "Exemplos:\n"
            "• 1200\n"
            "• 39,90"
        )
        return

    if state == STATE_AWAITING_RECURRING_AMOUNT:
        amount = normalize_amount(text)
        if amount is None or amount < 0:
            await update.message.reply_text("⚠️ Não consegui entender esse valor. Me envie apenas o número da recorrência.")
            return
        recurring_data = context.user_data.get("recurring_draft") or {}
        recurring_data["amount"] = amount
        context.user_data["recurring_draft"] = recurring_data
        context.user_data["state"] = STATE_AWAITING_RECURRING_DAY
        await update.message.reply_text(
            "📅 Em qual dia do mês isso costuma acontecer?\n\n"
            "Me envie apenas um número entre 1 e 31.\n"
            "Exemplos:\n"
            "• 5\n"
            "• 10\n"
            "• 28"
        )
        return

    if state == STATE_AWAITING_RECURRING_DAY:
        try:
            day_of_month = int(text)
        except ValueError:
            await update.message.reply_text("⚠️ Me envie apenas o dia do mês, com um número entre 1 e 31.")
            return
        if not 1 <= day_of_month <= 31:
            await update.message.reply_text("⚠️ O dia precisa estar entre 1 e 31.")
            return
        recurring_data = context.user_data.get("recurring_draft") or {}
        recurring_data["day_of_month"] = day_of_month
        context.user_data["recurring_draft"] = recurring_data
        await _save_recurring_rule(update, context)
        return

    if state == STATE_AWAITING_RECURRING_EDIT_DESCRIPTION:
        await _apply_recurring_edit(update, context, "description", text)
        return

    if state == STATE_AWAITING_RECURRING_EDIT_AMOUNT:
        await _apply_recurring_edit(update, context, "amount", text)
        return

    if state == STATE_AWAITING_RECURRING_EDIT_DAY:
        await _apply_recurring_edit(update, context, "day", text)
        return

    if state == STATE_AWAITING_ONBOARDING_SALARY:
        salary = normalize_amount(text)
        if salary is None or salary < 0:
            await update.message.reply_text("⚠️ Não consegui entender esse valor. Me envie apenas o número do salário, como 3500 ou 4500,00.")
            return
        email = context.user_data.get("onboarding_email", "")
        with runtime.db.session() as session:
            runtime.users.create_or_update(session, str(update.effective_user.id), email, salary)
        context.user_data.clear()
        await update.message.reply_text(
            "🎉 Cadastro concluído.\n\n"
            "Agora eu já consigo te ajudar a registrar gastos, receitas e acompanhar seu mês com mais clareza.\n\n"
            "Se quiser, você pode registrar por texto ou por áudio.",
            reply_markup=_menu_markup(),
        )
        return

    if state == STATE_AWAITING_SALARY_UPDATE:
        salary = normalize_amount(text)
        if salary is None or salary < 0:
            await update.message.reply_text("⚠️ Não consegui entender esse valor. Envie apenas o número do salário.")
            return
        with runtime.db.session() as session:
            user = runtime.get_user(session, update)
            if user is None:
                await update.message.reply_text("⚠️ Antes de atualizar o salário, preciso que você inicie seu cadastro com /start.")
                return
            runtime.users.update_salary(session, user.telegram_user_id, salary)
        context.user_data.pop("state", None)
        await update.message.reply_text("✅ Salário atualizado com sucesso. Já considerei esse valor no seu acompanhamento.", reply_markup=_menu_markup())
        return

    if state == STATE_AWAITING_TRANSACTION:
        await _handle_transaction_candidate(update, context, text)
        return

    if state == STATE_AWAITING_TRANSACTION_CONFIRM:
        if text.lower() in {"sim", "confirmar", "ok"}:
            await _confirm_pending_transaction(update, context, as_edit=False)
            return
        if text.lower() in {"nao", "não", "cancelar"}:
            context.user_data.pop("pending_transaction", None)
            context.user_data.pop("state", None)
            await update.message.reply_text("↩️ Tudo certo, cancelei essa movimentação. Pode me mandar outra quando quiser.", reply_markup=_menu_markup())
            return

    with runtime.db.session() as session:
        user = runtime.get_user(session, update)

    if user is None:
        await update.message.reply_text("👋 Para eu cuidar direitinho do seu histórico, preciso que você comece com /start.")
        return

    intent = detect_intent(text)
    if intent.intent == "register_transaction" and intent.draft is not None:
        await _handle_transaction_candidate(update, context, text)
    elif intent.intent == "show_history":
        await _show_history(update, context, as_edit=False)
    elif intent.intent == "show_summary":
        await _show_summary(update, context, as_edit=False)
    elif intent.intent == "undo_last_transaction":
        await _undo_last_transaction(update, context, as_edit=False)
    elif intent.intent == "edit_last_transaction_amount":
        amount = intent.entities.get("amount")
        if amount:
            await _update_last_transaction_amount(update, context, amount)
        else:
            await _prompt_edit_last_transaction(update, context, as_edit=False)
    elif intent.intent == "update_salary":
        amount = intent.entities.get("amount")
        if amount:
            with runtime.db.session() as session:
                runtime.users.update_salary(session, str(update.effective_user.id), Decimal(amount))
            await update.message.reply_text("✅ Salário atualizado com sucesso. Já vou considerar esse novo valor no seu resumo.", reply_markup=_menu_markup())
        else:
            context.user_data["state"] = STATE_AWAITING_SALARY_UPDATE
            await update.message.reply_text("💵 Me diga o novo salário mensal e eu atualizo para você.")
    elif intent.intent == "manage_recurring":
        await _show_recurring_menu(update, context, as_edit=False)
    elif intent.intent == "request_report":
        await _send_report(update, context, as_edit=False)
    else:
        await update.message.reply_text(
            "🦎 Estou aqui para te ajudar a registrar, entender e organizar melhor sua vida financeira.\n\n"
            "Você pode tentar:\n"
            "• gastei 32 no uber\n"
            "• me mostra minhas transações\n"
            "• quanto ainda posso gastar esse mês?\n"
            "• quero ver minhas recorrências\n"
            "• corrige o valor para 52\n"
            "• desfaz o último lançamento\n\n"
            "Também aceito áudio, se você preferir falar em vez de digitar.",
            reply_markup=_menu_markup(),
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Erro ao processar update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("❌ Tive um problema interno por aqui. Tente novamente em instantes.")


def build_application() -> Application:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    runtime = BotRuntime(settings)
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["runtime"] = runtime
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("registro", command_registro))
    app.add_handler(CommandHandler("historico", command_historico))
    app.add_handler(CommandHandler("salario", command_summary))
    app.add_handler(CommandHandler("dinheiro", command_summary))
    app.add_handler(CommandHandler("relatorio", command_report))
    app.add_handler(CommandHandler("recorrencias", command_recurring))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, _handle_audio_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages))
    app.add_error_handler(error_handler)
    if app.job_queue is not None:
        app.job_queue.run_repeating(
            _dispatch_scheduled_reminders,
            interval=settings.reminder_check_interval_minutes * 60,
            first=10,
            name="scheduled-reminders",
        )
    return app


def main() -> None:
    application = build_application()
    logger.info("Iniciando ChamaLeon em polling")
    application.run_polling()
