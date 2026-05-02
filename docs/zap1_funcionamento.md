# Zap 1 — Funcionamento Atualizado

> Documento atualizado após implementação do **REPORT com IA via MistralAI**.
>
> O Zap 1 é o fluxo principal do FinBot para operações ligadas a transações financeiras, histórico, exclusão e relatório por e-mail.

---

## 1. Objetivo do Zap 1

O **Zap 1** recebe payloads enviados pelo Bot Telegram e executa ações relacionadas à aba `transactions` do Google Sheets.

Ele é responsável por:

- criar transações;
- consultar histórico via fluxo legado/complementar;
- deletar transações;
- gerar relatório financeiro por e-mail;
- executar a análise comportamental por IA no branch `REPORT`.

O Zap 1 **não** deve atualizar salário. Atualização de salário pertence exclusivamente ao **Zap 2**.

---

## 2. Estrutura geral

```text
1. Webhooks by Zapier — Catch Hook
2. Code by Zapier — Normalização inicial
3. Paths by Zapier — Roteamento por action
   ├── CREATE
   ├── READ
   ├── DELETE
   └── REPORT
```

---

## 3. Payload esperado do Bot Telegram

### 3.1 CREATE

```json
{
  "action": "create",
  "user_id": "7500965215",
  "description": "mercado",
  "details": "compra do mês com arroz e carne",
  "amount": 84.0,
  "category": "Compras",
  "type": "expense",
  "date": "2026-05-02",
  "_source": "telegram_bot",
  "_timestamp": "2026-05-02T12:00:00",
  "_normalized": true
}
```

### 3.2 READ

```json
{
  "action": "read",
  "user_id": "7500965215",
  "_source": "telegram_bot",
  "_timestamp": "2026-05-02T12:00:00"
}
```

### 3.3 DELETE

```json
{
  "action": "delete",
  "user_id": "7500965215",
  "transaction_id": "7500965215_20260502120000",
  "_source": "telegram_bot",
  "_timestamp": "2026-05-02T12:00:00"
}
```

### 3.4 REPORT

```json
{
  "action": "report",
  "user_id": "7500965215",
  "_source": "telegram_bot",
  "_timestamp": "2026-05-02T12:00:00"
}
```

---

## 4. Estrutura das abas do Google Sheets

### 4.1 Aba `transactions`

| Coluna | Campo | Uso |
|---|---|---|
| A | `id` | ID único da transação |
| B | `user_id` | ID do usuário do Telegram |
| C | `date` | Data da transação |
| D | `description` | Descrição curta |
| E | `category` | Categoria |
| F | `amount` | Valor |
| G | `type` | `expense` ou `income` |
| H | `created_at` | Data de criação |
| I | `updated_at` | Data de atualização |
| J | `details` | Observações adicionais |

### 4.2 Aba `users`

| Coluna | Campo | Uso |
|---|---|---|
| A | `user_id` | ID do usuário do Telegram |
| B | `email` | E-mail para envio de relatório |
| C | `registered_date` | Data de cadastro |
| D | `salary` | Salário base |
| E | `updated_at` | Última atualização |

---

## 5. Step 2 — Normalização inicial

O Step 2 recebe os dados crus do Webhook e padroniza os campos principais.

### Responsabilidades

- detectar `action`;
- normalizar `user_id`;
- normalizar `amount`;
- preservar `details`;
- gerar `id` quando necessário;
- preparar dados para os Paths.

### Actions suportadas

| Action | Responsabilidade |
|---|---|
| `create` | Criar uma transação |
| `read` | Consultar histórico |
| `delete` | Deletar transação |
| `report` | Gerar relatório financeiro por IA |

### Observação

O action `update` não deve ser tratado como path ativo no Zap 1 neste estágio.

---

## 6. Path CREATE

### Objetivo

Inserir uma nova linha na aba `transactions`.

### Fluxo

```text
CREATE
1. Filter: action == create
2. Code by Zapier: estrutura dados para Sheets
3. Code by Zapier: finaliza JSON/status
4. Google Sheets: Create Spreadsheet Row
```

### Mapeamento no Google Sheets

