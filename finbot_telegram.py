"""
FinBot Telegram — Assistente Financeiro com IA
Suporta: CREATE (novo gasto via Zapier) + READ/UPDATE (histórico e perfil via gspread)
Google Sheets integrado para persistência de dados
"""
import asyncio
import os
import re
import requests
import logging
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
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "assistente-financeiro-492800-0a343c503971.json")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1debpPb-JxXFAPf84rLOZ-HldYbOAYVwHc4B1lPbVTt4")
SHEET_NAME = "transactions"
SHEET_USERS = "users"

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
    # Alimentação
    "ifood": "Alimentação", "uber eats": "Alimentação", "rappi": "Alimentação",
    "pizza": "Alimentação", "restaurante": "Alimentação", "lanche": "Alimentação", "café": "Alimentação",
    # Transporte
    "uber": "Transporte", "99": "Transporte", "taxi": "Transporte",
    "passagem": "Transporte", "combustível": "Transporte", "gasolina": "Transporte",
    # Entretenimento
    "netflix": "Entretenimento", "spotify": "Entretenimento",
    "cinema": "Entretenimento", "jogo": "Entretenimento",
    # Saúde
    "farmácia": "Saúde", "médico": "Saúde", "dentista": "Saúde", "vitamina": "Saúde",
    # Educação
    "curso": "Educação", "livro": "Educação", "escola": "Educação",
    # Compras
    "mercado": "Compras", "supermercado": "Compras", "roupa": "Compras", "eletrônico": "Compras",
}

CATEGORIES = ["Alimentação", "Transporte", "Entretenimento", "Saúde", "Educação", "Moradia", "Compras", "Outros"]

# Emojis por categoria
CATEGORY_EMOJI = {
    "Alimentação": "🍔", "Transporte": "🚕", "Entretenimento": "🎬",
    "Saúde": "⚕️", "Educação": "📚", "Moradia": "🏠", "Compras": "🛍️", "Outros": "📌"
}


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
        except Exception:
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


def parse_salary_input(text: str) -> float | None:
    """
    Faz parse robusto de valores monetários digitados pelo usuário.
    Aceita: '3500', '3.500', '3500.50', '3.500,00', '3500,50'
    Retorna float ou None se inválido.
    """
    cleaned = re.sub(r"[^\d,.]", "", text.strip())
    if not cleaned:
        return None
    # Caso brasileiro: vírgula como decimal (ex: 3.500,00 ou 3500,50)
    if ',' in cleaned and '.' in cleaned:
        cleaned = cleaned.replace('.', '').replace(',', '.')
    elif ',' in cleaned:
        cleaned = cleaned.replace(',', '.')
    # Remove pontos de milhar restantes (ex: "3.500" → "3500")
    elif cleaned.count('.') > 1:
        cleaned = cleaned.replace('.', '', cleaned.count('.') - 1)
    try:
        value = float(cleaned)
        return value if value > 0 else None
    except ValueError:
        return None


def format_transactions(transactions: List[dict], page: int = 1, items_per_page: int = 5) -> Tuple[str, int]:
    """Formata transações para exibição no Telegram. Retorna (texto, total_páginas)."""
    if not transactions:
        return "📭 Nenhuma transação encontrada.\n\nComece a registrar seus gastos!", 1

    total_pages = (len(transactions) + items_per_page - 1) // items_per_page
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_transactions = transactions[start_idx:end_idx]

    header = f"📊 *Suas Transações* (página {page}/{total_pages})\n"
    header += f"Total: {len(transactions)} registros\n"
    header += "─" * 30 + "\n\n"

    body = ""
    for i, trans in enumerate(page_transactions, start=start_idx + 1):
        date = trans.get('date', 'N/A')
        description = trans.get('description', 'N/A')
        category = trans.get('category', 'N/A')
        amount = trans.get('amount', '0')
        trans_type = trans.get('type', 'expense')

        emoji = "💰" if trans_type == "income" else "💸"
        cat_emoji = CATEGORY_EMOJI.get(category, "📌")

        body += f"{emoji} *{str(description).title()}*\n"
        body += f"   {cat_emoji} {category} | R$ {amount}\n"
        body += f"   📅 {date}\n\n"

    footer = "─" * 30
    return header + body + footer, total_pages


