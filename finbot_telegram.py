"""
FinBot Telegram — Assistente Financeiro com IA
Suporta: CREATE (novo gasto) + READ (histórico) + SALÁRIO (registrar/consultar)
Google Sheets integrado para persistência de dados
Zap 1: CRUD de transações | Zap 2: atualização de salário
"""

import os
import re
import asyncio
import requests
import logging
import json
from datetime import datetime, timedelta
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

# Logging  (DEBUG temporário para diagnóstico — mude para INFO em produção)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)
# Silencia libs barulhentas para não poluir o log de debug
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# Estados da conversa
(
    MENU,
    AWAITING_EXPENSE,
    SELECTING_CATEGORY,
    CONFIRMING,
    AWAITING_SALARY,
    AWAITING_EMAIL,            # onboarding — aguardando email
    AWAITING_ONBOARDING_SALARY # onboarding — aguardando salário inicial
) = range(7)

# Mapeamento inteligente de categorias
# Cada entrada: keyword → (categoria, type)
CATEGORY_MAP = {
    # Alimentação — expense
    "ifood":         ("Alimentação",    "expense"),
    "uber eats":     ("Alimentação",    "expense"),
    "rappi":         ("Alimentação",    "expense"),
    "pizza":         ("Alimentação",    "expense"),
    "restaurante":   ("Alimentação",    "expense"),
    "lanche":        ("Alimentação",    "expense"),
    "café":          ("Alimentação",    "expense"),
    # Transporte — expense
    "uber":          ("Transporte",     "expense"),
    "99":            ("Transporte",     "expense"),
    "taxi":          ("Transporte",     "expense"),
    "passagem":      ("Transporte",     "expense"),
    "combustível":   ("Transporte",     "expense"),
    "gasolina":      ("Transporte",     "expense"),
    # Entretenimento — expense
    "netflix":       ("Entretenimento", "expense"),
    "spotify":       ("Entretenimento", "expense"),
    "cinema":        ("Entretenimento", "expense"),
    "jogo":          ("Entretenimento", "expense"),
    # Saúde — expense
    "farmácia":      ("Saúde",          "expense"),
    "médico":        ("Saúde",          "expense"),
    "dentista":      ("Saúde",          "expense"),
    "vitamina":      ("Saúde",          "expense"),
    # Educação — expense
    "curso":         ("Educação",       "expense"),
    "livro":         ("Educação",       "expense"),
    "escola":        ("Educação",       "expense"),
    # Compras — expense
    "mercado":       ("Compras",        "expense"),
    "supermercado":  ("Compras",        "expense"),
    "roupa":         ("Compras",        "expense"),
    "eletrônico":    ("Compras",        "expense"),
    # Trabalho / Receitas — income (espelha as keywords do Zapier)
    "salário":       ("Trabalho",       "income"),
    "recebi":        ("Trabalho",       "income"),
    "ganhei":        ("Trabalho",       "income"),
    "bônus":         ("Trabalho",       "income"),
    "freelance":     ("Trabalho",       "income"),
    "venda":         ("Trabalho",       "income"),
    "trabalho":      ("Trabalho",       "income"),
    "renda":         ("Trabalho",       "income"),
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
        credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")
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

    async def get_user_transactions(self, user_id: str) -> List[dict]:
        """Busca todas as transações de um usuário"""
        try:
            all_rows = await asyncio.to_thread(self.worksheet.get_all_records)
            user_transactions = [
                row for row in all_rows
                if str(row.get('user_id', '')).strip() == str(user_id).strip()
            ]
            logger.info(f"📊 {len(user_transactions)} transações para user_id={user_id}")
            return user_transactions
        except Exception as e:
            logger.error(f"❌ Erro ao buscar transações: {str(e)}")
            return []

    async def user_exists(self, user_id: str) -> bool:
        """Verifica se user_id já está cadastrado na aba users."""
        target = str(user_id).strip()
        try:
            ws = await asyncio.to_thread(
                self.spreadsheet.worksheet, SHEET_USERS
            )
            all_rows = await asyncio.to_thread(ws.get_all_records)
            for row in all_rows:
                uid = str(row.get('user_id', '')).strip()
                email = str(row.get('email', '')).strip()
                salary_raw = str(row.get('salary', '')).strip()
                if uid == target:
                    # Considera cadastrado se tem email E salário preenchidos
                    if email and salary_raw and salary_raw not in ('0', '0.0', ''):
                        logger.debug(f"[ONBOARDING] user_id={target!r} já cadastrado")
                        return True
                    logger.debug(f"[ONBOARDING] user_id={target!r} incompleto — refaz onboarding")
                    return False
            logger.debug(f"[ONBOARDING] user_id={target!r} não encontrado")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao verificar usuário: {e}")
            return False

    async def create_user(self, user_id: str, email: str, salary: float) -> bool:
        """Cria ou atualiza linha do usuário na aba users.

        Estrutura: user_id | email | registered_date | salary | updated_at
        """
        target = str(user_id).strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            ws = await asyncio.to_thread(
                self.spreadsheet.worksheet, SHEET_USERS
            )
            all_rows = await asyncio.to_thread(ws.get_all_records)

            # Procura linha existente para atualizar
            for i, row in enumerate(all_rows):
                if str(row.get('user_id', '')).strip() == target:
                    row_number = i + 2  # +1 cabeçalho, +1 base 1
                    await asyncio.to_thread(
                        ws.update,
                        f"A{row_number}:E{row_number}",
                        [[target, email, row.get('registered_date', today), salary, now]]
                    )
                    logger.info(f"[ONBOARDING] Linha atualizada para user_id={target!r}")
                    return True

            # Usuário novo — append
            await asyncio.to_thread(
                ws.append_row,
                [target, email, today, salary, now]
            )
            logger.info(f"[ONBOARDING] Nova linha criada para user_id={target!r}")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao criar/atualizar usuário: {e}")
            return False

    async def get_user_salary(self, user_id: str) -> float:
        """
        Busca o salário do usuário na aba 'users' por match EXATO de user_id.
        Nunca usa a primeira linha como fallback.
        Retorna 0.0 se não encontrado.
        """
        target_id = str(user_id).strip()
        try:
            all_rows = await asyncio.to_thread(
                self.spreadsheet.worksheet(SHEET_USERS).get_all_records
            )
            # DEBUG: listar todos os user_ids encontrados na aba users
            found_ids = [str(r.get('user_id', '')).strip() for r in all_rows]
            logger.debug(f"[SALARY] user_id recebido: {target_id!r}")
            logger.debug(f"[SALARY] user_ids na aba users: {found_ids}")

            matched_row = None
            for row in all_rows:
                row_id = str(row.get('user_id', '')).strip()
                if row_id == target_id:
                    matched_row = row
                    break

            if matched_row is None:
                logger.warning(f"[SALARY] Nenhuma linha encontrada para user_id={target_id!r}")
                return 0.0

            logger.debug(f"[SALARY] Linha usada para salário: {matched_row}")
            value = matched_row.get('salary', 0)
            salary = float(str(value).replace(',', '.')) if value else 0.0
            logger.info(f"[SALARY] Salário encontrado para {target_id!r}: {salary}")
            return salary

        except Exception as e:
            logger.error(f"❌ Erro ao buscar salário: {str(e)}")
            return 0.0

    async def get_monthly_summary(self, user_id: str) -> tuple[float, float]:
        """Calcula despesas e entradas do mês atual para o usuário.

        Retorna: (total_expense, total_income)

        - Filtra por transactions.user_id (nunca por transactions.id)
        - Normaliza type: expense/gasto/despesa/saida/saída → 'expense'
                          income/receita/entrada/recebido/freelance/venda → 'income'
        - Normaliza amount: aceita 50 | 50.00 | 50,00 | R$ 50,00
        - Normaliza date:   YYYY-MM-DD | DD/MM/YYYY | ISO | serial GSheets
        """
        EXPENSE_ALIASES = {"expense", "gasto", "despesa", "saida", "saída"}
        INCOME_ALIASES  = {"income", "receita", "entrada", "recebido",
                           "pix recebido", "freelance", "venda"}

        target_id = str(user_id).strip()
        mes_atual = datetime.now().strftime("%Y-%m")
        total_expense = 0.0
        total_income  = 0.0

        try:
            all_rows = await asyncio.to_thread(self.worksheet.get_all_records)

            if all_rows:
                logger.debug(f"[SUMMARY] Colunas: {list(all_rows[0].keys())}")
            logger.debug(f"[SUMMARY] user_id={target_id!r} | mês={mes_atual}")
            logger.debug(f"[SUMMARY] Total de linhas na aba: {len(all_rows)}")

            for i, row in enumerate(all_rows):
                row_trans_id = str(row.get('id', '')).strip()       # identificador único — só log
                row_user     = str(row.get('user_id', '')).strip()  # ← ÚNICO campo de filtro
                row_type_raw = str(row.get('type', '')).lower().strip()
                row_date_raw = row.get('date')
                row_amount   = row.get('amount', 0)
                row_desc     = row.get('description', '')

                logger.debug(
                    f"[SUMMARY] L{i+1}: id={row_trans_id!r} user_id={row_user!r} "
                    f"type={row_type_raw!r} date={row_date_raw!r} amount={row_amount!r}"
                )

                # Filtro 1: user_id exato — nunca comparar com coluna id
                if row_user != target_id:
                    logger.debug(f"[SUMMARY]   ↳ IGNORADA — user_id diferente")
                    continue

                # Filtro 2: mês atual com parser multi-formato
                row_ym = parse_date_to_ym(row_date_raw)
                logger.debug(f"[SUMMARY]   data bruta={str(row_date_raw)!r} → {row_ym!r}")
                if row_ym is None:
                    logger.debug(f"[SUMMARY]   ↳ IGNORADA — data não reconhecida")
                    continue
                if row_ym != mes_atual:
                    logger.debug(f"[SUMMARY]   ↳ IGNORADA — fora do mês ({row_ym} != {mes_atual})")
                    continue

                # Filtro 3: normalizar tipo
                if row_type_raw in EXPENSE_ALIASES:
                    tipo = "expense"
                elif row_type_raw in INCOME_ALIASES:
                    tipo = "income"
                else:
                    logger.debug(f"[SUMMARY]   ↳ IGNORADA — tipo desconhecido ({row_type_raw!r})")
                    continue

                # Normalizar amount: remove 'R$', espaços, troca vírgula por ponto
                valor = normalize_amount(row_amount)
                if valor is None:
                    logger.debug(f"[SUMMARY]   ↳ IGNORADA — amount inválido ({row_amount!r})")
                    continue

                if tipo == "expense":
                    total_expense += valor
                    logger.debug(f"[SUMMARY]   ↳ ✅ EXPENSE +{valor} (acum={total_expense:.2f})")
                else:
                    total_income += valor
                    logger.debug(f"[SUMMARY]   ↳ ✅ INCOME  +{valor} (acum={total_income:.2f})")

            logger.info(
                f"[SUMMARY] user_id={target_id!r} mês={mes_atual} → "
                f"expense=R${total_expense:.2f} income=R${total_income:.2f}"
            )

        except Exception as e:
            logger.error(f"❌ Erro ao calcular resumo mensal: {str(e)}")

        return total_expense, total_income


# Inicializar cliente Google Sheets (global)
try:
    gs_client = GoogleSheetsClient(CREDENTIALS_PATH, SHEET_ID)
except Exception as e:
    logger.warning(f"⚠️ Google Sheets não disponível: {str(e)}")
    gs_client = None


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

# Época base para serial dates do Google Sheets / Excel
_GS_EPOCH = datetime(1899, 12, 30)


def parse_date_to_ym(raw_date) -> str | None:
    """Converte qualquer formato de data suportado para 'YYYY-MM'.

    Formatos aceitos:
      - int/float  → serial date do Google Sheets  (ex: 46141)
      - YYYY-MM-DD (com ou sem hora/timezone)       (ex: '2026-04-27')
      - DD/MM/YYYY                                  (ex: '27/04/2026')
      - ISO 8601 com T                              (ex: '2026-04-27T17:54:22')

    Retorna 'YYYY-MM' ou None se não conseguir interpretar.
    """
    if raw_date is None or str(raw_date).strip() in ('', 'None'):
        return None

    # --- Serial date numérico (Google Sheets / Excel) ---
    try:
        serial = float(str(raw_date).strip())
        # Só trata como serial se não contiver '-' ou '/' (evita tratar '2026' como serial)
        if str(raw_date).strip().lstrip('-').replace('.', '', 1).isdigit():
            dt = _GS_EPOCH + timedelta(days=serial)
            return dt.strftime("%Y-%m")
    except (ValueError, TypeError):
        pass

    raw_str = str(raw_date).strip()

    # --- ISO 8601 com hora (ex: 2026-04-27T17:54:22 ou 2026-04-27 17:54:22) ---
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(raw_str[:19], fmt).strftime("%Y-%m")
        except ValueError:
            pass

    # --- YYYY-MM-DD ---
    try:
        return datetime.strptime(raw_str[:10], "%Y-%m-%d").strftime("%Y-%m")
    except ValueError:
        pass

    # --- DD/MM/YYYY ---
    try:
        return datetime.strptime(raw_str[:10], "%d/%m/%Y").strftime("%Y-%m")
    except ValueError:
        pass

    return None


def format_date_br(date_str: str) -> str:
    """Formata data de YYYY-MM-DD para DD/MM"""
    try:
        date_only = date_str.split("T")[0].split(" ")[0]
        date_obj = datetime.strptime(date_only, "%Y-%m-%d")
        return date_obj.strftime("%d/%m")
    except:
        return date_str


def format_currency_br(value) -> str:
    """Formata valor para padrão brasileiro com vírgula"""
    try:
        val = float(str(value).replace(',', '.'))
        s = f"{val:,.2f}"
        return s.replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return str(value)


def normalize_amount(raw) -> float | None:
    """Converte amount para float aceitando múltiplos formatos.

    Aceita: 50 | 50.00 | 50,00 | R$ 50.00 | R$ 50,00
    Retorna None se não conseguir converter.
    """
    try:
        s = str(raw).strip()
        s = s.upper().replace('R$', '').replace('\xa0', '').strip()
        # Se tiver vírgula E ponto: formato 1.234,56 → remove ponto de milhar, troca vírgula
        if ',' in s and '.' in s:
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '.')
        return float(s)
    except (ValueError, TypeError):
        return None


