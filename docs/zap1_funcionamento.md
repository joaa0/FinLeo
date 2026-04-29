# FinBot - Assistente Financeiro com Webhooks e Google Sheets

## Documentação Completa do Sistema

---

## 1. Visão Geral

O **FinBot** é um sistema de automação financeira baseado em Zapier que gerencia transações através de webhooks, normaliza dados com Python, e distribui entre 4 branches de ação:

- 🟢 **CREATE**: Insere novas transações no Google Sheets
- 🔵 **READ**: Recupera e exibe transações ao usuário
- 🔴 **DELETE**: Remove transações existentes
- 📊 **REPORT**: Gera relatórios financeiros por email

---

## 2. Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                     WEBHOOK RECEIVER                        │
│   (Aceita POST com transaction data + novo campo 'details') │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              CODE: Normalização Python (Step 2)             │
│  • Parse e validação de dados                              │
│  • Detecção de action (create/read/delete/report)          │
│  • Normalização de categoria baseada em keywords           │
│  • Preservação do campo 'details'                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   PARALLEL PATHS (Paths)                    │
│              Distribuição para 4 branches                   │
└──────┬──────────────┬──────────────┬──────────────┬─────────┘
       │              │              │              │
    CREATE         READ           DELETE         REPORT
```

---

## 3. Fluxo Detalhado

### 3.1 Webhook Trigger (Step 1)

**Função**: Recebe dados de transações via HTTP POST

**Campos Aceitos**:
```json
{
  "action": "create|read|delete|update|report",
  "user_id": "123456789",
  "description": "Descrição da transação",
  "amount": 100.50,
  "category": "Educação",
  "type": "expense|income",
  "date": "2026-04-29",
  "transaction_id": "uuid-opcional",
  "details": "Informações adicionais (NOVO CAMPO)",
  "_source": "telegram_bot",
  "_normalized": "true"
}
```

**Características**:
- Aceita qualquer JSON POST
- Todos os campos são opcionais
- Suporta múltiplas fontes (Telegram, API externa, etc)

---

### 3.2 Code Step: Normalização (Step 2 - `359719004`)

**Função Principal**: Padronizar dados de entrada e detectar intenção do usuário

**Lógica**:

#### A. Fast-Track para Telegram Bot Normalizado
Se os dados vêm do Telegram Bot já normalizados:
```python
if (_source == 'telegram_bot' and _normalized == 'true' and
    amount > 0 and description and category and type and action):
    # PULA processamento - retorna dados direto
```

#### B. Processamento Normal

**Extração de Campos**:
```python
action = input_data.get('action', 'create')
user_id = input_data.get('user_id', '')
description = input_data.get('description', '')
amount = float(input_data.get('amount', 0))
category = input_data.get('category', 'Outro')
type_ = input_data.get('type', 'expense')
date = input_data.get('date', today)
details = input_data.get('details', '').strip() if details else ''
```

**Geração de ID Único**:
```python
if transaction_id:
    unique_id = transaction_id  # Usa ID vindo do webhook
else:
    unique_id = user_id + '_' + timestamp  # Gera ID automático
```

**Detecção de Action por Keyword** (se não fornecido):
| Keyword | Action | Exemplo |
|---------|--------|---------|
| deletar, remove, apagar | `delete` | "Remover última transação" |
| corrigir, atualizar, mudar | `update` | "Corrigir a descrição" |
| relat, report, extrato | `report` | "Me envie um relatório" |
| ver, mostre, transac, histórico | `read` | "Mostre minhas transações" |

**Normalização Automática de Categoria** (se = 'Outro'):
```python
if 'cafe' or 'ifood' or 'uber eats' in description.lower():
    category = 'Alimentacao'
    type = 'expense'

elif 'uber' or 'taxi' or 'metro' in description.lower():
    category = 'Transporte'
    type = 'expense'

elif 'saude' or 'farmacia' or 'consulta' in description.lower():
    category = 'Saude'
    type = 'expense'

elif 'lazer' or 'cinema' or 'show' in description.lower():
    category = 'Lazer'
    type = 'expense'

