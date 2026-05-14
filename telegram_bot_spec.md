# ChamaLeon — Especificação Técnica

Documento técnico alinhado ao comportamento real de `ChamaLeon_telegram.py`.

## 1. Visão geral

ChamaLeon é um assistente financeiro pessoal no Telegram com persistência em Google Sheets e automações no Zapier.

O fluxo atual está dividido assim:

- O bot controla interface, onboarding, estados, histórico e resumo mensal.
- O Google Sheets armazena usuários e transações.
- O Zap 1 recebe `create`, `delete` e `report`.
- O Zap 2 recebe `update_salary`.

## 2. Fonte da verdade do runtime

Hoje a fonte de verdade do comportamento implementado é o arquivo `ChamaLeon_telegram.py`.

Os pontos centrais do runtime são:

- `message_handler()`
- `button_handler()`
- `GoogleSheetsClient`
- os `CommandHandler(...)` registrados em `main()`

## 3. Comandos realmente registrados

No `main()`, o bot registra:

- `/start`
- `/registro`
- `/historico`
- `/salario`
- `/relatorio`

Observação importante:

- `main()` também tenta registrar `/dinheiro`, mas `command_dinheiro` não existe no arquivo atual.
- Portanto, este documento trata `/dinheiro` como **lacuna do código**, não como comando funcional confirmado.

## 4. Estados da conversa

Estados definidos hoje:

```python
MENU = 0
AWAITING_EXPENSE = 1
SELECTING_CATEGORY = 2
CONFIRMING = 3
AWAITING_SALARY = 4
AWAITING_EMAIL = 5
AWAITING_ONBOARDING_SALARY = 6
```

Uso real observado:

- `AWAITING_EMAIL`: aguarda e-mail do onboarding.
- `AWAITING_ONBOARDING_SALARY`: aguarda salário inicial do onboarding.
- `AWAITING_SALARY`: aguarda novo valor de salário via menu.
- `AWAITING_EXPENSE`: aguarda texto de transação iniciado pelo botão de novo registro.

Estados definidos mas sem papel claro no fluxo atual:

- `MENU`
- `SELECTING_CATEGORY`
- `CONFIRMING`

## 5. Componentes do sistema

### 5.1 Bot Telegram

Responsabilidades atuais:

- receber comandos, texto e cliques em botões;
- validar onboarding;
- ler `users` e `transactions` direto no Google Sheets;
- calcular resumo mensal localmente;
- enviar payloads para os webhooks do Zapier;
- manter cache local em `context.user_data`.

O que o bot faz diretamente:

- leitura de histórico;
- leitura de salário;
- cálculo de entradas e gastos do mês;
- criação ou atualização do usuário durante onboarding;
- filtro de transações por `user_id` exato.

O que o bot não faz diretamente:

- gravar transação na aba `transactions`;
- deletar linha da planilha por conta própria;
- atualizar salário diretamente na aba `users` fora do onboarding;
- produzir análise financeira com IA localmente.

### 5.2 Zap 1

Contrato observado no bot:

- `action=create`
- `action=delete`
- `action=report`

Payload de `create` enviado pelo bot:

```json
{
  "action": "create",
  "user_id": "7500965215",
  "description": "mercado",
  "details": "compra do mês",
  "amount": 84.0,
  "category": "Compras",
  "type": "expense",
  "date": "2026-05-02",
  "_source": "telegram_bot",
  "_timestamp": "2026-05-02T12:00:00",
  "_normalized": true
}
```

Payload de `delete`:

```json
{
  "action": "delete",
  "user_id": "7500965215",
  "transaction_id": "7500965215_20260502120000",
  "_source": "telegram_bot",
  "_timestamp": "2026-05-02T12:00:00"
}
```

Payload de `report`:

```json
{
  "action": "report",
  "user_id": "7500965215",
  "_source": "telegram_bot",
  "_timestamp": "2026-05-02T12:00:00"
}
```

Observação:

- O bot dispara o relatório pelo payload acima.
- No sistema atual, o fluxo externo do Zap 1 usa salário e transações mensais do usuário para montar um relatório personalizado.
- O e-mail final contém insights, dicas e apontamentos.
- Dentro deste repositório, o que está implementado diretamente é o disparo do fluxo e o contrato de integração.

### 5.3 Zap 2

Contrato observado no bot:

```json
{
  "action": "update_salary",
  "user_id": "7500965215",
  "salary": 3500.0,
  "_source": "telegram_bot",
  "_timestamp": "2026-05-02T12:00:00"
}
```

