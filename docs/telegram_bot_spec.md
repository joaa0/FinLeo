# FinBot — Especificação Técnica

> Documento de referência para desenvolvimento, manutenção e extensão do sistema.

---

## 1. Visão Geral

FinBot é um assistente financeiro pessoal via Telegram que permite registrar, consultar e excluir transações financeiras usando linguagem natural simples. O sistema combina um bot Python, workflows no Zapier e Google Sheets como camada de persistência.

**Objetivo principal:** permitir que o usuário registre um gasto ou recebimento em menos de 10 segundos, sem abrir planilhas ou aplicativos externos.

**Estado atual do sistema:**

- Bot Telegram em Python funcionando como interface principal.
- Google Sheets usado como banco simplificado.
- Zap 1 responsável pelas operações de transação: `CREATE`, `READ`, `DELETE` e `REPORT`.
- Zap 2 responsável apenas por atualização de salário do usuário.
- Relatório por e-mail já existe no Zap 1, mas ainda é um resumo operacional simples.
- Relatório com insights comportamentais por IA ainda não foi implementado.

---

## 2. Componentes do Sistema

### 2.1 Bot Telegram (`finbot_telegram.py`)

Responsável por toda a interface com o usuário. Gerencia estados de conversa, roteamento de mensagens, leitura direta no Google Sheets e chamadas aos webhooks do Zapier.

**Tecnologia:** Python 3.10+ com `python-telegram-bot`.

**Responsabilidades:**

- Receber comandos, mensagens e cliques de botões.
- Controlar estado por usuário via `context.user_data`.
- Validar onboarding inicial: e-mail e salário.
- Ler histórico e salário diretamente do Google Sheets via `gspread`.
- Calcular resumo mensal localmente: `saldo = salário + entradas - gastos`.
- Enviar payloads para os webhooks do Zapier:
  - `ZAPIER_WEBHOOK_EXPENSE` → Zap 1.
  - `ZAPIER_WEBHOOK_SALARY` → Zap 2.
- Exibir menu, confirmação de registro, histórico paginado, resumo de salário e fluxo de exclusão.

**O que o bot não deve fazer:**

- Escrever transações diretamente na aba `transactions`.
- Executar a deleção diretamente no Google Sheets.
- Fazer análise financeira avançada com IA.
- Substituir os workflows do Zapier.

---

### 2.2 Zap 1 — Transações e Relatórios

Webhook principal para operações ligadas à aba `transactions` e ao envio de relatório por e-mail.

**Trigger:** `POST` no webhook do Zapier com payload JSON.

**Estrutura baseada no workflow atual:**

```text
1. Webhooks by Zapier — Catch Hook
2. Code by Zapier — Run Python
3. Paths — Split into paths
    ├── CREATE
    │   ├── Path conditions
    │   ├── Code by Zapier — Run Python
    │   ├── Code by Zapier — Run Python
    │   └── Google Sheets — Create Spreadsheet Row
    │
    ├── READ
    │   ├── Path conditions
    │   ├── Google Sheets — Lookup Spreadsheet Rows
    │   ├── Code by Zapier — Run Python
    │   ├── Code by Zapier — Run Python
    │   └── Telegram — Send Message
    │
    ├── DELETE
    │   ├── Path conditions
    │   ├── Google Sheets — Lookup Spreadsheet Row
    │   └── Google Sheets — Delete Spreadsheet Row(s)
    │
    └── REPORT
        ├── Path conditions
        ├── Google Sheets — Lookup Spreadsheet Rows
        ├── Code by Zapier — Run Python
        ├── Google Sheets — Lookup Spreadsheet Row
        └── Email by Zapier — Send Outbound Email
```

**Ações suportadas:**

| Action | Status | Responsabilidade |
|---|---:|---|
| `create` | Implementado | Inserir nova transação na aba `transactions` |
| `read` | Implementado/legado | Buscar transações e enviar resposta via Telegram pelo Zap |
| `delete` | Implementado | Buscar transação por `transaction_id` e deletar linha |
| `report` | Parcial | Gerar resumo financeiro e enviar e-mail |
| `update` | Removido do fluxo atual | Não deve ser tratado como path ativo no Zap 1 neste estágio |