elif 'curso' or 'livro' or 'aula' in description.lower():
    category = 'Educacao'
    type = 'expense'

elif 'trabalho' or 'salario' or 'renda' in description.lower():
    category = 'Trabalho'
    type = 'income'
```

**Output Normalizado**:
```python
{
    'id': unique_id,
    'action': action,
    'user_id': user_id,
    'email': '',
    'description': description.strip(),
    'amount': float(amount),
    'category': category,
    'type': type_,
    'date': date,
    'details': details  # ✅ PRESERVADO SEM MODIFICAÇÕES
}
```

---

### 3.3 Parallel Paths (Step 3 - `parallel_359719006`)

**Função**: Distribuir fluxo para diferentes ações baseado no `action` normalizado

**Estructura**:
```
if action == 'create'   → Branch CREATE (🟢)
if action == 'read'     → Branch READ (🔵)
if action == 'delete'   → Branch DELETE (🔴)
if action == 'report'   → Branch REPORT (📊)
```

---

## 4. Os 4 Branches Detalhados

### 4.1 🟢 Branch CREATE - Inserir Transação

**Steps**:
1. **Filter (359719007)**: Valida condições
2. **Code Structuring (359719008)**: Formata dados para Sheets
3. **Code Finalization (359719009)**: Retorna JSON final
4. **Google Sheets (359719010)**: Insere linha

**Validações do Filter**:
```
✓ action == 'create'
✓ salary (verificação) NOT existe
✓ amount > 0
✓ description existe
```

**Transformação de Dados**:

**Step 5 (359719008)** - Estrutura para Google Sheets:
```python
{
    "id": id,
    "user_id": user_id,
    "date": date,
    "description": description,
    "category": category,
    "amount": amount,
    "type": type_,
    "created_at": date,
    "updated_at": date,
    "details": details  # ✅ NOVO - Preservado
}
```

**Step 6 (359719009)** - JSON Final com Status:
```python
{
    'status': 'success',
    'message': 'Transacao inserida',
    'id': id,
    'user_id': user_id,
    'date': date,
    'description': description,
    'category': category,
    'amount': amount,
    'type': type_,
    'created_at': created_at,
    'updated_at': updated_at,
    'details': details  # ✅ NOVO - Preservado
}
```

**Step 7 (359719010)** - Google Sheets Add Row:

**Mapeamento de Colunas** (aba: transactions):
| Coluna | Campo | Exemplo |
|--------|-------|---------|
| A | id | `7500965215_20260429152343` |
| B | user_id | `7500965215` |
| C | date | `2026-04-29` |
| D | description | `curso` |
| E | category | `Educacao` |
| F | amount | `100` |
| G | type | `expense` |
| H | created_at | `2026-04-29` |
| I | updated_at | `2026-04-29` |
| **J** | **details** | **`Python backend na Udemy`** ✅ NOVO |

---

### 4.2 🔵 Branch READ - Consultar Transações

**Steps**:
1. **Filter (359719011)**: Valida `action == 'read'`
2. **Google Sheets Search (359719012)**: Busca todas as transações do user_id
3. **Code Aggregation (359719013)**: Processa e calcula totais
4. **Code Escape (359719014)**: Escapa caracteres para Telegram
5. **Telegram Send (359719015)**: Envia mensagem formatada

**Lógica**:
```python
# Busca transações
rows = Google_Sheets.find_many_rows(
    lookup_key='COL$B',  # user_id
    lookup_value=user_id,
    row_count=500
)

# Calcula totais
total_count = len(rows)
total_amount = sum(row['COL$F'] for row in rows)

# Formata últimas 5 transações
for row in rows[-5:]:
    print(f"• {row['COL$C']} - {row['COL$D']}: R$ {row['COL$F']}")
```

**Output Telegram**:
```
📊 **SUAS TRANSAÇÕES**

Encontrei 42 transações totalizando R$ 5.234,50

