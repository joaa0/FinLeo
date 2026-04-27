📊 Contexto Completo do Zap: Assistente Financeiro com Webhooks

Seu Zap é um sistema completo de gestão financeira que recebe requisições via webhook, processa inteligentemente os dados, e executa diferentes ações baseadas no tipo de solicitação. Aqui está o fluxo completo:
🎯 Visão Geral
 Componente 	 Função
 Trigger 	 Webhook que recebe dados financeiros em JSON
 Processamento 	 3 etapas: Python → Normalização → IA (Mistral)
 Roteamento 	 5 branches condicionais (CREATE, READ, UPDATE, DELETE, REPORT)
 Saídas 	 Google Sheets, Telegram, Email
📥 Step 1: Webhook Trigger

O que faz: Recebe dados POST com campos:

    action – Tipo de operação (create, read, update, delete, report)
    description – Descrição da transação
    amount – Valor
    category – Categoria (Alimentação, Transporte, etc.)
    type – income/expense
    date – Data
    user_id – ID do usuário
    from__first_name, from__id – Dados do remetente (para contexto)

Status: 🟢 Ativo e pronto para receber dados
🔧 Step 2: Python Code (Normalizador)

Lógica:

    Extrai dados do webhook
    Gera ID único: combina user_id + timestamp (2025_10_31_14_30_45)
    Detecta ação automaticamente baseado em keywords no description:
        "deletar", "remover" → action: delete
        "corrigir", "atualizar" → action: update
        "relat", "extrato" → action: report
        "ver", "histórico" → action: read
    Normaliza categoria (se vazia) detectando keywords:
        Alimentação: "pizza", "restaurante", "ifood", etc.
        Transporte: "uber", "taxi", "gasolina", etc.
        Saúde: "farmácia", "consulta", "medicamento", etc.
        Lazer: "cinema", "show", "ingresso", etc.
        Educação: "curso", "livro", "aula", etc.
        Trabalho/Renda: "salário", "freelance", "venda", etc.
    Detecta tipo (income/expense) pela categoria

Output normalizado:

{
  "action": "create|read|update|delete|report",
  "user_id": "seu_user_id",
  "description": "Seu texto limpo",
  "amount": 45.50,
  "category": "Alimentacao",
  "type": "expense",
  "date": "2025-10-31",
  "id": "seu_user_id_20251031143045"
}


🤖 Step 3: AI (Mistral-small)

Função: Double-check de normalização

    Valida se action está vazio → deixa "create"
    Tenta extrair amount do description se for 0
    Infere category se estiver "Outro"
    Detecta income/expense se type vazio

Output: JSON normalizado e validado (garante dados consistentes)
🎋 Paths: 5 Branches Condicionais

Baseado no action após normalização, o fluxo se divide em 5 caminhos:
🟢 Branch 1: CREATE (Inserir transação)

Condição: action = "create"

Fluxo:

    Code Step → Estrutura dados para Google Sheets:

    {
    "id": "unique_id_123",
    "user_id": "joão",
    "date": "2025-10-31",
    "description": "Pizza no Dom Luigi",
    "category": "Alimentacao",
    "amount": 45.50,
    "type": "expense",
    "created_at": "2025-10-31",
    "updated_at": "2025-10-31"
    }


    Google Sheets "add_row" → Insere nova linha na aba "transactions":
        Colunas: A=ID, B=userid, C=date, D=description, E=category, F=amount, G=type, H=createdat, I=updated_at
        Spreadsheet: "Assistente Financeiro"

Resultado: ✅ Transação salva no Google Sheets
🔵 Branch 2: READ (Consultar transações do usuário)

Condição: action = "read"

Fluxo:

    Google Sheets lookup → Busca todas as transações onde user_id = seu_id
        Busca na aba "transactions"
        Retorna até 500 linhas

    Code Step (Debug) → Processa os dados:
        Calcula total_count (quantas transações)
        Calcula total_amount (soma de todos os valores)
        Filtra últimas 5 transações
        Formata mensagem legível

    Code Step (Escape) → Escapa caracteres especiais para Telegram (. → .)

    Telegram Send → Envia para sua DM (chat_id: 7500965215):

    📊 **SUAS TRANSAÇÕES**

Encontrei 42 transacoes totalizando R$ 1.234,56

Ultimas transacoes:
  • 2025-10-31 - Pizza no Dom Luigi: R$ 45,50 (Alimentacao)
  • 2025-10-30 - Uber para casa: R$ 28,90 (Transporte)
  ...


**Resultado:** 📱 Relatório enviado para Telegram

---

### 🟡 **Branch 3: UPDATE** (Atualizar salário)

**Condição:** `action = "update_salary"`

