"""
FinBot Telegram — Assistente Financeiro com IA
Suporta: CREATE (novo gasto) + READ (histórico) + SALÁRIO (registrar/consultar)
Google Sheets integrado para persistência de dados
Zap 1: CRUD de transações | Zap 2: atualização de salário
"""

import os
import requests
import logging
import json
from datetime import datetime
from typing import List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

# Google Sheets
try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("⚠️ Instale gspread: pip install gspread")

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_TOKEN         = os.getenv("TELEGRAM_BOT_TOKEN")
ZAPIER_WEBHOOK_EXPENSE = os.getenv("ZAPIER_WEBHOOK_EXPENSE")   # Zap 1 — CRUD
ZAPIER_WEBHOOK_SALARY  = os.getenv("ZAPIER_WEBHOOK_SALARY")    # Zap 2 — salário
CREDENTIALS_PATH       = os.getenv("GOOGLE_CREDENTIALS_PATH", "")
SHEET_ID               = os.getenv("GOOGLE_SHEET_ID", "")
SHEET_NAME             = os.getenv("SHEET_NAME", "transactions")
SHEET_USERS            = os.getenv("USERS_SHEET_NAME", "users")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados da conversa
MENU, AWAITING_EXPENSE, SELECTING_CATEGORY, CONFIRMING, AWAITING_SALARY = range(5)

# Mapeamento inteligente de categorias
CATEGORY_MAP = {
    "ifood":         "Alimentação",
    "uber eats":     "Alimentação",
    "rappi":         "Alimentação",
    "pizza":         "Alimentação",
    "restaurante":   "Alimentação",
    "lanche":        "Alimentação",
    "café":          "Alimentação",
    "uber":          "Transporte",
    "99":            "Transporte",
    "taxi":          "Transporte",
    "passagem":      "Transporte",
    "combustível":   "Transporte",
    "gasolina":      "Transporte",
    "netflix":       "Entretenimento",
    "spotify":       "Entretenimento",
    "cinema":        "Entretenimento",
    "jogo":          "Entretenimento",
    "farmácia":      "Saúde",
    "médico":        "Saúde",
    "dentista":      "Saúde",
    "vitamina":      "Saúde",
    "curso":         "Educação",
    "livro":         "Educação",
    "escola":        "Educação",
    "mercado":       "Compras",
    "supermercado":  "Compras",
    "roupa":         "Compras",
    "eletrônico":    "Compras",
}

CATEGORIES = [
    "Alimentação", "Transporte", "Entretenimento",
    "Saúde", "Educação", "Moradia", "Compras", "Outros"
]


# ============================================================================
# GOOGLE SHEETS INTEGRATION
# ============================================================================