Últimas transações:
  • 2026-04-29 - curso: R$ 100 (Educacao)
  • 2026-04-28 - ifood: R$ 45,90 (Alimentacao)
  • 2026-04-27 - uber: R$ 25,00 (Transporte)
```

---

### 4.3 🔴 Branch DELETE - Remover Transação

**Steps**:
1. **Filter (359719019)**: Valida `action == 'delete'`
2. **Google Sheets Lookup (359719022)**: Encontra transação por ID
3. **Google Sheets Delete (359719023)**: Remove a linha

**Lógica**:
```python
# Busca transação
row = Google_Sheets.lookup_row(
    lookup_key='COL$A',  # id
    lookup_value=transaction_id
)

# Deleta
Google_Sheets.delete_row(row_number)
```

---

### 4.4 📊 Branch REPORT - Relatório Financeiro

**Steps**:
1. **Filter (359719024)**: Valida `action == 'report'`
2. **Google Sheets Search (359719025)**: Busca user info
3. **Code Analysis (359719027)**: Calcula resumo financeiro
4. **Google Sheets Lookup (359719028)**: Pega email do usuário
5. **Email Send (359719029)**: Envia relatório por email

**Análise de Dados**:
```python
total_income = 0
total_expense = 0
by_category = {}

for transaction in all_transactions:
    if type == 'income':
        total_income += amount
    else:
        total_expense += amount
        by_category[category] += amount

balance = total_income - total_expense
```

**Email Template**:
```
Olá {{user_id}},

📊 Aqui está seu relatório financeiro:

========================================
✅ RECEITAS: R$ {{total_income}}
❌ DESPESAS: R$ {{total_expense}}
💰 SALDO: R$ {{balance}}
📄 TOTAL DE TRANSAÇÕES: {{transaction_count}}
========================================

DESPESAS POR CATEGORIA:
{{by_category}}

ÚLTIMAS TRANSAÇÕES:
{{transactions}}
```

---

## 5. O Novo Campo "details" - Implementação Completa

### 5.1 Especificação

**Propósito**: Armazenar informações adicionais sobre a transação sem modificar agressivamente

**Regras**:
- ✅ Preservar exatamente como recebido
- ✅ Aceitar strings vazias
- ✅ Apenas limpar espaços extras (`.strip()`)
- ❌ Não resumir
- ❌ Não reescrever
- ❌ Não truncar

### 5.2 Fluxo do Campo "details"

```
Webhook Input
└─ details: "Python backend na Udemy"
   │
   ▼
Step 2 (Normalização)
└─ details = input.get('details', '').strip() if details else ''
   └─ Output: "Python backend na Udemy"
   │
   ▼
Step 5 (Estruturação)
└─ details: input.get('details', '')
   └─ Output: "Python backend na Udemy"
   │
   ▼
Step 6 (JSON Final)
└─ details: input.get('details', '')
   └─ Output: "Python backend na Udemy"
   │
   ▼
Step 7 (Google Sheets)
└─ COL$J: {{359719009__details}}
   └─ Valor inserido: "Python backend na Udemy"
```

### 5.3 Exemplos de Uso

**Exemplo 1 - Com Details**:
```json
POST /webhook {
  "user_id": "123",
  "description": "curso",
  "category": "Educação",
  "amount": 100,
  "details": "Python backend na Udemy"
}

Google Sheets Row:
D=curso | E=Educação | F=100 | J=Python backend na Udemy
```

**Exemplo 2 - Sem Details**:
```json
POST /webhook {
  "user_id": "123",
  "description": "ifood",
  "category": "Alimentação",
  "amount": 45.90
}

Google Sheets Row:
D=ifood | E=Alimentação | F=45.90 | J=(vazio)
```

**Exemplo 3 - Details Vazio**:
```json
POST /webhook {
  "user_id": "123",
  "description": "uber",
  "details": ""
}

