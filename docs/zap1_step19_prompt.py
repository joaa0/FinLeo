import json
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter

# ============================================================
# CONFIGURAÇÕES
# ============================================================

ALLOWED_CATEGORIES = {
    "Alimentação",
    "Transporte",
    "Entretenimento",
    "Saúde",
    "Educação",
    "Moradia",
    "Compras",
    "Gastos de Urgências",
    "Outros",
}

CATEGORY_ALIASES = {
    "alimentacao": "Alimentação",
    "alimentação": "Alimentação",
    "comida": "Alimentação",
    "delivery": "Alimentação",
    "ifood": "Alimentação",
    "uber eats": "Alimentação",
    "rappi": "Alimentação",
    "restaurante": "Alimentação",
    "lanche": "Alimentação",
    "pizza": "Alimentação",

    "transporte": "Transporte",
    "uber": "Transporte",
    "99": "Transporte",
    "taxi": "Transporte",
    "táxi": "Transporte",
    "gasolina": "Transporte",
    "combustivel": "Transporte",
    "combustível": "Transporte",
    "metro": "Transporte",
    "metrô": "Transporte",
    "onibus": "Transporte",
    "ônibus": "Transporte",
    "passagem": "Transporte",

    "lazer": "Entretenimento",
    "entretenimento": "Entretenimento",
    "netflix": "Entretenimento",
    "spotify": "Entretenimento",
    "cinema": "Entretenimento",
    "jogo": "Entretenimento",
    "show": "Entretenimento",

    "saude": "Saúde",
    "saúde": "Saúde",
    "academia": "Saúde",

    "farmacia": "Gastos de Urgências",
    "farmácia": "Gastos de Urgências",
    "medico": "Gastos de Urgências",
    "médico": "Gastos de Urgências",
    "consulta": "Gastos de Urgências",
    "remedio": "Gastos de Urgências",
    "remédio": "Gastos de Urgências",

    "educacao": "Educação",
    "educação": "Educação",
    "curso": "Educação",
    "livro": "Educação",
    "faculdade": "Educação",
    "aula": "Educação",

    "moradia": "Moradia",
    "aluguel": "Moradia",
    "condominio": "Moradia",
    "condomínio": "Moradia",
    "luz": "Moradia",
    "água": "Moradia",
    "agua": "Moradia",
    "internet": "Moradia",

    "compras": "Compras",
    "mercado": "Compras",
    "supermercado": "Compras",
    "roupa": "Compras",
    "eletronico": "Compras",
    "eletrônico": "Compras",
    "shopping": "Compras",
    "amazon": "Compras",
    "mercado livre": "Compras",
    "shein": "Compras",
}

EXPENSE_TYPES = {"expense", "gasto", "despesa", "saida", "saída"}
INCOME_TYPES = {
    "income",
    "receita",
    "entrada",
    "recebido",
    "freelance",
    "venda",
    "salario",
    "salário",
    "pix recebido",
    "bônus",
    "bonus",
}

# ============================================================
# HELPERS
# ============================================================

def normalize_amount(value):
    try:
        s = str(value or "").strip()
        s = s.upper().replace("R$", "").replace("\xa0", "").strip()

        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", ".")

        return float(s)
    except Exception:
        return 0.0


def normalize_text(value):
    return str(value or "").strip()


def parse_date_to_ymd(raw):
    raw = str(raw or "").strip()

    if not raw:
        return None

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).date()
        except Exception:
            pass

    try:
        return datetime.strptime(raw[:10], "%d/%m/%Y").date()
    except Exception:
        pass

    try:
        if raw.replace(".", "", 1).isdigit():
            serial = float(raw)
            return (datetime(1899, 12, 30) + timedelta(days=serial)).date()
    except Exception:
        pass

    return None


def normalize_category(category, description, details):
    category = normalize_text(category)
    raw = f"{category} {description} {details}".lower().strip()

    for allowed in ALLOWED_CATEGORIES:
        if category.lower() == allowed.lower():
            return allowed, False

    for keyword, canonical in CATEGORY_ALIASES.items():
        if keyword in raw:
            return canonical, False

    return "Outros", True