# ============================================================================
# HANDLERS - ONBOARDING & MENU
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start — Onboarding ou menu principal"""
    user_id = str(update.effective_user.id)

    if not context.user_data.get('is_onboarded'):
        # Verifica na aba 'users' se já tem salário cadastrado
        if gs_client:
            salary = gs_client.get_user_salary(user_id)
            if salary == 0.0:
                # Usuário novo: inicia onboarding
                context.user_data['state'] = AWAITING_SALARY
                await update.message.reply_text(
                    "👋 *Bem-vindo ao FinBot!* 🎉\n\n"
                    "Para gerar análises inteligentes, preciso saber sua renda mensal.\n\n"
                    "Digite seu *salário mensal líquido*.\n"
                    "Exemplo: `3500` ou `4200.50`",
                    parse_mode="Markdown"
                )
                return

        context.user_data['is_onboarded'] = True

    await show_main_menu(update)


async def show_main_menu(update: Update):
    """Exibe o menu principal com todos os botões"""
    keyboard = [
        [InlineKeyboardButton("⚡ Novo Gasto", callback_data="new_expense")],
        [InlineKeyboardButton("📊 Histórico", callback_data="history"),
         InlineKeyboardButton("💰 Relatório", callback_data="report")],
        [InlineKeyboardButton("⚙️ Configurações", callback_data="settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_message = (
        "🤖 *Menu Principal* 💰\n\n"
        "Escolha uma opção ou registre rapidamente:\n"
        "`/gasto ifood 39`"
    )
    if update.message:
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(welcome_message, reply_markup=reply_markup, parse_mode="Markdown")


# ============================================================================
# HANDLERS - CREATE (NOVO GASTO)
# ============================================================================

async def quick_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /gasto — Modo rápido: /gasto ifood 39"""
    description, amount, error = parse_quick_expense(update.message.text)

    if error:
        await update.message.reply_text(
            f"❌ {error}\n\nUso correto: `/gasto ifood 39`",
            parse_mode="Markdown"
        )
        return

    category = detect_category(description)
    context.user_data['pending_expense'] = {
        'description': description,
        'amount': amount,
        'category': category,
        'date': datetime.now().strftime("%Y-%m-%d"),
        'mode': 'quick'
    }
    await show_confirmation(update, context)