class GoogleSheetsClient:
    """Cliente para interagir com Google Sheets"""

    def __init__(self, credentials_path: str, sheet_id: str):
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        self._connect()

    def _connect(self):
        """Conecta ao Google Sheets — suporta JSON string (Railway) ou arquivo local"""
        try:
            scopes = ['https://www.googleapis.com/auth/spreadsheets']

            credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if credentials_json:
                logger.info("🔑 Usando credenciais via GOOGLE_CREDENTIALS_JSON")
                try:
                    credentials_dict = json.loads(credentials_json)
                except json.JSONDecodeError as e:
                    raise ValueError(f"GOOGLE_CREDENTIALS_JSON inválido: {e}")
                credentials = Credentials.from_service_account_info(
                    credentials_dict, scopes=scopes
                )

            elif self.credentials_path:
                logger.info(f"🔑 Usando credenciais via arquivo: {self.credentials_path}")
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Arquivo não encontrado: {self.credentials_path}\n"
                        "Configure GOOGLE_CREDENTIALS_JSON ou verifique o path."
                    )
                credentials = Credentials.from_service_account_file(
                    self.credentials_path, scopes=scopes
                )

            else:
                raise ValueError(
                    "Nenhuma credencial configurada.\n"
                    "Defina GOOGLE_CREDENTIALS_JSON ou GOOGLE_CREDENTIALS_PATH no .env"
                )

            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.sheet_id)
            self.worksheet = self.spreadsheet.worksheet(SHEET_NAME)
            logger.info("✅ Conectado ao Google Sheets")

        except Exception as e:
            logger.error(f"❌ Erro ao conectar Google Sheets: {str(e)}")
            raise

    def get_user_transactions(self, user_id: str) -> List[dict]:
        """Busca todas as transações de um usuário"""
        try:
            all_rows = self.worksheet.get_all_records()
            user_transactions = [
                row for row in all_rows
                if str(row.get('user_id', '')).strip() == str(user_id).strip()
            ]
            logger.info(f"📊 {len(user_transactions)} transações para user_id={user_id}")
            return user_transactions
        except Exception as e:
            logger.error(f"❌ Erro ao buscar transações: {str(e)}")
            return []

    def get_user_salary(self, user_id: str) -> float:
        """
        Busca o salário do usuário na aba 'users'.
        Estrutura: user_id | email | registered_date | salary | updated_at
        Retorna 0.0 se não encontrado.
        """
        try:
            worksheet = self.spreadsheet.worksheet(SHEET_USERS)
            cell = worksheet.find(str(user_id), in_column=1)
            if cell:
                value = worksheet.cell(cell.row, 4).value  # col D = salary
                return float(str(value).replace(",", ".")) if value else 0.0
            return 0.0
        except Exception as e:
            logger.error(f"❌ Erro ao buscar salário: {str(e)}")
            return 0.0

    def get_monthly_expenses(self, user_id: str) -> float:
        """Soma despesas do mês atual do usuário na aba 'transactions'."""
        mes_atual = datetime.now().strftime("%Y-%m")
        total = 0.0
        try:
            all_rows = self.worksheet.get_all_records()
            for row in all_rows:
                row_user   = str(row.get('user_id', '')).strip()
                row_type   = str(row.get('type', '')).lower().strip()
                row_date   = str(row.get('date', ''))
                row_amount = row.get('amount', 0)

                if (row_user == str(user_id)
                        and row_type == 'expense'
                        and row_date.startswith(mes_atual)):
                    try:
                        total += float(str(row_amount).replace(',', '.'))
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            logger.error(f"❌ Erro ao calcular despesas mensais: {str(e)}")
        return total


# Inicializar cliente Google Sheets (global)
try:
    gs_client = GoogleSheetsClient(CREDENTIALS_PATH, SHEET_ID)
except Exception as e:
    logger.warning(f"⚠️ Google Sheets não disponível: {str(e)}")
    gs_client = None


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def detect_category(text: str) -> str:
    """Detecta categoria por keyword matching"""
    text_lower = text.lower()
    for keyword, category in CATEGORY_MAP.items():
        if keyword in text_lower:
            return category
    return "Outros"


def parse_quick_expense(text: str) -> tuple:
    """Parse do formato: /gasto descrição valor"""
    try:
        parts = text.split()
        if len(parts) < 3:
            return None, None, "Formato inválido"
        description = parts[1]
        try:
            amount = float(parts[2])
        except ValueError:
            return None, None, "Valor deve ser um número"
        return description, amount, None
    except Exception as e:
        return None, None, str(e)