Google Sheets Row:
D=uber | E=Transporte | F=25 | J=(vazio)
```

---

## 6. Compatibilidade com Dados Históricos

**Sistema mantém retrocompatibilidade**:
- Transações antigas **sem** `details` continuam funcionando
- Campo `details` é **opcional** em todas as etapas
- Se não fornecido, retorna string vazia `""`
- Branches READ, DELETE, REPORT **ignoram** `details` sem erros

---

## 7. Fluxo Completo - Caso de Uso Real

### Cenário: Usuário envia transação de curso

```bash
# 1. Webhook recebe
POST /webhook
{
  "user_id": "7500965215",
  "description": "curso Python",
  "amount": 100,
  "details": "Python backend na Udemy - módulo completo"
}

# 2. Step 2 Normaliza
Saída:
- id: 7500965215_20260429152343
- action: 'create' (por padrão)
- description: 'curso Python'
- category: 'Educacao' (detectado por keyword 'curso')
- amount: 100
- type: 'expense'
- details: 'Python backend na Udemy - módulo completo'

# 3. Parallel Paths roteia
- action = 'create' ✓
- amount > 0 ✓
- description existe ✓
→ Vai para CREATE

# 4. Step 5 Estrutura
{
  "id": "7500965215_20260429152343",
  "user_id": "7500965215",
  "date": "2026-04-29",
  "description": "curso Python",
  "category": "Educacao",
  "amount": 100,
  "type": "expense",
  "created_at": "2026-04-29",
  "updated_at": "2026-04-29",
  "details": "Python backend na Udemy - módulo completo"
}

# 5. Google Sheets insere linha
Coluna:  A                          B            C           D            E        F    G        H           I           J
Valor: 7500965215_20260429152343 | 7500965215 | 2026-04-29 | curso Python | Educa. | 100 | expense | 2026-04-29 | 2026-04-29 | Python backend...

# ✅ Sucesso!
```

---

## 8. Tratamento de Erros e Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| Sem `action` | Detecta por keywords em `description` |
| Sem `category` | Classifica como 'Outro' ou detecta por keywords |
| `amount` = 0 | Bloqueado no Filter (não insere) |
| Sem `user_id` | Usa ID genérico; pode quebrar buscas |
| `details` vazio | Armazena como string vazia `""` |
| `details` com quebras | Preservado com `\n` no Google Sheets |
| Caracteres especiais em details | Preservados (sem escape) |

---

## 9. Estrutura de Autenticações

| Step | App | Auth ID |
|------|-----|---------|
| 7 | Google Sheets | 63641885 |
| 12 | Google Sheets | 63358101 |
| 15 | Telegram | 63358135 |
| 22 | Google Sheets | 63358101 |
| 23 | Google Sheets | 63358101 |
| 25 | Google Sheets | 63358101 |
| 28 | Google Sheets | 63358101 |
| 29 | Email (Zapier) | N/A |

---

## 10. Performance e Limites

- ⚡ **Tempo de execução**: ~2-3 segundos por transação
- 📊 **Google Sheets**: Suporta até 1M+ linhas
- 🔄 **Rate limit**: Dependente do plano Zapier
- 💾 **Storage**: Ilimitado no Google Sheets
- 🔀 **Paths simultâneos**: Executados sequencialmente (não paralelo)

---

## 11. Segurança e Boas Práticas

✅ **Implementado**:
- Validação de campos obrigatórios
- Detecção de intenção por keywords
- IDs únicos para rastreamento
- Tratamento de campos vazios

⚠️ **Considerações**:
- Webhook público = qualquer pessoa pode enviar dados
- Considere adicionar validação de token/API key
- Details pode conter dados sensíveis - não expostos em READ
- Emails contêm resumo financeiro - garantir HTTPS

---

## 12. Resumo da Atualização "details"

✅ **Adicionado**:
- Campo opcional em webhook
- Preservado em todos os 3 Code Steps
- Armazenado em Coluna J do Google Sheets
- Retrocompatível com transações antigas

📝 **Sem agressividade**:
- Apenas `.strip()` para limpar espaços
- Nenhum processamento de IA
- Sem resumo ou reescrita
- Sem truncagem

🚀 **Status**: Pronto para produção

---

**Versão**: 2.0 com suporte a `details`
**Data**: 2026-04-29
**Responsável**: FinBot Automation System