def detect_category(text: str) -> Tuple[str, str]:
    """Detecta categoria e tipo (expense/income) por keyword matching.
    Retorna: (categoria, type)
    """
    text_lower = text.lower()
    for keyword, (category, trans_type) in CATEGORY_MAP.items():
        if keyword in text_lower:
            return category, trans_type
    return "Outros", "expense"  # fallback padrão


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
# HELPERS — ONBOARDING
# ============================================================================

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _is_valid_email(text: str) -> bool:
    return bool(_EMAIL_RE.match(text.strip()))


async def _show_main_menu(target, parse_mode="Markdown"):
    """Envia ou edita a mensagem do menu principal.

    target pode ser update.message ou update.callback_query.
    """
    keyboard = [
        [InlineKeyboardButton("⚡ Novo Registro", callback_data="new_expense")],
        [InlineKeyboardButton("📊 Histórico",   callback_data="history")],
        [InlineKeyboardButton("💰 Relatório",   callback_data="report")],
        [InlineKeyboardButton("💵 Meu Salário", callback_data="salary_menu")],
        [InlineKeyboardButton("🗑️ Deletar Transação", callback_data="menu_delete_transaction")],
    ]
    text = (
        "🤖 *Bem-vindo ao FinBot!* 💰\n\n"
        "Escolha uma opção ou digite rapidamente:\n"
        "`/registro ifood 39`\n\n"
        "_Registre seus gastos e veja seu histórico!_"
    )
    markup = InlineKeyboardMarkup(keyboard)
    if hasattr(target, 'reply_text'):
        await target.reply_text(text, reply_markup=markup, parse_mode=parse_mode)
    else:
        await target.edit_message_text(text, reply_markup=markup, parse_mode=parse_mode)


