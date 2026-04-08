# FinBot Telegram — Guia de Implementação

Assistente financeiro com IA integrado ao Telegram. Suporta dois modos de entrada:
- **Menu Completo** (`/start`) — Interface visual com botões
- **Modo Rápido** (`/gasto ifood 39`) — Comando direto

---

## 🚀 Quick Start (5 minutos)

### 1. Criar Bot no Telegram

1. Abra o Telegram e pesquise por **@BotFather**
2. Digite `/newbot`
3. Siga as instruções (nome, username)
4. **Copie o token** (exemplo: `123456789:ABCDEFghijklmnopqrstuvwxyz`)

### 2. Configurar Zapier Webhook

1. Acesse [zapier.com](https://zapier.com)
2. Crie um novo Zap:
   - **Trigger:** `Webhooks by Zapier` → `Catch raw hook`
   - **Copie o URL** (exemplo: `https://hooks.zapier.com/hooks/catch/xxxxx/yyyy/`)

### 3. Configurar Variáveis de Ambiente

```bash
# Clone ou crie a pasta do projeto
mkdir finbot && cd finbot

# Copie os arquivos Python
cp finbot_telegram.py telegram_bot_spec.md requirements.txt .env.example .

# Crie um .env real
cp .env.example .env

# Edite .env com seus valores
nano .env
```

**Seu `.env` deve ter:**
```
TELEGRAM_BOT_TOKEN=seu_token_do_botfather_aqui
ZAPIER_WEBHOOK_URL=https://hooks.zapier.com/hooks/catch/xxxxx/yyyy/
```

### 4. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 5. Rodar o Bot

```bash
python finbot_telegram.py
```

Você verá: `FinBot iniciando...`

---

## 📱 Como Usar o Bot

### Modo 1: Menu Completo

```
/start
     ↓
[⚡ Novo Gasto] [📊 Histórico] [💰 Relatório]
     ↓
Clique em "Novo Gasto"
     ↓
Digite: "ifood 39"
     ↓
[✅ Confirmar] [✏️ Editar]
     ↓
Bot envia para Zapier → Google Sheets
```

### Modo 2: Comando Rápido

```
/gasto ifood 39
     ↓
Bot mostra preview
     ↓
[✅ Confirmar] [✏️ Editar]
     ↓
Pronto! Gasto registrado
```

---

## 🔗 Integrando com Google Sheets

### Passo 1: Criar o Zap no Zapier

1. **Trigger:** Webhooks by Zapier → Catch raw hook
2. **Action 1:** Google Generative AI (opcional — para classificação inteligente)
3. **Action 2:** Google Sheets → Create spreadsheet row

### Passo 2: Mapear Campos

| Campo Zapier | Origem (Bot) |
|---|---|
| `user_id` | `data.user_id` |
| `description` | `data.description` |
| `amount` | `data.amount` |
| `category` | `data.category` |
| `date` | `data.date` |
| `type` | `data.type` |

### Passo 3: Google Sheets Setup

Crie uma planilha com colunas:
```
A: Data
B: Descrição
C: Valor
D: Categoria
E: Tipo (income/expense)
F: Usuário
G: Hora
```

---

## 📊 Estrutura do Payload (Zapier)

Cada gasto enviado é um JSON assim:

```json
{
  "action": "create",
  "user_id": "123456789",
  "description": "ifood",
  "amount": 39.0,
  "category": "Alimentação",
  "type": "expense",
  "date": "2025-04-02",
  "_source": "telegram_bot",
  "_timestamp": "2025-04-02T14:30:00"
}
```

---

## 🏷️ Categorias Reconhecidas (Automático)

O bot detecta automaticamente:

| Palavra-chave | Categoria |
|---|---|
| ifood, uber eats, pizza | Alimentação |
| uber, 99, taxi | Transporte |
| netflix, spotify, cinema | Entretenimento |
| farmácia, médico | Saúde |
| mercado, supermercado | Compras |
| curso, livro | Educação |

**Se não detectar, usa:** "Outros"

---

## 🛠️ Troubleshooting

### "TELEGRAM_BOT_TOKEN não configurado!"

✅ Verifique se `.env` existe e tem o token correto

```bash
cat .env | grep TELEGRAM_BOT_TOKEN
```

### Bot não responde a /start

✅ Verifique:
- Token está correto (copie novamente de @BotFather)
- Bot está rodando (`python finbot_telegram.py`)
- Você adicionou o bot à lista de contatos

### Webhook timeout no Zapier

✅ Zapier pode estar lento. Tente:
- Testar webhook manualmente no Zapier
- Aumentar timeout em `send_to_zapier()`: `timeout=15`

### "Não consigo encontrar meus dados no Google Sheets"

✅ Verifique:
- Zap está ativado no Zapier
- Webhook URL está correta
- Google Sheets está compartilhado (se usar email)

---

## 🚢 Deploy em Produção

### Opção 1: Railway (Recomendado)

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Deploy
railway up
```

### Opção 2: Heroku

```bash
heroku login
heroku create seu-app-name
heroku config:set TELEGRAM_BOT_TOKEN=seu_token
heroku config:set ZAPIER_WEBHOOK_URL=seu_webhook
git push heroku main
```

### Opção 3: Replit

1. Suba o código para Replit
2. Configure variáveis de ambiente
3. Run → Select `finbot_telegram.py`
4. Use **Replit UptimeRobot** para manter vivo

---

## 📈 Roadmap

### MVP (Agora)
- ✅ Menu principal
- ✅ Comando `/gasto`
- ✅ Detecção de categoria
- ✅ Envio para Zapier

### Fase 2 (Próximas 2 semanas)
- Histórico de gastos (com paginação)
- Relatório mensal simples
- Edição de transações existentes

### Fase 3 (Futuro)
- Gráficos de gastos (plotly/matplotlib)
- Alertas de limite
- Web App integrado
- Multi-idioma (EN/PT/ES)
- Suporte a renda (income)

---

## 💡 Dicas de Uso

### Adicionar Novas Categorias

Edite `CATEGORY_MAP` em `finbot_telegram.py`:

```python
CATEGORY_MAP = {
    "burger king": "Alimentação",  # Adicione aqui
    "seu_keyword": "Sua Categoria",
}
```

### Customizar Mensagens

Busque por `await query.edit_message_text` e customize o texto.

### Adicionar Novos Botões

```python
keyboard = [
    [InlineKeyboardButton("📈 Meta de Gastos", callback_data="budget")],
    [InlineKeyboardButton("🔄 Últimos 7 dias", callback_data="week")],
]
```

---

## 📞 Suporte

- Erro? Cheque os logs: `python finbot_telegram.py` (vai mostrar detalhes)
- Tire screenshots do erro
- Verifique [documentação do python-telegram-bot](https://docs.python-telegram-bot.org/)

---

## 📝 Licença

Uso livre para projetos pessoais e comerciais.

---

**Pronto para começar?** Execute:

```bash
python finbot_telegram.py
```

E mande uma mensagem para seu bot no Telegram! 🚀
