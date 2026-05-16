# ChamaLeon

Bot financeiro conversacional para Telegram, agora estruturado como produto Python com PostgreSQL como fonte de verdade.

## O que mudou

- texto natural virou fluxo principal;
- comandos continuam como atalho e fallback operacional;
- Google Sheets e Zapier saem do runtime;
- relatorio passa a ser gerado pelo backend Python e enviado por email;
- a aplicacao foi dividida em camadas menores e testaveis.

## Stack

- Python 3.10+
- `python-telegram-bot`
- PostgreSQL
- SQLAlchemy
- Alembic
- `requests` para cliente de IA compatível com API OpenAI
- Mistral como provedor padrão de IA para relatório
- SMTP para envio de relatorio

## Estrutura

```text
src/chamaleon/
  bot/
  domain/
  infra/
  repos/
  services/
alembic/
tests/
docs/
```

Detalhes da arquitetura: [docs/arquitetura_produto.md](/home/jj/ChamaLeon-main/docs/arquitetura_produto.md)

## Fluxos principais

### Navegacao do menu

O menu principal fica persistente no Telegram via `Reply Keyboard`.
Os `Inline Keyboards` ficam reservados para fluxos contextuais, como confirmacoes, historico paginado, exclusao, recorrencias, orcamentos, relatorio e configuracoes sensiveis.
Ao entrar em `⚡ Novo registro`, o bot troca temporariamente para um teclado curto de captura com `❌ Cancelar registro` e `🔙 Voltar ao menu`, evitando conflito visual com o menu principal enquanto espera a movimentacao.

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

### Onboarding

```text
/start
-> pede email
-> pede salario
-> grava user no PostgreSQL
-> libera o menu principal
```

### Registro conversacional

Exemplos aceitos:

```text
gastei 39 no ifood
recebi 1200 de freelance
ontem paguei 82 no mercado
/registro uber 25
```

Fluxo:

```text
mensagem
-> parser heuristico
-> score de confidence
-> se confidence < threshold ou texto ambiguo: fallback de parser com IA
-> rascunho de transacao
-> confirmacao
-> persistencia em transactions
```

Fora de onboarding e configuracoes, o bot aceita uma nova movimentacao em qualquer momento do chat, mesmo se o usuario estiver vindo de outro submenu.

Quando a mensagem trouxer 2 ou 3 movimentacoes claras, o bot tenta separar e abrir uma confirmacao assistida em bloco.

Regras do fallback com IA:

- a heuristica continua como primeira camada;
- a IA so entra quando a confianca esta baixa, ha ambiguidade ou multiplas transacoes complexas;
- a IA devolve apenas JSON estruturado;
- nenhuma transacao extraida pela IA e salva direto: tudo passa por confirmacao no Telegram;
- se o JSON vier invalido, o bot volta para a mensagem segura pedindo reformulacao manual.

### Registro por audio

O bot agora tambem aceita `voice note` e arquivos de audio no Telegram.

Fluxo:

```text
audio
-> download temporario do arquivo
-> transcricao via Mistral
-> parser de movimentacao
-> fallback de parser com IA, se necessario
-> confirmacao
-> persistencia em transactions
```

### Recorrencias e lembretes

O bot agora tambem cobre contas fixas, assinaturas e entradas recorrentes.

Fluxo:

```text
/recorrencias ou botao "Recorrencias"
-> cadastro guiado de descricao
-> valor
-> frequencia
-> agenda
-> prazo do lembrete
-> persistencia em recurring_rules
-> lembrete automatico perto do vencimento
```

Gestao atual da recorrencia:

- criar pelo chat;
- editar nome, valor e dia do mes;
- escolher frequencia mensal, semanal ou quinzenal;
- ajustar quantos dias antes o lembrete deve chegar;
- pausar e reativar;
- excluir pelo proprio Telegram.

Tambem existe um lembrete diario de uso:

- apenas uma mensagem por dia por usuario;
- horario aleatorio atribuido ao usuario dentro da faixa configurada;
- objetivo pratico: lembrar de registrar gastos, entradas ou revisar o mes.
- o proprio usuario pode ligar, desligar ou sortear um novo horario pelo chat.

### Fechamento semanal automatico

Uma vez por semana, o bot envia um fechamento curto direto no Telegram.

O texto e deterministico e calcula:

- total de gastos da semana;
- total de entradas da semana;
- saldo da semana;
- maior categoria da semana;
- categorias em atencao no orcamento mensal;
- recorrencias proximas;
- principal ponto de atencao.

O envio usa o mesmo `JobQueue` do bot e evita duplicacao na mesma semana.

### Resumo do mes

```text
quanto sobrou esse mes?
/salario
/dinheiro
```

O resumo considera:

- salario base do usuario;
- entradas do mes;
- gastos do mes;
- saldo calculado;
- categorias com maior peso;
- orcamentos por categoria configurados pelo usuario;
- insights mensais curtos com leitura do ritmo de gastos, categoria dominante e folego estimado.