# ============================================================================
# HANDLERS - START / MENU
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start — verifica onboarding antes de mostrar menu."""
    user_id = str(update.effective_user.id)
    logger.info(f"[START] user_id={user_id!r}")

    if gs_client and not await gs_client.user_exists(user_id):
        await onboarding_ask_email(update, context)
        return

    await _show_main_menu(update.message)


async def onboarding_ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia onboarding pedindo o email."""
    context.user_data['state'] = AWAITING_EMAIL
    msg = update.message or update.callback_query.message
    await msg.reply_text(
        "👋 *Olá! Antes de começar, precisamos de alguns dados.*\n\n"
        "Por favor, informe seu *email*:",
        parse_mode="Markdown"
    )


async def onboarding_process_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Valida email e avança para pedir salário."""
    text = update.message.text.strip()
    if not _is_valid_email(text):
        await update.message.reply_text(
            "❌ Email inválido. Use o formato: `usuario@email.com`",
            parse_mode="Markdown"
        )
        return  # permanece em AWAITING_EMAIL

    context.user_data['onboarding_email'] = text
    context.user_data['state'] = AWAITING_ONBOARDING_SALARY
    await update.message.reply_text(
        f"✅ Email salvo!\n\n"
        f"Agora informe seu *salário mensal*:\n"
        f"Exemplo: `3500` ou `3.500,00`",
        parse_mode="Markdown"
    )


async def onboarding_process_salary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Valida salário, persiste usuário e exibe menu principal."""
    salary = normalize_amount(update.message.text.strip())
    if salary is None or salary < 0:
        await update.message.reply_text(
            "❌ Valor inválido. Use apenas números, exemplo: `3500` ou `3.500,00`",
            parse_mode="Markdown"
        )
        return  # permanece em AWAITING_ONBOARDING_SALARY

    user_id = str(update.effective_user.id)
    email   = context.user_data.get('onboarding_email', '')

    if not gs_client:
        await update.message.reply_text("❌ Erro interno. Tente novamente mais tarde.")
        return

    ok = await gs_client.create_user(user_id, email, salary)
    if not ok:
        await update.message.reply_text(
            "❌ Não foi possível salvar o cadastro. Tente novamente."
        )
        return

    # Limpa estado de onboarding
    context.user_data.pop('state', None)
    context.user_data.pop('onboarding_email', None)

    await update.message.reply_text(
        "✅ *Cadastro concluído!* Bem-vindo ao FinBot 🎉",
        parse_mode="Markdown"
    )
    await _show_main_menu(update.message)