| Campo | Coluna |
|---|---|
| `id` | A |
| `user_id` | B |
| `date` | C |
| `description` | D |
| `category` | E |
| `amount` | F |
| `type` | G |
| `created_at` | H |
| `updated_at` | I |
| `details` | J |

### Regra do campo `details`

O campo `details` deve ser preservado como veio do bot, apenas com limpeza simples de espaços.

Exemplo:

```text
/registro mercado 84 | compra semanal com arroz e carne
```

Resultado:

```text
description = mercado
amount = 84
details = compra semanal com arroz e carne
```

---

## 7. Path READ

### Objetivo

Buscar transações do usuário e retornar histórico formatado.

### Fluxo

```text
READ
1. Filter: action == read
2. Google Sheets: Lookup/Search Rows em transactions
3. Code by Zapier: agrega e formata
4. Code by Zapier: escapa/ajusta para Telegram
5. Telegram: Send Message
```

### Observação

Atualmente o Bot Telegram também faz leitura direta via `gspread` para histórico e salário. Portanto, o Path READ pode permanecer como fluxo legado ou complementar.

---

## 8. Path DELETE

### Objetivo

Remover uma transação específica da aba `transactions`.

### Fluxo

```text
DELETE
1. Filter: action == delete
2. Google Sheets: Lookup Spreadsheet Row
3. Google Sheets: Delete Spreadsheet Row
```

### Configuração do Lookup

```text
Worksheet: transactions
Lookup Column: id ou COL$A
Lookup Value: transaction_id recebido do bot
```

### Regra de segurança lógica

O bot só envia `transaction_id` de transações previamente carregadas para o próprio `user_id`. Ainda assim, o ideal futuro é o Zap validar também `user_id` antes de deletar.

---

# 9. Path REPORT — Relatório financeiro com IA

## 9.1 Objetivo

Gerar um relatório financeiro mensal com análise comportamental usando MistralAI.

O relatório deixou de ser apenas um resumo numérico e passou a gerar:

- diagnóstico financeiro do mês;
- análise de padrões de gasto;
- sinais comportamentais;
- tabela de ajuste sugerida;
- plano de ação;
- recomendações práticas;
- avisos sobre limitações dos dados.

---

## 9.2 Fluxo atual do REPORT

```text
REPORT
1. Filter: action == report
2. Google Sheets: Lookup Spreadsheet Row em users
3. Google Sheets: Lookup/Search Rows em transactions
4. Code by Zapier — REPORT_ANALYSIS_PREP
5. Webhooks by Zapier — Custom Request para MistralAI
6. Code by Zapier — FORMAT_EMAIL
7. Email by Zapier — Send Outbound Email
```

---

## 9.3 Step 17 — Buscar usuário

### Função

Buscar e-mail e salário do usuário na aba `users`.

### Configuração

```text
App: Google Sheets
Action: Lookup Spreadsheet Row
Worksheet: users
Lookup Column: user_id ou COL$A
Lookup Value: user_id recebido do webhook/Step 2
Create if not found: desativado
```

### Saídas usadas

```text
email
salary
user_id
```

---

## 9.4 Step 18 — Buscar transações

### Função

Buscar todas as transações do usuário na aba `transactions`.

### Configuração

```text
App: Google Sheets
Action: Lookup Spreadsheet Rows / Find Many Spreadsheet Rows
Worksheet: transactions
Lookup Column: user_id ou COL$B
Lookup Value: user_id recebido do webhook/Step 2
Row Count: 500 ou 1000
```

### Importante

O Step 18 precisa retornar line-items das colunas da aba `transactions`.

No Step 19, não usar `18. Results` como objeto genérico se ele não for reconhecido corretamente pelo Code Step.

O mapeamento mais estável é por colunas separadas:

| Input do Step 19 | Campo do Step 18 |
|---|---|
| `tx_ids` | `COL$A` |
| `tx_user_ids` | `COL$B` |
| `tx_dates` | `COL$C` |
| `tx_descriptions` | `COL$D` |
| `tx_categories` | `COL$E` |
| `tx_amounts` | `COL$F` |
| `tx_types` | `COL$G` |
| `tx_details` | `COL$J` |

---

## 9.5 Step 19 — `REPORT_ANALYSIS_PREP`

### Função

Preparar os dados financeiros para a IA.