### Orcamentos por categoria

```text
/orcamentos
ou botao "Orcamentos"
```

Fluxo:

```text
abre lista de orcamentos atuais
-> escolhe categoria
-> envia limite mensal
-> bot salva ou atualiza o orçamento
-> se enviar 0, o orçamento da categoria e removido
```

Alertas atuais:

- ao registrar um gasto, o bot avisa quando a categoria cruza 70%, 90% ou 100% do limite;
- o resumo do mês e a tela de orçamentos também passam a destacar categorias em atenção.

### Relatorio por email

```text
me manda meu relatorio
/relatorio
```

Fluxo:

```text
consulta dados do mes
-> monta payload financeiro
-> chama provedor de IA direto do Python
-> persiste relatorio em generated_reports
-> envia email via SMTP
```

## Banco de dados

Tabelas iniciais:

- `users`
- `transactions`
- `generated_reports`
- `recurring_rules`
- `category_budgets`

Migracoes atuais:

- [alembic/versions/20260514_0001_initial_schema.py](/home/jj/ChamaLeon-main/alembic/versions/20260514_0001_initial_schema.py)
- [alembic/versions/20260514_0002_recurring_rules_and_nudges.py](/home/jj/ChamaLeon-main/alembic/versions/20260514_0002_recurring_rules_and_nudges.py)
- [alembic/versions/20260515_0003_category_budgets.py](/home/jj/ChamaLeon-main/alembic/versions/20260515_0003_category_budgets.py)
- [alembic/versions/20260515_0004_recurring_frequency_and_schedule.py](/home/jj/ChamaLeon-main/alembic/versions/20260515_0004_recurring_frequency_and_schedule.py)
- [alembic/versions/20260515_0005_weekly_closure_tracking.py](/home/jj/ChamaLeon-main/alembic/versions/20260515_0005_weekly_closure_tracking.py)

## Variaveis de ambiente

Use `.env.example` como base. Campos principais:

```bash
TELEGRAM_BOT_TOKEN=
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/chamaleon

MISTRAL_API_KEY=
OPENAI_MODEL=mistral-small-latest
OPENAI_BASE_URL=https://api.mistral.ai/v1
MISTRAL_TRANSCRIPTION_MODEL=voxtral-mini-latest
MISTRAL_TRANSCRIPTION_LANGUAGE=pt
REMINDER_CHECK_INTERVAL_MINUTES=15
DAILY_NUDGE_START_HOUR=8
DAILY_NUDGE_END_HOUR=20

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
EMAIL_FROM=
```

O cliente HTTP continua OpenAI-compatible, mas o default agora aponta para Mistral.

## Setup local

Instale dependencias:

```bash
pip install -r requirements.txt
```

Rode migracoes:

```bash
alembic upgrade head
```

Inicie o bot:

```bash
python3 ChamaLeon_telegram.py
```

O `Procfile` continua usando esse entrypoint para preservar compatibilidade de deploy.

## Comandos compatíveis

- `/start`
- `/registro`
- `/historico`
- `/salario`
- `/dinheiro`
- `/relatorio`
- `/recorrencias`
- `/orcamentos`
- `/lembrete`

## Lacunas e problemas atuais

- o parser conversacional atual e heuristico; ele cobre intents centrais, mas ainda nao faz entendimento profundo de frases muito ambíguas;
- o fallback com IA melhora casos ambiguos, mas ainda depende da qualidade da transcricao e do texto enviado;
- a confirmacao assistida de multiplas transacoes continua propositalmente conservadora e so entra quando os blocos estao bem separados ou a IA consegue estruturar o retorno com seguranca;
- a data relativa implementada no v1 cobre `ontem` e `hoje`, mas nao um conjunto grande de referencias temporais;
- o relatorio usa fallback deterministico quando `MISTRAL_API_KEY` ou `OPENAI_API_KEY` nao esta configurada;
- o envio por email depende de SMTP valido; se a configuracao faltar, o relatorio pode ser gerado mas nao entregue;
- o estado conversacional continua em `context.user_data`, entao um restart pode interromper fluxos em andamento;
- recorrencias hoje ja contam com gestao no chat e frequencias principais, mas ainda nao oferecem automacao de lancamento real;
- os orcamentos por categoria hoje sao mensais e por categoria fixa; ainda nao ha metas semanais nem ajuste fino de politicas de alerta;
- o fechamento semanal hoje e heuristico e deterministicamente montado pelo backend; a IA ainda nao reescreve o comentario final;
- os lembretes dependem do processo do bot estar rodando; se o polling ficar offline, a entrega daquele horario pode ser perdida;
- o runtime cria schema automaticamente por default para facilitar bootstrap local, mas o fluxo recomendado em producao continua sendo Alembic.
