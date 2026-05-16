# Backend Project Context

## Visao Geral

`ChamaLeon-main` deixou de ser um script unico acoplado a Sheets/Zapier e passou a ser um backend Python modular para um bot financeiro conversacional no Telegram.

Responsabilidades atuais:

- onboarding com email e salario;
- registro conversacional de receitas e despesas;
- parser hibrido com heuristica local + fallback de IA para casos ambiguos;
- registro por audio com transcricao;
- historico paginado;
- resumo mensal;
- fechamento semanal automatico via Telegram;
- orcamentos mensais por categoria;
- recorrencias mensais com lembretes;
- lembrete diario de uso em faixa horaria configurada;
- geracao e envio de relatorio por email;
- persistencia relacional em PostgreSQL.

Navegacao atual do bot:

- menu principal compacto com `Novo registro`, `Resumo do mês`, `Transações` e `Mais opções`;
- navegacao principal persistente via `Reply Keyboard`;
- `Inline Keyboard` reservado para acoes contextuais e sensiveis;
- submenus para manter a UI menos poluída;
- `Novo registro` continua como CTA principal isolado;
- ao entrar em `Novo registro`, o teclado troca para um modo de captura com `Cancelar registro` e `Voltar ao menu`.

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
- O parser heuristico continua como primeira camada e agora explicita melhor a confidence.
- Quando a confianca cai abaixo do threshold ou o texto fica ambiguo, o backend tenta um fallback estruturado com IA.
- A resposta da IA e validada como JSON estrito antes de virar `TransactionDraft` ou lista de drafts.
- Nenhuma transacao vinda da IA e salva direto; tudo continua passando pela mesma confirmacao do Telegram.
- o bot tambem tenta aceitar mensagens de novo registro em qualquer momento normal do chat, exceto onboarding e configuracoes;
- O bot tambem aceita audio e transcreve com Mistral antes de passar pelo mesmo parser.

### Historico e Resumo

- historico usa `transactions` no PostgreSQL;
- resumo mensal usa salario base mais entradas e gastos do mes atual;
- o resumo agora tambem gera insights mensais curtos a partir do saldo, do peso das categorias e do ritmo de consumo;
- o resumo tambem mostra orcamentos por categoria ja configurados.

### Fechamento semanal

- o backend calcula um fechamento semanal deterministico com base na semana encerrada anterior;
- o texto mostra gastos, entradas, saldo, categoria dominante, orcamentos em atencao, recorrencias proximas e um ponto de atencao;
- o disparo reaproveita o `JobQueue`;
- o controle anti-duplicacao fica em `users.last_weekly_closure_sent_for`.

### Orcamentos por categoria

- orcamentos ficam em `category_budgets`;
- o cadastro atual e guiado pelo bot: categoria e limite mensal;
- o mesmo fluxo tambem atualiza o valor existente;
- enviar `0` remove o orçamento daquela categoria.
- ao registrar gastos, o backend agora calcula cruzamento de 70%, 90% e 100% do teto por categoria e devolve alerta contextual no chat.

### Recorrencias e lembretes

- recorrencias ficam em `recurring_rules`;
- o cadastro atual e guiado pelo bot com descricao, valor e dia do mes;
- o usuario tambem consegue editar nome, valor, frequencia, agenda e prazo do lembrete, alem de pausar, reativar e excluir a recorrencia pelo proprio chat;
- o bot dispara lembrete perto do vencimento da recorrencia;
- cada usuario tambem recebe no maximo um lembrete de uso por dia em um horario sorteado dentro da janela configurada;
- o usuario pode ligar, desligar e sortear novo horario desse lembrete pelo proprio chat;
- os disparos sao feitos pelo `JobQueue` do `python-telegram-bot`, sem processo separado.

### Relatorio

- o backend agrega dados do periodo;
- chama o cliente de IA diretamente;
- persiste o relatorio em `generated_reports`;
- tenta enviar o conteudo por email.

## Lacunas / Problemas

- o parser natural ainda e heuristico e precisa de mais cobertura de linguagem real;
- o fallback com IA melhora ambiguidade, mas ainda depende de validacao defensiva e da disponibilidade do provedor;
- o estado da conversa continua volátil em memoria;
- os alertas de orçamento hoje cobrem cruzamento de 70%, 90% e 100%, mas ainda nao oferecem preferencia por usuario nem histórico de notificações;
- recorrencias ainda nao contam com frequencias mais ricas que as tres principais nem com calendarios personalizados por data fixa;
- o lembrete diario ja pode ser ligado, desligado e rerrolado pelo usuario, mas ainda nao permite escolha manual exata de horario;
- o fechamento semanal e heuristico e ainda nao usa IA apenas para reescrever a leitura final;
- a geracao do relatorio ainda ocorre inline no fluxo do bot, sem fila ou job worker;
- o fallback deterministico do relatorio e util para disponibilidade, mas reduz a qualidade quando a IA nao esta configurada;
- falta uma suite maior cobrindo callbacks Telegram e repositorios com PostgreSQL real;
- o bootstrap automatico do schema ajuda no desenvolvimento, mas producao deve depender de migracoes controladas.
