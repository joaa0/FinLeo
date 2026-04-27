# FinBot Telegram — Assistente Financeiro com IA

Bot de Telegram para gestão financeira pessoal. Registre gastos e receitas, acompanhe seu histórico, gerencie seu salário e monitore seu saldo mensal — tudo por mensagens no Telegram.

---

## 🏗️ Arquitetura

O FinBot opera em três camadas que trabalham juntas:

```
┌────────────────────────────────────────────────────────────────┐
│                      TELEGRAM BOT (Python)                     │
│  • Interface conversacional com inline buttons                 │
│  • Detecção automática de categoria e tipo (income/expense)    │
│  • Leitura direta do Google Sheets (histórico, salário, saldo) │
└──────────┬──────────────────────────────────┬──────────────────┘
           │ Escrita (webhook POST)           │ Leitura (gspread)
           ↓                                  ↓
┌─────────────────────┐        ┌──────────────────────────────┐
│    ZAPIER (2 Zaps)  │        │       GOOGLE SHEETS          │
│                     │        │  "Assistente Financeiro"      │
│  Zap 1 — CRUD de   │───────→│  ┌────────────────────────┐  │
│  transações         │        │  │ aba: transactions      │  │
│                     │        │  │ ID | user_id | date |  │  │
│  Zap 2 — Atualizar  │───────→│  │ description | category│  │
│  salário do usuário │        │  │ amount | type |        │  │
│                     │        │  │ created_at | updated_at│  │
└─────────────────────┘        │  └────────────────────────┘  │
                               │  ┌────────────────────────┐  │
                               │  │ aba: users             │  │
                               │  │ user_id | email |      │  │
                               │  │ registered_date |      │  │
                               │  │ salary | updated_at    │  │
                               │  └────────────────────────┘  │
                               └──────────────────────────────┘
```

### Fluxo de dados

| Operação | Caminho |
|---|---|
| **Criar transação** | Bot → Zap 1 (webhook) → Google Sheets (`transactions`) |
| **Atualizar salário** | Bot → Zap 2 (webhook) → Google Sheets (`users`) |
| **Consultar histórico** | Bot ← Google Sheets (leitura direta via `gspread`) |
| **Consultar salário/saldo** | Bot ← Google Sheets (leitura direta via `gspread`) |

---

## ⚙️ O que cada Zap faz

### Zap 1 — CRUD de Transações

Pipeline: **Webhook → Python (normalização) → IA Mistral (validação) → Paths condicionais**

1. **Webhook** recebe JSON com `action`, `description`, `amount`, `category`, `type`, `date`, `user_id`
2. **Code (Python)** gera ID único, detecta ação por keywords no texto, normaliza categoria e tipo
3. **AI (Mistral)** faz double-check: preenche campos vazios, extrai valor do texto, infere categoria
4. **Paths** roteia para 5 branches:

| Branch | Condição | Ação |
|---|---|---|
| **CREATE** | `action = "create"` | Insere linha na aba `transactions` |
| **READ** | `action = "read"` | Busca transações e envia resumo via Telegram |
| **UPDATE** | `action = "update_salary"` | Busca e atualiza na aba `users` ⚠️ |
| **DELETE** | `action = "delete"` | Remove linha da aba `transactions` |
| **REPORT** | `action = "report"` | Calcula resumo financeiro e envia por email |

> ⚠️ A branch UPDATE dentro do Zap 1 está incompleta (falta o step `update_row`). A atualização de salário funciona de fato pelo **Zap 2**.

### Zap 2 — Atualização de Salário

Pipeline: **Webhook → Python (validação de entity) → IA Mistral → Paths (user / transaction)**

- Detecta se o payload contém `salary` → `entity = "user"` → **Path A** (atualiza salário na aba `users`)
- Caso contrário → `entity = "transaction"` → **Path B** (atualiza transação na aba `transactions`)
- Retorna resposta JSON via webhook com status de confirmação

---

## 📱 Como usar o Bot

### Comandos disponíveis

| Comando | Descrição |
|---|---|
| `/start` | Menu principal com botões interativos |
| `/registro <desc> <valor>` | Registro rápido (ex: `/registro ifood 39`) |
| `/historico` | Ver histórico de transações com paginação |
| `/salario` | Ver salário registrado e saldo do mês |