### Inputs esperados

```text
user_id
email
salary
tx_ids
tx_user_ids
tx_dates
tx_descriptions
tx_categories
tx_amounts
tx_types
tx_details
```

### Responsabilidades

- normalizar salário;
- filtrar transações do mês atual;
- separar `income` e `expense`;
- normalizar valores em formato brasileiro;
- normalizar categorias;
- usar `details` para enriquecer a análise;
- calcular totais por categoria;
- calcular saldo estimado;
- identificar top transações;
- criar sinais comportamentais;
- montar `mistral_body_json`.

### Categorias permitidas para análise

```text
Alimentação
Transporte
Entretenimento
Saúde
Educação
Moradia
Compras
Gastos de Urgências
Outros
```

### Saídas principais

```text
user_id
email
salary
month
expense_total
income_total
balance
mistral_body_json
fallback_email_body
```

### Observação sobre debug

Durante diagnóstico, podem existir campos como:

```text
debug_tx_dates_count
debug_tx_amounts_count
debug_processed_transactions
```

Após validação em produção controlada, esses campos devem ser removidos para reduzir exposição desnecessária de dados.

---

## 9.6 Step 20 — MistralAI

### Função

Enviar o payload financeiro para o modelo da Mistral e receber a análise.

### Configuração

```text
App: Webhooks by Zapier
Action: Custom Request
Method: POST
URL: https://api.mistral.ai/v1/chat/completions
```

### Headers

```text
Authorization: Bearer SUA_MISTRAL_API_KEY
Content-Type: application/json
```

### Body/Data

```text
{{19. mistral_body_json}}
```

### Modelo recomendado

```json
{
  "model": "mistral-small-latest",
  "temperature": 0.3,
  "max_tokens": 1800
}
```

### Saída importante

O campo usado no Step 21 deve ser:

```text
20. Choices Message Content
```

ou, dependendo da interface do Zapier:

```text
20. Choices Messages Content
```

Esse campo contém diretamente o texto gerado pela IA.

---

## 9.7 Step 21 — `FORMAT_EMAIL`

### Função

Transformar o conteúdo da IA em e-mail.

### Inputs esperados

```text
ai_content = 20. Choices Message Content
user_id = 19. user_id
email = 19. email
fallback_email_body = 19. fallback_email_body
```

### Regra crítica

O input do Step 21 **não** deve apontar para status code, headers, request body ou campo genérico vazio.

O mapeamento correto é:

```text
ai_content ou response = 20. Choices Message Content
```

### Responsabilidades

- receber texto final da Mistral;
- aplicar fallback se a IA falhar;
- converter Markdown básico em HTML;
- montar `email_subject`;
- montar `email_text`;
- montar `email_html`.

### Saídas principais

```text
email_subject
email_text
email_html
user_id
email
```

---

## 9.8 Step 22 — Envio de e-mail

### Função

Enviar o relatório ao usuário.

### Configuração

```text
App: Email by Zapier
Action: Send Outbound Email
```

### Mapeamento

```text
To: 21. email ou 19. email
Subject: 21. email_subject
Body: 21. email_html
```

Se o HTML não renderizar corretamente, usar:

```text
Body: 21. email_text
```

---

# 10. Comportamento esperado do relatório com IA

## Exemplo de cenário

Transações do mês:

```text
mercado 300 | compra do mês
ifood 80 | jantar por preguiça
uber 45 | faculdade
academia 120 | mensalidade
```

Saída esperada no relatório:

- despesas maiores que zero;
- categorias preenchidas;
- análise proporcional ao salário;
- destaque para mercado + delivery, se existir;
- recomendação prática de corte;
- plano de ação para o próximo mês;
- aviso caso existam muitas transações em `Outros`.

---

# 11. Regras da IA no REPORT

A IA deve seguir estas regras:

- não inventar dados;
- não prometer resultados;
- não recomendar bancos, crédito, investimentos específicos ou produtos financeiros;
- não culpar o usuário;
- tratar inferências como hipóteses;
- priorizar categorias variáveis antes de despesas fixas;
- analisar primeiro `Compras`, `Alimentação`, `Entretenimento` e `Transporte`;
- não sugerir corte em `Moradia` antes de avaliar desperdícios claros;
- usar `details` quando disponível;
- sinalizar baixa confiabilidade se houver muitas transações em `Outros`.

