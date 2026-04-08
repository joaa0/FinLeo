# FinBot Telegram Assistant — Especificação Técnica

**Projeto:** Assistente financeiro com IA integrado ao Telegram  
**Status:** Design aprovado (Dual-mode interface)  
**Data:** Abril 2025

---

## 1. Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                   TELEGRAM BOT (Trigger)                     │
├─────────────────────────────────────────────────────────────┤
│  • Menu Principal (Inline Buttons)                           │
│  • Modo Rápido: /gasto <descrição> <valor>                 │
│  • Modo Completo: [Novo Gasto] → Entrada → Seleção → OK   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                      ZAPIER WEBHOOK                          │
├─────────────────────────────────────────────────────────────┤
│  • Recebe JSON estruturado do bot                           │
│  • Passa para Google Generative AI (classificação)          │
│  • Envia para Google Sheets                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    GOOGLE SHEETS                             │
├─────────────────────────────────────────────────────────────┤
│  Data | Descrição | Valor | Categoria | Tipo | Usuário      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Fluxo de Interação — Opção A (Menu Completo)

### 2.1 First-Time User

```
Bot: "Bem-vindo ao FinBot! 💰"
     [⚡ Novo Gasto] [📊 Histórico] [💰 Relatório]
     
     OU digite: /gasto ifood 39

Usuário clica: [⚡ Novo Gasto]
Bot: "Qual foi o gasto? (ex: ifood 39 reais)"

Usuário: "ifood 39"
Bot: "Confirmando:
     📝 Descrição: ifood
     💵 Valor: R$ 39,00
     
     Categoria sugerida: [Alimentação] [Transporte] [Outro]"

Usuário clica: [Alimentação]
Bot: "✅ Gasto registrado!
     Data: 02/04/2025
     Descrição: ifood
     Valor: R$ 39,00
     Categoria: Alimentação"
```

### 2.2 Fluxo de Estados (State Machine)

```
START
  │
  ├─→ MENU_PRINCIPAL
  │     │
  │     ├─→ [⚡ Novo Gasto] → AGUARDA_ENTRADA
  │     ├─→ [📊 Histórico] → MOSTRA_HISTÓRICO
  │     └─→ [💰 Relatório] → GERA_RELATÓRIO
  │
  └─→ COMANDO_DIRETO (/gasto ...)
        │
        ├─→ Valida input
        └─→ AGUARDA_CONFIRMAÇÃO
              │
              ├─→ [Confirmar] → ENVIANDO
              └─→ [Editar] → AGUARDA_ENTRADA
```

---

## 3. Opção B (Comando Direto) — Modo Rápido

```
Usuário: /gasto ifood 39
Bot: "Processando...
     📝 Descrição: ifood
     💵 Valor: R$ 39,00
     Categoria: Alimentação
     Data: 02/04/2025
     
     [✅ Confirmar] [✏️ Editar]"

Usuário clica: [✅ Confirmar]
Bot: "✅ Gasto registrado!"
```

---

## 4. Estrutura de Dados

### 4.1 Payload para Zapier

```json
{
  "action": "create",
  "user_id": "user_telegram_id",
  "description": "ifood",
  "amount": 39,
  "category": "Alimentação",
  "type": "expense",
  "date": "2025-04-02",
  "filter": null,
  "target": null,
  "updates": null,
  "_source": "telegram_bot"
}
```

### 4.2 Mapeamento de Categorias (Hardcoded no Bot)

```python
CATEGORY_MAP = {
    # Alimentação
    "ifood": "Alimentação",
    "uber eats": "Alimentação",
    "rappi": "Alimentação",
    "pizza": "Alimentação",
    "restaurante": "Alimentação",
    "mercado": "Compras",
    "supermercado": "Compras",
    
    # Transporte
    "uber": "Transporte",
    "99": "Transporte",
    "taxi": "Transporte",
    "passagem": "Transporte",
    
    # Entretenimento
    "netflix": "Entretenimento",
    "spotify": "Entretenimento",
    "cinema": "Entretenimento",
    
    # Saúde
    "farmácia": "Saúde",
    "médico": "Saúde",
    "dentista": "Saúde",
    
    # Educação
    "curso": "Educação",
    "livro": "Educação",
}
```

---

## 5. Código Python — Bot Telegram

### 5.1 Setup Inicial

