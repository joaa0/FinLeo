from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from chamaleon.domain.types import IntentResult, TransactionDraft, TransactionParseResult


CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "ifood": ("Alimentacao", "expense"),
    "ubereats": ("Alimentacao", "expense"),
    "uber eats": ("Alimentacao", "expense"),
    "rappi": ("Alimentacao", "expense"),
    "aiqfome": ("Alimentacao", "expense"),
    "delivery": ("Alimentacao", "expense"),
    "padaria": ("Alimentacao", "expense"),
    "restaurante": ("Alimentacao", "expense"),
    "almoco": ("Alimentacao", "expense"),
    "janta": ("Alimentacao", "expense"),
    "jantar": ("Alimentacao", "expense"),
    "cafe": ("Alimentacao", "expense"),
    "cafeteria": ("Alimentacao", "expense"),
    "lanche": ("Alimentacao", "expense"),
    "lanchonete": ("Alimentacao", "expense"),
    "hamburguer": ("Alimentacao", "expense"),
    "hamburgueria": ("Alimentacao", "expense"),
    "pizza": ("Alimentacao", "expense"),
    "sushi": ("Alimentacao", "expense"),
    "sorvete": ("Alimentacao", "expense"),
    "acougue": ("Alimentacao", "expense"),
    "mercadinho": ("Alimentacao", "expense"),
    "mercado": ("Compras", "expense"),
    "supermercado": ("Compras", "expense"),
    "atacadao": ("Compras", "expense"),
    "compra": ("Compras", "expense"),
    "shopping": ("Compras", "expense"),
    "roupa": ("Compras", "expense"),
    "tenis": ("Compras", "expense"),
    "presente": ("Compras", "expense"),
    "eletronico": ("Compras", "expense"),
    "amazon": ("Compras", "expense"),
    "mercado livre": ("Compras", "expense"),
    "shopee": ("Compras", "expense"),
    "uber": ("Transporte", "expense"),
    "99": ("Transporte", "expense"),
    "taxi": ("Transporte", "expense"),
    "corrida": ("Transporte", "expense"),
    "combustivel": ("Transporte", "expense"),
    "gasolina": ("Transporte", "expense"),
    "etanol": ("Transporte", "expense"),
    "diesel": ("Transporte", "expense"),
    "posto": ("Transporte", "expense"),
    "pedagio": ("Transporte", "expense"),
    "estacionamento": ("Transporte", "expense"),
    "passagem": ("Transporte", "expense"),
    "onibus": ("Transporte", "expense"),
    "metro": ("Transporte", "expense"),
    "trem": ("Transporte", "expense"),
    "transporte": ("Transporte", "expense"),
    "blablacar": ("Transporte", "expense"),
    "aluguel": ("Moradia", "expense"),
    "condominio": ("Moradia", "expense"),
    "luz": ("Moradia", "expense"),
    "energia": ("Moradia", "expense"),
    "agua": ("Moradia", "expense"),
    "gas": ("Moradia", "expense"),
    "internet": ("Moradia", "expense"),
    "wifi": ("Moradia", "expense"),
    "telefone": ("Moradia", "expense"),
    "celular": ("Moradia", "expense"),
    "moradia": ("Moradia", "expense"),
    "iptu": ("Moradia", "expense"),
    "reparo": ("Moradia", "expense"),
    "manutencao": ("Moradia", "expense"),
    "netflix": ("Entretenimento", "expense"),
    "spotify": ("Entretenimento", "expense"),
    "primevideo": ("Entretenimento", "expense"),
    "prime video": ("Entretenimento", "expense"),
    "disney": ("Entretenimento", "expense"),
    "max": ("Entretenimento", "expense"),
    "hbo": ("Entretenimento", "expense"),
    "cinema": ("Entretenimento", "expense"),
    "show": ("Entretenimento", "expense"),
    "festa": ("Entretenimento", "expense"),
    "bar": ("Entretenimento", "expense"),
    "balada": ("Entretenimento", "expense"),
    "viagem": ("Entretenimento", "expense"),
    "hotel": ("Entretenimento", "expense"),
    "passeio": ("Entretenimento", "expense"),
    "jogo": ("Entretenimento", "expense"),
    "game": ("Entretenimento", "expense"),
    "steam": ("Entretenimento", "expense"),
    "farmacia": ("Saude", "expense"),
    "dentista": ("Saude", "expense"),
    "remedio": ("Saude", "expense"),
    "remedios": ("Saude", "expense"),
    "medicamento": ("Saude", "expense"),
    "medicamentos": ("Saude", "expense"),
    "consulta": ("Saude", "expense"),
    "medico": ("Saude", "expense"),
    "exame": ("Saude", "expense"),
    "hospital": ("Saude", "expense"),
    "clinica": ("Saude", "expense"),
    "psicologo": ("Saude", "expense"),
    "terapia": ("Saude", "expense"),
    "vitamina": ("Saude", "expense"),
    "plano de saude": ("Saude", "expense"),
    "academia": ("Saude", "expense"),
    "curso": ("Educacao", "expense"),
    "livro": ("Educacao", "expense"),
    "faculdade": ("Educacao", "expense"),
    "mensalidade": ("Educacao", "expense"),
    "escola": ("Educacao", "expense"),
    "colegio": ("Educacao", "expense"),
    "apostila": ("Educacao", "expense"),
    "material escolar": ("Educacao", "expense"),
    "certificacao": ("Educacao", "expense"),
    "idioma": ("Educacao", "expense"),
    "ingles": ("Educacao", "expense"),
    "freelance": ("Trabalho", "income"),
    "salario": ("Trabalho", "income"),
    "bonus": ("Trabalho", "income"),
    "pix": ("Trabalho", "income"),
    "cliente": ("Trabalho", "income"),
    "venda": ("Trabalho", "income"),
    "recebi": ("Trabalho", "income"),
    "recebimento": ("Trabalho", "income"),
    "ganhei": ("Trabalho", "income"),
    "comissao": ("Trabalho", "income"),
    "freela": ("Trabalho", "income"),
    "pagamento": ("Trabalho", "income"),
    "renda": ("Trabalho", "income"),
    "trabalho": ("Trabalho", "income"),
    "prolabore": ("Trabalho", "income"),
    "pro labore": ("Trabalho", "income"),
    "reembolso": ("Trabalho", "income"),
    "cashback": ("Trabalho", "income"),
}
CATEGORY_NAMES = tuple(sorted({value[0] for value in CATEGORY_MAP.values()} | {"Outros"}))

