from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, TYPE_CHECKING

import requests

from chamaleon.domain.types import TransactionDraft, TransactionParseResult
from chamaleon.services.parser import CATEGORY_NAMES, detect_category, normalize_amount, normalize_keyword

if TYPE_CHECKING:
    from chamaleon.config import Settings


class AIParserService:
    def __init__(self, settings: "Settings"):
        self.settings = settings
        self.threshold = settings.parser_ai_confidence_threshold

    def available(self) -> bool:
        return bool(self.settings.openai_api_key)

    def parse(self, text: str, today: date | None = None) -> TransactionParseResult | None:
        if not self.available():
            return None

        prompt = self._build_prompt(text, today or date.today())
        response = requests.post(
            f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.openai_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Voce extrai movimentacoes financeiras de mensagens em portugues do Brasil. "
                            "Responda apenas com JSON valido, sem markdown, sem texto extra, sem comentarios."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        content = payload["choices"][0]["message"]["content"]
        return self._validate_response(content, text, today or date.today())

    def _build_prompt(self, text: str, today: date) -> str:
        schema = {
            "intent": "register_transaction",
            "confidence": 0.91,
            "transactions": [
                {
                    "description": "mercado",
                    "amount": 87.0,
                    "category": "Compras",
                    "transaction_type": "expense",
                    "transaction_date": "YYYY-MM-DD",
                    "details": "",
                }
            ],
            "needs_confirmation": True,
        }
        return (
            "Extraia movimentacoes financeiras da mensagem abaixo.\n"
            "Regras:\n"
            "- use apenas as categorias permitidas\n"
            "- transaction_type deve ser expense ou income\n"
            "- se houver mais de uma movimentacao, devolva cada uma separadamente\n"
            "- se houver duvida, ainda assim devolva o melhor palpite estruturado com confidence menor\n"
            "- needs_confirmation deve ser true\n"
            "- nao invente valores ausentes\n\n"
            f"Data de referencia: {today.isoformat()}\n"
            f"Categorias permitidas: {', '.join(CATEGORY_NAMES)}\n"
            f"JSON esperado: {json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Mensagem do usuario: {text}"
        )

    def _validate_response(self, raw_content: str, source_text: str, today: date) -> TransactionParseResult | None:
        try:
            data = json.loads(raw_content.strip())
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None
        if data.get("intent") != "register_transaction":
            return None

        confidence = data.get("confidence")
        if not isinstance(confidence, (int, float)):
            return None

        transactions = data.get("transactions")
        if not isinstance(transactions, list) or not 1 <= len(transactions) <= 3:
            return None

        source_amounts = self._source_amounts(source_text)
        has_approximate_language = any(
            token in normalize_keyword(source_text)
            for token in ("acho que", "uns", "umas", "e pouco", "aprox", "aproximadamente", "mais ou menos")
        )

        drafts: list[TransactionDraft] = []
        for item in transactions:
            draft = self._validate_transaction_item(item, source_amounts, has_approximate_language, today)
            if draft is None:
                return None
            drafts.append(draft)

        result_confidence = max(0.0, min(float(confidence), 0.99))
        return TransactionParseResult(
            confidence=result_confidence,
            draft=drafts[0] if len(drafts) == 1 else None,
            drafts=drafts if len(drafts) > 1 else [],
            needs_confirmation=True,
            should_use_ai_fallback=False,
            reasons=["ai_fallback"],
        )

    def _validate_transaction_item(
        self,
        item: Any,
        source_amounts: set[Decimal],
        has_approximate_language: bool,
        today: date,
    ) -> TransactionDraft | None:
        if not isinstance(item, dict):
            return None

        description_raw = str(item.get("description", "")).strip()
        description = normalize_keyword(description_raw)[:80].strip()
        if not description:
            return None

        amount = normalize_amount(str(item.get("amount", "")).strip())
        if amount is None or amount <= 0:
            return None
        if source_amounts and amount not in source_amounts and not has_approximate_language:
            return None

        category = str(item.get("category", "")).strip()
        if category not in CATEGORY_NAMES:
            inferred_category, _ = detect_category(description)
            if inferred_category not in CATEGORY_NAMES:
                return None
            category = inferred_category

        transaction_type = str(item.get("transaction_type", "")).strip().lower()
        if transaction_type not in {"expense", "income"}:
            return None

        transaction_date_raw = str(item.get("transaction_date", "")).strip()
        try:
            transaction_date = datetime.strptime(transaction_date_raw, "%Y-%m-%d").date()
        except ValueError:
            return None
        if transaction_date > today or transaction_date < today - timedelta(days=120):
            return None

        details = str(item.get("details", "") or "").strip()[:180]
        return TransactionDraft(
            description=description,
            amount=amount,
            category=category,
            transaction_type=transaction_type,
            transaction_date=transaction_date,
            details=details,
            confidence=0.79,
            raw_text=description_raw,
        )

    def _source_amounts(self, source_text: str) -> set[Decimal]:
        amounts: set[Decimal] = set()
        for token in normalize_keyword(source_text).replace("/", " ").replace(":", " ").split():
            amount = normalize_amount(token)
            if amount is not None:
                amounts.add(amount)
        return amounts
