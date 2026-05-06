# 📋 Documentação Completa: ZAP 1 - CRUD Principal do ChamaLeon

## Visão Geral

Este é um sistema de automação financeira completo que funciona como um **gerenciador de transações com análise de IA**. Ele recebe dados via webhook, processa, normaliza e distribui em 4 fluxos distintos (CREATE, READ, DELETE, REPORT) com base no tipo de ação solicitada.
=======

---

## 🏗️ Arquitetura Geral

```
Webhook → Normalização Python → Paths (4 Branches) → Ações específicas
```

| Componente | Função |
|-----------|--------|
| **Webhook** | Entrada de dados (trigger) |
| **Normalização** | Processa e estrutura dados |
| **Paths** | Distribui para 4 fluxos diferentes |
| **Branches** | CREATE, READ, DELETE, REPORT |

---

## 📥 Step 1: Webhook (Hook v2)

**ID:** `362293100`
**App:** WebHookCLIAPI
**Tipo:** Trigger (read)

### Função
Aguarda requisições HTTP POST e captura os dados enviados.

### Dados Esperados

```json
{
  "date": "2025-01-15",
  "text": "Descrição da transação",
  "type": "expense",
  "action": "create|read|delete|report",
  "amount": 150.50,
  "details": "Informações adicionais",
  "user_id": "7500965215",
  "category": "Alimentacao",
  "from__id": "xyz",
  "description": "Almoço",
  "transaction_id": "tx_12345",
  "from__first_name": "João",
  "_source": "telegram_bot",
  "_normalized": "true",
  "salary": 3500
}
```

### Campos Chave
- **action**: Determina qual branch executará (create/read/delete/report)
- **user_id**: Identificador do usuário (geralmente ID do Telegram)
- **amount**: Valor da transação
- **category**: Categoria financeira

---

## ⚙️ Step 2: Normalização em Python (Code Step)

**ID:** `362293101`
**App:** CodeCLIAPI
**Tipo:** Write (action)

### Função
**Processa, valida e normaliza os dados recebidos do webhook antes do roteamento.**

### Fluxo Lógico

#### 1️⃣ Bypass para Telegram Bot Normalizado
Se os dados chegam do Telegram Bot já normalizados (`_source === 'telegram_bot'` e `_normalized === 'true'`), **pula todo o processamento** e retorna direto:

```python
if (_source == 'telegram_bot' and _normalized == 'true' and
    amount_val > 0 and input_data.get('description') and
    input_data.get('category')):
    # Retorna direto, sem processamento
    return { estrutura_normalizada }
```

**Benefício:** Evita re-processamento de dados já validados, economizando tempo.

#### 2️⃣ Processamento Normal
Se não vem do Telegram normalizado, executa o pipeline completo:

**a) Extrai campos básicos:**
```python
action = input_data.get('action', 'create')
user_id = input_data.get('user_id', '')
amount = float(input_data.get('amount', 0))
```

**b) Gera ID único:**
- Se `transaction_id` foi fornecido, usa-o
- Senão, cria: `user_id + '_' + timestamp`

**c) Normaliza ação baseado em palavras-chave:**
```
"deletar", "apagar" → action = "delete"
"corrigir", "atualizar" → action = "update"
"relat", "extrato" → action = "report"
"ver", "minhas transações" → action = "read"
```

**d) Normaliza categoria:**
- Se categoria for "Outro", tenta identificar pela descrição:
  - **Alimentação**: "ifood", "uber eats", "pizza", "restaurante"
  - **Transporte**: "uber", "taxi", "gasolina", "metro"
  - **Saúde**: "farmacia", "consulta", "medicamento"
  - **Lazer**: "cinema", "show", "ingresso"
  - **Educação**: "curso", "livro", "faculdade"
  - **Trabalho/Renda**: "salario", "freelance", "venda"

### Output da Normalização

```python
{
  'id': 'tx_único_gerado',
  'action': 'create|read|delete|update|report',
  'user_id': '7500965215',
  'description': 'Texto normalizado',
  'amount': 150.50,
  'category': 'Alimentacao',
  'type': 'expense|income',
  'date': '2025-01-15',
  'details': 'Info adicional'
}
```

---

## 🛣️ Step 3: Paths (Roteamento Condicional)

**ID:** `362293102`
**App:** EngineAPI
**Tipo:** Parallel Paths

### Função
**Avalia 4 condições diferentes (uma por branch) e executa apenas a branch correspondente.**

Cada branch começa com um **Filter (BranchingAPI)** que verifica condições:

| Branch | ID | Condição | Cor | Ação |
|--------|----|-----------|----|------|
| CREATE | 362293103 | action == "create" | 🔵 Azul | Insere transação no Sheets |
| READ | 362293107 | action == "read" | 🔵 Azul | Busca transações do usuário |
| DELETE | 362293112 | action == "delete" | 🔴 Vermelho | Deleta transação do Sheets |
| REPORT | 362293115 | action == "report" | 📊 Verde | Gera relatório com IA |

---

## 🟢 Branch 1: CREATE (Criar Transação)

**IDs:** 362293103 → 362293104 → 362293105 → 362293106

### Filtro (362293103)
```
Condição 1: action == "create" (continue)
Condição 2: salary existe (stop se não existir)
Condição 3: amount > 0 (continue)
Condição 4: description existe (continue)
```

### Fluxo
1. **Filter**: Valida se é um CREATE com dados válidos
2. **Code Step 362293104**: Estrutura dados para Google Sheets
   ```python
   return {
       'id': transaction_id,
       'user_id': user_id,
       'date': date,
       'description': description,
       'category': category,
       'amount': amount,
       'type': type,
       'created_at': date,
       'updated_at': date,
       'details': details
   }
   ```

3. **Code Step 362293105**: Retorna status de sucesso
   ```python
   return {
       'status': 'success',
       'message': 'Transacao inserida',
       'id': id,
       ... (todos os campos)
   }
   ```

4. **Google Sheets**: Insere como nova linha na aba "transactions"
   ```
   COL$A: id
   COL$B: user_id
   COL$C: date
   COL$D: description
   COL$E: category
   COL$F: amount
   COL$G: type
   COL$H: created_at
   COL$I: updated_at
   COL$J: details
   ```

**Resultado:** ✅ Transação registrada em Google Sheets

---

## 🔵 Branch 2: READ (Buscar Transações)

**IDs:** 362293107 → 362293108 → 362293109 → 362293110 → 362293111

### Filtro (362293107)
```
Condição: action == "read"
```

### Fluxo

**1. Filter (362293107):** Valida se é READ

**2. Google Sheets - Find Many Rows (362293108)**
- Busca todas as transações do `user_id`
- Lookup: `COL$B (user_id) == {{362293101__user_id}}`
- Retorna até 500 linhas (resultados agrupados)

**3. Code Step 362293109 - Processamento de Resultados**
```python
# Pega os dados do lookup
results = input_data.get('results', [])
rows = results[0]['rows'] if results else []

# Calcula totais
total_count = len(rows)
total_amount = sum(float(row['COL$F']) for row in rows)

# Formata últimas 5 transações
transactions = [
    {
        'date': row['COL$C'],
        'description': row['COL$D'],
        'amount': float(row['COL$F']),
        'category': row['COL$E']
    }
    for row in rows[-5:]
]

return {
    'total_count': total_count,
    'total_amount': total_amount,
    'message': f'Encontrei {total_count} transacoes totalizando R$ {total_amount}...',
    'transactions': transactions
}
```

**4. Code Step 362293110 - Escape Markdown**
```python
# Escapa caracteres especiais para Telegram markdown
escaped_message = message.replace('.', '\\.')
return {'escaped_message': escaped_message}
```

**5. Telegram - Send Message (362293111)**
```markdown
📊 **SUAS TRANSAÇÕES**

Encontrei {total_count} transacoes totalizando R$ {total_amount}

Ultimas transacoes:
  • {date} - {description}: R$ {amount} ({category})
  ...
```

**Resultado:** 📱 Mensagem enviada no Telegram com resumo das transações

---

## 🔴 Branch 3: DELETE (Deletar Transação)

**IDs:** 362293112 → 362293113 → 362293114

### Filtro (362293112)
```
Condição: action == "delete"
```

### Fluxo

**1. Filter (362293112):** Valida se é DELETE

**2. Google Sheets - Lookup Row (362293113)**
- Busca a transação específica
- Lookup: `COL$A (id) == {{362293101__id}}`
- Retorna a primeira linha encontrada

**3. Google Sheets - Delete Row (362293114)**
- Deleta a linha encontrada no step anterior
- Remove permanentemente do Sheets

**Resultado:** 🗑️ Transação deletada do Sheets

---

## 📊 Branch 4: REPORT (Gerar Relatório com IA)

**IDs:** 362293115 → 362294316 → 362294317 → 362294318 → 362294319 → 362294320 → 362294321

### Filtro (362293115)
```
Condição: action == "report"
```

### Fluxo (Complexo - ⚠️ Mais detalhado)