Responsabilidade esperada:

- localizar o `user_id` na aba `users`;
- atualizar `salary`;
- atualizar `updated_at`.

O bot usa o Zap 2 apenas para atualização posterior de salário. O onboarding inicial grava o usuário diretamente via `gspread`.

### 5.4 Google Sheets

A planilha é tratada como banco simplificado.

Abas usadas hoje:

- `transactions`
- `users`

Estrutura esperada de `transactions`:

| Coluna | Campo |
|---|---|
| A | `id` |
| B | `user_id` |
| C | `date` |
| D | `description` |
| E | `category` |
| F | `amount` |
| G | `type` |
| H | `created_at` |
| I | `updated_at` |
| J | `details` |

Estrutura esperada de `users`:

| Coluna | Campo |
|---|---|
| A | `user_id` |
| B | `email` |
| C | `registered_date` |
| D | `salary` |
| E | `updated_at` |

## 6. Fluxos implementados

### 6.1 `/start` e onboarding

Fluxo real:

```text
/start
→ user_exists(user_id)
→ se não existir ou não tiver salário válido:
    → pedir e-mail
    → validar e-mail
    → pedir salário
    → create_user(user_id, email, salary)
    → mostrar menu principal
→ caso contrário:
    → mostrar menu principal
```

Detalhe relevante:

- `user_exists()` considera o usuário apto apenas quando existe linha com `salary` preenchido e diferente de `0`.

### 6.2 Registro de transação

O registro rápido aceita:

```text
/registro ifood 39
/registro mercado 84 | compra semanal
/registro freelance 800 | cliente x
```

Processamento:

```text
parse_quick_expense()
→ split_transaction_details()
→ normalize_amount()
→ detect_category()
→ show_confirmation()
→ send_expense_to_zapier()
```

Regras relevantes:

- `description` vem do segundo token.
- `amount` vem do terceiro token.
- tudo após `|` vira `details`.
- o parse rápido aceita tanto gasto quanto recebimento.

### 6.3 Histórico

O histórico é lido localmente pelo bot:

```text
get_user_transactions(user_id)
→ get_all_records() na aba transactions
→ filtro exato por row["user_id"]
→ paginação em format_transactions()
```

O cache local usa a chave:

- `transactions`

### 6.4 Resumo mensal e salário

Fluxo:

```text
show_salary_menu() ou command_salario()
→ get_user_salary(user_id)
→ get_monthly_summary(user_id)
→ calcular balance = salary + total_income - total_expense
```

Regras de `get_monthly_summary()`:

- filtra por `transactions.user_id` com match exato;
- filtra apenas o mês atual;
- normaliza aliases de tipo para `expense` e `income`;
- normaliza valores como `50`, `50.00`, `50,00` e `R$ 50,00`;
- aceita datas em múltiplos formatos compatíveis com Sheets e ISO.

O cache local usa a chave:

- `salary_summary`

### 6.5 Deleção

Fluxo:

```text
menu_delete_transaction
→ listar até 10 transações recentes do usuário
→ delete_select:{transaction_id}
→ confirmação
→ delete_confirm:{transaction_id}
→ POST para Zap 1 com action=delete
```

Proteção lógica atual:

- o bot só deixa selecionar IDs vindos das transações filtradas do próprio usuário.

### 6.6 Relatório

Fluxo real do bot:

```text
/relatorio ou botão "Relatório"
→ montar payload com action=report
→ POST no ZAPIER_WEBHOOK_EXPENSE
→ exibir sucesso ou falha
```

No sistema atual, o texto exibido ao usuário corresponde ao comportamento esperado da integração: o relatório é montado fora do bot, usando salário e transações mensais do usuário, e enviado por e-mail com insights, dicas e apontamentos.

## 7. Categorização atual

O mapeamento local hoje inclui:

### Alimentação / `expense`

- `ifood`
- `uber eats`
- `rappi`
- `pizza`
- `restaurante`
- `lanche`
- `café`

### Transporte / `expense`

- `uber`
- `99`
- `taxi`
- `passagem`
- `combustível`
- `gasolina`
- `onibus`
- `onibûs`

### Entretenimento / `expense`

- `netflix`
- `spotify`
- `cinema`
- `jogo`

### Saúde / `expense`

- `farmácia`
- `médico`
- `dentista`
- `vitamina`
- `remédio`

### Educação / `expense`

- `curso`
- `livro`
- `escola`
- `apostila`

### Compras / `expense`

- `mercado`
- `supermercado`
- `roupa`
- `eletrônico`

### Trabalho / `income`

