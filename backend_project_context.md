# Backend Project Context

## Visão Geral

`ChamaLeon-main` é um backend conversacional centrado em um bot Telegram escrito em Python no arquivo `ChamaLeon_telegram.py`.

O sistema atua como um assistente financeiro pessoal com estas responsabilidades:

- onboarding inicial do usuário com email e salário;
- leitura de usuários e transações no Google Sheets;
- registro e exclusão de transações por webhooks no Zapier;
- cálculo local do resumo financeiro mensal;
- solicitação de relatório financeiro por email.

## Stack e Integrações

- Python
- `python-telegram-bot`
- `requests`
- `gspread`
- `google-auth`
- `python-dotenv`
- Google Sheets como persistência nas abas `transactions` e `users`
- Zapier com dois webhooks:
  - `ZAPIER_WEBHOOK_EXPENSE` para `create`, `delete` e `report`
  - `ZAPIER_WEBHOOK_SALARY` para `update_salary`
- Mistral AI de forma indireta no fluxo `REPORT` do Zap 1

## Fluxos Principais

### Onboarding

- `/start` verifica se o `user_id` já existe na aba `users` com salário válido.
- Se não existir, o bot pede email e salário.
- O onboarding inicial grava ou atualiza a linha diretamente no Google Sheets, sem usar o Zap 2.

### Registro de Transações

- `/registro` aceita mensagens curtas como `ifood 39 | almoço com cliente`.
- O bot extrai `description`, `amount` e `details`.
- A categoria e o tipo são inferidos localmente antes de enviar o payload ao Zap 1.

### Histórico e Resumo

- Histórico e resumo mensal são calculados pelo próprio bot a partir do Google Sheets.
- Existe cache em memória por usuário com TTL curto para reduzir leituras repetidas.

## Ajuste Recente

### Ampliação do mapa de categorias

O classificador local foi ampliado para capturar mais formas de registro livre vindas do usuário.

Mudanças aplicadas:

- expansão do `CATEGORY_MAP` com mais termos de Alimentação, Transporte, Moradia, Entretenimento, Saúde, Educação, Compras e Trabalho;
- inclusão explícita de `Trabalho` em `CATEGORIES`;
- adoção de normalização de texto antes do matching para tolerar:
  - acentos;
  - variações com e sem espaço;
  - diferenças simples de digitação como `ubereats`, `ônibus`, `pro labore`, `salario`.

## Lacunas / Problemas

- O parser de `/registro` ainda depende de um formato curto de texto e não entende frases mais naturais como “gastei 42 no ifood ontem”.
- O classificador continua baseado em palavras-chave; ele ficou mais amplo, mas ainda não aprende automaticamente com novos padrões reais de uso.
- Não há suíte de testes automatizados cobrindo o classificador de categorias, o parser de transações e os contratos com os webhooks.
- O arquivo principal concentra lógica demais: integração Telegram, Google Sheets, cache, parsing e regras de negócio seguem acoplados em um único módulo.
- O `.env.example` contém um token preenchido e deveria ficar totalmente sanitizado.
- Há dependência operacional forte de Google Sheets e Zapier; indisponibilidade externa afeta o comportamento do bot.
