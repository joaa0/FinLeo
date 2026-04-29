# FinBot — Especificação Técnica

> Documento de referência para desenvolvimento, manutenção e extensão do sistema.

---

## 1. Visão Geral

FinBot é um assistente financeiro pessoal via Telegram que permite registrar e consultar transações financeiras usando linguagem natural. O sistema combina um bot Python com workflows de automação no Zapier e Google Sheets como camada de persistência.

**Objetivo principal:** permitir que o usuário registre um gasto em menos de 10 segundos, sem abrir planilhas ou apps externos.

---

## 2. Componentes do Sistema

### 2.1 Bot Telegram (`finbot_telegram.py`)

Responsável por toda a interface com o usuário. Gerencia estados de conversa, roteamento de mensagens e chamadas às APIs externas.

**Tecnologia:** Python 3.10+ com `python-telegram-bot` v20+

**Responsabilidades:**
- Receber e processar mensagens e cliques de botões
- Manter estado de conversa por usuário via `context.user_data`
- Ler transações e salário diretamente do Google Sheets via `gspread`
- Enviar payloads para os dois webhooks do Zapier

**O que o bot NÃO faz:**
- Escrever transações diretamente no Sheets (isso é responsabilidade do Zap 1)
- Processar ou validar dados com IA (responsabilidade do Zap 1)

---

### 2.2 Zap 1 — CRUD de Transações

Webhook de entrada para todas as operações de criação, leitura, atualização e deleção de transações.

**Trigger:** `POST` no webhook do Zapier com payload JSON

**Pipeline:**

```
Webhook (catch hook)
    → Python (normaliza campos, gera ID, detecta action)
    → Claude AI via Mistral (valida e normaliza com IA)
    → Parallel Paths (roteia por action)
        ├── CREATE  → Google Sheets (append row)
        ├── READ    → Google Sheets (lookup) → Telegram (mensagem)
        ├── UPDATE  → Google Sheets (lookup + update row)
        ├── DELETE  → Google Sheets (lookup + delete row)
        └── REPORT  → Google Sheets (lookup) → Python (calcula resumo) → Email
```

**Payload esperado (CREATE):**

```json
{
  "action": "create",
  "user_id": "7500965215",
  "description": "ifood",
  "details": "Combo com entrega",
  "amount": 39.0,
  "category": "Alimentação",
  "type": "expense",
  "date": "2026-04-17",
  "_source": "telegram_bot",
  "_timestamp": "2026-04-17T14:30:00.000000"
}
```

---

### 2.3 Zap 2 — Atualização de Salário

Webhook dedicado exclusivamente ao registro e atualização do salário do usuário na aba `users`.

**Trigger:** `POST` no webhook com `action: update_salary`

**Payload esperado:**

```json
{
  "action": "update_salary",
  "user_id": "7500965215",
  "salary": 3500.00,
  "_source": "telegram_bot",
  "_timestamp": "2026-04-17T14:30:00.000000"
}
```

**Lógica no Sheets:**
- Se o `user_id` já existe na aba `users`: atualiza colunas `salary` (D) e `updated_at` (E)
- Se não existe: cria nova linha com `user_id` na col A, `salary` na col D

---

### 2.4 Google Sheets (Banco de Dados)

Atua como banco de dados relacional simplificado. Cada aba é tratada como uma tabela.

**Abas:**

| Aba | Função |
|---|---|
| `transactions` | Armazena todas as transações financeiras |
| `users` | Armazena dados de usuário (email, salário) |
| `categories` | Lista canônica de categorias *(não implementada)* |
| `logs` | Auditoria de operações *(não implementada)* |

---

## 3. Fluxo de Dados

### 3.1 CREATE — Registrar Gasto