# ============================================================================
# HANDLERS - CREATE (NOVO GASTO)
# ============================================================================

async def quick_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /gasto — Modo rápido"""
    description, amount, error = parse_quick_expense(update.message.text)
    if error:
        await update.message.reply_text(
            f"❌ {error}\n\nUso correto: `/registro ifood 39`",
            parse_mode="Markdown"
        )
        return

    category, trans_type = detect_category(description)
    context.user_data['pending_expense'] = {
        'description': description,
        'amount':      amount,
        'category':    category,
        'type':        trans_type,
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
    type_emoji = "💰" if expense['type'] == "income" else "💸"
    text = (
        f"Confirmando:\n"
        f"📝 *Descrição:* {expense['description']}\n"
        f"💵 *Valor:* R$ {expense['amount']:.2f}\n"
        f"🏷️ *Categoria:* {expense['category']}\n"
        f"{type_emoji} *Tipo:* {'Recebimento' if expense['type'] == 'income' else 'Gasto'}\n"
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
        "type":        expense['type'],
        "date":        expense['date'],
        "_source":     "telegram_bot",
        "_timestamp":  datetime.now().isoformat()
    }

    try:
        logger.info(f"Enviando gasto para Zap 1: {payload}")
        response = _post_zapier(ZAPIER_WEBHOOK_EXPENSE, payload)

        if response.status_code == 200:
            await query.edit_message_text(
                "✅ *Transação registrada com sucesso!*\n\n"
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

    transactions = await gs_client.get_user_transactions(user_id)
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

    transactions = await gs_client.get_user_transactions(user_id)
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
    """Mostra menu de salário com saldo calculado em tempo real.

    saldo = salary + total_income - total_expense
    """
    query   = update.callback_query
    user_id = str(update.effective_user.id)
    logger.info(f"[SALARY_MENU] user_id recebido pelo Telegram: {user_id!r}")

    if not gs_client:
        await query.edit_message_text("❌ Erro: Conexão com Google Sheets não disponível")
        return

    salary, (total_expense, total_income) = await asyncio.gather(
        gs_client.get_user_salary(user_id),
        gs_client.get_monthly_summary(user_id)
    )
    balance = salary + total_income - total_expense

    if salary > 0:
        balance_emoji = "🟢" if balance >= 0 else "🔴"
        message = (
            f"💵 *Resumo do Mês*\n\n"
            f"💰 Salário registrado: R$ {salary:.2f}\n"
            f"📥 Entradas este mês: R$ {total_income:.2f}\n"
            f"💸 Gastos do mês: R$ {total_expense:.2f}\n"
            f"{balance_emoji} Saldo disponível: R$ {balance:.2f}\n\n"
            f"_Deseja atualizar o salário?_"
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
    """Comando /salario — exibe resumo financeiro calculado em tempo real.

    saldo = salary + total_income - total_expense
    """
    user_id = str(update.effective_user.id)
    logger.info(f"[SALARIO_CMD] user_id recebido pelo Telegram: {user_id!r}")

    if not gs_client:
        await update.message.reply_text("❌ Erro: Conexão com Google Sheets não disponível")
        return

    salary, (total_expense, total_income) = await asyncio.gather(
        gs_client.get_user_salary(user_id),
        gs_client.get_monthly_summary(user_id)
    )
    balance = salary + total_income - total_expense

    if salary > 0:
        balance_emoji = "🟢" if balance >= 0 else "🔴"
        message = (
            f"💵 *Resumo do Mês*\n\n"
            f"💰 Salário registrado: R$ {salary:.2f}\n"
            f"📥 Entradas este mês: R$ {total_income:.2f}\n"
            f"💸 Gastos do mês: R$ {total_expense:.2f}\n"
            f"{balance_emoji} Saldo disponível: R$ {balance:.2f}\n\n"
            f"_Deseja atualizar o salário?_"
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
# HANDLERS - DELETE (EXCLUSÃO)
# ============================================================================

async def show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra as últimas transações para o usuário selecionar e deletar."""
    query = update.callback_query
    user_id = str(update.effective_user.id)
    
    if not gs_client:
        await query.edit_message_text("❌ Erro: Conexão com Google Sheets não disponível")
        return

    transactions = await gs_client.get_user_transactions(user_id)
    
    recent_transactions = list(reversed(transactions))[:10]
    
    if not recent_transactions:
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "Você ainda não tem transações para deletar.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    keyboard = []
    for trans in recent_transactions:
        t_id = trans.get('id')
        if not t_id:
            continue
            
        date = trans.get('date', '')
        desc = trans.get('description', 'N/A')
        amount = trans.get('amount', 0)
        
        btn_text = f"{format_date_br(date)} • {desc} • R$ {format_currency_br(amount)}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"delete_select:{t_id}")])

    keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")])
    
    await query.edit_message_text(
        "🗑️ *Selecione a transação para deletar:*\n"
        "_Exibindo as 10 mais recentes._",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def delete_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra confirmação para deletar a transação."""
    query = update.callback_query
    user_id = str(update.effective_user.id)
    transaction_id = query.data.split(":", 1)[1]
    
    if not gs_client:
        await query.edit_message_text("❌ Erro: Conexão com Google Sheets não disponível")
        return
        
    transactions = await gs_client.get_user_transactions(user_id)
    selected_trans = next((t for t in transactions if str(t.get('id')) == str(transaction_id)), None)
    
    if not selected_trans:
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="menu_delete_transaction")]]
        await query.edit_message_text(
            "❌ Transação não encontrada. Pode já ter sido deletada.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
        
    type_emoji = "💰" if selected_trans.get('type') == "income" else "💸"
    text = (
        f"🗑️ *Confirmar exclusão?*\n\n"
        f"📝 *Descrição:* {selected_trans.get('description')}\n"
        f"💵 *Valor:* R$ {format_currency_br(selected_trans.get('amount'))}\n"
        f"🏷️ *Categoria:* {selected_trans.get('category')}\n"
        f"{type_emoji} *Tipo:* {'Recebimento' if selected_trans.get('type') == 'income' else 'Gasto'}\n"
        f"📅 *Data:* {selected_trans.get('date')}"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Sim, deletar", callback_data=f"delete_confirm:{transaction_id}")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="delete_cancel")]
    ]
    
    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )

async def delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia o comando de delete para o Zapier."""
    query = update.callback_query
    user_id = str(update.effective_user.id)
    transaction_id = query.data.split(":", 1)[1]
    
    if not gs_client:
        await query.edit_message_text("❌ Erro: Conexão com Google Sheets não disponível")
        return
        
    transactions = await gs_client.get_user_transactions(user_id)
    selected_trans = next((t for t in transactions if str(t.get('id')) == str(transaction_id)), None)
    
    if not selected_trans:
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="menu_delete_transaction")]]
        await query.edit_message_text(
            "❌ Transação não encontrada ou você não tem permissão para deletá-la.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    payload = {
        "action": "delete",
        "user_id": user_id,
        "transaction_id": transaction_id,
        "_source": "telegram_bot",
        "_timestamp": datetime.now().isoformat()
    }
    
    try:
        logger.info(f"Enviando delete para Zap 1: {payload}")
        response = _post_zapier(ZAPIER_WEBHOOK_EXPENSE, payload)
        
        if response.status_code >= 200 and response.status_code < 300:
            keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")]]
            await query.edit_message_text(
                "✅ Transação deletada com sucesso!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            logger.error(f"Erro Zap 1 (Delete): {response.status_code} — {response.text}")
            keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="menu_delete_transaction")]]
            await query.edit_message_text(
                "❌ Não consegui deletar essa transação agora. Tente novamente.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
    except requests.exceptions.Timeout:
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="menu_delete_transaction")]]
        await query.edit_message_text("⚠️ Webhook timeout. Tente novamente.", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Erro ao enviar delete: {str(e)}")
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="menu_delete_transaction")]]
        await query.edit_message_text(f"❌ Erro: {str(e)}", reply_markup=InlineKeyboardMarkup(keyboard))


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
            "O que deseja registrar?\n"
            "Gasto: `ifood 39` ou `uber 25`\n"
            "Recebimento: `salário 3500` ou `freelance 800`",
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
            [InlineKeyboardButton("⚡ Novo Registro", callback_data="new_expense")],
            [InlineKeyboardButton("📊 Histórico",   callback_data="history")],
            [InlineKeyboardButton("💰 Relatório",   callback_data="report")],
            [InlineKeyboardButton("💵 Meu Salário", callback_data="salary_menu")],
            [InlineKeyboardButton("🗑️ Deletar Transação", callback_data="menu_delete_transaction")],
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

    elif query.data == "menu_delete_transaction":
        await show_delete_menu(update, context)

    elif query.data.startswith("delete_select:"):
        await delete_select(update, context)

    elif query.data.startswith("delete_confirm:"):
        await delete_confirm(update, context)

    elif query.data == "delete_cancel":
        await show_delete_menu(update, context)


