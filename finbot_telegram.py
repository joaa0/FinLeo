import os
import requests
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ZAPIER_WEBHOOK = os.getenv("ZAPIER_WEBHOOK_URL")

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
        "_Registre seus gastos de forma rápida e inteligente!_"
    )
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    return MENU


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
        return AWAITING_EXPENSE
    
    elif query.data == "history":
        await query.edit_message_text(
            "📊 *Histórico:*\n\n"
            "Funcionalidade em desenvolvimento...\n"
            "(Integrando com Google Sheets)",
            parse_mode="Markdown"
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="back_to_menu")]]
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
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
        # Adiciona o /gasto para parsear a mensagem como quick_expense
        description, amount, error = parse_quick_expense("/gasto " + text)
        if error:
            await update.message.reply_text(
                f"❌ {error}\nFormato: 'ifood 39'",
                parse_mode="Markdown"
            )
            return
        
        category = detect_category(description)
        
        # Salva para confirmação
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
        logger.warning("ZAPIER_WEBHOOK_URL não configurado. Teste localmente sem envio.")
    
    # Criar aplicação
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gasto", quick_expense))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("FinBot iniciando...")
    
    # Polling
    app.run_polling()


if __name__ == "__main__":
    main()
