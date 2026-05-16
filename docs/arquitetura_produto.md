# Arquitetura do Produto ChamaLeon

## Objetivo

O runtime do ChamaLeon deixou de depender de Google Sheets e Zapier. A aplicacao agora usa PostgreSQL como fonte de verdade e organiza o bot em camadas Python menores e testaveis.

## Estrutura de Pastas

```text
src/chamaleon/
  bot/        -> handlers Telegram, callbacks e entrypoint da aplicacao
  domain/     -> tipos internos e contratos
  infra/      -> banco, modelos SQLAlchemy, logging, email e IA
  repos/      -> acesso a users, transactions, recurring_rules, category_budgets e generated_reports
  services/   -> parser conversacional, fallback de IA, resumo financeiro, recorrencias e relatorios
alembic/      -> migracoes do banco
tests/        -> parser e servicos principais
```

## Fluxo de Dados

1. O usuario envia texto natural ou comando no Telegram.
2. `bot/app.py` identifica onboarding, fluxo guiado ou intent conversacional.
3. `services/parser.py` tenta resolver localmente com heuristica e confidence explicita.
4. Se a confidence estiver baixa ou houver ambiguidade, `services/ai_parser.py` tenta estruturar JSON validado.
5. `repos/` persiste e consulta dados no PostgreSQL.
6. `services/finance.py` calcula resumo mensal, fechamento semanal, orcamentos e alertas.
7. `services/recurring.py` calcula janelas de lembrete e apoio aos nudges diarios.
8. `services/reports.py` monta o contexto, usa `infra/ai.py` e envia o email por `infra/email.py`.

## Banco de Dados

Tabelas iniciais:

- `users`
- `transactions`
- `generated_reports`
- `recurring_rules`
- `category_budgets`
- `users.last_weekly_closure_sent_for` para controlar fechamento semanal sem duplicacao

As migracoes ficam versionadas em `alembic/versions/`.

## Compatibilidade

- `ChamaLeon_telegram.py` permanece como entrypoint do deploy.
- `/registro`, `/historico`, `/salario`, `/dinheiro`, `/relatorio`, `/orcamentos`, `/recorrencias` e `/lembrete` continuam funcionando.
- Mensagens naturais como `gastei 39 no ifood` e `quanto sobrou esse mes?` passam a ser tratadas como fluxo principal.
- O bot tambem aceita audio, recorrencias com frequencia mensal/semanal/quinzenal, orcamentos por categoria, confirmacao assistida de multiplas transacoes claras e fechamento semanal automatico.
