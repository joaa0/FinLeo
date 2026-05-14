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
-> rascunho de transacao
-> confirmacao
-> persistencia em transactions
```

### Registro por audio

O bot agora tambem aceita `voice note` e arquivos de audio no Telegram.

Fluxo:

```text
audio
-> download temporario do arquivo
-> transcricao via Mistral
-> parser de movimentacao
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
-> dia do mes
-> persistencia em recurring_rules
-> lembrete automatico perto do vencimento
```

Gestao atual da recorrencia:

- criar pelo chat;
- editar nome, valor e dia do mes;
- pausar e reativar;
- excluir pelo proprio Telegram.

Tambem existe um lembrete diario de uso:

- apenas uma mensagem por dia por usuario;
- horario aleatorio atribuido ao usuario dentro da faixa configurada;
- objetivo pratico: lembrar de registrar gastos, entradas ou revisar o mes.

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
- insights mensais curtos com leitura do ritmo de gastos, categoria dominante e folego estimado.

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

Migração inicial: [alembic/versions/20260514_0001_initial_schema.py](/home/jj/ChamaLeon-main/alembic/versions/20260514_0001_initial_schema.py)

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

## Lacunas e problemas atuais

- o parser conversacional atual e heuristico; ele cobre intents centrais, mas ainda nao faz entendimento profundo de frases muito ambíguas;
- a data relativa implementada no v1 cobre `ontem` e `hoje`, mas nao um conjunto grande de referencias temporais;
- o relatorio usa fallback deterministico quando `MISTRAL_API_KEY` ou `OPENAI_API_KEY` nao esta configurada;
- o envio por email depende de SMTP valido; se a configuracao faltar, o relatorio pode ser gerado mas nao entregue;
- o estado conversacional continua em `context.user_data`, entao um restart pode interromper fluxos em andamento;
- recorrencias hoje ja contam com gestao basica no chat, mas ainda nao oferecem ajuste de lembrete ou automacao de lancamento real;
- os lembretes dependem do processo do bot estar rodando; se o polling ficar offline, a entrega daquele horario pode ser perdida;
- o runtime cria schema automaticamente por default para facilitar bootstrap local, mas o fluxo recomendado em producao continua sendo Alembic.