- `salário`
- `recebi`
- `ganhei`
- `bônus`
- `freelance`
- `venda`
- `trabalho`
- `renda`

Fallback:

- categoria `Outros`
- tipo `expense`

## 8. Variáveis de ambiente

Variáveis lidas pelo runtime:

| Variável | Uso |
|---|---|
| `TELEGRAM_BOT_TOKEN` | token do bot |
| `ZAPIER_WEBHOOK_EXPENSE` | webhook do Zap 1 |
| `ZAPIER_WEBHOOK_SALARY` | webhook do Zap 2 |
| `GOOGLE_CREDENTIALS_PATH` | credencial local em arquivo |
| `GOOGLE_CREDENTIALS_JSON` | credencial inline para cloud |
| `GOOGLE_SHEET_ID` | ID da planilha |
| `SHEET_NAME` | nome da aba de transações |
| `USERS_SHEET_NAME` | nome da aba de usuários |

Condição mínima para conectar no Sheets:

- `GOOGLE_SHEET_ID`
- e pelo menos uma credencial entre `GOOGLE_CREDENTIALS_PATH` e `GOOGLE_CREDENTIALS_JSON`

## 9. Cache local

O bot mantém cache em `context.user_data["_cache"]`.

Configuração atual:

- TTL de 60 segundos

Invalidações implementadas:

- após `create`: `transactions` e `salary_summary`
- após `delete`: `transactions` e `salary_summary`
- após update de salário: `salary_summary`

## 10. Dependências confirmadas no repositório

`requirements.txt` contém hoje:

```text
python-telegram-bot==21.1
requests==2.31.0
python-dotenv==1.0.0
gspread==5.12.0
```

Observação:

- o código também importa `google.oauth2.service_account.Credentials`;
- portanto, o ambiente precisa disponibilizar `google-auth`, mesmo que ele não apareça explicitamente no `requirements.txt` atual.

## 11. Lacunas e problemas atuais

### 11.1 `/dinheiro` está registrado, mas não implementado

`main()` registra `CommandHandler("dinheiro", command_dinheiro)`, porém `command_dinheiro` não existe no arquivo. Isso é um desalinhamento real do runtime.

### 11.2 Estados definidos além do fluxo realmente usado

`MENU`, `SELECTING_CATEGORY` e `CONFIRMING` existem na enumeração, mas o fluxo atual depende principalmente de `AWAITING_EMAIL`, `AWAITING_ONBOARDING_SALARY`, `AWAITING_SALARY` e `AWAITING_EXPENSE`.

### 11.3 Estado da conversa é volátil

Todo o fluxo depende de `context.user_data`. Se o processo reiniciar, onboarding e edições pendentes são perdidos.

### 11.4 Runtime com logs de debug excessivos

O arquivo imprime sinais de ambiente no startup e configura logging global em `DEBUG`. Isso é útil para diagnóstico, mas hoje aumenta ruído e sensibilidade operacional.

### 11.5 Geração do relatório vive fora deste repositório

O comportamento do sistema em produção inclui relatório personalizado por e-mail com base em salário e transações mensais. Ainda assim, neste repositório o que fica visível é apenas o disparo de `action=report`; a montagem final do conteúdo continua dependente do Zap 1.

### 11.6 Webhooks continuam sendo ponto operacional sensível

Os webhooks do Zapier seguem como endpoints externos críticos. O código atual não adiciona autenticação extra nem assinatura própria nas chamadas.

### 11.7 `requirements.txt` parece incompleto para o runtime real

O código usa `google.oauth2.service_account`, mas `google-auth` não aparece no arquivo atual de dependências.

## 12. Resumo de responsabilidades

| Parte | Responsabilidade atual |
|---|---|
| Bot Telegram | interface, onboarding, leitura de Sheets, resumo mensal, envio aos webhooks |
| Zap 1 | create, delete, report |
| Zap 2 | update_salary |
| Google Sheets | persistência de `transactions` e `users` |

## 13. Status consolidado

| Área | Status |
|---|---|
| Onboarding por e-mail e salário | Funcional |
| Registro de transações | Funcional |
| Campo `details` | Funcional |
| Histórico via Sheets | Funcional |
| Resumo mensal | Funcional |
| Deleção via Zap 1 | Funcional |
| Update de salário via Zap 2 | Funcional |
| Relatório por e-mail | Funcional no sistema integrado; disparado pelo bot e gerado no Zap 1 |
| Alias `/dinheiro` | Quebrado no código atual |
| Estado persistente | Não implementado |