```python
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, \
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from datetime import datetime
import json

# Configuração
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ZAPIER_WEBHOOK = os.getenv("ZAPIER_WEBHOOK_URL")

# Estados da conversa
MENU, AWAITING_EXPENSE, SELECTING_CATEGORY, CONFIRMING = range(4)

# Mapeamento de categorias
CATEGORY_MAP = {
    "ifood": "Alimentação",
    "uber eats": "Alimentação",
    "rappi": "Alimentação",
    "uber": "Transporte",
    "99": "Transporte",
    "netflix": "Entretenimento",
    "spotify": "Entretenimento",
    "farmácia": "Saúde",
    "mercado": "Compras",
}

CATEGORIES = [
    "Alimentação", "Transporte", "Entretenimento",
    "Saúde", "Educação", "Moradia", "Compras", "Outros"
]
```

### 5.2 Comando START (Menu Principal)

```python
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra o menu principal com inline buttons"""
    keyboard = [
        [InlineKeyboardButton("⚡ Novo Gasto", callback_data="new_expense")],
        [InlineKeyboardButton("📊 Histórico", callback_data="history")],
        [InlineKeyboardButton("💰 Relatório", callback_data="report")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Bem-vindo ao FinBot! 💰\n\n"
        "Escolha uma opção ou digite rapidamente:\n"
        "`/gasto ifood 39`",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    return MENU
```

### 5.3 Comando Rápido (/gasto)

```python
async def quick_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Modo rápido: /gasto <descrição> <valor>"""
    
    try:
        # Parse: /gasto ifood 39
        args = update.message.text.split()
        
        if len(args) < 3:
            await update.message.reply_text(
                "❌ Formato inválido!\n"
                "Use: `/gasto ifood 39`",
                parse_mode="Markdown"
            )
            return
        
        description = args[1]
        try:
            amount = float(args[2])
        except ValueError:
            await update.message.reply_text(
                "❌ Valor inválido! Use números.",
                parse_mode="Markdown"
            )
            return
        
        # Detecta categoria
        category = detect_category(description)
        
        # Armazena contexto para confirmação
        context.user_data['pending_expense'] = {
            'description': description,
            'amount': amount,
            'category': category,
            'date': datetime.now().strftime("%Y-%m-%d")
        }
        
        # Mostra preview com botões
        await show_confirmation_inline(update, context)
        return CONFIRMING
        
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")
```

### 5.4 Menu Button Handler

```python
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa cliques nos inline buttons"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_expense":
        await query.edit_message_text(
            text="Qual foi o gasto?\n"
                 "Exemplo: `ifood 39 reais` ou `uber 25`",
            parse_mode="Markdown"
        )
        return AWAITING_EXPENSE
    
    elif query.data == "history":
        await query.edit_message_text(text="📊 Histórico dos últimos gastos:\n(Integrando com Google Sheets...)")
        return MENU
    
    elif query.data == "report":
        await query.edit_message_text(text="💰 Relatório mensal:\n(Integrando com Google Sheets...)")
        return MENU
```

### 5.5 Função de Confirmação com Inline Buttons

```python
async def show_confirmation_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra preview do gasto com opções [Confirmar] [Editar]"""
    
    expense = context.user_data['pending_expense']
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar", callback_data="confirm_expense"),
            InlineKeyboardButton("✏️ Editar", callback_data="edit_expense")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    preview = (
        f"📝 Descrição: {expense['description']}\n"
        f"💵 Valor: R$ {expense['amount']:.2f}\n"
        f"🏷️ Categoria: {expense['category']}\n"
        f"📅 Data: {expense['date']}"
    )
    
    await update.message.reply_text(
        f"Confirmando:\n{preview}",
        reply_markup=reply_markup
    )
```

### 5.6 Envio para Zapier

```python
async def send_to_zapier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia gasto para Zapier"""
    
    expense = context.user_data.get('pending_expense')
    
    if not expense:
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
        "_source": "telegram_bot"
    }
    
    try:
        response = requests.post(ZAPIER_WEBHOOK, json=payload, timeout=10)
        
        if response.status_code == 200:
            await update.callback_query.edit_message_text(
                text="✅ Gasto registrado com sucesso!\n\n"
                     f"📝 {expense['description']}\n"
                     f"💵 R$ {expense['amount']:.2f}\n"
                     f"🏷️ {expense['category']}"
            )
        else:
            await update.callback_query.edit_message_text(
                text=f"❌ Erro ao registrar: {response.status_code}"
            )
    
    except Exception as e:
        await update.callback_query.edit_message_text(
            text=f"❌ Erro: {str(e)}"
        )
    
    context.user_data.pop('pending_expense', None)
```