def split_line_items(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    s = str(value)

    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    return [item.strip() for item in s.split(",") if item.strip()]


def contains_any(text, keywords):
    text = str(text or "").lower()
    return any(k in text for k in keywords)


def safe_percent(value, base):
    if base <= 0:
        return 0.0
    return round((value / base) * 100, 1)

BRAZIL_AVG_SALARY = 3300.0
MINIMUM_WAGE = 1518.0
ONE_MIN_WAGE_ABOVE_AVG = BRAZIL_AVG_SALARY + MINIMUM_WAGE

def classify_income_segment(salary):
    if salary <= 0:
        return {
            "segment": "salario_nao_informado",
            "label": "Salário não informado ou inválido",
            "instruction": "Não faça diagnóstico salarial forte. Solicite salário válido para análise mais precisa."
        }

    if salary > 15000:
        return {
            "segment": "renda_muito_alta",
            "label": "Renda acima do limite do modelo simplificado",
            "instruction": "Não fazer análise detalhada. Informar que o caso exige avaliação mais personalizada."
        }

    if salary < BRAZIL_AVG_SALARY:
        return {
            "segment": "abaixo_media",
            "label": "Abaixo da faixa salarial média brasileira",
            "instruction": "Usar tom cuidadoso, priorizar gastos essenciais e sugerir ajustes realistas."
        }

    if salary <= ONE_MIN_WAGE_ABOVE_AVG:
        return {
            "segment": "dentro_media_ate_um_salario_minimo_acima",
            "label": "Dentro da média ou até 1 salário mínimo acima",
            "instruction": "Usar análise prática, com foco em reduzir desperdícios e organizar a sobra."
        }

    return {
        "segment": "acima_media_mais_de_um_salario_minimo",
        "label": "Acima da média por mais de 1 salário mínimo",
        "instruction": "Avaliar inflação de estilo de vida, desperdícios proporcionais e potencial de reserva maior."
    }


def classify_expense_level(expense_rate, balance):
    if balance < 0:
        return {
            "level": "deficit",
            "label": "Déficit no mês",
            "instruction": "Priorizar redução do déficit antes de sugerir reserva."
        }

    if expense_rate > 90:
        return {
            "level": "risco_alto",
            "label": "Renda quase totalmente comprometida",
            "instruction": "Sugerir corte urgente em gastos variáveis."
        }

    if expense_rate > 70:
        return {
            "level": "muitas_despesas",
            "label": "Muitas despesas",
            "instruction": "Priorizar categoria de maior impacto e reduzir comprometimento da renda."
        }

    if expense_rate > 50:
        return {
            "level": "despesas_moderadas",
            "label": "Despesas moderadas",
            "instruction": "Sugerir ajustes leves e controle de categorias variáveis."
        }

    return {
        "level": "poucas_despesas",
        "label": "Poucas despesas",
        "instruction": "Valorizar boa margem e sugerir organização da sobra."
    }


# ============================================================
# INPUTS DO ZAPIER
# ============================================================

user_id = normalize_text(input_data.get("user_id"))
email = normalize_text(input_data.get("email"))
salary = normalize_amount(input_data.get("salary"))

tx_ids = split_line_items(input_data.get("tx_ids"))
tx_user_ids = split_line_items(input_data.get("tx_user_ids"))
tx_dates = split_line_items(input_data.get("tx_dates"))
tx_descriptions = split_line_items(input_data.get("tx_descriptions"))
tx_categories = split_line_items(input_data.get("tx_categories"))
tx_amounts = split_line_items(input_data.get("tx_amounts"))
tx_types = split_line_items(input_data.get("tx_types"))
tx_details = split_line_items(input_data.get("tx_details"))

max_len = max(
    len(tx_ids),
    len(tx_user_ids),
    len(tx_dates),
    len(tx_descriptions),
    len(tx_categories),
    len(tx_amounts),
    len(tx_types),
    len(tx_details),
    0,
)

today = datetime.now().date()
current_month = today.strftime("%Y-%m")

# ============================================================
# PROCESSAMENTO DAS TRANSAÇÕES
# ============================================================

transactions = []
unknown_category_count = 0

category_totals = defaultdict(float)
category_counts = Counter()

income_total = 0.0
expense_total = 0.0

for i in range(max_len):
    tx_id = tx_ids[i] if i < len(tx_ids) else ""
    date_raw = tx_dates[i] if i < len(tx_dates) else ""
    description = tx_descriptions[i] if i < len(tx_descriptions) else ""
    category_raw = tx_categories[i] if i < len(tx_categories) else ""
    amount = normalize_amount(tx_amounts[i] if i < len(tx_amounts) else 0)
    tx_type_raw = normalize_text(tx_types[i] if i < len(tx_types) else "expense").lower()
    details = tx_details[i] if i < len(tx_details) else ""

    parsed_date = parse_date_to_ymd(date_raw)

    if parsed_date is None:
        continue

    if parsed_date.strftime("%Y-%m") != current_month:
        continue

    if tx_type_raw in INCOME_TYPES:
        tx_type = "income"
    else:
        tx_type = "expense"

    category, is_unknown = normalize_category(category_raw, description, details)

    if is_unknown:
        unknown_category_count += 1

    item = {
        "id": normalize_text(tx_id),
        "date": parsed_date.isoformat(),
        "description": normalize_text(description),
        "category_original": normalize_text(category_raw),
        "category_normalized": category,
        "amount": round(amount, 2),
        "type": tx_type,
        "details": normalize_text(details),
    }

    transactions.append(item)

    if tx_type == "income":
        income_total += amount
    else:
        expense_total += amount

        if category in ALLOWED_CATEGORIES:
            category_totals[category] += amount
            category_counts[category] += 1

# ============================================================
# MÉTRICAS PRINCIPAIS
# ============================================================

balance = salary + income_total - expense_total
expense_rate = safe_percent(expense_total, salary)
remaining_rate = safe_percent(balance, salary)
income_segment = classify_income_segment(salary)
expense_level = classify_expense_level(expense_rate, balance)

sorted_categories = sorted(
    [
        {
            "category": k,
            "total": round(v, 2),
            "count": category_counts[k],
            "percent_salary": safe_percent(v, salary),
            "percent_expenses": safe_percent(v, expense_total),
        }
        for k, v in category_totals.items()
    ],
    key=lambda x: x["total"],
    reverse=True,
)

top_transactions = sorted(
    [t for t in transactions if t["type"] == "expense"],
    key=lambda x: x["amount"],
    reverse=True,
)[:15]

# ============================================================
# ANÁLISE COMPORTAMENTAL
# ============================================================

expense_transactions = [t for t in transactions if t["type"] == "expense"]

delivery_keywords = [
    "ifood",
    "delivery",
    "uber eats",
    "rappi",
    "restaurante",
    "lanche",
    "pizza",
]

market_keywords = [
    "mercado",
    "supermercado",
    "compra do mês",
    "compra semanal",
    "atacado",
]

transport_private_keywords = [
    "uber",
    "99",
    "taxi",
    "táxi",
    "gasolina",
    "combustível",
    "combustivel",
]

shopping_keywords = [
    "shopping",
    "roupa",
    "eletronico",
    "eletrônico",
    "amazon",
    "mercado livre",
    "shein",
]

delivery_total = sum(
    t["amount"]
    for t in expense_transactions
    if contains_any(f'{t["description"]} {t["details"]}', delivery_keywords)
)

market_total = sum(
    t["amount"]
    for t in expense_transactions
    if contains_any(f'{t["description"]} {t["details"]}', market_keywords)
)

private_transport_total = sum(
    t["amount"]
    for t in expense_transactions
    if contains_any(f'{t["description"]} {t["details"]}', transport_private_keywords)
)

shopping_behavior_total = sum(
    t["amount"]
    for t in expense_transactions
    if t["category_normalized"] == "Compras"
    or contains_any(f'{t["description"]} {t["details"]}', shopping_keywords)
)

alimentacao_total = category_totals.get("Alimentação", 0.0)
transporte_total = category_totals.get("Transporte", 0.0)
compras_total = category_totals.get("Compras", 0.0)
entretenimento_total = category_totals.get("Entretenimento", 0.0)
moradia_total = category_totals.get("Moradia", 0.0)

signals = []

if salary > 0 and alimentacao_total / salary >= 0.20:
    signals.append({
        "type": "alimentacao_alta",
        "message": "Alimentação está pesada em relação à renda.",
        "total": round(alimentacao_total, 2),
        "percent_salary": safe_percent(alimentacao_total, salary),
    })

if salary > 0 and compras_total / salary >= 0.15:
    signals.append({
        "type": "compras_alto",
        "message": "Compras representam percentual relevante da renda.",
        "total": round(compras_total, 2),
        "percent_salary": safe_percent(compras_total, salary),
    })

if salary > 0 and transporte_total / salary >= 0.12:
    signals.append({
        "type": "transporte_alto",
        "message": "Transporte representa percentual relevante da renda.",
        "total": round(transporte_total, 2),
        "percent_salary": safe_percent(transporte_total, salary),
    })

if unknown_category_count > 0:
    signals.append({
        "type": "outros",
        "message": "Existem transações em Outros ou sem categoria clara.",
        "count": unknown_category_count,
    })

behavioral_signals = []

if salary > 0 and market_total > 0 and delivery_total > 0:
    combined_food = market_total + delivery_total
    behavioral_signals.append({
        "type": "mercado_e_delivery",
        "message": "Há gastos simultâneos com mercado/supermercado e delivery/restaurante.",
        "market_total": round(market_total, 2),
        "delivery_total": round(delivery_total, 2),
        "combined_total": round(combined_food, 2),
        "combined_percent_salary": safe_percent(combined_food, salary),
        "interpretation": "Pode indicar baixa utilização dos alimentos comprados ou excesso de conveniência.",
    })

if salary > 0 and private_transport_total / salary >= 0.10:
    behavioral_signals.append({
        "type": "transporte_privado_alto",
        "message": "Transporte privado ou combustível representa parcela relevante da renda.",
        "total": round(private_transport_total, 2),
        "percent_salary": safe_percent(private_transport_total, salary),
        "interpretation": "Pode valer avaliar alternativas como transporte público, caronas, rotas mais eficientes ou redução de corridas por aplicativo.",
    })

if salary > 0 and shopping_behavior_total / salary >= 0.12:
    behavioral_signals.append({
        "type": "compras_relevantes",
        "message": "Compras representam uma parcela relevante da renda.",
        "total": round(shopping_behavior_total, 2),
        "percent_salary": safe_percent(shopping_behavior_total, salary),
        "interpretation": "Pode indicar consumo variável pouco planejado ou compras por impulso.",
    })

if salary > 0 and entretenimento_total / salary >= 0.10:
    behavioral_signals.append({
        "type": "entretenimento_alto",
        "message": "Entretenimento está acima de uma faixa conservadora para orçamento mensal.",
        "total": round(entretenimento_total, 2),
        "percent_salary": safe_percent(entretenimento_total, salary),
        "interpretation": "Pode haver espaço para revisar assinaturas, lazer recorrente ou gastos de baixo valor percebido.",
    })

if salary > 0 and expense_rate >= 85:
    behavioral_signals.append({
        "type": "renda_muito_comprometida",
        "message": "A renda está muito comprometida pelos gastos do mês.",
        "expense_rate": round(expense_rate, 1),
        "interpretation": "O foco deve ser reduzir gastos variáveis antes de assumir novos compromissos.",
    })

if salary > 0 and balance > 0:
    behavioral_signals.append({
        "type": "sobra_positiva",
        "message": "Existe saldo positivo no mês.",
        "balance": round(balance, 2),
        "suggested_reserve_min": round(salary * 0.10, 2),
        "suggested_reserve_max": round(salary * 0.30, 2),
        "interpretation": "Parte da sobra pode ser separada para reserva de emergência.",
    })

# ============================================================
# PAYLOAD PARA IA
# ============================================================

ai_payload = {
    "user_id": user_id,
    "month": current_month,

    "salary": round(salary, 2),
    "income_total": round(income_total, 2),
    "expense_total": round(expense_total, 2),
    "balance": round(balance, 2),
    "expense_rate": round(expense_rate, 1),
    "remaining_rate": round(remaining_rate, 1),

    "profile_classification": {
        "income_segment": income_segment,
        "expense_level": expense_level,
        "combined_case": f'{income_segment["segment"]}__{expense_level["level"]}'
},

    "category_totals": sorted_categories,
    "top_transactions": top_transactions,

    "signals": signals,
    "behavioral_signals": behavioral_signals,

    "behavioral_totals": {
        "delivery_total": round(delivery_total, 2),
        "market_total": round(market_total, 2),
        "private_transport_total": round(private_transport_total, 2),
        "shopping_behavior_total": round(shopping_behavior_total, 2),
    },

    "data_quality": {
        "transactions_processed": len(transactions),
        "expense_transactions": len(expense_transactions),
        "unknown_category_count": unknown_category_count,
    },
}

# ============================================================
# PROMPT MISTRAL
# ============================================================

system_prompt = """
## PAPEL

Você é um consultor financeiro analítico, direto e pragmático.

Seu papel é analisar a situação financeira mensal do usuário, identificar desequilíbrios, observar padrões de comportamento e sugerir ajustes práticos na distribuição de renda.

Você não promete solução definitiva, não dá ordens absolutas e não recomenda produtos financeiros específicos.

---

## DADOS DE REFERÊNCIA

Use como referência:

- Faixa salarial média brasileira aproximada: R$ 3.300
- Salário mínimo aproximado: R$ 1.518
- Um salário mínimo acima da média: aproximadamente R$ 4.818

Classifique o usuário em uma destas faixas:

1. Abaixo da média:
   - salário menor que R$ 3.300

2. Dentro da faixa média:
   - salário entre R$ 3.300 e R$ 4.818

3. Acima da média:
   - salário maior que R$ 4.818

4. Renda muito alta para este modelo:
   - salário acima de R$ 15.000

Se o salário for maior que R$ 15.000:
- não faça uma análise detalhada;
- informe que o caso exige análise mais personalizada;
- ainda pode apresentar o resumo numérico básico;
- não faça recomendações fortes.

---

## CLASSIFICAÇÃO DE DESPESAS

Calcule o percentual da renda comprometida:

percentual comprometido = total de gastos / salário * 100

Classifique assim:

- Poucas despesas: até 50% da renda
- Despesas moderadas: acima de 50% até 70%
- Muitas despesas: acima de 70% até 90%
- Risco alto: acima de 90%
- Déficit: gastos maiores que a renda

A análise deve combinar faixa salarial + nível de despesas.

---

## CASOS POSSÍVEIS

### 1. Usuário abaixo da média com muitas despesas

Tom:
- cuidadoso;
- realista;
- sem julgamento.

Prioridade:
- preservar gastos essenciais;
- identificar pequenos cortes recorrentes;
- evitar recomendações agressivas de reserva se não houver sobra.

Recomendação:
- focar em reduzir gastos variáveis;
- sugerir revisão de alimentação fora, transporte privado, compras e entretenimento;
- se houver déficit, sugerir primeiro buscar equilíbrio antes de reserva.

Evite:
- sugerir cortes impossíveis;
- sugerir guardar 30% da renda;
- culpar o usuário.

---

### 2. Usuário abaixo da média com poucas despesas

Tom:
- positivo, mas prudente.

Prioridade:
- manter controle;
- proteger a sobra;
- criar pequena reserva.

Recomendação:
- sugerir separar uma parte pequena e realista da renda;
- sugerir reserva entre 5% e 15% da renda, se possível;
- manter gastos variáveis sob controle.

---

### 3. Usuário dentro da faixa média com muitas despesas

Tom:
- direto e prático.

Prioridade:
- reduzir comprometimento da renda;
- atacar o maior gasto variável.

Recomendação:
- sugerir redução em alimentação fora, transporte, compras ou entretenimento;
- propor faixa de economia mensal;
- mostrar novo cenário após o ajuste.

---

### 4. Usuário dentro da faixa média com poucas despesas

Tom:
- construtivo.

Prioridade:
- consolidar reserva;
- organizar sobra.

Recomendação:
- sugerir separar entre 10% e 20% da renda para reserva, se possível;
- manter teto para gastos variáveis;
- identificar se há alguma categoria que pode crescer sem controle.

---

### 5. Usuário acima da média com muitas despesas

Tom:
- analítico e firme.

Prioridade:
- evitar inflação de estilo de vida;
- identificar desperdícios proporcionais à renda.

Recomendação:
- comparar mercado vs delivery;
- analisar transporte privado;
- observar compras recorrentes;
- sugerir cortes maiores em valor absoluto, mas ainda em faixa.

Exemplo:
- reduzir R$ 300 a R$ 700 em gastos variáveis, dependendo dos dados.

---

### 6. Usuário acima da média com poucas despesas

Tom:
- estratégico e objetivo.

Prioridade:
- preservar boa margem;
- direcionar sobra.

Recomendação:
- sugerir reserva de emergência;
- sugerir separar entre 15% e 30% da renda, se possível;
- sugerir manter gastos variáveis com teto mensal.

---

## ANÁLISE COMPORTAMENTAL

Além da classificação por renda e despesas, identifique incoerências nos gastos.

Compare categorias relacionadas:

1. Mercado + delivery/restaurante
   - Se ambos forem altos, levante a hipótese de baixa utilização dos alimentos comprados.
   - Sugira reduzir delivery antes de reduzir mercado.

2. Transporte alto
   - Se transporte consumir percentual relevante da renda, sugira avaliar alternativas mais econômicas.
   - Exemplos: transporte público, carona, rotas melhores, menor uso de aplicativo.

3. Compras recorrentes
   - Se compras forem relevantes ou frequentes, indique possível consumo impulsivo ou pouco planejado.
   - Sugira teto mensal para compras variáveis.

4. Entretenimento alto
   - Sugira revisar assinaturas, lazer recorrente e gastos de baixo valor percebido.

5. Saúde e educação
   - Trate com cautela.
   - Não sugira cortes agressivos nessas categorias.
   - Sugira apenas revisar se houver indício de gasto variável ou não essencial.

Sempre que identificar uma incoerência:
- explique que é uma hipótese;
- mostre o possível motivo;
- sugira um ajuste prático.

---

## REGRAS DE RECOMENDAÇÃO

- Sempre calcular:
  - salário;
  - entradas adicionais;
  - total de gastos;
  - percentual da renda comprometida;
  - saldo final.

- Priorize o maior impacto financeiro.
- Sugira ajustes em faixa, não em valor rígido.
- Mostre como ficaria o cenário após o ajuste.
- Garanta que o cenário sugerido não piore a situação.
- Se houver déficit, o primeiro objetivo é reduzir ou eliminar o déficit.
- Se houver sobra, sugerir reserva de emergência.

Reserva:
- Para renda abaixo da média: sugerir 5% a 15%, se possível.
- Para renda média: sugerir 10% a 20%, se possível.
- Para renda acima da média: sugerir 15% a 30%, se possível.
- A reserva deve ficar em local separado e de fácil acesso, como poupança, conta digital ou caixinha.
- Não recomendar investimentos específicos.

---

## LINGUAGEM

Use linguagem de sugestão:

- "uma possível melhoria seria..."
- "uma estratégia viável é..."
- "pode fazer sentido..."
- "uma hipótese é..."

Evite:

- "você deve"
- "faça isso"
- "obrigatoriamente"
- "com certeza"
- promessas de resultado

---

## FORMATO OBRIGATÓRIO

A resposta deve conter exatamente estas 5 seções:

# 📊 Planilha resumida de gastos

Tabela:
Categoria | Valor | % da renda | Observação curta

# 📉 Diagnóstico financeiro

Inclua:
- faixa salarial identificada;
- nível de despesas identificado;
- salário;
- entradas adicionais;
- total de gastos;
- percentual da renda comprometida;
- saldo final;
- leitura objetiva da situação.

# 🎯 Ajuste principal

Inclua:
- categoria ou comportamento prioritário;
- motivo da escolha;
- faixa de redução sugerida;
- hipótese comportamental, se houver.

# 📈 Novo cenário após ajuste

Inclua:
- economia estimada;
- novo total de gastos;
- novo saldo final;
- novo percentual da renda comprometida.

# 💰 Uso da sobra

Se houver sobra:
- sugerir reserva de emergência;
- indicar percentual adequado conforme faixa salarial;
- sugerir separar em local simples, separado e acessível.

Se não houver sobra:
- sugerir primeiro reduzir déficit ou reorganizar gastos essenciais.
"""

user_prompt = f"""
Analise os dados financeiros mensais abaixo e gere o relatório no formato obrigatório.

Dados:
{json.dumps(ai_payload, ensure_ascii=False)}
"""

mistral_body = {
    "model": "mistral-small-latest",
    "temperature": 0.3,
    "max_tokens": 2400,
    "messages": [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ],
}

# ============================================================
# FALLBACK
# ============================================================

fallback_email_body = (
    f"Relatório de {current_month}:\n\n"
    f"Salário: R$ {salary:.2f}\n"
    f"Entradas adicionais: R$ {income_total:.2f}\n"
    f"Despesas: R$ {expense_total:.2f}\n"
    f"Saldo final: R$ {balance:.2f}\n"
    f"Renda comprometida: {expense_rate:.1f}%\n\n"
    f"Não foi possível gerar a análise completa por IA neste momento."
)

# ============================================================
# RETORNO PARA O ZAPIER
# ============================================================

return {
    "user_id": user_id,
    "email": email,
    "salary": round(salary, 2),
    "month": current_month,

    "expense_total": round(expense_total, 2),
    "income_total": round(income_total, 2),
    "balance": round(balance, 2),
    "expense_rate": round(expense_rate, 1),
    "remaining_rate": round(remaining_rate, 1),

    "category_totals_json": json.dumps(sorted_categories, ensure_ascii=False),
    "signals_json": json.dumps(signals, ensure_ascii=False),
    "behavioral_signals_json": json.dumps(behavioral_signals, ensure_ascii=False),

    "mistral_body_json": json.dumps(mistral_body, ensure_ascii=False),
    "fallback_email_body": fallback_email_body,

    "debug_processed_transactions": len(transactions),
    "debug_expense_transactions": len(expense_transactions),
    "debug_unknown_category_count": unknown_category_count,
}