> Observação: o bot atualmente também faz leitura direta via `gspread` para histórico e salário. O path `READ` no Zap 1 pode existir como fluxo legado ou complementar, mas a leitura principal do bot não depende dele.

---

### 2.3 Zap 2 — Atualização de Salário

Webhook dedicado exclusivamente ao registro ou atualização de salário do usuário na aba `users`.

**Trigger:** `POST` no webhook com `action: update_salary`.

**Estrutura atual recomendada:**

```text
1. Webhooks by Zapier — Catch Hook
2. Code by Zapier — Run Python
3. Filter — entity exactly matches user
4. Google Sheets — Lookup Spreadsheet Row (users)
5. Google Sheets — Update Spreadsheet Row (users)
6. Webhook Response (opcional)
```

**Regra importante:** o Zap 2 não deve ter múltiplos paths. O antigo Path B foi apagado e não deve voltar.

**O Zap 2 não deve conter:**

- Paths paralelos.
- IA.
- Lógica de transação.
- Campos como `description`, `category`, `amount`, `type`, `id` ou `transaction_id`.
- Criação automática de linha via `Create if not found` no Lookup.

**Payload esperado:**

```json
{
  "action": "update_salary",
  "user_id": "7500965215",
  "salary": 3500.00,
  "_source": "telegram_bot",
  "_timestamp": "2026-04-29T21:00:00"
}
```

**Mapeamento esperado na aba `users`:**

| Coluna | Campo |
|---|---|
| A | `user_id` |
| B | `email` |
| C | `registered_date` |
| D | `salary` |
| E | `updated_at` |

No update de salário, mapear apenas:

- `salary` → coluna D.
- `updated_at` → coluna E.

Não remapear `user_id`, `email` ou `registered_date` durante update simples de salário.

---

### 2.4 Google Sheets

Atua como banco de dados simplificado. Cada aba funciona como uma tabela.

| Aba | Função | Status |
|---|---|---|
| `transactions` | Armazena transações financeiras | Implementada |
| `users` | Armazena e-mail, salário e datas de usuário | Implementada |
| `categories` | Lista canônica de categorias | Planejada/não implementada |
| `logs` | Auditoria de operações | Planejada/não implementada |

**Estrutura esperada da aba `transactions`:**

| Coluna | Campo | Observação |
|---|---|---|
| A | `id` | ID único da transação |
| B | `user_id` | ID numérico do Telegram |
| C | `date` | Data da transação |
| D | `description` | Descrição curta |
| E | `category` | Categoria normalizada |
| F | `amount` | Valor |
| G | `type` | `expense` ou `income` |
| H | `created_at` | Data/hora de criação |
| I | `updated_at` | Data/hora de atualização |
| J | `details` | Observações opcionais |

---

## 3. Fluxos de Dados

### 3.1 Onboarding

```text
Usuário envia /start
    → Bot verifica se user_id existe na aba users
    → Se não existe ou não tem salário válido:
        → pede e-mail
        → valida e-mail
        → pede salário inicial
        → cria ou atualiza usuário na aba users via gspread
        → libera menu principal
    → Se já existe:
        → exibe menu principal
```

**Observação:** o onboarding inicial pode criar/atualizar o usuário diretamente pelo bot via `gspread`. O Zap 2 continua sendo usado para atualização posterior de salário pelo menu.

---

### 3.2 CREATE — Registrar transação

```text
Usuário digita:
    /registro ifood 39
ou:
    /registro mercado 84 | compra semanal com arroz e carne

Bot:
    → parse_quick_expense() extrai description, amount e details
    → detect_category() define category e type por keyword
    → show_confirmation() exibe preview
    → usuário confirma
    → send_expense_to_zapier() envia payload para Zap 1

Zap 1:
    → normaliza campos
    → roteia para path CREATE
    → insere nova linha na aba transactions

Bot:
    → invalida cache local
    → mostra confirmação de sucesso
```