INCOME_VERBS = {
    "recebi",
    "ganhei",
    "entrou",
    "caiu",
    "vendi",
    "faturei",
    "pingou",
    "creditou",
    "recebo",
}
EXPENSE_VERBS = {
    "gastei",
    "paguei",
    "comprei",
    "gasto",
    "debitei",
    "usei",
    "assinei",
    "abasteci",
    "desembolsei",
    "peguei",
}
TRANSACTION_VERBS = tuple(sorted(INCOME_VERBS | EXPENSE_VERBS, key=len, reverse=True))
SUMMARY_PATTERNS = (
    "quanto sobrou",
    "quanto tenho",
    "meu saldo",
    "saldo do mes",
    "resumo do mes",
    "quanto gastei",
    "como esta meu mes",
    "como ta meu mes",
    "quanto ainda posso gastar",
)
HISTORY_PATTERNS = (
    "meu historico",
    "ultimas transacoes",
    "minhas transacoes",
    "historico",
    "me mostra minhas transacoes",
    "quais foram meus ultimos gastos",
    "me mostra meu historico",
)
REPORT_PATTERNS = (
    "me manda meu relatorio",
    "envia meu relatorio",
    "quero meu relatorio",
    "relatorio",
    "gera um relatorio",
    "cria um relatorio",
    "gera meu relatorio",
)
BUDGET_PATTERNS = (
    "orcamento",
    "orçamento",
    "meus orcamentos",
    "meus orçamentos",
    "limite por categoria",
    "meta por categoria",
    "gastos por categoria",
)
RECURRING_PATTERNS = (
    "recorrencia",
    "recorrência",
    "recorrente",
    "conta fixa",
    "conta recorrente",
    "gasto fixo",
    "entrada fixa",
    "assinatura mensal",
)
SALARY_PATTERNS = (
    "meu salario",
    "atualizar salario",
    "salario",
    "dinheiro",
    "quero atualizar meu salario",
    "trocar salario",
    "mudar salario",
)
UNDO_PATTERNS = (
    "desfaz",
    "desfazer",
    "desfaca",
    "desfaça",
    "apaga o ultimo",
    "apagar o ultimo",
    "remove o ultimo",
    "exclui o ultimo",
)
EDIT_PATTERNS = (
    "corrige o valor para",
    "corrigir o valor para",
    "altera o valor para",
    "altera pra",
    "ajusta para",
    "muda para",
)
AMOUNT_PATTERN = re.compile(r"\d[\d\.,]*")
NOISE_TOKENS = {
    "ai",
    "ainda",
    "agora",
    "apenas",
    "foi",
    "meu",
    "minha",
    "pro",
    "pra",
    "um",
    "uma",
    "uns",
    "umas",
}
DESCRIPTION_FILLERS = {
    *INCOME_VERBS,
    *EXPENSE_VERBS,
    "de",
    "do",
    "da",
    "dos",
    "das",
    "no",
    "na",
    "nos",
    "nas",
    "com",
    "por",
    "pra",
    "para",
    "em",
    "real",
    "reais",
    "rs",
    "r",
}
APPROXIMATION_HINTS = (
    "acho que",
    "mais ou menos",
    "mais ou menos",
    "uns",
    "umas",
    "aprox",
    "aproximadamente",
    "quase",
    "e pouco",
    "por volta de",
)
AMBIGUOUS_DATE_HINTS = (
    "anteontem",
    "semana passada",
    "mes passado",
    "mês passado",
    "esses dias",
    "outro dia",
)
MULTI_SPLIT_PATTERN = re.compile(
    rf"(?:\s+e\s+|,\s*|;\s*)(?=(?:{'|'.join(re.escape(verb) for verb in TRANSACTION_VERBS)})\b)",
    flags=re.IGNORECASE,
)