**1. Filter (362293115):** Valida se é REPORT

**2. Google Sheets - Lookup User (362294316)**
- Busca dados do usuário na aba "users"
- Lookup: `COL$A (user_id) == {{362293101__user_id}}`
- Retorna: email, salary, etc.

**3. Google Sheets - Find All Transactions (362294317)**
- Busca todas as transações do mês do usuário
- Lookup: `COL$B (user_id) == {{362293101__user_id}}`
- Retorna até 500 transações com seus dados completos

**4. Code Step 362294318 - Análise Financeira Completa** ⭐ **[MAIS IMPORTANTE]**

Este é o coração do relatório. Processa:

#### a) Normalização de Dados
```python
# Parse de amounts, datas, categorias, tipos
normalize_amount("R$ 150,50") → 150.50
normalize_category("", "ifood", "") → "Alimentação"
parse_date_to_ymd("2025-01-15") → date(2025, 1, 15)
```

#### b) Filtro Temporal
- Filtra apenas transações do mês atual
- Descarta transações de outros meses

#### c) Cálculo de Totais por Categoria
```python
category_totals = {
    'Alimentação': 450.75,
    'Transporte': 280.30,
    'Compras': 150.00,
    ...
}
```

#### d) Detecção de Sinais (Flags Financeiras)
```python
# Sinal 1: Alimentação alta?
if alimentacao / salary >= 0.20:
    signals.append('Alimentação está pesada')

# Sinal 2: Compras altas?
if compras / salary >= 0.15:
    signals.append('Compras representam percentual relevante')

# Sinal 3: Transporte alto?
if transporte / salary >= 0.12:
    signals.append('Transporte representa percentual relevante')

# Sinal 4: Categorias desconhecidas?
if unknown_categories > 0:
    signals.append('Existem transações em Outros')
```

#### e) Análise Comportamental Avançada
```python
# Padrão 1: Mercado + Delivery simultâneo?
if market_total > 0 and delivery_total > 0:
    behavioral_signals.append({
        'type': 'mercado_e_delivery',
        'interpretation': 'Pode indicar baixa utilização dos alimentos comprados'
    })

# Padrão 2: Transporte privado alto?
if private_transport / salary >= 0.10:
    behavioral_signals.append({
        'type': 'transporte_privado_alto',
        'interpretation': 'Avaliar alternativas (público, caronas, rotas)'
    })

# Padrão 3: Compras frequentes?
if shopping_total / salary >= 0.12:
    behavioral_signals.append({
        'type': 'compras_relevantes',
        'interpretation': 'Pode indicar consumo impulsivo'
    })

# Padrão 4: Renda muito comprometida?
if expense_rate >= 85:
    behavioral_signals.append({
        'type': 'renda_muito_comprometida',
        'message': 'Foco em reduzir gastos variáveis'
    })

# Padrão 5: Sobra positiva?
if balance > 0:
    behavioral_signals.append({
        'type': 'sobra_positiva',
        'suggested_reserve': salary * 0.10 a 0.30
    })
```

#### f) Classificação de Perfil Financeiro
```python
# Classifica renda
if salary <= 3300:
    income_segment = 'abaixo_media'
elif salary <= 4818:
    income_segment = 'dentro_media'
elif salary <= 15000:
    income_segment = 'acima_media'
else:
    income_segment = 'renda_muito_alta'

# Classifica nível de despesas
expense_rate = (despesas / salary) * 100

if expense_rate <= 50:
    expense_level = 'poucas_despesas'
elif expense_rate <= 70:
    expense_level = 'despesas_moderadas'
elif expense_rate <= 90:
    expense_level = 'muitas_despesas'
else:
    expense_level = 'risco_alto'
```

#### g) Construção do Payload para IA
```python
ai_payload = {
    'user_id': user_id,
    'month': '2025-01',
    'salary': 3500.00,
    'income_total': 200.00,
    'expense_total': 1850.50,
    'balance': 1849.50,
    'expense_rate': 52.9,
    'profile_classification': {
        'income_segment': 'dentro_media',
        'expense_level': 'despesas_moderadas'
    },
    'category_totals': [...],
    'top_transactions': [...],
    'signals': [...],
    'behavioral_signals': [...]
}
```

**5. Webhook para Mistral API (362294319)**

Envia os dados para a IA Mistral com:
- **System Prompt**: 2400+ caracteres com regras de análise financeira
- **User Prompt**: Dados do usuario em JSON