**Payload enviado pelo bot:**

```json
{
  "action": "create",
  "user_id": "7500965215",
  "description": "mercado",
  "details": "compra semanal com arroz e carne",
  "amount": 84.0,
  "category": "Compras",
  "type": "expense",
  "date": "2026-04-29",
  "_source": "telegram_bot",
  "_timestamp": "2026-04-29T21:00:00",
  "_normalized": true
}
```

---

### 3.3 READ — Histórico

Fluxo principal atual:

```text
Usuário clica em "📊 Histórico" ou usa /historico
    → Bot chama gs_client.get_user_transactions(user_id)
    → gspread lê rows da aba transactions
    → Bot filtra por user_id exato
    → format_transactions() pagina e formata
    → Telegram exibe histórico com navegação
```

O bot usa cache local temporário para reduzir leituras repetidas no Google Sheets.

---

### 3.4 DELETE — Excluir transação

```text
Usuário clica em "🗑️ Deletar Transação"
    → Bot lê as últimas transações do usuário
    → Exibe até 10 transações recentes como botões
    → Usuário escolhe uma transação
    → Bot mostra tela de confirmação
    → Usuário confirma
    → Bot envia payload para Zap 1 com action=delete e transaction_id
    → Zap 1 busca a linha por id
    → Zap 1 deleta a linha no Google Sheets
    → Bot invalida cache e confirma exclusão
```

**Payload de delete:**

```json
{
  "action": "delete",
  "user_id": "7500965215",
  "transaction_id": "7500965215_20260429152343",
  "_source": "telegram_bot",
  "_timestamp": "2026-04-29T21:30:00"
}
```

**Regra de segurança lógica:** o bot só permite selecionar transações carregadas para o próprio `user_id`. O Zap 1 deve buscar a linha pelo `id` da transação.

---

### 3.5 SALARY — Atualizar salário

```text
Usuário clica em "💵 Meu Salário"
    → Bot lê salário em users
    → Bot calcula entradas e gastos do mês em transactions
    → Exibe resumo do mês
    → Usuário clica em "Registrar / Atualizar"
    → Bot recebe novo valor
    → Bot envia payload para Zap 2
    → Zap 2 faz lookup do user_id em users
    → Zap 2 atualiza salary e updated_at
    → Bot invalida cache e confirma
```

**Cálculo exibido pelo bot:**

```text
saldo disponível = salário registrado + entradas do mês - gastos do mês
```

---

### 3.6 REPORT — Relatório por e-mail

Estado atual:

```text
Usuário aciona report
    → Zap 1 entra no path REPORT
    → Busca transações/dados do usuário no Google Sheets
    → Code Step calcula resumo financeiro básico
    → Lookup busca o e-mail do usuário
    → Email by Zapier envia e-mail
```

**Status:** parcialmente implementado.

**O que já existe:**

- Envio de e-mail via Email by Zapier.
- Cálculo básico de receitas, despesas, saldo, categorias e últimas transações.

**O que ainda não existe:**

- Análise comportamental avançada por IA.
- Cruzamento profundo entre salário, categorias, recorrência e padrões humanos.
- Geração de insights fortes com justificativa.
- Recomendações como:
  - gasto alto em delivery apesar de gasto alto em mercado;
  - transporte privado acima de alternativa pública estimada;
  - recorrências pequenas que somam valor relevante;
  - categorias que cresceram muito em relação ao padrão do usuário;
  - alertas de risco financeiro baseados em proporção da renda.

**Meta futura para o REPORT com IA:**

```text
REPORT atual:
    dados tabulares → resumo numérico → e-mail

REPORT desejado:
    dados tabulares + salário + histórico + padrões
        → IA analisa comportamento financeiro
        → gera diagnóstico, hipóteses e sugestões acionáveis
        → e-mail com insights personalizados
```

A IA do report deve ser tratada como etapa futura do Zap 1, não como responsabilidade do bot Telegram.

---

## 4. Gerenciamento de Estado

O bot usa `context.user_data` para controlar o fluxo de conversa por usuário.