# ============================================================================
# HANDLER - MENSAGENS DE TEXTO (roteador por estado)
# ============================================================================

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagens de texto — roteia pelo estado atual"""
    text  = update.message.text
    state = context.user_data.get('state')

    # ---- Onboarding (prioridade máxima) ----
    if state == AWAITING_EMAIL:
        await onboarding_process_email(update, context)
        return

    if state == AWAITING_ONBOARDING_SALARY:
        await onboarding_process_salary(update, context)
        return

    # ---- Bloqueia ações se onboarding ainda pendente ----
    if gs_client:
        user_id = str(update.effective_user.id)
        if not await gs_client.user_exists(user_id):
            await update.message.reply_text(
                "⚠️ Finalize seu cadastro primeiro. Use /start para iniciar."
            )
            return

    # Estado: aguardando atualização de salário
    if state == AWAITING_SALARY:
        await process_salary_input(update, context)
        return

    # Modo rápido via /registro
    if text.startswith("/registro"):
        await quick_expense(update, context)
        return

    # Estado: aguardando gasto pelo menu
    if state == AWAITING_EXPENSE:
        description, amount, error = parse_quick_expense("/registro " + text)
        if error:
            await update.message.reply_text(
                f"❌ {error}\nFormato: 'ifood 39'",
                parse_mode="Markdown"
            )
            return
        category, trans_type = detect_category(description)
        context.user_data['pending_expense'] = {
            'description': description,
            'amount':      amount,
            'category':    category,
            'type':        trans_type,
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
                category, trans_type = detect_category(parts[0])
                context.user_data['pending_expense']['description'] = parts[0]
                context.user_data['pending_expense']['amount']      = amount
                context.user_data['pending_expense']['category']    = category
                context.user_data['pending_expense']['type']        = trans_type
                await show_confirmation(update, context)
                return
            except ValueError:
                pass
        category, trans_type = detect_category(text)
        context.user_data['pending_expense']['description'] = text
        context.user_data['pending_expense']['category']    = category
        context.user_data['pending_expense']['type']        = trans_type
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
    app.add_handler(CommandHandler("registro",     quick_expense))
    app.add_handler(CommandHandler("historico", command_historico))
    app.add_handler(CommandHandler("salario",   command_salario))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("✅ FinBot iniciando...")
    app.run_polling()


if __name__ == "__main__":
    main()