**Fluxo:**
1. **Google Sheets lookup** → Busca usuário na aba "users" (coluna A = user_id)
2. **Code Step** → Prepara dados para atualização:

json
{
  "status": "success",
  "message": "Salário do usuário joão atualizado para R$ 5.500,00",
  "userid": "joão",
  "row": "rownumber",
  "new_salary": 5500.00
}


**⚠️ Status:** Este branch existe mas a atualização no Sheets não está completa (falta update_row)

---

### 🔴 **Branch 4: DELETE** (Deletar transação)

**Condição:** `action = "delete"`

**Fluxo:**
1. **Google Sheets lookup** → Busca transação específica:
   - Por `user_id` na aba "transactions"
   - Com descrição igual a `description` fornecida no webhook

2. **Google Sheets delete_row** → Remove a linha

**Resultado:** ❌ Transação deletada

---

### 📊 **Branch 5: REPORT** (Gerar relatório financeiro)

**Condição:** `action = "report"`

**Fluxo:**
1. **Google Sheets lookup** → Busca TODOS os usuários na aba "users"
2. **Code Step (Análise)** → Processa e calcula:

json
{
  "totalincome": 8500.00,
  "totalexpense": 2145.67,
  "balance": 6354.33,
  "transactioncount": 47,
  "bycategory": {

"Alimentacao": 450.00,
"Transporte": 280.50,
"Saude": 125.00,
...

}
}


3. **Google Sheets lookup** → Busca email do usuário na aba "users"

4. **Email by Zapier** → Envia relatório para o email:

Olá joão,

📊 Aqui está seu relatório financeiro:

========
✅ RECEITAS: R$ 8500.00
❌ DESPESAS: R$ 2145.67
💰 SALDO: R$ 6354.33
📄 TOTAL DE TRANSAÇÕES: 47
========

DESPESAS POR CATEGORIA:
{...}

ÚLTIMAS TRANSAÇÕES:
[...]

Abra sua planilha para mais detalhes:
https://docs.google.com/spreadsheets/d/1debpPb-JxXFAPf84rLOZ-HldYbOAYVwHc4B1lPbVTt4


**Resultado:** 📧 Relatório enviado por email

---

## 📱 **Fluxo de Dados Completo (Exemplo)**

POST Webhook com:
{
  "user_id": "joão",
  "description": "Uber até a pizzaria",
  "amount": 28.90,
  "type": "expense"
}

↓

Python Code (Step 2):

    Detecta "Uber" → category = "Transporte"
    Gera ID único
    Action = "create" (padrão, não tem keywords de delete/update/read/report)
      ↓
    AI Mistral (Step 3):
    Valida e normaliza
      ↓
    Paths branching:
    action = "create" ✅ BRANCH 1 ATIVADA
      ↓
    CREATE Branch:
    Code estrutura dados
    Google Sheets insere nova linha
      ↓
    ✅ Transação salva em:
     A: uniqueid123
     B: joão
     C: 2025-10-31
     D: Uber até a pizzaria
     E: Transporte
     F: 28.90
     G: expense
     H: 2025-10-31
     I: 2025-10-31
    ```

🔐 Autenticações Conectadas
 Step 	 App 	 Auth ID 	 Status
 Step 3 	 AI (Mistral) 	 63358046 	 ✅ Conectado
 Google Sheets 	 Sheets API 	 63358101 	 ✅ Conectado
 Telegram 	 Telegram Bot 	 63358135 	 ✅ Conectado
⚙️ Recursos Utilizados

    ✅ Code by Zapier (Python) – 3 steps para transformação
    ✅ Paths – 5 branches condicionais
    ✅ Google Sheets – Leitura, busca e escrita
    ✅ AI by Zapier – Normalização inteligente
    ✅ Telegram – Notificações
    ✅ Email – Relatórios

🎯 Casos de Uso
 Comando 	 O que Acontece
 "Gastei R$ 50 em pizza" 	 CREATE → Salva transação em Alimentação
 "Ver minhas transações" 	 READ → Telegram com últimas transações
 "Meu salário é R$ 5500" 	 UPDATE → Atualiza na aba users
 "Deletar última transação" 	 DELETE → Remove linha do Sheets
 "Gerar relatório" 	 REPORT → Email com resumo financeiro
📈 Status Atual

    🟢 Zap publicado e ativo
    ✅ Todas as autenticações conectadas
    ✅ Planilha "Assistente Financeiro" sincronizada
    ✅ Telegram e Email funcionando
    ⚠️ Branch UPDATE não tem step de atualização final (falta update_row)

Este é um Zap production-ready de gestão financeira inteligente com interpretação natural de linguagem! 🚀
