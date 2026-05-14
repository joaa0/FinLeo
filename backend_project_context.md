# Backend Project Context

## Visao Geral

`ChamaLeon-main` deixou de ser um script unico acoplado a Sheets/Zapier e passou a ser um backend Python modular para um bot financeiro conversacional no Telegram.

Responsabilidades atuais:

- onboarding com email e salario;
- registro conversacional de receitas e despesas;
- registro por audio com transcricao;
- historico paginado;
- resumo mensal;
- recorrencias mensais com lembretes;
- lembrete diario de uso em faixa horaria configurada;
- geracao e envio de relatorio por email;
- persistencia relacional em PostgreSQL.

## Stack e Integracoes

- Python
- `python-telegram-bot`
- PostgreSQL
- SQLAlchemy
- Alembic
- `requests`
- `python-dotenv`
- SMTP
- Mistral como provedor padrão de IA via API OpenAI-compatible

## Arquitetura atual

- `src/chamaleon/bot/`: handlers Telegram e callbacks
- `src/chamaleon/services/`: parser, resumo e relatorios
- `src/chamaleon/repos/`: acesso a dados
- `src/chamaleon/infra/`: DB, modelos, email, IA e config
- `alembic/`: migracoes
- `tests/`: parser e resumo financeiro

## Fluxos Principais

### Onboarding

- `/start` verifica existencia do usuario por `telegram_user_id`.
- Se nao existir, pede email e depois salario.
- O cadastro e salvo em `users`.

### Registro de Transacoes

- `/registro` continua suportado.
- Texto natural passou a ser o fluxo principal.
- O parser extrai valor, categoria, tipo e data relativa simples antes da confirmacao.
- O bot tambem aceita audio e transcreve com Mistral antes de passar pelo mesmo parser.

### Historico e Resumo

- historico usa `transactions` no PostgreSQL;
- resumo mensal usa salario base mais entradas e gastos do mes atual;
- o resumo agora tambem gera insights mensais curtos a partir do saldo, do peso das categorias e do ritmo de consumo.

### Recorrencias e lembretes

- recorrencias ficam em `recurring_rules`;
- o cadastro atual e guiado pelo bot com descricao, valor e dia do mes;
- o usuario tambem consegue editar nome, valor e dia, alem de pausar, reativar e excluir a recorrencia pelo proprio chat;
- o bot dispara lembrete perto do vencimento da recorrencia;
- cada usuario tambem recebe no maximo um lembrete de uso por dia em um horario sorteado dentro da janela configurada;
- os disparos sao feitos pelo `JobQueue` do `python-telegram-bot`, sem processo separado.

### Relatorio

- o backend agrega dados do periodo;
- chama o cliente de IA diretamente;
- persiste o relatorio em `generated_reports`;
- tenta enviar o conteudo por email.

## Lacunas / Problemas

- o parser natural ainda e heuristico e precisa de mais cobertura de linguagem real;
- o estado da conversa continua volátil em memoria;
- recorrencias ainda nao contam com configuracao de frequencia mais rica, como semanal ou quinzenal, nem com ajuste do prazo de lembrete pelo usuario;
- o lembrete diario e util para reativacao leve, mas ainda nao respeita preferencia fina por usuario alem do horario sorteado no onboarding;
- a geracao do relatorio ainda ocorre inline no fluxo do bot, sem fila ou job worker;
- o fallback deterministico do relatorio e util para disponibilidade, mas reduz a qualidade quando a IA nao esta configurada;
- falta uma suite maior cobrindo callbacks Telegram e repositorios com PostgreSQL real;
- o bootstrap automatico do schema ajuda no desenvolvimento, mas producao deve depender de migracoes controladas.
