# Assistente Financeiro com Webhooks e Google Sheets

## 📋 Descrição Geral

Este Zap automatiza o gerenciamento de dados financeiros através de webhooks, processamento inteligente de dados e sincronização com Google Sheets. Ele recebe solicitações via webhook, normaliza os dados usando IA, e distribui as informações para duas planilhas diferentes dependendo do tipo de entidade (usuário ou transação).

---

## 🔄 Fluxo de Funcionamento

### **1️⃣ Trigger: Webhook (Passo 1)**
- **App**: Webhook by Zapier
- **Função**: Aguarda requisições HTTP POST em um endpoint seguro
- **Dados esperados**:
  - `action` (create, read, update, delete)
  - `entity` (user ou transaction)
  - `user_id` / `user_name`
  - `description`
  - `amount`
  - `category`
  - `type` (income/expense)
  - `date`
  - `salary` (opcional)

---

### **2️⃣ Processamento: Code Step (Passo 2)**
- **App**: Code by Zapier (Python)
- **Função**: Processa e normaliza os dados recebidos
- **Lógica principal**:
  - 🔴 **Validação 1**: Detecta a entidade (user/transaction) baseado na presença de `salary`
  - 🔴 **Validação 2**: Converte `salary` para float com tratamento de erros
  - Gera ID único combinando `user_id` + timestamp
  - Normaliza campos vazios com valores padrão
  - **Detecção automática de ação**: Se `entity = transaction`, analisa o `description` para inferir a ação:
    - Palavras-chave como "deletar", "remover" → action = `delete`
    - "corrigir", "atualizar" → action = `update`
    - "relatar", "extrato" → action = `report`
    - "ver", "histórico" → action = `read`
  - **Normalização de categoria**: Se `category = Outro`, infere automaticamente baseado em palavras-chave:
    - 🍔 **Alimentação**: ifood, uber eats, pizza, restaurante, etc.
    - 🚕 **Transporte**: uber, taxi, metro, combustível, etc.
    - 🏥 **Saúde**: farmácia, consulta, medicamento, etc.
    - 🎬 **Lazer**: cinema, show, ingresso, etc.
    - 📚 **Educação**: curso, livro, aula, faculdade, etc.
    - 💼 **Trabalho**: salário, renda, freelance, etc.
- **Saída**: JSON estruturado com todos os campos normalizados

---

### **3️⃣ Inteligência Artificial: Normalização com Mistral (Passo 3)**
- **App**: Mistral AI
- **Modelo**: `mistral-small-latest`
- **Função**: Recebe os dados do Code step e aplica regras de normalização final
- **Regras aplicadas**:
  1. Se `action` vazio → padroniza como `create`
  2. Se `amount = 0` → tenta extrair do `description`
  3. Se `category = Outro` → infere da descrição
  4. Se `type` vazio → detecta como income ou expense
  5. Se `email` vazio → mantém vazio
- **Saída**: JSON totalmente normalizado e pronto para atualização

---

### **4️⃣ Roteamento Condicional: Paths**

O Zap usa **conditional logic (Paths)** para rotear os dados para duas workflows diferentes:

#### **🟦 Path A: Usuários**
**Condição**: `entity = "user"`

**Passos**:
1. **Lookup em Google Sheets** (usuários)
   - Procura pelo `user_id` na coluna A
   - Encontra a linha correspondente

2. **Update Row** - Atualiza os dados do usuário
   - `COL$D` (Salary) ← `salary` normalizado
   - `COL$E` (Data) ← `date`

3. **Webhook POST** - Confirma sucesso
   - Envia resposta com status `success`
   - Inclui `entity`, `user_id`, `salary`, `updated_at`

---

#### **🟥 Path B: Transações**
**Condição**: `entity = "transaction"`

**Passos**:
1. **Lookup em Google Sheets** (transações)
   - Procura pelo `id` gerado na coluna A
   - Encontra a linha da transação

2. **Update Row** - Atualiza os dados da transação
   - `COL$D` (Descrição) ← `description`
   - `COL$E` (Categoria) ← `category`
   - `COL$F` (Valor) ← `amount`
   - `COL$G` (Tipo) ← `type` (income/expense)
   - `COL$I` (Data) ← `date`

3. **Webhook POST** - Confirma sucesso
   - Envia resposta com status `success`
   - Inclui detalhes completos da transação

---

## 📊 Estrutura de Dados

### **Entrada (Webhook)**
```json
{
  "action": "create",
  "entity": "transaction",
  "user_id": "user123",
  "description": "Uber para trabalho",
  "amount": 25.50,
  "category": "Transporte",
  "type": "expense",
  "date": "2025-10-31"
}
```

### **Saída (Webhook Response)**
```json
{
  "status": "success",
  "entity": "transaction",
  "user_id": "user123",
  "description": "Uber para trabalho",
  "category": "Transporte",
  "amount": 25.50,
  "type": "expense",
  "updated_at": "2025-10-31",
  "error": null
}
```

---

## 🎯 Casos de Uso

| Caso | Descrição |
|------|-----------|
| **Registrar Usuário** | Envia webhook com `salary` → atualiza planilha de usuários |
| **Registrar Transação** | Envia webhook com `description` → categoriza e registra em transactions |
| **Categorização Automática** | IA infere categoria baseada em keywords do description |
| **Validação de Dados** | Detecta erros em salary e marca com `error_status` |

---

## ⚙️ Recursos Técnicos

- ✅ **Webhook seguro** com endpoint criptografado
- ✅ **Validação robusta** com error handling
- ✅ **IA inteligente** para normalização de dados
- ✅ **Paths condicionais** para múltiplos fluxos
- ✅ **Google Sheets integrado** para persistência
- ✅ **Webhooks de confirmação** para rastreamento

---

## 🔐 Segurança

- Webhook endpoint não expõe dados sensíveis
- Validação de tipos antes de salvar
- Fallback seguro para valores inválidos
- ID único gerado para rastreabilidade