```json
{
  "model": "mistral-small-latest",
  "temperature": 0.3,
  "max_tokens": 2400,
  "messages": [
    {
      "role": "system",
      "content": "[REGRAS COMPLETAS DE ANÁLISE FINANCEIRA...]"
    },
    {
      "role": "user",
      "content": "[PAYLOAD COM DADOS DO USUÁRIO...]"
    }
  ]
}
```

**Resposta da IA:** Relatório estruturado em 5 seções Markdown:
1. 📊 Planilha resumida de gastos
2. 📉 Diagnóstico financeiro
3. 🎯 Ajuste principal
4. 📈 Novo cenário após ajuste
5. 💰 Uso da sobra

**6. Code Step 362294320 - Formatação de Email**

Converte resposta da IA para HTML:

```python
# Converte Markdown para HTML
# Títulos: # → <h2>
# Negrito: ** → <strong>
# Tabelas: | → <table>
# Bullet points: - → <p class='bullet'>

email_html = f"""
<div style="...">
  <div style="background:#111827;...">
    <h1>📊 Relatório Financeiro Mensal</h1>
  </div>
  <div style="background:#ffffff;...">
    {html_content_convertido}
  </div>
</div>
"""
```

**7. Email by Zapier (362294321)**

Envia relatório formatado para o email do usuário:
- **To**: `{{362294318__email}}`
- **Subject**: `📊 Seu relatório financeiro mensal — 01/2025`
- **Body**: HTML formatado com tabelas, cores, tipografia profissional

**Resultado:** 📧 Relatório enviado por email com análise completa

---

## 🔄 Fluxo Completo Resumido

```
1. Webhook recebe JSON
   ↓
2. Code normaliza dados
   ↓
3. Paths avalia ação (action field)
   ├─ CREATE → Insere em Sheets
   ├─ READ → Busca e envia Telegram
   ├─ DELETE → Remove de Sheets
   └─ REPORT → Análise IA + Email
```

---

## 🔐 Autenticações Necessárias

| App | Auth ID | Função |
|-----|---------|--------|
| Google Sheets | 63698675 | Ler/escrever transações e usuários |
| Telegram | 63698765 | Enviar mensagens ao usuário |
| Mistral API | Header API Key | Análise de IA |

---

## 📈 Métricas Calculadas

| Métrica | Cálculo | Uso |
|---------|---------|-----|
| **expense_rate** | (despesas / salary) × 100 | Determina nível de comprometimento |
| **balance** | salary + income - expenses | Saldo final do mês |
| **category_totals** | Soma por categoria | Identifica maiores gastos |
| **behavioral_signals** | Análise de padrões | Detecção de anomalias |

---

## ⚡ Otimizações Implementadas

1. **Bypass para Telegram Bot**: Evita re-processamento de dados já normalizados
2. **Filtros no início de cada branch**: Só executa passos relevantes
3. **Cálculos em Python**: Processamento local (não requer múltiplos steps)
4. **Markdown escape no Telegram**: Evita erros de renderização
5. **Temperature 0.3 na IA**: Responses mais consistentes, menos criativas

---

## 🛠️ Troubleshooting

| Problema | Causa | Solução |
|----------|-------|--------|
| Transação não aparece | Ação != "create" | Verificar `action` no webhook |
| Read retorna vazio | Usuário sem transações | Criar transação com CREATE |
| Email não chega | Auth expirada | Reconectar Google Sheets |
| Telegram não envia | Chat ID inválido | Verificar `chat_id` no params |
| IA retorna erro | Payload muito grande | Reduzir `row_count` no lookup |

---

## 📝 Dados de Exemplo

### Webhook Input para CREATE
```json
{
  "action": "create",
  "user_id": "7500965215",
  "date": "2025-01-15",
  "description": "Almoço no restaurante",
  "amount": "45.50",
  "category": "Alimentacao",
  "type": "expense",
  "details": "Restaurante próximo ao trabalho"
}
```

### Webhook Input para READ
```json
{
  "action": "read",
  "user_id": "7500965215"
}
```

### Webhook Input para DELETE
```json
{
  "action": "delete",
  "user_id": "7500965215",
  "transaction_id": "tx_12345"
}
```

### Webhook Input para REPORT
```json
{
  "action": "report",
  "user_id": "7500965215"
}
```

---

## 🎯 Conclusão

Este Zap implementa um **sistema completo de gestão financeira pessoal** com:
- ✅ CRUD (Create, Read, Delete) de transações
- ✅ Análise automática via IA
- ✅ Detecção de padrões comportamentais
- ✅ Relatórios por email personalizados
- ✅ Integração com Telegram para consultas rápidas

**Status:** 🟢 Publicado e ativo
