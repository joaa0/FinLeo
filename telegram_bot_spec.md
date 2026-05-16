# ChamaLeon — Especificacao Tecnica

Documento tecnico alinhado ao runtime modular atual.

## Visao geral

O ChamaLeon e um bot financeiro conversacional para Telegram. O runtime atual opera com PostgreSQL, servicos Python locais e fluxo guiado por estados + intents heuristicas.

Fonte principal do runtime:

- [src/chamaleon/bot/app.py](/home/jj/ChamaLeon-main/src/chamaleon/bot/app.py)

## Componentes

### Camada `bot`

Responsavel por:

- handlers Telegram;
- callbacks de menu em hierarquia;
- onboarding;
- confirmacao simples e assistida;
- roteamento entre estados guiados e intents conversacionais;
- agendamento do `JobQueue`.

### Camada `services`

Responsavel por:

- parser heuristico de linguagem natural;
- fallback estruturado de parser com IA;
- separacao conservadora de multiplas transacoes;
- resumo mensal e alertas de orcamento;
- fechamento semanal automatico;
- recorrencias e lembretes;
- geracao e envio de relatorio.

### Camada `repos`

Responsavel por:

- `UserRepository`
- `TransactionRepository`
- `CategoryBudgetRepository`
- `RecurringRuleRepository`
- `ReportRepository`

### Camada `infra`

Responsavel por:

- configuracao por ambiente;
- engine SQLAlchemy;
- modelos do banco;
- cliente de IA;
- cliente SMTP;
- cliente de transcricao;
- logging.

## Comandos registrados

- `/start`
- `/registro`
- `/historico`
- `/salario`
- `/dinheiro`
- `/relatorio`
- `/orcamentos`
- `/recorrencias`
- `/lembrete`

Observacao:

- `/salario` e `/dinheiro` convergem para o mesmo resumo financeiro.

## Hierarquia visual do menu

O menu principal e os submenus de navegacao usam `Reply Keyboard` persistente.
Os `Inline Keyboards` ficam restritos a acoes contextuais e sensiveis:

- confirmacao de transacao;
- confirmacao assistida de multiplas transacoes;
- paginacao do historico;
- exclusao de transacao;
- gestao de recorrencia;
- escolhas especificas em orcamentos, recorrencias, relatorio e configuracoes.

Ao tocar em `⚡ Novo registro`, o bot entra em um modo de captura com `Reply Keyboard` reduzido:

- `❌ Cancelar registro`
- `🔙 Voltar ao menu`

Esse teclado temporario fica ativo enquanto o bot espera a movimentacao por texto ou audio.

Menu principal:

- `⚡ Novo registro`
- `📊 Resumo do mês`
- `📁 Transações`
- `⚙️ Mais opções`

Submenu `Transações`:

- `📜 Histórico`
- `✏️ Corrigir último`
- `🗑️ Excluir transação`

Submenu `Resumo do mês`:

- `💰 Meu dinheiro`
- `🎯 Orçamentos`
- `📧 Relatório`
- `🔁 Recorrências`

Submenu `Mais opções`:

- `🔔 Lembrete diário`
- `⚙️ Configurações`
- `❓ Ajuda`

## Intents conversacionais

O parser atual tenta identificar:

- `register_transaction`
- `show_history`
- `show_summary`
- `manage_budgets`
- `manage_recurring`
- `update_salary`
- `undo_last_transaction`
- `edit_last_transaction_amount`
- `request_report`
- `help`

Exemplos suportados:

```text
gastei 39 no ifood
recebi 1200 de freelance
ontem paguei 82 no mercado
quero ver meus orcamentos
quero ver minhas recorrencias
quanto sobrou esse mes?
me manda meu relatorio
```

## Contratos internos principais

### `TransactionDraft`

- `description`
- `amount`
- `category`
- `transaction_type`
- `transaction_date`
- `details`
- `confidence`
- `raw_text`

### `IntentResult`

- `intent`
- `confidence`
- `entities`
- `draft`

### `TransactionParseResult`

- `confidence`
- `draft`
- `drafts`
- `needs_confirmation`
- `should_use_ai_fallback`
- `reasons`

### `MonthlySummary`

- `salary`
- `income_total`
- `expense_total`
- `balance`
- `top_categories`
- `budget_statuses`
- `insights`

## Persistencia

### `users`

- `telegram_user_id`
- `email`
- `monthly_salary`
- `daily_nudge_enabled`
- `nudge_hour`
- `nudge_minute`
- `last_nudge_sent_on`
- `last_weekly_closure_sent_for`
- timestamps

### `transactions`

- `user_id`
- `transaction_type`
- `category`
- `description`
- `details`
- `amount`
- `transaction_date`
- timestamps

### `generated_reports`

- `user_id`
- `period_label`
- `status`
- `delivery_channel`
- `content`
- timestamps

### `recurring_rules`

- `user_id`
- `description`
- `category`
- `transaction_type`
- `amount`
- `frequency`
- `day_of_month`
- `weekday`
- `start_date`
- `reminder_days_before`
- `enabled`
- `last_reminder_period`
- timestamps

