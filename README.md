# 🤖 FinBot — Assistente Financeiro no Telegram

> Registre registros, acompanhe seu histórico e controle seu saldo mensal direto no Telegram — com IA e Google Sheets como banco de dados.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=flat&logo=telegram&logoColor=white)
![Google Sheets](https://img.shields.io/badge/Google_Sheets-Database-34A853?style=flat&logo=googlesheets&logoColor=white)
![Zapier](https://img.shields.io/badge/Zapier-Automation-FF4A00?style=flat&logo=zapier&logoColor=white)
![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat&logo=railway&logoColor=white)

---

## ✨ Funcionalidades

| Feature | Descrição |
|---|---|
| ⚡ **Novo Registro** | Registra uma transação via menu ou comando rápido `/registro` |
| 📊 **Histórico** | Lista transações com paginação, direto do Google Sheets |
| 💵 **Salário** | Registra o salário mensal e exibe o saldo disponível em tempo real |
| 💰 **Relatório** | *(em desenvolvimento)* Resumo mensal por categoria via e-mail |
| 🏷️ **Auto-categoria** | Detecta a categoria automaticamente pela descrição do registro |
| 🤖 **Normalização por IA** | MistralAI (via Zapier) valida e normaliza os dados antes de salvar |

---

## 🏗️ Arquitetura

```
Telegram Bot (Python)
       │
       ├── CREATE ──► Zapier Zap 1 ──► Mistral AI ──► Google Sheets (transactions)
       │
       ├── READ ────► Google Sheets (transactions) — leitura direta via gspread
       │
       └── SALARY ──► Zapier Zap 2 ──────────────► Google Sheets (users)
```

O bot tem **duas camadas**:

- **Frontend (finbot_telegram.py):** gerencia a conversa no Telegram, estados da UI e roteamento
- **Backend (Zapier):** processa os dados, aplica IA para normalização e persiste no Google Sheets

### Zap 1 — CRUD de Transações
Recebe o payload do bot → normaliza com Python → valida com Mistral AI → insere/atualiza/deleta no Sheets → notifica via Telegram e e-mail.

### Zap 2 — Salário
Recebe `user_id` + valor do salário → salva/atualiza na aba `users` do Sheets.

---

## 🗂️ Estrutura do Google Sheets

**Aba `transactions`**

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | string | `{user_id}_{timestamp}` |
| `user_id` | string | ID numérico do Telegram |
| `date` | date | Data da transação (YYYY-MM-DD) |
| `description` | string | Descrição do registro |
| `category` | string | Categoria detectada automaticamente |
| `amount` | float | Valor em R$ |
| `type` | string | `expense` ou `income` |
| `created_at` | date | Data de criação |
| `updated_at` | date | Data da última atualização |

**Aba `users`**

| Coluna | Tipo | Descrição |
|---|---|---|
| `user_id` | string | ID numérico do Telegram |
| `email` | string | E-mail para relatórios |
| `registered_date` | date | Data de cadastro |
| `salary` | float | Salário mensal em R$ |
| `updated_at` | datetime | Última atualização |

---

## 🚀 Como Rodar

### Pré-requisitos

- Python 3.10+
- Conta no [Telegram](https://t.me/BotFather) para criar o bot
- Conta no [Zapier](https://zapier.com) (plano gratuito suporta 2 Zaps)
- Google Sheets com as abas `transactions` e `users` configuradas
- Credenciais de Service Account do Google Cloud

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/finbot.git
cd finbot
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Configure o `.env`

Copie o arquivo de exemplo e preencha com seus valores:

```bash
cp .env.example .env
```

```env
TELEGRAM_BOT_TOKEN=
ZAPIER_WEBHOOK_EXPENSE=
ZAPIER_WEBHOOK_SALARY=
GOOGLE_SHEET_ID=
GOOGLE_CREDENTIALS_PATH=credentials.json   # desenvolvimento local
GOOGLE_CREDENTIALS_JSON=                   # Railway (cole o JSON completo)
SHEET_NAME=transactions
USERS_SHEET_NAME=users
```

### 4. Rode localmente

```bash
python finbot_telegram.py
```

> ⚠️ Se o bot já estiver rodando no Railway, pause o serviço lá antes de rodar localmente. O Telegram não aceita dois processos de polling simultâneos com o mesmo token.

---

## ☁️ Deploy no Railway

1. Crie um novo projeto no [Railway](https://railway.app)
2. Conecte o repositório GitHub
3. Em **Variables**, adicione todas as variáveis do `.env`
4. Para `GOOGLE_CREDENTIALS_JSON`, cole o conteúdo completo do arquivo `.json` de credenciais
5. Deixe `GOOGLE_CREDENTIALS_PATH` vazio
6. O Railway detecta automaticamente o `requirements.txt` e faz o deploy

---

## 💬 Como Usar o Bot

### Modo rápido (comando direto)

```
/registro ifood 39
/registro freelance 250
/historico
/salario
```

### Modo menu

Digite `/start` e use os botões inline para navegar entre as opções.

### Exemplos de registros reconhecidos automaticamente

| Você digita | Categoria detectada |
|---|---|
| `ifood 35` | 🍔 Alimentação |
| `uber 22` | 🚕 Transporte |
| `netflix 45` | 🎬 Entretenimento |
| `farmácia 18` | ⚕️ Saúde |
| `curso 120` | 📚 Educação |

---

## 🛠️ Stack

- **[python-telegram-bot](https://python-telegram-bot.org/)** — framework do bot
- **[gspread](https://docs.gspread.org/)** — leitura direta do Google Sheets
- **[google-auth](https://google-auth.readthedocs.io/)** — autenticação via Service Account
- **[Zapier](https://zapier.com)** — orquestração dos workflows e integração com Claude AI
- **[Railway](https://railway.app)** — deploy em nuvem
- **[python-dotenv](https://pypi.org/project/python-dotenv/)** — gerenciamento de variáveis de ambiente

---

## 📁 Estrutura do Projeto

```
finbot/
├── finbot_telegram.py                  # Código principal do bot
├── requirements.txt        # Dependências Python
├── .env.example            # Template de variáveis de ambiente
├── .gitignore              # Ignora .env e credenciais
└── README.md
```

---

## 🔐 Segurança

- O arquivo `.env` e as credenciais do Google (`*.json`) **nunca devem ser commitados**
- Confirme que seu `.gitignore` contém:
  ```
  .env
  *.json
  ```
- No Railway, use sempre `GOOGLE_CREDENTIALS_JSON` em vez do arquivo físico

---

## 📌 Roadmap

- [ ] Relatório mensal completo (receitas, despesas, saldo, categorias)
- [ ] Comando `/deletar` para remover transações pelo bot
- [ ] Gráfico mensal de registros por categoria
- [ ] Alertas automáticos quando o saldo ficar abaixo de um limite

---

## 📄 Licença

MIT License — veja o arquivo [LICENSE](LICENSE) para detalhes.
# FinBot Telegram — Guia de Implementação

Assistente financeiro com IA integrado ao Telegram. Suporta dois modos de entrada:
- **Menu Completo** (`/start`) — Interface visual com botões
- **Modo Rápido** (`/registro ifood 39`) — Comando direto

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
cp finbot_telegram.py telegram_bot_spec.md requirements.txt .env .

# Crie um .env real
cp .env .env

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
[⚡ Novo Registro] [📊 Histórico] [💰 Relatório]
     ↓
Clique em "Novo Registro"
     ↓
Digite: "ifood 39"
     ↓
[✅ Confirmar] [✏️ Editar]
     ↓
Bot envia para Zapier → Google Sheets
```

### Modo 2: Comando Rápido

```
/registro ifood 39
     ↓
Bot mostra preview
     ↓
[✅ Confirmar] [✏️ Editar]
     ↓
Pronto! registro registrado
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

Cada registro enviado é um JSON assim:

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
| ifood, uber eats, pizza -> Alimentação |
| uber, 99, taxi, gasolina -> Transporte |
| netflix, spotify, cinema -> Entretenimento |
| farmácia, médico, remédio -> Saúde |
| mercado, supermercado -> Compras |
| curso, livro, escola -> Educação |
| venda, freelance, bônus -> Trabalho | 
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
- ✅ Comando `/registro`
- ✅ Detecção de categoria
- ✅ Envio para Zapier

### Fase 2 (Próximas 2 semanas)
- Histórico de registros (com paginação)
- Relatório mensal simples
- Edição de transações existentes

### Fase 3 (Futuro)
- Gráficos de registros (plotly/matplotlib)
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
    [InlineKeyboardButton("📈 Meta de registros", callback_data="budget")],
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