```
Usuário digita "ifood 39" ou "ifood 39 | sem cebola" no Telegram
    → finbot_telegram.py: parse_quick_expense() extrai descrição, valor e details opcional
    → finbot_telegram.py: detect_category() detecta categoria por keyword
    → finbot_telegram.py: show_confirmation() exibe preview
    → Usuário confirma
    → finbot_telegram.py: send_expense_to_zapier() envia POST para ZAPIER_WEBHOOK_EXPENSE
    → Zap 1: Python normaliza + Claude valida
    → Zap 1: insere linha na aba transactions
    → finbot_telegram.py: exibe confirmação de sucesso
```

### 3.2 READ — Ver Histórico

```
Usuário clica em "📊 Histórico"
    → finbot_telegram.py: show_history() chama gs_client.get_user_transactions(user_id)
    → gspread: lê todas as linhas da aba transactions
    → finbot_telegram.py: filtra por user_id
    → finbot_telegram.py: format_transactions() pagina e formata
    → Telegram: exibe lista com navegação
```

### 3.3 SALARY — Registrar Salário

```
Usuário clica em "💵 Meu Salário"
    → finbot_telegram.py: show_salary_menu() lê salary + expenses do Sheets
    → Exibe: salário, gastos do mês, saldo disponível
    → Usuário clica "✏️ Registrar / Atualizar"
    → finbot_telegram.py: state = AWAITING_SALARY
    → Usuário digita o valor
    → finbot_telegram.py: process_salary_input() valida e envia POST para ZAPIER_WEBHOOK_SALARY
    → Zap 2: cria ou atualiza linha na aba users
    → finbot_telegram.py: exibe confirmação
```

---

## 4. Gerenciamento de Estado

O bot usa `context.user_data` do `python-telegram-bot` para manter estado por usuário entre mensagens. Não há persistência de estado — se o bot reiniciar, os estados são perdidos.

**Estados definidos:**

```python
MENU               = 0  # estado padrão (sem estado ativo)
AWAITING_EXPENSE   = 1  # aguardando "descrição valor" via menu
SELECTING_CATEGORY = 2  # reservado (não implementado)
CONFIRMING         = 3  # reservado (não implementado)
AWAITING_SALARY    = 4  # aguardando valor do salário
```

**Chaves usadas em `context.user_data`:**

| Chave | Tipo | Descrição |
|---|---|---|
| `state` | int | Estado atual da conversa |
| `pending_expense` | dict | Gasto aguardando confirmação |
| `history_page` | int | Página atual do histórico |
| `history_transactions` | list | Cache das transações carregadas |
| `history_total_pages` | int | Total de páginas do histórico |

---

## 5. Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Token do bot (obtido no @BotFather) |
| `ZAPIER_WEBHOOK_EXPENSE` | ✅ | URL do webhook do Zap 1 |
| `ZAPIER_WEBHOOK_SALARY` | ✅ | URL do webhook do Zap 2 |
| `GOOGLE_SHEET_ID` | ✅ | ID da planilha (extraído da URL) |
| `GOOGLE_CREDENTIALS_JSON` | ✅* | Conteúdo JSON das credenciais (Railway) |
| `GOOGLE_CREDENTIALS_PATH` | ✅* | Caminho para o arquivo `.json` (local) |
| `SHEET_NAME` | ❌ | Nome da aba de transações (padrão: `transactions`) |
| `USERS_SHEET_NAME` | ❌ | Nome da aba de usuários (padrão: `users`) |

*Apenas uma das duas opções de credencial é necessária. `GOOGLE_CREDENTIALS_JSON` tem prioridade sobre `GOOGLE_CREDENTIALS_PATH`.

---

## 6. Autenticação Google Sheets

O `GoogleSheetsClient` suporta dois modos de autenticação, com prioridade definida:

```
1. GOOGLE_CREDENTIALS_JSON (string JSON)  ← usado no Railway
       ↓ se não existir
2. GOOGLE_CREDENTIALS_PATH (arquivo .json) ← usado localmente
       ↓ se não existir
3. ValueError — erro explícito na inicialização
```

