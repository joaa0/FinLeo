"""
FinBot Telegram — Assistente Financeiro com IA
Suporta: CREATE (novo gasto) + READ (histórico)
Google Sheets integrado para persistência de dados
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
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ZAPIER_WEBHOOK = os.getenv("ZAPIER_WEBHOOK_URL")
# FIX: default vazio para não conflitar com GOOGLE_CREDENTIALS_JSON no Railway
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
SHEET_NAME = os.getenv("SHEET_NAME", "transactions")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados da conversa
MENU, AWAITING_EXPENSE, SELECTING_CATEGORY, CONFIRMING = range(4)

# Mapeamento inteligente de categorias
CATEGORY_MAP = {
    # Alimentação
    "ifood": "Alimentação",
    "uber eats": "Alimentação",
    "rappi": "Alimentação",
    "pizza": "Alimentação",
    "restaurante": "Alimentação",
    "lanche": "Alimentação",
    "café": "Alimentação",

    # Transporte
    "uber": "Transporte",
    "99": "Transporte",
    "taxi": "Transporte",
    "passagem": "Transporte",
    "combustível": "Transporte",
    "gasolina": "Transporte",

    # Entretenimento
    "netflix": "Entretenimento",
    "spotify": "Entretenimento",
    "cinema": "Entretenimento",
    "jogo": "Entretenimento",

    # Saúde
    "farmácia": "Saúde",
    "médico": "Saúde",
    "dentista": "Saúde",
    "vitamina": "Saúde",

    # Educação
    "curso": "Educação",
    "livro": "Educação",
    "escola": "Educação",

    # Compras
    "mercado": "Compras",
    "supermercado": "Compras",
    "roupa": "Compras",
    "eletrônico": "Compras",
}

CATEGORIES = [
    "Alimentação",
    "Transporte",
    "Entretenimento",
    "Saúde",
    "Educação",
    "Moradia",
    "Compras",
    "Outros"
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

            # Prioridade 1: variável de ambiente com conteúdo JSON (Railway)
            credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
            if credentials_json:
                logger.info("🔑 Usando credenciais via GOOGLE_CREDENTIALS_JSON")
                try:
                    credentials_dict = json.loads(credentials_json)
                except json.JSONDecodeError as e:
                    raise ValueError(f"GOOGLE_CREDENTIALS_JSON inválido (erro de JSON): {e}")

                credentials = Credentials.from_service_account_info(
                    credentials_dict,
                    scopes=scopes
                )

            # Prioridade 2: arquivo local (desenvolvimento)
            elif self.credentials_path:
                logger.info(f"🔑 Usando credenciais via arquivo: {self.credentials_path}")
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Arquivo de credenciais não encontrado: {self.credentials_path}\n"
                        "Configure GOOGLE_CREDENTIALS_JSON ou verifique o path."
                    )
                credentials = Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=scopes
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

            logger.info(f"📊 Encontradas {len(user_transactions)} transações para user_id={user_id}")
            return user_transactions

        except Exception as e:
            logger.error(f"❌ Erro ao buscar transações: {str(e)}")
            return []

    def get_user_salary(self, user_id: str) -> float:
    """
    Busca o salário atual do usuário na aba 'users'.
    Lê da coluna D (índice 4).
    Estrutura da aba: user_id | email | registered_date | salary | updated_at
    Retorna 0.0 se não encontrado.
    """
    try:
        worksheet = self.spreadsheet.worksheet(SHEET_USERS)
        cell = worksheet.find(str(user_id), in_column=1)
        if cell:
            value = worksheet.cell(cell.row, 4).value  # coluna D = salary
            return float(str(value).replace(",", ".")) if value else 0.0
        return 0.0
    except Exception as e:
        logger.error(f"❌ Erro ao buscar salário: {str(e)}")
        return 0.0

    def update_user_salary(self, user_id: str, salary: float):
        """
        Cria ou atualiza o salário do usuário na aba 'users'.
        Estrutura preservada: user_id | email | registered_date | salary | updated_at
        - Usuário existente: atualiza apenas col D (salary) e col E (updated_at)
        - Usuário novo: append com user_id na A, email/registered_date vazios, salary na D
        """
        try:
            worksheet = self.spreadsheet.worksheet(SHEET_USERS)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                cell = worksheet.find(str(user_id), in_column=1)
                # Atualiza só salary (col D=4) e updated_at (col E=5)
                worksheet.update_cell(cell.row, 4, salary)
                worksheet.update_cell(cell.row, 5, now)
            except Exception:
                # Novo usuário: deixa email e registered_date vazios (col B e C)
                worksheet.append_row([str(user_id), "", "", salary, now])
            logger.info(f"✅ Salário atualizado para user_id={user_id}: R$ {salary:.2f}")
        except Exception as e:
            logger.error(f"❌ Erro ao salvar salário: {str(e)}")
            raise  # Propaga para o handler tratar

    def get_monthly_expenses(self, user_id: str) -> float:
        """
        Soma despesas do mês atual do usuário na aba 'transactions'.
        Filtra type == 'expense' e date começa com YYYY-MM do mês atual.
        """
        mes_atual = datetime.now().strftime("%Y-%m")
        total = 0.0
        try:
            all_rows = self.worksheet.get_all_records()
            for row in all_rows:
                row_user = str(row.get('user_id', '')).strip()
                row_type = str(row.get('type', '')).lower().strip()
                row_date = str(row.get('date', ''))
                row_amount = row.get('amount', 0)

                if row_user == str(user_id) and row_type == 'expense' and row_date.startswith(mes_atual):
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
    """Formata transações para exibição no Telegram

    Retorna: (texto_formatado, total_de_paginas)
    """
    if not transactions:
        return "📭 Nenhuma transação encontrada.\n\nComece a registrar seus gastos!", 1

    # Calcular paginação
    total_pages = (len(transactions) + items_per_page - 1) // items_per_page
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page

    page_transactions = transactions[start_idx:end_idx]

    # Cabeçalho
    header = f"📊 *Suas Transações* (página {page}/{total_pages})\n"
    header += f"Total: {len(transactions)} registros\n"
    header += "─" * 40 + "\n\n"

    # Transações formatadas
    body = ""
    for i, trans in enumerate(page_transactions, start=start_idx + 1):
        date = trans.get('date', 'N/A')
        description = trans.get('description', 'N/A')
        category = trans.get('category', 'N/A')
        amount = trans.get('amount', '0')
        trans_type = trans.get('type', 'expense')

        # Emoji por tipo
        emoji = "💰" if trans_type == "income" else "💸"

        # Emoji por categoria
        category_emoji = {
            "Alimentação": "🍔",
            "Transporte": "🚕",
            "Entretenimento": "🎬",
            "Saúde": "⚕️",
            "Educação": "📚",
            "Moradia": "🏠",
            "Compras": "🛍️",
            "Outros": "📌"
        }.get(category, "📌")

        body += f"{emoji} *{description.title()}*\n"
        body += f"   {category_emoji} {category} | R$ {amount}\n"
        body += f"   📅 {date}\n\n"

    footer = "─" * 40

    return header + body + footer, total_pages


# ============================================================================
# HANDLERS - CREATE
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start — Menu principal"""

    keyboard = [
        [InlineKeyboardButton("⚡ Novo Gasto", callback_data="new_expense")],
        [InlineKeyboardButton("📊 Histórico", callback_data="history")],
        [InlineKeyboardButton("💰 Relatório", callback_data="report")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_message = (
        "🤖 *Bem-vindo ao FinBot!* 💰\n\n"
        "Escolha uma opção ou digite rapidamente:\n"
        "`/gasto ifood 39`\n\n"
        "_Registre seus gastos e veja seu histórico!_"
    )

    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def quick_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /gasto — Modo rápido"""

    description, amount, error = parse_quick_expense(update.message.text)

    if error:
        await update.message.reply_text(
            f"❌ {error}\n\n"
            "Uso correto: `/gasto ifood 39`",
            parse_mode="Markdown"
        )
        return

    # Detecta categoria
    category = detect_category(description)

    # Armazena para confirmação
    context.user_data['pending_expense'] = {
        'description': description,
        'amount': amount,
        'category': category,
        'date': datetime.now().strftime("%Y-%m-%d"),
        'mode': 'quick'
    }

    # Mostra preview
    await show_confirmation(update, context)


async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra preview com botões de confirmação"""

    expense = context.user_data.get('pending_expense')
    if not expense:
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar", callback_data="confirm_expense"),
            InlineKeyboardButton("✏️ Editar", callback_data="edit_expense")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    preview = (
        f"📝 *Descrição:* {expense['description']}\n"
        f"💵 *Valor:* R$ {expense['amount']:.2f}\n"
        f"🏷️ *Categoria:* {expense['category']}\n"
        f"📅 *Data:* {expense['date']}"
    )

    if update.message:
        await update.message.reply_text(
            f"Confirmando:\n{preview}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.callback_query.edit_message_text(
            f"Confirmando:\n{preview}",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


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

    # Formatar e exibir (página 1)
    message, total_pages = format_transactions(transactions, page=1)

    # Botões de navegação
    keyboard = []
    if total_pages > 1:
        nav_buttons = []
        if 1 < total_pages:
            nav_buttons.append(InlineKeyboardButton("➡️ Próxima", callback_data="history_page_2"))
        nav_buttons.append(InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu"))
        keyboard.append(nav_buttons)
    else:
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")])

    # Armazenar página atual no contexto
    context.user_data['history_page'] = 1
    context.user_data['history_transactions'] = transactions
    context.user_data['history_total_pages'] = total_pages

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def navigate_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navega entre páginas do histórico"""

    query = update.callback_query
    await query.answer()

    # Extrair número da página do callback_data
    page = int(query.data.split("_")[-1])

    transactions = context.user_data.get('history_transactions', [])
    total_pages = context.user_data.get('history_total_pages', 1)

    # Formatar página
    message, _ = format_transactions(transactions, page=page)

    # Botões de navegação
    keyboard = []
    nav_buttons = []

    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"history_page_{page - 1}"))

    nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))

    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("➡️ Próxima", callback_data=f"history_page_{page + 1}"))

    keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def command_historico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /historico — atalho para histórico"""

    user_id = str(update.effective_user.id)

    if not gs_client:
        await update.message.reply_text(
            "❌ Erro: Conexão com Google Sheets não disponível"
        )
        return

    transactions = gs_client.get_user_transactions(user_id)

    # Formatar e exibir
    message, total_pages = format_transactions(transactions, page=1)

    # Botões de navegação
    keyboard = []
    if total_pages > 1:
        nav_buttons = []
        if 1 < total_pages:
            nav_buttons.append(InlineKeyboardButton("➡️ Próxima", callback_data="history_page_2"))
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🏠 Menu", callback_data="back_to_menu")])

    # Armazenar contexto
    context.user_data['history_page'] = 1
    context.user_data['history_transactions'] = transactions
    context.user_data['history_total_pages'] = total_pages

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# ============================================================================
# HANDLERS - BUTTONS
# ============================================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa cliques nos inline buttons"""

    query = update.callback_query
    await query.answer()

    if query.data == "new_expense":
        context.user_data['state'] = AWAITING_EXPENSE
        await query.edit_message_text(
            "Qual foi o gasto?\n"
            "Exemplo: `ifood 39` ou `uber 25`",
            parse_mode="Markdown"
        )

    elif query.data == "history":
        await show_history(update, context)

    elif query.data.startswith("history_page_"):
        await navigate_history(update, context)

    elif query.data == "noop":
        pass

    elif query.data == "report":
        await query.edit_message_text(
            "💰 *Relatório Mensal:*\n\n"
            "Funcionalidade em desenvolvimento...\n"
            "(Integrando com Google Sheets)",
            parse_mode="Markdown"
        )

        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")]]
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "back_to_menu":
        keyboard = [
            [InlineKeyboardButton("⚡ Novo Gasto", callback_data="new_expense")],
            [InlineKeyboardButton("📊 Histórico", callback_data="history")],
            [InlineKeyboardButton("💰 Relatório", callback_data="report")]
        ]
        await query.edit_message_text(
            "🤖 *Menu Principal*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data == "confirm_expense":
        await send_to_zapier(update, context)

    elif query.data == "edit_expense":
        await query.edit_message_text(
            "Qual campo deseja editar?\n"
            "Envie a mensagem com o novo valor.",
            parse_mode="Markdown"
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagens de entrada"""

    text = update.message.text

    # Modo rápido
    if text.startswith("/gasto"):
        await quick_expense(update, context)
        return

    # Modo menu completo
    if context.user_data.get('state') == AWAITING_EXPENSE:
        description, amount, error = parse_quick_expense("/gasto " + text)
        if error:
            await update.message.reply_text(
                f"❌ {error}\nFormato: 'ifood 39'",
                parse_mode="Markdown"
            )
            return

        category = detect_category(description)

        context.user_data['pending_expense'] = {
            'description': description,
            'amount': amount,
            'category': category,
            'date': datetime.now().strftime("%Y-%m-%d"),
            'mode': 'menu'
        }

        await show_confirmation(update, context)
        return

    # Editando gasto
    if 'pending_expense' in context.user_data:
        text = update.message.text
        parts = text.split()
        if len(parts) >= 2:
            description = parts[0]
            try:
                amount = float(parts[1])
                context.user_data['pending_expense']['description'] = description
                context.user_data['pending_expense']['amount'] = amount
                context.user_data['pending_expense']['category'] = detect_category(description)

                await show_confirmation(update, context)
                return
            except ValueError:
                pass

        context.user_data['pending_expense']['description'] = text
        context.user_data['pending_expense']['category'] = detect_category(text)

        await show_confirmation(update, context)


async def send_to_zapier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia gasto para Zapier"""

    query = update.callback_query
    expense = context.user_data.get('pending_expense')

    if not expense:
        await query.edit_message_text("❌ Erro: Nenhum gasto pendente")
        return

    payload = {
        "action": "create",
        "user_id": str(update.effective_user.id),
        "description": expense['description'],
        "amount": expense['amount'],
        "category": expense['category'],
        "type": "expense",
        "date": expense['date'],
        "filter": None,
        "target": None,
        "updates": None,
        "_source": "telegram_bot",
        "_timestamp": datetime.now().isoformat()
    }

    try:
        logger.info(f"Enviando para Zapier: {payload}")

        response = requests.post(ZAPIER_WEBHOOK, json=payload, timeout=10)

        if response.status_code == 200:
            await query.edit_message_text(
                "✅ *Gasto registrado com sucesso!*\n\n"
                f"📝 {expense['description']}\n"
                f"💵 R$ {expense['amount']:.2f}\n"
                f"🏷️ {expense['category']}\n"
                f"📅 {expense['date']}",
                parse_mode="Markdown"
            )

            logger.info(f"Gasto registrado: {expense}")
        else:
            logger.error(f"Erro Zapier: {response.status_code} - {response.text}")
            await query.edit_message_text(
                f"❌ Erro ao registrar (status {response.status_code})"
            )

    except requests.exceptions.Timeout:
        await query.edit_message_text(
            "⚠️ Webhook timeout. Tente novamente."
        )
    except Exception as e:
        logger.error(f"Erro ao enviar: {str(e)}")
        await query.edit_message_text(
            f"❌ Erro: {str(e)}"
        )

    finally:
        context.user_data.pop('pending_expense', None)
        context.user_data.pop('state', None)


def main():
    """Inicializa e roda o bot"""

    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado!")

    if not ZAPIER_WEBHOOK:
        logger.warning("ZAPIER_WEBHOOK_URL não configurado. CREATE desativado.")

    if not gs_client:
        logger.warning("Google Sheets não conectado. READ desativado.")

    # Criar aplicação
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gasto", quick_expense))
    app.add_handler(CommandHandler("historico", command_historico))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("✅ FinBot iniciando...")

    # Polling
    app.run_polling()


if __name__ == "__main__":
    main()