def normalize_keyword(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9\s,./|:-]", " ", normalized)
    normalized = re.sub(r"(?<=\D)[\.,:;!?]+(?=\s|$)", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_amount(raw: str) -> Decimal | None:
    text = raw.strip().replace("R$", "").replace("r$", "").replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def detect_category(text: str) -> tuple[str, str]:
    normalized = normalize_keyword(text)
    normalized_words = set(normalized.split())
    compact = normalized.replace(" ", "")
    for keyword, category in CATEGORY_MAP.items():
        candidate = normalize_keyword(keyword)
        if " " in candidate:
            if candidate in normalized or candidate.replace(" ", "") in compact:
                return category
        elif candidate in normalized_words:
            return category
    return ("Outros", "expense")


def _extract_amount(text: str) -> tuple[Decimal | None, str]:
    match = AMOUNT_PATTERN.search(text)
    if not match:
        return None, text
    amount = normalize_amount(match.group(0))
    if amount is None:
        return None, text
    remaining = (text[: match.start()] + " " + text[match.end() :]).strip()
    return amount, re.sub(r"\s+", " ", remaining)


def _extract_all_amounts(text: str) -> list[Decimal]:
    amounts: list[Decimal] = []
    for match in AMOUNT_PATTERN.finditer(text):
        amount = normalize_amount(match.group(0))
        if amount is not None:
            amounts.append(amount)
    return amounts


def _extract_details(text: str) -> tuple[str, str]:
    if "|" not in text:
        return text.strip(), ""
    main, details = text.split("|", 1)
    return main.strip(), details.strip()


def _extract_relative_date(text: str) -> tuple[date, str]:
    normalized = normalize_keyword(text)
    tx_date = date.today()
    if "ontem" in normalized:
        tx_date = date.today() - timedelta(days=1)
        normalized = normalized.replace("ontem", "").strip()
    elif "hoje" in normalized:
        normalized = normalized.replace("hoje", "").strip()
    return tx_date, normalized


def _has_approximation_language(text: str) -> bool:
    normalized = normalize_keyword(text)
    return any(hint in normalized for hint in APPROXIMATION_HINTS)


def _has_ambiguous_date_language(text: str) -> bool:
    normalized = normalize_keyword(text)
    return any(hint in normalized for hint in AMBIGUOUS_DATE_HINTS)


def _compute_confidence(
    source_text: str,
    description: str,
    category: str,
    transaction_type: str,
    amount_count: int,
) -> float:
    confidence = 0.45
    if amount_count == 1:
        confidence += 0.22
    if category != "Outros":
        confidence += 0.14
    else:
        confidence -= 0.08
    if transaction_type in {"income", "expense"}:
        confidence += 0.08
    if description != "transacao":
        confidence += 0.06
    if len(description.split()) <= 4:
        confidence += 0.03
    if _has_approximation_language(source_text):
        confidence -= 0.22
    if _has_ambiguous_date_language(source_text):
        confidence -= 0.12
    return max(0.0, min(confidence, 0.99))


def _build_description(remaining: str) -> str:
    description = remaining
    for filler in DESCRIPTION_FILLERS:
        description = re.sub(rf"\b{re.escape(filler)}\b", " ", description, flags=re.IGNORECASE)
    description = re.sub(r"\s+", " ", description).strip(" -")

    tokens = [token for token in normalize_keyword(description).split() if token not in NOISE_TOKENS]
    deduped: list[str] = []
    for token in tokens:
        if not deduped or deduped[-1] != token:
            deduped.append(token)

    return " ".join(deduped).strip() or "transacao"


def parse_transaction_text(text: str) -> TransactionDraft | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    if cleaned.startswith("/registro"):
        cleaned = cleaned[len("/registro") :].strip()

    main_text, details = _extract_details(cleaned)
    tx_date, normalized = _extract_relative_date(main_text)
    all_amounts = _extract_all_amounts(normalized)
    if len(all_amounts) != 1:
        return None

    normalized_words = set(normalize_keyword(normalized).split())
    has_income_verb = any(word in normalized_words for word in INCOME_VERBS)
    has_expense_verb = any(word in normalized_words for word in EXPENSE_VERBS)
    if has_income_verb and has_expense_verb:
        return None

    amount, remaining = _extract_amount(normalized)
    if amount is None:
        return None

    category, tx_type = detect_category(remaining)
    lowered = normalize_keyword(remaining)
    if has_income_verb or any(word in lowered.split() for word in INCOME_VERBS):
        tx_type = "income"
    elif has_expense_verb or any(word in lowered.split() for word in EXPENSE_VERBS):
        tx_type = "expense"

    description = _build_description(remaining)

    confidence = _compute_confidence(
        source_text=text,
        description=description,
        category=category,
        transaction_type=tx_type,
        amount_count=len(all_amounts),
    )
    return TransactionDraft(
        description=description[:80],
        amount=amount,
        category=category,
        transaction_type=tx_type,
        transaction_date=tx_date,
        details=details,
        confidence=min(confidence, 0.99),
        raw_text=text,
    )


def parse_multiple_transaction_texts(text: str, max_items: int = 3) -> list[TransactionDraft]:
    cleaned = text.strip()
    if not cleaned:
        return []

    parts = [part.strip(" ,;") for part in MULTI_SPLIT_PATTERN.split(cleaned) if part.strip(" ,;")]
    if len(parts) < 2 or len(parts) > max_items:
        return []

    drafts: list[TransactionDraft] = []
    for part in parts:
        draft = parse_transaction_text(part)
        if draft is None:
            return []
        drafts.append(draft)
    return drafts


def parse_transaction_candidate(text: str, ai_threshold: float = 0.80) -> TransactionParseResult:
    cleaned = text.strip()
    if not cleaned:
        return TransactionParseResult(confidence=0.0, reasons=["empty"])

    multiple_drafts = parse_multiple_transaction_texts(cleaned)
    if multiple_drafts:
        average_confidence = sum(draft.confidence for draft in multiple_drafts) / len(multiple_drafts)
        complex_multi = len(_extract_all_amounts(cleaned)) > len(multiple_drafts)
        should_use_ai = average_confidence < ai_threshold or complex_multi or _has_ambiguous_date_language(cleaned)
        reasons = []
        if average_confidence < ai_threshold:
            reasons.append("low_confidence_multi")
        if complex_multi:
            reasons.append("multiple_values_competing")
        if _has_ambiguous_date_language(cleaned):
            reasons.append("ambiguous_date")
        return TransactionParseResult(
            confidence=round(average_confidence, 2),
            drafts=multiple_drafts,
            should_use_ai_fallback=should_use_ai,
            reasons=reasons,
        )

    draft = parse_transaction_text(cleaned)
    if draft is not None:
        reasons: list[str] = []
        should_use_ai = False
        if draft.confidence < ai_threshold:
            should_use_ai = True
            reasons.append("low_confidence_single")
        if _has_ambiguous_date_language(cleaned):
            should_use_ai = True
            reasons.append("ambiguous_date")
        return TransactionParseResult(
            confidence=round(draft.confidence, 2),
            draft=draft,
            should_use_ai_fallback=should_use_ai,
            reasons=reasons,
        )

    normalized = normalize_keyword(cleaned)
    amount_count = len(_extract_all_amounts(normalized))
    normalized_words = set(normalized.split())
    has_income_verb = any(word in normalized_words for word in INCOME_VERBS)
    has_expense_verb = any(word in normalized_words for word in EXPENSE_VERBS)
    likely_financial = amount_count > 0 or has_income_verb or has_expense_verb or detect_category(normalized)[0] != "Outros"
    reasons: list[str] = []
    if amount_count > 1:
        reasons.append("multiple_values")
    if has_income_verb and has_expense_verb:
        reasons.append("mixed_income_and_expense")
    if _has_ambiguous_date_language(cleaned):
        reasons.append("ambiguous_date")
    if _has_approximation_language(cleaned):
        reasons.append("approximate_amount")
    return TransactionParseResult(
        confidence=0.25 if likely_financial else 0.0,
        should_use_ai_fallback=likely_financial,
        reasons=reasons or ["heuristic_parse_failed"],
    )


def detect_intent(text: str) -> IntentResult:
    normalized = normalize_keyword(text)
    if any(pattern in normalized for pattern in UNDO_PATTERNS):
        return IntentResult(intent="undo_last_transaction", confidence=0.92)
    if any(pattern in normalized for pattern in EDIT_PATTERNS):
        amount, _ = _extract_amount(normalized)
        entities = {"amount": str(amount)} if amount is not None else {}
        return IntentResult(intent="edit_last_transaction_amount", confidence=0.88, entities=entities)
    if any(pattern in normalized for pattern in SUMMARY_PATTERNS):
        return IntentResult(intent="show_summary", confidence=0.92)
    if any(pattern in normalized for pattern in HISTORY_PATTERNS):
        return IntentResult(intent="show_history", confidence=0.90)
    if any(pattern in normalized for pattern in REPORT_PATTERNS):
        return IntentResult(intent="request_report", confidence=0.90)
    if any(pattern in normalized for pattern in BUDGET_PATTERNS):
        return IntentResult(intent="manage_budgets", confidence=0.86)
    if any(pattern in normalized for pattern in RECURRING_PATTERNS):
        return IntentResult(intent="manage_recurring", confidence=0.84)
    if any(pattern in normalized for pattern in SALARY_PATTERNS):
        amount, _ = _extract_amount(normalized)
        entities = {"amount": str(amount)} if amount is not None else {}
        return IntentResult(intent="update_salary", confidence=0.82, entities=entities)
    draft = parse_transaction_text(text)
    if draft:
        return IntentResult(
            intent="register_transaction",
            confidence=draft.confidence,
            entities={"category": draft.category, "type": draft.transaction_type},
            draft=draft,
            needs_confirmation=True,
        )
    if normalized in {"ajuda", "menu", "comandos", "opcoes", "opções"}:
        return IntentResult(intent="help", confidence=0.99)
    return IntentResult(intent="unknown", confidence=0.0)


def draft_to_dict(draft: TransactionDraft) -> dict[str, str]:
    payload = asdict(draft)
    payload["amount"] = f"{draft.amount:.2f}"
    payload["transaction_date"] = draft.transaction_date.isoformat()
    return payload