### Menu principal (`/start`)

```
🤖 Bem-vindo ao FinBot! 💰

[⚡ Novo Registro]    — registrar gasto ou receita
[📊 Histórico]       — consultar transações
[💰 Relatório]       — relatório mensal (em desenvolvimento)
[💵 Meu Salário]     — ver/atualizar salário e saldo
```

### Fluxo de registro de gasto

```
Usuário: /registro uber 28
         ↓
Bot: Confirmando:
     📝 Descrição: uber
     💵 Valor: R$ 28.00
     🏷️ Categoria: Transporte
     💸 Tipo: Gasto
     📅 Data: 2026-04-27
     [✅ Confirmar] [✏️ Editar]
         ↓
Usuário clica: [✅ Confirmar]
         ↓
Bot: ✅ Transação registrada com sucesso!
     (payload enviado ao Zap 1)
```

### Fluxo de salário

```
Usuário: /salario
         ↓
Bot: 💵 Seu Salário
     💰 Salário registrado: R$ 5.500,00
     💸 Gastos este mês: R$ 1.230,00
     🟢 Saldo disponível: R$ 4.270,00
     [✏️ Registrar / Atualizar]  [⬅️ Voltar]
         ↓
Usuário clica: [✏️ Registrar / Atualizar]
         ↓
Bot: Qual é o seu salário mensal? Digite o valor.
         ↓
Usuário: 6000
         ↓
Bot: ✅ Salário registrado com sucesso!
     (payload enviado ao Zap 2)
```

---

## 🏷️ Detecção automática de categorias

O bot detecta categoria e tipo (`expense`/`income`) automaticamente por keywords:

| Categoria | Keywords | Tipo |
|---|---|---|
| Alimentação | ifood, uber eats, rappi, pizza, restaurante, lanche, café | expense |
| Transporte | uber, 99, taxi, passagem, combustível, gasolina | expense |
| Entretenimento | netflix, spotify, cinema, jogo | expense |
| Saúde | farmácia, médico, dentista, vitamina | expense |
| Educação | curso, livro, escola | expense |
| Compras | mercado, supermercado, roupa, eletrônico | expense |
| Trabalho | salário, recebi, ganhei, bônus, freelance, venda, renda | **income** |

Se nenhuma keyword for encontrada, usa **"Outros"** como categoria e **"expense"** como tipo.

---

## 🚀 Quick Start

### 1. Pré-requisitos