---

# 12. Erros comuns e correções

## 12.1 Step 19 retorna despesas zeradas

### Sintoma

```text
expense_total = 0
income_total = 0
balance = salary
```

### Causas prováveis

- Step 18 não encontrou transações;
- Step 18 buscou pela coluna errada;
- Step 19 recebeu `18. Results` em formato incompatível;
- transações antigas têm `user_id` inconsistente;
- datas estão fora do mês atual;
- tipos estão em formato não reconhecido.

### Correção

Usar line-items separados no Step 19:

```text
tx_ids           → 18. COL$A
tx_user_ids      → 18. COL$B
tx_dates         → 18. COL$C
tx_descriptions  → 18. COL$D
tx_categories    → 18. COL$E
tx_amounts       → 18. COL$F
tx_types         → 18. COL$G
tx_details       → 18. COL$J
```

---

## 12.2 Step 21 cai no fallback apesar do Step 20 ter resposta

### Sintoma

```text
Email Subject: Relatório Financeiro - Indisponível
Email Text: Relatório de YYYY-MM: Despesas R$ X, Saldo R$ Y
```

### Causa provável

O input `response` do Step 21 foi mapeado para o campo errado.

### Correção

Mapear:

```text
response ou ai_content = 20. Choices Message Content
```

Não mapear:

```text
20. Status Code
20. Headers
20. Request Body
20. Raw vazio
```

---

## 12.3 SyntaxError com `18. COL$A`

### Sintoma

```text
SyntaxError: invalid syntax
```

### Causa

O mapeamento visual do Zapier foi colado dentro do código Python.

### Correção

No código Python, usar:

```python
tx_ids = split_line_items(input_data.get("tx_ids"))
```

Na tela de Input Data do Zapier, mapear visualmente:

```text
tx_ids → 18. COL$A
```

---

# 13. Checklist de validação do REPORT com IA

Antes de considerar o fluxo estável:

- [ ] Bot envia `action=report` para Zap 1.
- [ ] Path REPORT é acionado corretamente.
- [ ] Step 17 encontra `email` e `salary` na aba `users`.
- [ ] Step 18 encontra transações pelo `user_id` na aba `transactions`.
- [ ] Step 19 retorna `expense_total > 0` quando há gastos no mês.
- [ ] Step 19 gera `mistral_body_json` válido.
- [ ] Step 20 retorna `Choices Message Content` com texto da IA.
- [ ] Step 21 usa `20. Choices Message Content` como input.
- [ ] Step 21 retorna `email_subject`, `email_text` e `email_html`.
- [ ] Step 22 envia e-mail com análise da IA, não fallback.
- [ ] Campos de debug temporários foram removidos.

---

# 14. Divisão correta de responsabilidades

| Camada | Responsabilidade |
|---|---|
| Bot Telegram | Interface, menus, confirmação e disparo do report |
| Zap 1 | Transações, delete, histórico legado e report com IA |
| Zap 2 | Atualização de salário apenas |
| Google Sheets | Persistência de `transactions` e `users` |
| MistralAI | Geração do diagnóstico financeiro textual |

---

# 15. Status atual

| Área | Status |
|---|---|
| CREATE | Funcional |
| READ | Funcional/legado |
| DELETE | Funcional |
| REPORT básico por e-mail | Substituído pelo REPORT com IA |
| REPORT com MistralAI | Funcional após mapeamento correto |
| Uso de `details` na análise | Implementado |
| Fallback de e-mail | Implementado |
| Zap 2 separado para salário | Mantido |

---

# 16. Observações finais

O REPORT com IA deve permanecer no Zap 1. O bot não deve fazer análise financeira avançada, apenas disparar o relatório.

A robustez do fluxo depende principalmente de dois mapeamentos:

1. Step 18 → Step 19: transações por line-items separados.
2. Step 20 → Step 21: `Choices Message Content` como texto da IA.

Com esses dois pontos corretos, o relatório consegue cruzar salário, despesas, categorias, detalhes e padrões comportamentais sem sobrecarregar o bot Telegram.
