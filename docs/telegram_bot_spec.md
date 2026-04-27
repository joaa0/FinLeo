# FinBot Telegram Assistant — Especificação Técnica

**Projeto:** Assistente financeiro com IA integrado ao Telegram e Zapier
**Status:** Implementado (Dual Zapier integration + Direct Sheets Reading)
**Data:** Abril 2026

---

## 1. Visão Geral da Arquitetura

```
┌────────────────────────────────────────────────────────────────┐
│                      TELEGRAM BOT (Python)                     │
│  • Interface conversacional (Inline Buttons)                   │
│  • Modo Rápido: /registro <descrição> <valor>                  │
│  • Modo Completo: [Novo Registro] → Entrada → Confirmação      │
│  • Classificação automática de Categoria e Tipo (Income/Expense│
└──────────┬──────────────────────────────────┬──────────────────┘
           │ Webhook POST (Escrita)           │ Direct API (Leitura)
           ↓                                  ↓
┌─────────────────────┐        ┌──────────────────────────────┐
│    ZAPIER (2 Zaps)  │        │       GOOGLE SHEETS          │
│                     │        │  "Assistente Financeiro"     │
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

---

## 2. Fluxo de Interação

### 2.1 Start & Menu Principal

```
Bot: "Bem-vindo ao FinBot! 💰
      Escolha uma opção ou digite rapidamente:
      /registro ifood 39"
      
      [⚡ Novo Registro] [📊 Histórico]
      [💰 Relatório]     [💵 Meu Salário]
```

### 2.2 Fluxo de Novo Registro (Gasto/Receita)

```
Usuário clica: [⚡ Novo Registro]
Bot: "O que deseja registrar?
      Gasto: ifood 39 ou uber 25
      Recebimento: salário 3500 ou freelance 800"

Usuário: "uber 25"
Bot: "Confirmando:
      📝 Descrição: uber
      💵 Valor: R$ 25.00
      🏷️ Categoria: Transporte
      💸 Tipo: Gasto
      📅 Data: 2026-04-27
      
      [✅ Confirmar] [✏️ Editar]"

Usuário clica: [✅ Confirmar]
Bot: "✅ Transação registrada com sucesso!" (Envia para Zap 1)
```

### 2.3 Fluxo de Salário

```
Usuário clica: [💵 Meu Salário]
Bot: "💵 Seu Salário
      💰 Salário registrado: R$ 5000.00
      💸 Gastos este mês: R$ 1200.00
      🟢 Saldo disponível: R$ 3800.00
      
      [✏️ Registrar / Atualizar] [⬅️ Voltar]"

Usuário clica: [✏️ Registrar / Atualizar]
Bot: "Qual é o seu salário mensal? Digite apenas o valor."
Usuário: "5500"
Bot: "✅ Salário registrado com sucesso!" (Envia para Zap 2)
```

### 2.4 Fluxo de Estados (State Machine)

```
START
  │
  ├─→ MENU
  │     │
  │     ├─→ [⚡ Novo Registro] → AWAITING_EXPENSE
  │     ├─→ [📊 Histórico]    → SHOW_HISTORY (Leitura GSheets)
  │     ├─→ [💰 Relatório]    → REPORT (Em dev)
  │     └─→ [💵 Meu Salário]  → SHOW_SALARY (Leitura GSheets)
  │                              └─→ [Atualizar] → AWAITING_SALARY
  │
  └─→ COMANDO DIRETO (/registro ou /gasto)
        │
        ├─→ Valida input + Detecta Categoria
        └─→ CONFIRMING
              │
              ├─→ [Confirmar] → SEND_TO_ZAPIER (Zap 1)
              └─→ [Editar]    → EDIT_EXPENSE