### `category_budgets`

- `user_id`
- `category`
- `monthly_limit`
- timestamps

## Fluxos implementados

### Onboarding

```text
/start
-> se user inexistente:
   -> awaiting_email
   -> awaiting_onboarding_salary
   -> create_or_update em users
-> senao:
   -> menu principal
```

### Registro de transacao

```text
mensagem ou /registro
-> parse_transaction_candidate()
-> se confidence alta:
   -> pending_transaction
-> se confidence baixa ou ambiguidade:
   -> AIParserService
   -> validacao rigorosa do JSON
   -> pending_transaction ou pending_transactions
-> confirmacao via botao ou texto
-> create() em transactions
```

Fora de onboarding e configuracoes, uma nova mensagem de movimentacao pode interromper o contexto atual e abrir um novo fluxo de registro.

### Multiplas transacoes com confirmacao assistida

```text
mensagem com 2 ou 3 blocos claros
-> parse_multiple_transaction_texts()
-> pending_transactions
-> confirmacao unica
-> create() em transactions para cada item
```

### Registro por audio

```text
audio
-> download temporario
-> transcricao via Mistral
-> mesmo fluxo do parser textual
-> fallback com IA, se necessario
```

### Historico

```text
/historico ou intent "historico"
-> count_for_user()
-> list_recent()
-> pagina com callbacks history:{page}
```

### Resumo financeiro

```text
/salario, /dinheiro ou intent equivalente
-> build_monthly_summary()
-> salario + entradas - gastos
```

O resumo atual tambem inclui:

- categorias com maior peso;
- orcamentos por categoria;
- insights textuais;
- marcacao visual de categorias em 70%, 90% e 100% do limite.

### Fechamento semanal automatico

```text
job agendado
-> identifica semana fechada anterior
-> calcula totais e categoria dominante
-> cruza orcamentos e recorrencias proximas
-> monta texto deterministico
-> envia no Telegram
-> marca last_weekly_closure_sent_for
```

### Orcamentos

```text
/orcamentos ou menu
-> lista de orcamentos atuais
-> escolha de categoria
-> envio do limite
-> upsert em category_budgets
-> opcionalmente remove com valor 0
```

### Recorrencias

```text
/recorrencias ou menu
-> descricao
-> valor
-> frequencia mensal/semanal/quinzenal
-> agenda
-> prazo do lembrete
-> create() em recurring_rules
```

Gestao atual:

- editar nome;
- editar valor;
- editar frequencia;
- editar agenda;
- editar prazo do lembrete;
- pausar/reativar;
- excluir.

### Lembrete diario

```text
/lembrete ou menu
-> mostra status e horario atual
-> ligar/desligar
-> sortear novo horario
```

O disparo e feito pelo `JobQueue` do `python-telegram-bot`.

### Relatorio

```text
/relatorio ou intent equivalente
-> build_report_payload()
-> ReportAIClient.generate_report()
-> ReportRepository.upsert()
-> EmailClient.send_report()
```

## Variaveis de ambiente

- `TELEGRAM_BOT_TOKEN`
- `DATABASE_URL`
- `APP_ENV`
- `LOG_LEVEL`
- `AUTO_CREATE_SCHEMA`
- `CACHE_TTL_SECONDS`
- `MISTRAL_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`
- `MISTRAL_TRANSCRIPTION_MODEL`
- `MISTRAL_TRANSCRIPTION_LANGUAGE`
- `PARSER_AI_CONFIDENCE_THRESHOLD`
- `REMINDER_CHECK_INTERVAL_MINUTES`
- `DAILY_NUDGE_START_HOUR`
- `DAILY_NUDGE_END_HOUR`
- `WEEKLY_CLOSURE_HOUR`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `EMAIL_FROM`
- `REPORT_EMAIL_SUBJECT`

## Validacao esperada

- `python3 -m py_compile` nos arquivos Python principais;
- `python3 -m unittest tests.test_parser tests.test_finance_service tests.test_recurring_service`;
- `alembic upgrade head` com `DATABASE_URL` valido.

## Lacunas e problemas atuais

- o parser continua heuristico e baseado em palavras-chave;
- a separacao de multiplas transacoes e conservadora e exige blocos claros;
- a IA entra so como fallback e ainda depende de validacao estrita de JSON;
- a camada de estado ainda depende de memoria de processo do Telegram bot;
- os alertas de orcamento sao imediatos, mas ainda nao possuem politica personalizavel por usuario;
- recorrencias ainda nao fazem lancamento automatico de transacao, apenas lembrete;
- o lembrete diario ainda nao permite horario exato escolhido manualmente pelo usuario;
- o fechamento semanal atual e deterministicamente montado pelo backend e ainda nao usa IA para reescrever a leitura final;
- ainda nao existe fila assíncrona para geracao de relatorios, entao a solicitacao roda no fluxo do bot;
- a seguranca operacional depende da postura do banco, do SMTP e da chave do provedor de IA.