async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra preview do gasto com botões de confirmação"""
    expense = context.user_data.get('pending_expense')
    if not expense:
        return

    keyboard = [[
        InlineKeyboardButton("✅ Confirmar", callback_data="confirm_expense"),
        InlineKeyboardButton("✏️ Editar", callback_data="edit_expense")
    ]]
    preview = (
        f"📝 *Descrição:* {expense['description']}\n"
        f"💵 *Valor:* R$ {expense['amount']:.2f}\n"
        f"🏷️ *Categoria:* {expense['category']}\n"
        f"📅 *Data:* {expense['date']}"
    )
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = f"Confirmando:\n{preview}"

    if update.message:
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(msg, reply_markup=reply_markup, parse_mode="Markdown")


async def send_to_zapier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia gasto para o Zapier via webhook"""
    query = update.callback_query
    expense = context.user_data.get('pending_expense')

    if not expense:
        await query.edit_message_text("❌ Erro: Nenhum gasto pendente.")
        return

    payload = {
        "action": "create",
        "user_id": str(update.effective_user.id),
        "description": expense['description'],
        "amount": expense['amount'],
        "category": expense['category'],
        "type": expense.get('type', 'expense'),
        "date": expense['date'],
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
            logger.info(f"✅ Gasto registrado: {expense}")
        else:
            logger.error(f"Erro Zapier: {response.status_code} - {response.text}")
            await query.edit_message_text(f"❌ Erro ao registrar (status {response.status_code})")

    except requests.exceptions.Timeout:
        await query.edit_message_text("⚠️ Webhook timeout. Tente novamente.")
    except Exception as e:
        logger.error(f"Erro ao enviar para Zapier: {str(e)}")
        await query.edit_message_text(f"❌ Erro: {str(e)}")
    finally:
        context.user_data.pop('pending_expense', None)
        context.user_data.pop('state', None)


# ============================================================================
# HANDLERS - READ (HISTÓRICO)
# ============================================================================

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra histórico de transações (página 1)"""
    user_id = str(update.effective_user.id)

    if not gs_client:
        await update.callback_query.edit_message_text("❌ Erro: Google Sheets não disponível.")
        return

    transactions = gs_client.get_user_transactions(user_id)
    message, total_pages = format_transactions(transactions, page=1)

    keyboard = []
    nav_buttons = []
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton("➡️ Próxima", callback_data="history_page_2"))
    nav_buttons.append(InlineKeyboardButton(f"📄 1/{total_pages}", callback_data="noop"))
    keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")])

    context.user_data['history_page'] = 1
    context.user_data['history_transactions'] = transactions
    context.user_data['history_total_pages'] = total_pages

    await update.callback_query.edit_message_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


async def navigate_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navega entre páginas do histórico"""
    query = update.callback_query
    await query.answer()

    page = int(query.data.split("_")[-1])
    transactions = context.user_data.get('history_transactions', [])
    total_pages = context.user_data.get('history_total_pages', 1)
    message, _ = format_transactions(transactions, page=page)

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"history_page_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("➡️ Próxima", callback_data=f"history_page_{page + 1}"))

    keyboard = [nav_buttons, [InlineKeyboardButton("🏠 Menu", callback_data="back_to_menu")]]

    await query.edit_message_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


async def command_historico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /historico — atalho para histórico via texto"""
    user_id = str(update.effective_user.id)

    if not gs_client:
        await update.message.reply_text("❌ Erro: Google Sheets não disponível.")
        return

    transactions = gs_client.get_user_transactions(user_id)
    message, total_pages = format_transactions(transactions, page=1)

    keyboard = []
    if total_pages > 1:
        keyboard.append([InlineKeyboardButton("➡️ Próxima", callback_data="history_page_2")])
    keyboard.append([InlineKeyboardButton("🏠 Menu", callback_data="back_to_menu")])

    context.user_data['history_page'] = 1
    context.user_data['history_transactions'] = transactions
    context.user_data['history_total_pages'] = total_pages

    await update.message.reply_text(
        message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


# ============================================================================
# HANDLERS - RELATÓRIO 50-30-20
# ============================================================================

async def show_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Exibe relatório financeiro mensal com simulação da regra 50/30/20.
    Busca salário na aba 'users' e despesas do mês em 'transactions'.
    """
    query = update.callback_query
    user_id = str(update.effective_user.id)

    await query.edit_message_text("⏳ Gerando seu relatório...")

    if not gs_client:
        await query.edit_message_text("❌ Erro: Google Sheets não disponível.")
        return

    try:
        salary = gs_client.get_user_salary(user_id)
        expenses = gs_client.get_monthly_expenses(user_id)
    except Exception as e:
        logger.error(f"Erro ao gerar relatório: {str(e)}")
        await query.edit_message_text(
            "⚠️ Erro ao buscar dados. Tente novamente em instantes."
        )
        return

    mes = datetime.now().strftime("%m/%Y")
    keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")]]

    # Sem salário cadastrado
    if salary == 0.0:
        await query.edit_message_text(
            "❌ *Salário não cadastrado*\n\n"
            "Para ver o relatório completo, cadastre seu salário em:\n"
            "⚙️ Configurações → 💵 Alterar Salário",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    # Cálculos principais
    saldo_restante = salary - expenses
    pct_comprometida = (expenses / salary * 100) if salary > 0 else 0

    # Indicador de saúde financeira
    if pct_comprometida <= 50:
        status_emoji, status_msg = "🟢", "Ótimo! Seus gastos estão controlados."
    elif pct_comprometida <= 80:
        status_emoji, status_msg = "🟡", "Atenção! Gastos elevados este mês."
    else:
        status_emoji, status_msg = "🔴", "Cuidado! Gastos ultrapassaram 80% da renda."

    # Simulação 50/30/20
    ideal_necessidades = salary * 0.50
    ideal_desejos = salary * 0.30
    ideal_economia = salary * 0.20

    # Barra visual de progresso (10 blocos)
    blocos_cheios = min(10, int(pct_comprometida / 10))
    barra = "█" * blocos_cheios + "░" * (10 - blocos_cheios)

    report = (
        f"📊 *Relatório Financeiro — {mes}*\n"
        f"{'─' * 30}\n\n"
        f"💰 *Salário líquido:* R$ {salary:,.2f}\n"
        f"💸 *Gastos no mês:* R$ {expenses:,.2f}\n"
        f"💵 *Saldo disponível:* R$ {saldo_restante:,.2f}\n\n"
        f"📉 *Renda comprometida:* {pct_comprometida:.1f}%\n"
        f"`{barra}` {pct_comprometida:.0f}%\n\n"
        f"{status_emoji} _{status_msg}_\n\n"
        f"{'─' * 30}\n"
        f"📐 *Regra 50/30/20 — Como distribuir R$ {salary:,.2f}*\n\n"
        f"🏠 *50% Necessidades* → R$ {ideal_necessidades:,.2f}\n"
        f"   _Moradia, alimentação, transporte, saúde_\n\n"
        f"🎉 *30% Desejos* → R$ {ideal_desejos:,.2f}\n"
        f"   _Lazer, restaurantes, assinaturas_\n\n"
        f"💎 *20% Economia* → R$ {ideal_economia:,.2f}\n"
        f"   _Reserva de emergência e investimentos_\n\n"
        f"{'─' * 30}\n"
        f"_⚙️ Atualize seu salário em Configurações._"
    )

    await query.edit_message_text(
        report,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ============================================================================
# HANDLERS - CONFIGURAÇÕES (AJUSTES)
# ============================================================================

async def ajustes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ajustes — Abre menu de configurações via texto"""
    keyboard = [
        [InlineKeyboardButton("💵 Alterar Salário", callback_data="edit_salary")],
        [InlineKeyboardButton("🏠 Menu Principal", callback_data="back_to_menu")],
    ]
    await update.message.reply_text(
        "⚙️ *Configurações de Perfil*\n\nO que deseja gerenciar?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ============================================================================
# HANDLER - BOTÕES INLINE (CENTRAL)
# ============================================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa todos os cliques em InlineKeyboard"""
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── Novo gasto ────────────────────────────────────────────────────────────
    if data == "new_expense":
        context.user_data['state'] = AWAITING_EXPENSE
        await query.edit_message_text(
            "Qual foi o gasto?\nExemplo: `ifood 39` ou `uber 25`",
            parse_mode="Markdown"
        )

    # ── Histórico ─────────────────────────────────────────────────────────────
    elif data == "history":
        await show_history(update, context)

    elif data.startswith("history_page_"):
        await navigate_history(update, context)

    elif data == "noop":
        pass  # Botão inerte (indicador de página)

    # ── Relatório ─────────────────────────────────────────────────────────────
    elif data == "report":
        await show_report(update, context)

    # ── Configurações ─────────────────────────────────────────────────────────
    elif data == "settings":
        keyboard = [
            [InlineKeyboardButton("💵 Alterar Salário", callback_data="edit_salary")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")],
        ]
        await query.edit_message_text(
            "⚙️ *Configurações de Perfil*\n\nO que deseja gerenciar?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "edit_salary":
        context.user_data['state'] = AWAITING_SALARY
        context.user_data['salary_edit_mode'] = True  # Veio dos ajustes (não onboarding)
        await query.edit_message_text(
            "💵 *Alterar Salário*\n\n"
            "Digite seu novo salário mensal líquido.\n"
            "Exemplo: `3500` ou `3.500,00`",
            parse_mode="Markdown"
        )

    # ── Confirmação de gasto ──────────────────────────────────────────────────
    elif data == "confirm_expense":
        await send_to_zapier(update, context)

    elif data == "edit_expense":
        await query.edit_message_text(
            "✏️ Digite novamente no formato: `descrição valor`\nExemplo: `ifood 45.90`",
            parse_mode="Markdown"
        )

    # ── Voltar ao menu ────────────────────────────────────────────────────────
    elif data == "back_to_menu":
        await show_main_menu(update)


# ============================================================================
# HANDLER - MENSAGENS DE TEXTO
# ============================================================================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagens de texto de acordo com o estado atual"""
    text = update.message.text.strip()
    state = context.user_data.get('state')

    # ── Estado: aguardando salário ────────────────────────────────────────────
    if state == AWAITING_SALARY:
        salary = parse_salary_input(text)

        if salary is None:
            await update.message.reply_text(
                "❌ Valor inválido. Digite apenas o número.\n"
                "Exemplo: `3500` ou `3.500,00`",
                parse_mode="Markdown"
            )
            return

        # Salva diretamente no Google Sheets via gspread (aba 'users')
        if not gs_client:
            await update.message.reply_text("⚠️ Erro: Google Sheets não disponível.")
            return

        try:
            gs_client.update_user_salary(str(update.effective_user.id), salary)
        except Exception:
            await update.message.reply_text(
                "⚠️ Erro ao salvar no Google Sheets. Tente novamente em instantes."
            )
            return

        edit_mode = context.user_data.pop('salary_edit_mode', False)
        context.user_data.pop('state', None)
        context.user_data['is_onboarded'] = True

        if edit_mode:
            msg = f"✅ *Salário atualizado!*\nNovo valor: R$ {salary:,.2f}"
        else:
            msg = (
                f"✅ *Salário cadastrado com sucesso!*\n"
                f"Valor: R$ {salary:,.2f}\n\n"
                "Agora você pode registrar suas despesas! 🚀"
            )

        await update.message.reply_text(msg, parse_mode="Markdown")
        await asyncio.sleep(0.5)
        await show_main_menu(update)
        return

    # ── Estado: aguardando gasto (via menu) ───────────────────────────────────
    if state == AWAITING_EXPENSE:
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ Formato inválido.\nExemplo: `ifood 39` ou `uber 25.50`",
                parse_mode="Markdown"
            )
            return

        description = parts[0]
        try:
            amount = float(parts[1].replace(',', '.'))
        except ValueError:
            await update.message.reply_text(
                "❌ Valor inválido. Use o formato: `descrição valor`\nExemplo: `ifood 39`",
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
        context.user_data.pop('state', None)
        await show_confirmation(update, context)
        return

    # ── Editando gasto pendente ───────────────────────────────────────────────
    if 'pending_expense' in context.user_data:
        parts = text.split()
        if len(parts) >= 2:
            description = parts[0]
            try:
                amount = float(parts[1].replace(',', '.'))
                context.user_data['pending_expense']['description'] = description
                context.user_data['pending_expense']['amount'] = amount
                context.user_data['pending_expense']['category'] = detect_category(description)
                await show_confirmation(update, context)
                return
            except ValueError:
                pass

        # Só a descrição foi enviada
        context.user_data['pending_expense']['description'] = text
        context.user_data['pending_expense']['category'] = detect_category(text)
        await show_confirmation(update, context)
        return

    # ── Mensagem fora de contexto ─────────────────────────────────────────────
    await update.message.reply_text(
        "🤖 Use o menu abaixo ou `/gasto ifood 39` para registrar rapidamente.",
        parse_mode="Markdown"
    )
    await show_main_menu(update)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Inicializa e roda o bot"""
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado!")
    if not ZAPIER_WEBHOOK:
        logger.warning("ZAPIER_WEBHOOK_URL não configurado. CREATE via Zapier desativado.")
    if not gs_client:
        logger.warning("Google Sheets não conectado. READ/UPDATE desativados.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gasto", quick_expense))
    app.add_handler(CommandHandler("historico", command_historico))
    app.add_handler(CommandHandler("ajustes", ajustes_command))

    # Callbacks inline — deve vir ANTES do MessageHandler
    app.add_handler(CallbackQueryHandler(button_handler))

    # Mensagens de texto
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("✅ FinBot iniciando...")

    # run_polling() gerencia o event loop internamente — não usar asyncio.run()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # Correção para Python 3.10+: garante que há um event loop antes de iniciar
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    main()