**Estados atuais:**

```python
MENU                       = 0
AWAITING_EXPENSE           = 1
SELECTING_CATEGORY         = 2
CONFIRMING                 = 3
AWAITING_SALARY            = 4
AWAITING_EMAIL             = 5
AWAITING_ONBOARDING_SALARY = 6
```

**Chaves relevantes em `context.user_data`:**

| Chave | Tipo | Função |
|---|---|---|
| `state` | int | Estado atual do fluxo |
| `pending_expense` | dict | Transação aguardando confirmação |
| `history_page` | int | Página atual do histórico |
| `history_transactions` | list | Cache de transações do histórico |
| `history_total_pages` | int | Total de páginas do histórico |
| `onboarding_email` | string | E-mail temporário antes de salvar cadastro |
| `_cache` | dict | Cache local com TTL para leituras do Sheets |

**Limitação:** o estado fica em memória. Se o processo reiniciar, fluxos em andamento são perdidos.

---

## 5. Variáveis de Ambiente

| Variável | Obrigatória | Uso |
|---|---:|---|
| `TELEGRAM_BOT_TOKEN` | Sim | Token do bot Telegram |
| `ZAPIER_WEBHOOK_EXPENSE` | Sim | Webhook do Zap 1 |
| `ZAPIER_WEBHOOK_SALARY` | Sim | Webhook do Zap 2 |
| `GOOGLE_SHEET_ID` | Sim | ID da planilha |
| `GOOGLE_CREDENTIALS_JSON` | Condicional | Credenciais Google em produção/cloud |
| `GOOGLE_CREDENTIALS_PATH` | Condicional | Credenciais Google localmente |
| `SHEET_NAME` | Não | Aba de transações; padrão `transactions` |
| `USERS_SHEET_NAME` | Não | Aba de usuários; padrão `users` |

Pelo menos uma forma de credencial Google deve existir: `GOOGLE_CREDENTIALS_JSON` ou `GOOGLE_CREDENTIALS_PATH`.

---

## 6. Categorização e Tipos

A categorização local é feita por keyword matching no campo `description`.

| Keywords | Categoria | Tipo |
|---|---|---|
| ifood, uber eats, rappi, pizza, restaurante, lanche, café | Alimentação | expense |
| uber, 99, taxi, passagem, combustível, gasolina | Transporte | expense |
| netflix, spotify, cinema, jogo | Entretenimento | expense |
| farmácia, médico, dentista, vitamina | Saúde | expense |
| curso, livro, escola | Educação | expense |
| mercado, supermercado, roupa, eletrônico | Compras | expense |
| salário, recebi, ganhei, bônus, freelance, venda, trabalho, renda | Trabalho | income |
| nenhum match | Outros | expense |

**Regra de ordem:** keywords compostas como `uber eats` devem aparecer antes de `uber` para evitar classificação errada.

---

## 7. Formato de Registro com `details`

O registro rápido aceita observações opcionais usando `|`.

```text
/registro mercado 84 | compra semanal com arroz e carne
```

**Regras:**

- Antes do `|`: usado para extrair `description` e `amount`.
- Depois do `|`: armazenado em `details`.
- `details` é opcional.
- `details` deve ser preservado sem reescrita agressiva.
- O Zap 1 deve gravar `details` na coluna J da aba `transactions`.

---

## 8. Cache e Latência

O bot usa cache local por usuário com TTL curto para reduzir chamadas repetidas ao Google Sheets.

**TTL atual:** 60 segundos.

**Chaves principais:**

- `transactions`
- `salary_summary`

**Invalidação:**

- Após `CREATE`: invalidar `transactions` e `salary_summary`.
- Após `DELETE`: invalidar `transactions` e `salary_summary`.
- Após atualização de salário: invalidar `salary_summary`.

---

## 9. Inconsistências Conhecidas

### 9.1 User ID histórico inconsistente

Transações antigas podem ter sido gravadas com `user_id = "João"` ou `user_id = "webhook_user"` em vez do ID numérico do Telegram. Essas linhas não aparecem corretamente no histórico filtrado pelo bot.