O cliente é inicializado como singleton global na startup do bot. Se a conexão falhar, `gs_client = None` e as features que dependem do Sheets exibem uma mensagem de erro ao usuário sem crashar o bot.

---

## 7. Categorização Automática

O bot detecta a categoria pelo campo `description` via keyword matching simples (sem IA). A IA do Zap 1 faz uma segunda passagem para refinar casos que o matching local não cobriu.

**Mapeamento atual:**

| Keywords | Categoria |
|---|---|
| ifood, uber eats, rappi, pizza, restaurante, lanche, café | Alimentação |
| uber, 99, taxi, passagem, combustível, gasolina | Transporte |
| netflix, spotify, cinema, jogo | Entretenimento |
| farmácia, médico, dentista, vitamina | Saúde |
| curso, livro, escola | Educação |
| mercado, supermercado, roupa, eletrônico | Compras |
| *(nenhum match)* | Outros |

**Limitação conhecida:** o matching é feito por `keyword in text.lower()`, então "uber eats" pode conflitar com "uber" se a ordem dos itens no dict for alterada. Python 3.7+ garante ordem de inserção nos dicts, então "uber eats" deve aparecer **antes** de "uber" no `CATEGORY_MAP`.

## 7.1 Formato rápido com details opcional

O registro rápido continua compatível com o formato legado:

```text
/registro mercado 84
```

Agora também aceita observações após o separador opcional `|`:

```text
/registro mercado 84 | compra semanal com arroz e carne
```

**Regras atuais:**

- Apenas o trecho antes de `|` é usado para extrair `description` e `amount`
- A inferência de `category` e `type` também usa apenas o trecho antes de `|`
- O trecho após `|` é armazenado em `details`
- Se `|` não existir, `details = ""`
- Espaços extras nas duas partes são removidos

---

## 8. Inconsistências Conhecidas

### 8.1 `user_id` histórico inconsistente

Transações antigas no Sheets foram inseridas com `user_id = "João"` ou `"webhook_user"` em vez do ID numérico do Telegram. O READ do bot filtra por ID numérico, então essas linhas não aparecem no histórico do usuário.

**Solução recomendada:** normalizar manualmente as linhas antigas no Sheets para `user_id = "7500965215"`.

### 8.2 Descriptions sujas

Alguns registros têm o valor embutido na descrição (`"Restaurante 39 reais"`). Isso ocorre quando o usuário envia a descrição no formato errado antes da normalização da IA ser aplicada.

### 8.3 Persistência de `details` depende do Zap/Sheets

O bot agora envia `details` no payload de criação e consegue exibir o campo no preview e no histórico. Ainda assim, o histórico só mostrará a observação se o Zap 1 e a planilha também persistirem e devolverem essa coluna/campo na leitura.

### 8.4 Sem ConversationHandler nativo

O bot gerencia estados manualmente via `context.user_data['state']` em vez de usar o `ConversationHandler` do `python-telegram-bot`. Isso pode causar estados "travados" se o usuário abandonar um fluxo no meio sem completar ou cancelar.

**Solução recomendada:** implementar um comando `/cancelar` que limpa `context.user_data` e retorna ao menu principal.

---

## 9. Dependências

```
python-telegram-bot==20.x
gspread==6.x
google-auth==2.x
requests==2.x
python-dotenv==1.x
```

---

## 10. Limitações e Considerações de Escala

- **Google Sheets não é um banco de dados real.** Para mais de ~1.000 linhas na aba `transactions`, o `get_all_records()` começa a ficar lento. Para escala maior, considerar migração para Supabase ou Firebase.
- **Sem autenticação multi-usuário real.** O sistema confia no `user_id` do Telegram como identificador único. Não há verificação adicional.
- **Zapier gratuito tem limite de 100 tasks/mês.** Para uso intenso, considerar n8n self-hosted como alternativa.
- **Estado de conversa não persiste entre reinicializações do bot.** Usuários em meio a um fluxo perdem o estado se o Railway reiniciar o serviço.
