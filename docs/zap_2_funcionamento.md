# Zap 2 — Atualização de Salário (Funcionamento)

## 📌 Objetivo

O **Zap 2** é responsável exclusivamente por **registrar ou atualizar o salário do usuário** na aba `users` do Google Sheets.

Ele **não deve processar transações**, nem conter lógica de categorização, IA ou múltiplos caminhos complexos.

---

## 🧠 Princípio de Design

- Simples
- Determinístico
- Sem IA
- Sem ambiguidade de entidade

> Zap 2 = apenas `user` + `salary`

---

## 📥 Entrada (Webhook)

Recebe dados do bot:

```json
{
  "action": "update_salary",
  "user_id": "7500965215",
  "salary": 3500.00,
  "_source": "telegram_bot",
  "_timestamp": "2026-04-29T21:00:00"
}
```

---

## ⚙️ Estrutura do Zap

```text
1. Webhook (Catch Hook)
2. Code by Zapier
3. Filter (entity = user)
4. Lookup Spreadsheet Row (users)
5. Update Spreadsheet Row (users)
6. Webhook Response (opcional)
```

---

## 🔧 Step 2 — Code by Zapier

### Código oficial (substituir completamente):

```python
from datetime import datetime

user_id = str(input_data.get("user_id", "")).strip()
salary_raw = input_data.get("salary", 0)

try:
    salary = float(str(salary_raw).replace(",", "."))
except Exception:
    salary = 0

return {
    "action": "update_salary",
    "entity": "user",
    "user_id": user_id,
    "salary": salary,
    "registered_date": datetime.now().strftime("%Y-%m-%d"),
    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}
```

---

## 🔍 Step 3 — Filter

Condição:

```text
entity exactly matches user
```

---

## 🔎 Step 4 — Lookup Spreadsheet Row

Configuração:

```text
Worksheet: users
Lookup Column: user_id
Lookup Value: 2. user_id
Create if not found: ❌ DESATIVADO
```

---

## ✏️ Step 5 — Update Spreadsheet Row

Configuração:

```text
Row: 4. ID (resultado do Lookup)

Campos mapeados:
- salary → 2. salary
- updated_at → 2. updated_at
```

⚠️ **Não mapear:**

- user_id
- email
- registered_date

---

## 🗃️ Estrutura da Aba `users`

| Coluna | Campo |
|-------|------|
| A | user_id |
| B | email |
| C | registered_date |
| D | salary |
| E | updated_at |

---

## 🔴 Problemas Comuns

### 1. Linha sendo criada torta

Causa:
- "Create if not found" ativado
- Campos não mapeados corretamente

Solução:
- Desativar criação no Zap 2

---

### 2. Dados indo para colunas D, E, F...

Causa:
- Schema desatualizado no Zapier

Solução:
- Clicar em:
  - Refresh Fields
  - Remove Extra Fields

---

### 3. Usuário duplicado

Causa:
- Lookup falhando por diferença de tipo (string vs número)

Solução:
- Sempre usar `str(user_id).strip()` no Code Step

---

## 🧪 Teste Esperado

1. Usuário já existe na planilha
2. Envia novo salário pelo bot

Resultado esperado:

```text
✔ mesma linha atualizada
✔ nenhuma nova linha criada
✔ colunas corretas (A–E)
```

---

## 🚫 O que NÃO deve existir no Zap 2

- Paths múltiplos (transaction, report, etc)
- IA (Mistral, GPT, etc)
- Campos como:
  - description
  - category
  - amount
  - type
  - id

Esses pertencem exclusivamente ao **Zap 1**.

---

## ✅ Resumo

Zap 2 deve ser:

- Simples
- Previsível
- Isolado

Qualquer complexidade adicional aqui tende a gerar bugs como:

- Linhas desalinhadas
- Duplicação de usuários
- Quebra no onboarding

---

**Status recomendado:** produção estável após simplificação.