**Correção:** normalizar manualmente linhas antigas para o ID real do Telegram.

### 9.2 Zap 2 não deve criar usuário novo via Lookup

O Zap 2 deve atualizar salário de usuário existente. Se `Create if not found` estiver ativado, pode criar linhas desalinhadas ou duplicadas.

**Correção:** manter `Create if not found` desativado no Lookup do Zap 2.

### 9.3 Report ainda não é análise inteligente

O path `REPORT` envia e-mail, mas ainda não entrega o objetivo final de análise comportamental com IA. Deve ser documentado como funcionalidade parcial.

### 9.4 Webhook público

Webhooks do Zapier são endpoints públicos. O sistema ainda deve evoluir para validação com token/API key ou outro mecanismo simples de proteção.

### 9.5 Estado em memória

Como o bot não usa persistência de estado, usuários podem ficar com fluxo interrompido após restart.

**Correção recomendada:** implementar comando `/cancelar` para limpar estado e voltar ao menu.

---

## 10. Segurança e Boas Práticas

- Nunca commitar `.env`, credenciais JSON ou URLs reais de webhook.
- Não expor `TELEGRAM_BOT_TOKEN`.
- Não expor `GOOGLE_CREDENTIALS_JSON`.
- Não expor webhooks reais do Zapier no README público.
- Evitar logs com payloads completos em produção quando contiverem e-mail, salário ou transações.
- Considerar autenticação simples nos webhooks.
- Tratar o Google Sheets como armazenamento provisório, não como banco definitivo para escala.

---

## 11. Dependências

```text
python-telegram-bot
requests
python-dotenv
gspread
google-auth
```

A versão exata deve ser mantida no `requirements.txt`.

---

## 12. Escala e Evolução

### Limitações atuais

- Google Sheets tende a ficar lento com crescimento da aba `transactions`.
- Zapier pode ter custo por volume de tasks.
- Webhooks públicos exigem proteção adicional antes de uso real amplo.
- Relatório inteligente ainda depende de nova etapa de IA.

### Evoluções prováveis

| Evolução | Prioridade | Observação |
|---|---:|---|
| IA no REPORT | Alta | Principal melhoria de valor percebido |
| Proteção de webhook | Alta | Necessária antes de uso público maior |
| `/cancelar` | Média | Reduz estado travado |
| Migração para banco real | Média/baixa | Supabase, Firebase ou PostgreSQL quando Sheets limitar |
| Logs/auditoria | Média | Útil para debug e confiabilidade |
| Categorias canônicas | Baixa/média | Melhora consistência de análise |

---

## 13. Papel dos Documentos no Repositório

### `README.md`

Documento de apresentação do projeto. Deve explicar rapidamente:

- O que é o FinBot.
- Como rodar.
- Quais tecnologias usa.
- Como a arquitetura geral funciona.
- Estrutura resumida dos Zaps.

### `telegram_bot_spec.md` ou `spec.md`

Documento técnico de manutenção. Deve explicar em detalhe:

- Fluxos internos.
- Contratos de payload.
- Estrutura das abas do Google Sheets.
- Responsabilidades de cada Zap.
- Limitações conhecidas.
- Decisões arquiteturais.
- Funcionalidades parciais e futuras.

**Recomendação:** manter este arquivo no repositório, mas sem segredos. Ele é útil para você, para agentes de IA como Codex/Gemini/Copilot e para qualquer pessoa que vá manter o projeto.

---

## 14. Status Consolidado

| Área | Status |
|---|---|
| Bot Telegram | Funcional |
| Onboarding | Funcional |
| Registro de transações | Funcional |
| Details em transações | Funcional se Zap/Sheets estiverem mapeados corretamente |
| Histórico | Funcional via leitura direta no Sheets |
| Deleção | Funcional via Zap 1 |
| Salário | Funcional via users + Zap 2 para update |
| Relatório por e-mail | Parcial |
| IA com insights financeiros | Não implementado |
| Proteção robusta dos webhooks | Pendente |