### 5.7 Main Application

```python
def main():
    """Inicializa o bot"""
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gasto", quick_expense))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Confirmar gasto
    app.add_handler(
        CallbackQueryHandler(
            lambda u, c: send_to_zapier(u, c) if u.callback_query.data == "confirm_expense" else None,
            pattern="confirm_expense"
        )
    )
    
    # Iniciar
    app.run_polling()

if __name__ == "__main__":
    main()
```

---

## 6. Integração com Zapier

### 6.1 Webhook Setup

1. **Criar Zap:**
   - Trigger: `Webhooks by Zapier` → Catch raw hook
   - Copiar URL
   - Passar ao bot como `ZAPIER_WEBHOOK_URL`

2. **Estrutura do Zap:**
   ```
   [Webhook Trigger] 
       ↓
   [Google Generative AI] (classificação inteligente)
       ↓
   [Google Sheets] (adicionar linha)
   ```

### 6.2 Mapeamento de Dados (Zapier)

| Campo Zapier | Origem |
|---|---|
| `user_id` | `data.user_id` |
| `description` | `data.description` |
| `amount` | `data.amount` |
| `category` | `data.category` |
| `date` | `data.date` |
| `type` | `data.type` |

---

## 7. Código de Configuração (Environment)

### 7.1 .env

```bash
TELEGRAM_BOT_TOKEN=seu_token_aqui
ZAPIER_WEBHOOK_URL=https://hooks.zapier.com/hooks/catch/xxxxx/yyyy/
GOOGLE_SHEETS_ID=sua_planilha_id
```

### 7.2 requirements.txt

```
python-telegram-bot==20.0
requests==2.31.0
python-dotenv==1.0.0
```

---

## 8. Função de Detecção de Categoria

```python
def detect_category(text: str) -> str:
    """Detecta categoria por keyword matching"""
    text_lower = text.lower()
    
    for keyword, category in CATEGORY_MAP.items():
        if keyword in text_lower:
            return category
    
    return "Outros"
```

---

## 9. Fluxo de Edição (Futuro)

```python
async def edit_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite editar antes de confirmar"""
    
    keyboard = [
        [InlineKeyboardButton("📝 Descrição", callback_data="edit_desc")],
        [InlineKeyboardButton("💵 Valor", callback_data="edit_amount")],
        [InlineKeyboardButton("🏷️ Categoria", callback_data="edit_category")],
        [InlineKeyboardButton("✅ Pronto!", callback_data="done_editing")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text="O que deseja editar?",
        reply_markup=reply_markup
    )
```

---

## 10. Próximos Passos

### Phase 1 (MVP)
- ✅ Menu Principal (3 botões)
- ✅ Comando rápido `/gasto`
- ✅ Detecção de categoria
- ✅ Envio para Zapier

### Phase 2 (Expansão)
- Edição de transações
- Histórico com botões de navegação
- Relatórios simples
- Limite de gastos com alertas

### Phase 3 (Avançado)
- Web App integrado (opcional)
- Gráficos de gastos
- Metas financeiras
- Exportar para Excel

---

## 11. Deployment

### 11.1 Deploy no Heroku / Railway

```bash
git init
git add .
git commit -m "Initial bot commit"
git push heroku main
```

### 11.2 Webhook Setup (Production)

```python
app.run_webhook(
    listen="0.0.0.0",
    port=8000,
    url_path=TELEGRAM_TOKEN,
    webhook_url=f"https://seu-dominio.com/{TELEGRAM_TOKEN}"
)
```

---

## Resumo

✅ **Opção A (Menu):** Menu principal intuitivo → Novo Gasto → Confirmação  
✅ **Opção B (Rápida):** `/gasto ifood 39` → Confirmação  
✅ **Integração Zapier:** Webhook → Google Sheets  
✅ **Categorização Automática:** Keywords + Fallback "Outros"  

**Próximo:** Clonar este código, configurar tokens e fazer deploy! 🚀