def format_transactions(transactions: List[dict], page: int = 1, items_per_page: int = 5) -> Tuple[str, int]:
    """Formata transações para exibição no Telegram.
    Retorna: (texto_formatado, total_de_paginas)
    """
    if not transactions:
        return "📭 Nenhuma transação encontrada.\n\nComece a registrar seus gastos!", 1

    total_pages = (len(transactions) + items_per_page - 1) // items_per_page
    start_idx = (page - 1) * items_per_page
    page_transactions = transactions[start_idx:start_idx + items_per_page]

    header  = f"📊 *Suas Transações* (página {page}/{total_pages})\n"
    header += f"Total: {len(transactions)} registros\n"
    header += "─" * 40 + "\n\n"

    body = ""
    for trans in page_transactions:
        date        = trans.get('date', 'N/A')
        description = trans.get('description', 'N/A')
        category    = trans.get('category', 'N/A')
        amount      = trans.get('amount', '0')
        trans_type  = trans.get('type', 'expense')

        emoji = "💰" if trans_type == "income" else "💸"
        category_emoji = {
            "Alimentação":    "🍔",
            "Transporte":     "🚕",
            "Entretenimento": "🎬",
            "Saúde":          "⚕️",
            "Educação":       "📚",
            "Moradia":        "🏠",
            "Compras":        "🛍️",
            "Outros":         "📌"
        }.get(category, "📌")

        body += f"{emoji} *{description.title()}*\n"
        body += f"   {category_emoji} {category} | R$ {amount}\n"
        body += f"   📅 {date}\n\n"

    return header + body + "─" * 40, total_pages


# ============================================================================
# ZAPIER HELPER
# ============================================================================

def _post_zapier(url: str, payload: dict) -> requests.Response:
    """Wrapper para chamadas ao Zapier com timeout padrão"""
    return requests.post(url, json=payload, timeout=10)


# ============================================================================
# HANDLERS - START / MENU
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start — Menu principal"""
    keyboard = [
        [InlineKeyboardButton("⚡ Novo Gasto",  callback_data="new_expense")],
        [InlineKeyboardButton("📊 Histórico",   callback_data="history")],
        [InlineKeyboardButton("💰 Relatório",   callback_data="report")],
        [InlineKeyboardButton("💵 Meu Salário", callback_data="salary_menu")],
    ]
    await update.message.reply_text(
        "🤖 *Bem-vindo ao FinBot!* 💰\n\n"
        "Escolha uma opção ou digite rapidamente:\n"
        "`/gasto ifood 39`\n\n"
        "_Registre seus gastos e veja seu histórico!_",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ============================================================================
# HANDLERS - CREATE (NOVO GASTO)
# ============================================================================

async def quick_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /gasto — Modo rápido"""
    description, amount, error = parse_quick_expense(update.message.text)
    if error:
        await update.message.reply_text(
            f"❌ {error}\n\nUso correto: `/gasto ifood 39`",
            parse_mode="Markdown"
        )
        return

    context.user_data['pending_expense'] = {
        'description': description,
        'amount':      amount,
        'category':    detect_category(description),
        'date':        datetime.now().strftime("%Y-%m-%d"),
        'mode':        'quick'
    }
    await show_confirmation(update, context)


async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra preview com botões de confirmação"""
    expense = context.user_data.get('pending_expense')
    if not expense:
        return

    keyboard = [[
        InlineKeyboardButton("✅ Confirmar", callback_data="confirm_expense"),
        InlineKeyboardButton("✏️ Editar",    callback_data="edit_expense")
    ]]
    text = (
        f"Confirmando:\n"
        f"📝 *Descrição:* {expense['description']}\n"
        f"💵 *Valor:* R$ {expense['amount']:.2f}\n"
        f"🏷️ *Categoria:* {expense['category']}\n"
        f"📅 *Data:* {expense['date']}"
    )

    if update.message:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    else:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )


async def send_expense_to_zapier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia gasto para o Zap 1 (CRUD de transações)"""
    query   = update.callback_query
    expense = context.user_data.get('pending_expense')

    if not expense:
        await query.edit_message_text("❌ Erro: Nenhum gasto pendente")
        return

    payload = {
        "action":      "create",
        "user_id":     str(update.effective_user.id),
        "description": expense['description'],
        "amount":      expense['amount'],
        "category":    expense['category'],
        "type":        "expense",
        "date":        expense['date'],
        "_source":     "telegram_bot",
        "_timestamp":  datetime.now().isoformat()
    }

    try:
        logger.info(f"Enviando gasto para Zap 1: {payload}")
        response = _post_zapier(ZAPIER_WEBHOOK_EXPENSE, payload)

        if response.status_code == 200:
            await query.edit_message_text(
                "✅ *Gasto registrado com sucesso!*\n\n"
                f"📝 {expense['description']}\n"
                f"💵 R$ {expense['amount']:.2f}\n"
                f"🏷️ {expense['category']}\n"
                f"📅 {expense['date']}",
                parse_mode="Markdown"
            )
        else:
            logger.error(f"Erro Zap 1: {response.status_code} — {response.text}")
            await query.edit_message_text(
                f"❌ Erro ao registrar (status {response.status_code})"
            )

    except requests.exceptions.Timeout:
        await query.edit_message_text("⚠️ Webhook timeout. Tente novamente.")
    except Exception as e:
        logger.error(f"Erro ao enviar gasto: {str(e)}")
        await query.edit_message_text(f"❌ Erro: {str(e)}")
    finally:
        context.user_data.pop('pending_expense', None)
        context.user_data.pop('state', None)


