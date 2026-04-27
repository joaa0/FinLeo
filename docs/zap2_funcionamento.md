# 📊 Contexto Completo do Zap: "Assistente Financeiro"

Este é um **Zap avançado** que gerencia dados financeiros através de webhooks, processamento de dados com IA, e sincronização com Google Sheets. Aqui está o funcionamento completo:

---

## 🔄 **Fluxo Principal**

### **1️⃣ TRIGGER - Webhook (Recepção de Dados)**
- **App**: Webhooks by Zapier (v2)
- **Função**: Recebe dados via HTTP POST com campos como:
  - `date`, `text`, `type`, `action`, `amount`, `user_id`, `category`, `description`, `salary`, etc.
- **Output**: Disponibiliza todos os campos para os próximos steps

---

### **2️⃣ Code Step - Processamento Python**
- **Linguagem**: Python
- **Funções principais**:
  - ✅ **Detecção de Entity**: Se `salary` existe → `entity = "user"`, senão → `entity = "transaction"`
  - ✅ **Validação**: Converte salary com error handling (se falhar → `entity = "error"`)
  - ✅ **ID Único**: Gera ID único combinando `user_id + timestamp`
  - ✅ **Normalização de Categoria**: Detecta automaticamente (Alimentação, Transporte, Saúde, Lazer, Educação, Trabalho) baseado em keywords no `description`
  - ✅ **Detecção de Action**: Analisa o description para encontrar ações (delete, update, report, read)
  - ✅ **Status de Erro**: Marca `error_status = 'invalid_salary'` se conversão falhar

**Output estruturado**: JSON com `action`, `entity`, `user_id`, `description`, `amount`, `category`, `type`, `date`, `salary`, `id`, `error_status`

---

### **3️⃣ AI Step - Normalização Mistral**
- **App**: Mistral AI (mistral-small-latest)
- **Temperatura**: 0.3 (muito determinístico)
- **Função**: Normaliza os dados do Step anterior aplicando regras:
  - Se `action` vazio → usa `create`
  - Se `amount` é 0 → tenta extrair do description
  - Se `category` é "Outro" → tenta inferir
  - Se `type` vazio → detecta income/expense
  - Se `email` vazio → deixa vazio

**Output**: JSON normalizado apenas (sem explicações)

---

### **4️⃣ Paths Condicionais (Decisão Paralela)**

Aqui acontece a "inteligência" do Zap. Baseado no **entity** do Step 2, o Zap segue dois caminhos diferentes:

#### **🟦 PATH A - Processamento de USERS**
*Executado quando: `entity = "user"`*

1. **Lookup Row** - Busca usuario no Google Sheets (worksheet "users")
   - Critério: `user_id` (coluna A)
   - Retorna: ID da linha encontrada

2. **Update Row** - Atualiza dados do usuário
   - Coluna D: `salary`
   - Coluna E: `date`

3. **Webhook Response** - Envia confirmação
   ```json
   {
     "status": "success",
     "entity": "user",
     "user_id": "...",
     "salary": "...",
     "updated_at": "..."
   }
   ```

---

#### **🟧 PATH B - Processamento de TRANSACTIONS**
*Executado quando: `entity = "transaction"`*

1. **Lookup Row** - Busca transação no Google Sheets (worksheet "transactions")
   - Critério: `id` gerado (coluna A)
   - Retorna: ID da linha encontrada

2. **Update Row** - Atualiza dados da transação
   - Coluna D: `description`
   - Coluna E: `category`
   - Coluna F: `amount`
   - Coluna G: `type` (income/expense)
   - Coluna I: `date`

3. **Webhook Response** - Envia confirmação
   ```json
   {
     "status": "success",
     "entity": "transaction",
     "user_id": "...",
     "description": "...",
     "amount": "...",
     "category": "...",
     "type": "...",
     "updated_at": "..."
   }
   ```

---

## 📈 **Exemplo de Funcionamento**

### **Cenário 1: Entrada de USUÁRIO**
```
POST /webhook?user_id=joao&salary=5000&date=2025-01-15
```
↓
- **Code Step**: Detecta `salary` → `entity = "user"`
- **AI Step**: Normaliza dados
- **PATH A**: Busca usuário "joao" em "users" e atualiza salary=5000
- **Webhook**: Retorna `{"status": "success", "entity": "user", ...}`

---

### **Cenário 2: Entrada de TRANSAÇÃO**
```
POST /webhook?description=Uber para trabalho&amount=25.50&category=Transporte
```
↓
- **Code Step**: Sem `salary` → `entity = "transaction"`, gera ID único
- **AI Step**: Valida description, amount, category
- **PATH B**: Busca/cria transação e atualiza colunas
- **Webhook**: Retorna `{"status": "success", "entity": "transaction", ...}`

---

## 🎯 **Resumo da Arquitetura**

| Componente | Responsabilidade |
|-----------|-----------------|
| **Webhook** | Receber dados externos |
| **Code (Python)** | Validar, detectar tipo, gerar IDs |
| **AI (Mistral)** | Normalizar dados com regras |
| **Paths** | Rotear para usuario OU transacao |
| **Google Sheets** | Armazenar dados persistentemente |
| **Webhooks (saída)** | Confirmar processamento |

---

## ⚡ **Status do Zap**
✅ **PUBLICADO** - O Zap está ativo e funcionando
📊 **Sem issues** - Nenhum erro detectado na configuração

---