- Python 3.10+
- Bot do Telegram (criar via [@BotFather](https://t.me/botfather))
- Conta no [Zapier](https://zapier.com) com 2 Zaps configurados (webhooks)
- Planilha Google Sheets com as abas `transactions` e `users`
- Credenciais de Service Account do Google Cloud (para leitura via `gspread`)

### 2. Clonar e configurar

```bash
git clone <repo-url> finbot && cd finbot

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# Instalar dependências
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente

```bash
cp .env.example .env
nano .env   # ou o editor de sua preferência
```

Preencha os valores obrigatórios:

```bash
# Token do bot (obtenha via @BotFather)
TELEGRAM_BOT_TOKEN=seu_token_aqui

# Webhooks do Zapier
ZAPIER_WEBHOOK_EXPENSE=https://hooks.zapier.com/hooks/catch/xxxxx/zap1/
ZAPIER_WEBHOOK_SALARY=https://hooks.zapier.com/hooks/catch/xxxxx/zap2/

# Google Sheets
GOOGLE_SHEET_ID=id_da_sua_planilha
GOOGLE_CREDENTIALS_PATH=credentials/sua-credencial.json
# OU (para deploy em cloud):
# GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}

# (Opcional) Nomes das abas
SHEET_NAME=transactions
USERS_SHEET_NAME=users
```

### 4. Google Sheets — Estrutura esperada

**Aba `transactions`:**

| A | B | C | D | E | F | G | H | I |
|---|---|---|---|---|---|---|---|---|
| id | user_id | date | description | category | amount | type | created_at | updated_at |

**Aba `users`:**

| A | B | C | D | E |
|---|---|---|---|---|
| user_id | email | registered_date | salary | updated_at |

### 5. Rodar

```bash
python finbot_telegram.py
```

Você verá: `✅ FinBot iniciando...`

---

## 🚢 Deploy

### Railway (recomendado)

O projeto inclui um `Procfile` configurado:

```
worker: python finbot_telegram.py
```

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login e deploy
railway login
railway up
```

> **Dica:** No Railway, use `GOOGLE_CREDENTIALS_JSON` (colando o JSON completo) em vez de um arquivo de credenciais. O bot detecta automaticamente qual variável usar.

### Heroku

```bash
heroku create finbot-app
heroku config:set TELEGRAM_BOT_TOKEN=xxx ZAPIER_WEBHOOK_EXPENSE=xxx ZAPIER_WEBHOOK_SALARY=xxx GOOGLE_SHEET_ID=xxx GOOGLE_CREDENTIALS_JSON='{"type":"service_account",...}'
git push heroku main
```

---

## 📁 Estrutura do projeto

```
finbot/
├── finbot_telegram.py        # Código principal do bot
├── requirements.txt           # Dependências Python
├── .env.example               # Template de variáveis de ambiente
├── .env                       # Variáveis reais (não versionado)
├── Procfile                   # Config de deploy (Railway/Heroku)
├── credentials/               # Credenciais Google (não versionado)
├── docs/
│   └── telegram_bot_spec.md   # Especificação técnica original
├── zap1_funcionamento.md      # Documentação do Zap 1 (CRUD)
└── zap2_funcionamento.md      # Documentação do Zap 2 (Salário)
```

---

## 🔧 Dependências

```
python-telegram-bot==21.1
requests==2.31.0
python-dotenv==1.0.0
gspread==5.12.0
google-auth (instalado como dependência do gspread)
```

---

## 📊 Payload enviado ao Zapier

### Zap 1 — Transação (CREATE)

```json
{
  "action": "create",
  "user_id": "7500965215",
  "description": "ifood",
  "amount": 39.0,
  "category": "Alimentação",
  "type": "expense",
  "date": "2026-04-27",
  "_source": "telegram_bot",
  "_timestamp": "2026-04-27T14:30:00"
}
```

### Zap 2 — Salário (UPDATE)

```json
{
  "action": "update_salary",
  "user_id": "7500965215",
  "salary": 5500.0,
  "_source": "telegram_bot",
  "_timestamp": "2026-04-27T14:35:00"
}
```

---

## 🛠️ Troubleshooting

| Problema | Solução |
|---|---|
| `TELEGRAM_BOT_TOKEN não configurado!` | Verifique se `.env` existe e contém o token correto |
| Bot não responde a `/start` | Confirme que o token está certo e o processo está rodando |
| `❌ Erro: Conexão com Google Sheets não disponível` | Verifique `GOOGLE_CREDENTIALS_PATH` ou `GOOGLE_CREDENTIALS_JSON` e `GOOGLE_SHEET_ID` |
| Webhook timeout no Zapier | Teste o webhook manualmente; o timeout padrão é 10s |
| Transação não aparece no Sheets | Confirme que o Zap está publicado e ativo no Zapier |
| Salário não atualiza | Verifique se `ZAPIER_WEBHOOK_SALARY` está configurado e o Zap 2 está ativo |

---

## 📈 Status atual

- ✅ Registro de gastos e receitas (CREATE via Zap 1)
- ✅ Histórico paginado com leitura direta do Google Sheets
- ✅ Gerenciamento de salário (consulta + atualização via Zap 2)
- ✅ Cálculo automático do saldo mensal (salário − despesas do mês)
- ✅ Detecção automática de categoria e tipo por keywords
- ✅ Suporte a receitas (`income`) e despesas (`expense`)
- ✅ Deploy em cloud (Railway/Heroku) com credenciais via variável de ambiente
- 🚧 Relatório mensal (em desenvolvimento)
- 🚧 DELETE e READ via Zap 1 (branches configuradas, não expostas no bot ainda)
- 🚧 REPORT via email (branch configurada no Zap 1, não exposta no bot ainda)

---

## 📝 Licença

Uso livre para projetos pessoais e comerciais.
