# 🤖 FinBot — Seu Assistente Financeiro Inteligente

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/Telegram-Bot-blue?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram Bot">
  <img src="https://img.shields.io/badge/Google-Sheets-green?style=for-the-badge&logo=google-sheets&logoColor=white" alt="Google Sheets">
  <img src="https://img.shields.io/badge/Zapier-Integration-orange?style=for-the-badge&logo=zapier&logoColor=white" alt="Zapier">
</p>

O **FinBot** é um assistente financeiro poderoso que vive no seu Telegram. Ele combina a simplicidade de mensagens de chat com a robustez do Google Sheets e automação do Zapier para ajudar você a manter suas finanças sob controle sem esforço.

---

## ✨ Principais Funcionalidades

*   🚀 **Onboarding Obrigatório**: Cadastro simples de e-mail e salário no primeiro uso.
*   💸 **Registro Ultrarrápido**: Use `/registro café 5` e pronto! O bot cuida da categoria e data.
*   📈 **Cálculo de Saldo em Tempo Real**: `Saldo = Salário + Entradas - Gastos`. Sempre atualizado.
*   📥 **Suporte a Receitas e Despesas**: Identificação inteligente de PIX recebidos, freelance, vendas, etc.
*   📊 **Histórico Paginado**: Veja suas últimas transações sem sair do Telegram.
*   🗑️ **Exclusão de Transações**: Interface intuitiva para remover registros incorretos.
*   📋 **Normalização Inteligente**: Aceita valores como `R$ 50,00`, `50.00` ou `50` e datas em múltiplos formatos (incluindo serial do Excel).

---

## 🏗️ Arquitetura do Sistema

O FinBot utiliza uma arquitetura híbrida para garantir velocidade e confiabilidade:

```mermaid
graph TD
    A[Telegram User] <--> B[Python Bot]
    B -- Webhook POST --> C[Zapier Webhooks]
    C -- "Ação (Create/Update/Delete)" --> D[Google Sheets]
    B -- "Leitura Direta (gspread)" --> D
    D -- "Dados (Histórico/Salário)" --> B
```

### Onde os dados moram:
1.  **Aba `transactions`**: Todas as suas movimentações financeiras.
2.  **Aba `users`**: Seus dados de perfil, e-mail e salário base.

---

## 📱 Guia de Uso

### 🆕 Primeiro Acesso (Onboarding)
Ao enviar `/start` pela primeira vez, o bot guiará você:
1.  **E-mail**: Informe seu e-mail para contato/relatórios.
2.  **Salário**: Informe quanto você ganha por mês.
*O acesso ao menu principal só é liberado após concluir estes passos.*

### 💵 Resumo Financeiro (`/salario`)
O bot exibe um resumo completo do seu mês:
> 💵 **Resumo do Mês**
> 
> 💰 Salário registrado: R$ 5.000,00
> 📥 Entradas este mês: R$ 800,00
> 💸 Gastos do mês: R$ 1.200,00
> 🟢 Saldo disponível: R$ 4.600,00

---

## 🏷️ Categorização Inteligente (Keywords)

O bot detecta automaticamente o tipo e categoria com base no que você escreve:

| Tipo | Categoria | Keywords Exemplos |
| :--- | :--- | :--- |
| **Gasto** | Alimentação | `ifood, burger king, restaurante, mercado` |
| **Gasto** | Transporte | `uber, 99, gasolina, metro` |
| **Receita** | Trabalho | `salário, pix recebido, freelance, venda` |
| **Gasto** | Saúde | `farmácia, médico, dentista` |

---

## ⚙️ Configuração e Instalação

### 1. Requisitos
*   Python 3.10+
*   Google Cloud Service Account (JSON)
*   2 Webhooks no Zapier (Zap 1: Transações, Zap 2: Salário)

### 2. Variáveis de Ambiente (`.env`)
```bash
TELEGRAM_BOT_TOKEN=seu_token_aqui
ZAPIER_WEBHOOK_EXPENSE=url_do_zap_1
ZAPIER_WEBHOOK_SALARY=url_do_zap_2
GOOGLE_SHEET_ID=id_da_planilha
GOOGLE_CREDENTIALS_PATH=caminho/para/credentials.json
# USERS_SHEET_NAME=users (opcional)
```

### 3. Execução
```bash
pip install -r requirements.txt
python finbot_telegram.py
```

---

## 🚢 Deploy no Railway / Cloud

Para deploy em nuvem, você pode usar a variável `GOOGLE_CREDENTIALS_JSON` colando o conteúdo do seu arquivo JSON de credenciais. O bot tratará automaticamente as quebras de linha da chave privada.

```
worker: python finbot_telegram.py
```

---

## 📝 Licença
Este projeto é de uso livre. Sinta-se à vontade para clonar e adaptar para suas necessidades financeiras! 🚀