# ============================================================================
# HANDLERS - READ (HISTÓRICO)
# ============================================================================

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra histórico de transações do usuário"""
    user_id = str(update.effective_user.id)

    if not gs_client:
        await update.callback_query.edit_message_text(
            "❌ Erro: Conexão com Google Sheets não disponível"
        )
        return

    transactions = gs_client.get_user_transactions(user_id)
    message, total_pages = format_transactions(transactions, page=1)

    if total_pages > 1:
        keyboard = [[
            InlineKeyboardButton("➡️ Próxima", callback_data="history_page_2"),
            InlineKeyboardButton("⬅️ Voltar",  callback_data="back_to_menu")
        ]]
    else:
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")]]

    context.user_data['history_page']         = 1
    context.user_data['history_transactions']  = transactions
    context.user_data['history_total_pages']   = total_pages

    await update.callback_query.edit_message_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


async def navigate_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navega entre páginas do histórico"""
    query = update.callback_query
    await query.answer()

    page         = int(query.data.split("_")[-1])
    transactions = context.user_data.get('history_transactions', [])
    total_pages  = context.user_data.get('history_total_pages', 1)
    message, _   = format_transactions(transactions, page=page)

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"history_page_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("➡️ Próxima", callback_data=f"history_page_{page + 1}"))

    keyboard = [nav_buttons, [InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")]]
    await query.edit_message_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


async def command_historico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /historico — atalho para histórico"""
    user_id = str(update.effective_user.id)

    if not gs_client:
        await update.message.reply_text("❌ Erro: Conexão com Google Sheets não disponível")
        return

    transactions = gs_client.get_user_transactions(user_id)
    message, total_pages = format_transactions(transactions, page=1)

    keyboard = []
    if total_pages > 1:
        keyboard.append([InlineKeyboardButton("➡️ Próxima", callback_data="history_page_2")])
    keyboard.append([InlineKeyboardButton("🏠 Menu", callback_data="back_to_menu")])

    context.user_data['history_page']         = 1
    context.user_data['history_transactions']  = transactions
    context.user_data['history_total_pages']   = total_pages

    await update.message.reply_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


# ============================================================================
# HANDLERS - SALÁRIO
# ============================================================================

async def show_salary_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra menu de salário com valor atual e saldo do mês"""
    query   = update.callback_query
    user_id = str(update.effective_user.id)

    if not gs_client:
        await query.edit_message_text("❌ Erro: Conexão com Google Sheets não disponível")
        return

    salary   = gs_client.get_user_salary(user_id)
    expenses = gs_client.get_monthly_expenses(user_id)
    balance  = salary - expenses

    if salary > 0:
        balance_emoji = "🟢" if balance >= 0 else "🔴"
        message = (
            f"💵 *Seu Salário*\n\n"
            f"💰 Salário registrado: R$ {salary:.2f}\n"
            f"💸 Gastos este mês: R$ {expenses:.2f}\n"
            f"{balance_emoji} Saldo disponível: R$ {balance:.2f}\n\n"
            f"_Deseja atualizar o valor?_"
        )
    else:
        message = (
            "💵 *Salário não registrado*\n\n"
            "Registre seu salário para acompanhar\n"
            "quanto você ainda pode gastar no mês!"
        )

    keyboard = [
        [InlineKeyboardButton("✏️ Registrar / Atualizar", callback_data="salary_set")],
        [InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")]
    ]
    await query.edit_message_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


async def salary_ask_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pede o valor do salário ao usuário"""
    query = update.callback_query
    await query.answer()

    context.user_data['state'] = AWAITING_SALARY
    await query.edit_message_text(
        "💵 *Qual é o seu salário mensal?*\n\n"
        "Digite apenas o valor numérico:\n"
        "Exemplo: `3500` ou `4750.50`",
        parse_mode="Markdown"
    )


async def process_salary_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Valida o valor digitado e envia para o Zap 2 (salário)"""
    text = update.message.text.strip().replace(",", ".")

    try:
        salary = float(text)
        if salary < 0:
            raise ValueError("Valor negativo")
    except ValueError:
        await update.message.reply_text(
            "❌ Valor inválido. Digite apenas números.\n"
            "Exemplo: `3500` ou `4750.50`",
            parse_mode="Markdown"
        )
        return

    user_id = str(update.effective_user.id)

    if not ZAPIER_WEBHOOK_SALARY:
        await update.message.reply_text("❌ Erro: ZAPIER_WEBHOOK_SALARY não configurado")
        context.user_data.pop('state', None)
        return

    payload = {
        "action":     "update_salary",
        "user_id":    user_id,
        "salary":     salary,
        "_source":    "telegram_bot",
        "_timestamp": datetime.now().isoformat()
    }

    try:
        logger.info(f"Enviando salário para Zap 2: {payload}")
        response = _post_zapier(ZAPIER_WEBHOOK_SALARY, payload)

        if response.status_code == 200:
            keyboard = [
                [InlineKeyboardButton("💵 Ver Salário",    callback_data="salary_menu")],
                [InlineKeyboardButton("🏠 Menu Principal", callback_data="back_to_menu")]
            ]
            await update.message.reply_text(
                f"✅ *Salário registrado com sucesso!*\n\n"
                f"💰 Valor: R$ {salary:.2f}\n\n"
                f"_Agora posso te mostrar quanto você ainda pode gastar este mês._",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            logger.error(f"Erro Zap 2: {response.status_code} — {response.text}")
            await update.message.reply_text(
                f"❌ Erro ao registrar salário (status {response.status_code})"
            )

    except requests.exceptions.Timeout:
        await update.message.reply_text("⚠️ Webhook timeout. Tente novamente.")
    except Exception as e:
        logger.error(f"Erro ao enviar salário: {str(e)}")
        await update.message.reply_text(f"❌ Erro: {str(e)}")
    finally:
        context.user_data.pop('state', None)


async def command_salario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /salario — atalho direto para menu de salário"""
    user_id = str(update.effective_user.id)

    if not gs_client:
        await update.message.reply_text("❌ Erro: Conexão com Google Sheets não disponível")
        return

    salary   = gs_client.get_user_salary(user_id)
    expenses = gs_client.get_monthly_expenses(user_id)
    balance  = salary - expenses

    if salary > 0:
        balance_emoji = "🟢" if balance >= 0 else "🔴"
        message = (
            f"💵 *Seu Salário*\n\n"
            f"💰 Salário registrado: R$ {salary:.2f}\n"
            f"💸 Gastos este mês: R$ {expenses:.2f}\n"
            f"{balance_emoji} Saldo disponível: R$ {balance:.2f}\n\n"
            f"_Deseja atualizar o valor?_"
        )
    else:
        message = (
            "💵 *Salário não registrado ainda.*\n\n"
            "Registre seu salário para acompanhar\n"
            "quanto você ainda pode gastar no mês!"
        )

    keyboard = [
        [InlineKeyboardButton("✏️ Registrar / Atualizar", callback_data="salary_set")],
        [InlineKeyboardButton("🏠 Menu", callback_data="back_to_menu")]
    ]
    await update.message.reply_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


# ============================================================================
# HANDLERS - BUTTONS (roteador central)
# ============================================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa cliques nos inline buttons"""
    query = update.callback_query
    await query.answer()

    if query.data == "new_expense":
        context.user_data['state'] = AWAITING_EXPENSE
        await query.edit_message_text(
            "Qual foi o gasto?\nExemplo: `ifood 39` ou `uber 25`",
            parse_mode="Markdown"
        )

    elif query.data == "history":
        await show_history(update, context)

    elif query.data.startswith("history_page_"):
        await navigate_history(update, context)

    elif query.data == "noop":
        pass

    elif query.data == "report":
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "💰 *Relatório Mensal:*\n\nFuncionalidade em desenvolvimento...",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data == "salary_menu":
        await show_salary_menu(update, context)

    elif query.data == "salary_set":
        await salary_ask_value(update, context)

    elif query.data == "back_to_menu":
        keyboard = [
            [InlineKeyboardButton("⚡ Novo Gasto",  callback_data="new_expense")],
            [InlineKeyboardButton("📊 Histórico",   callback_data="history")],
            [InlineKeyboardButton("💰 Relatório",   callback_data="report")],
            [InlineKeyboardButton("💵 Meu Salário", callback_data="salary_menu")],
        ]
        await query.edit_message_text(
            "🤖 *Menu Principal*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data == "confirm_expense":
        await send_expense_to_zapier(update, context)

    elif query.data == "edit_expense":
        await query.edit_message_text(
            "Qual campo deseja editar?\nEnvie a mensagem com o novo valor.",
            parse_mode="Markdown"
        )


# ============================================================================
# HANDLER - MENSAGENS DE TEXTO (roteador por estado)
# ============================================================================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagens de texto — roteia pelo estado atual"""
    text  = update.message.text
    state = context.user_data.get('state')

    # Estado: aguardando salário (prioridade máxima)
    if state == AWAITING_SALARY:
        await process_salary_input(update, context)
        return

    # Modo rápido via /gasto
    if text.startswith("/gasto"):
        await quick_expense(update, context)
        return

    # Estado: aguardando gasto pelo menu
    if state == AWAITING_EXPENSE:
        description, amount, error = parse_quick_expense("/gasto " + text)
        if error:
            await update.message.reply_text(
                f"❌ {error}\nFormato: 'ifood 39'",
                parse_mode="Markdown"
            )
            return
        context.user_data['pending_expense'] = {
            'description': description,
            'amount':      amount,
            'category':    detect_category(description),
            'date':        datetime.now().strftime("%Y-%m-%d"),
            'mode':        'menu'
        }
        await show_confirmation(update, context)
        return

    # Fallback: editando gasto pendente
    if 'pending_expense' in context.user_data:
        parts = text.split()
        if len(parts) >= 2:
            try:
                amount = float(parts[1])
                context.user_data['pending_expense']['description'] = parts[0]
                context.user_data['pending_expense']['amount']      = amount
                context.user_data['pending_expense']['category']    = detect_category(parts[0])
                await show_confirmation(update, context)
                return
            except ValueError:
                pass
        context.user_data['pending_expense']['description'] = text
        context.user_data['pending_expense']['category']    = detect_category(text)
        await show_confirmation(update, context)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Inicializa e roda o bot"""
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado!")
    if not ZAPIER_WEBHOOK_EXPENSE:
        logger.warning("⚠️ ZAPIER_WEBHOOK_EXPENSE não configurado. CREATE desativado.")
    if not ZAPIER_WEBHOOK_SALARY:
        logger.warning("⚠️ ZAPIER_WEBHOOK_SALARY não configurado. SALÁRIO desativado.")
    if not gs_client:
        logger.warning("⚠️ Google Sheets não conectado. READ e SALÁRIO desativados.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("gasto",     quick_expense))
    app.add_handler(CommandHandler("historico", command_historico))
    app.add_handler(CommandHandler("salario",   command_salario))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("✅ FinBot iniciando...")
    app.run_polling()


if __name__ == "__main__":
    main()