```

---

## 3. Integração Zapier e Webhooks

O sistema utiliza dois endpoints de webhook distintos, configurados no `.env`.

### 3.1 Zap 1: CRUD de Transações (`ZAPIER_WEBHOOK_EXPENSE`)

**Responsabilidade**: Processar transações (gastos e receitas).
**Módulo IA**: Usa `Mistral-small` para double-check (valida valores e infere categorias faltantes).
**Destino**: Google Sheets (`aba: transactions`).

**Payload enviado pelo Bot:**
```json
{
  "action": "create",
  "user_id": "123456789",
  "description": "ifood",
  "amount": 39.0,
  "category": "Alimentação",
  "type": "expense",
  "date": "2026-04-27",
  "_source": "telegram_bot",
  "_timestamp": "2026-04-27T14:30:00"
}
```

### 3.2 Zap 2: Atualização de Salário (`ZAPIER_WEBHOOK_SALARY`)

**Responsabilidade**: Processar a atualização do salário mensal do usuário.
**Destino**: Google Sheets (`aba: users`).

**Payload enviado pelo Bot:**
```json
{
  "action": "update_salary",
  "user_id": "123456789",
  "salary": 5500.0,
  "_source": "telegram_bot",
  "_timestamp": "2026-04-27T14:35:00"
}
```

---

## 4. Integração Google Sheets (Leitura Direta)

Em vez de usar webhooks para leitura (que teriam delay e formatação complexa via Telegram), o bot usa `gspread` para ler diretamente do Google Sheets usando credenciais de Service Account.

**Operações de leitura implementadas:**
1. `get_user_transactions(user_id)`: Busca todo o histórico do usuário.
2. `get_user_salary(user_id)`: Busca o salário atual na aba `users`.
3. `get_monthly_expenses(user_id)`: Soma todas as transações `type='expense'` do mês atual para o usuário.

---

## 5. Mapeamento Automático de Categorias

O bot faz a primeira triagem local para dar feedback imediato ao usuário, antes de enviar ao Zapier.

```python
CATEGORY_MAP = {
    # Alimentação — expense
    "ifood":         ("Alimentação",    "expense"),
    "uber eats":     ("Alimentação",    "expense"),
    "pizza":         ("Alimentação",    "expense"),
    # Transporte — expense
    "uber":          ("Transporte",     "expense"),
    "99":            ("Transporte",     "expense"),
    "gasolina":      ("Transporte",     "expense"),
    # Trabalho / Receitas — income
    "salário":       ("Trabalho",       "income"),
    "freelance":     ("Trabalho",       "income"),
    "venda":         ("Trabalho",       "income"),
    # ... (outras categorias: Saúde, Educação, Compras, etc)
}
```

---

## 6. Deployment e Configuração

### 6.1 Variáveis de Ambiente Necessárias

```bash
TELEGRAM_BOT_TOKEN="token_do_botfather"
ZAPIER_WEBHOOK_EXPENSE="url_do_zap_1"
ZAPIER_WEBHOOK_SALARY="url_do_zap_2"
GOOGLE_SHEET_ID="id_da_planilha_na_url"

# Credenciais do Google Service Account (escolha uma das opções)
GOOGLE_CREDENTIALS_PATH="credentials/file.json" # Para deploy local
# OU
GOOGLE_CREDENTIALS_JSON='{"type":"service_account",...}' # Para deploy em cloud (Railway/Heroku)
```

### 6.2 Dependências (requirements.txt)

```
python-telegram-bot==21.1
requests==2.31.0
python-dotenv==1.0.0
gspread==5.12.0
```

---

## 7. Roadmap e Status

### ✅ Fase 1 (Concluída)
- Integração base com Telegram (Inline keyboards).
- Zap 1 Webhook (CREATE transactions).
- Mapeamento local de categorias.

### ✅ Fase 2 (Atual - Concluída)
- Integração direta com gspread para leitura.
- Histórico paginado no Telegram.
- Zap 2 Webhook (UPDATE salary).
- Cálculo de saldo disponível (Salário - Gastos do mês atual).
- Suporte a receitas (income).

### 🚧 Fase 3 (Futuro)
- Relatório mensal detalhado direto no Telegram.
- Edição local da transação antes de confirmar (modificar a flag de `pending_expense`).
- Expor botões/comandos para DELETE (já suportado no Zap 1, mas sem interface no bot).
