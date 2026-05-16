from __future__ import annotations

import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chamaleon.services.ai_parser import AIParserService


class AIParserServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = SimpleNamespace(
            openai_api_key="test-key",
            openai_model="mistral-small-latest",
            openai_base_url="https://api.mistral.ai/v1",
            parser_ai_confidence_threshold=0.80,
        )
        self.service = AIParserService(self.settings)

    def test_validates_single_transaction_json(self) -> None:
        content = json.dumps(
            {
                "intent": "register_transaction",
                "confidence": 0.91,
                "transactions": [
                    {
                        "description": "mercado",
                        "amount": 87.0,
                        "category": "Compras",
                        "transaction_type": "expense",
                        "transaction_date": "2026-05-14",
                        "details": "",
                    }
                ],
                "needs_confirmation": True,
            }
        )

        result = self.service._validate_response(content, "ontem fui no mercado deu 87", date(2026, 5, 15))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIsNotNone(result.draft)
        assert result.draft is not None
        self.assertEqual(result.draft.amount, Decimal("87.00"))
        self.assertEqual(result.draft.category, "Compras")

    def test_rejects_json_with_amount_not_present_in_source(self) -> None:
        content = json.dumps(
            {
                "intent": "register_transaction",
                "confidence": 0.91,
                "transactions": [
                    {
                        "description": "uber",
                        "amount": 99.0,
                        "category": "Transporte",
                        "transaction_type": "expense",
                        "transaction_date": "2026-05-14",
                        "details": "",
                    }
                ],
                "needs_confirmation": True,
            }
        )

        result = self.service._validate_response(content, "peguei uber de 22", date(2026, 5, 15))
        self.assertIsNone(result)

    def test_can_infer_known_category_when_ai_returns_invalid_one(self) -> None:
        content = json.dumps(
            {
                "intent": "register_transaction",
                "confidence": 0.84,
                "transactions": [
                    {
                        "description": "ifood",
                        "amount": 39.0,
                        "category": "Delivery",
                        "transaction_type": "expense",
                        "transaction_date": "2026-05-14",
                        "details": "",
                    }
                ],
                "needs_confirmation": True,
            }
        )

        result = self.service._validate_response(content, "gastei 39 no ifood", date(2026, 5, 15))

        self.assertIsNotNone(result)
        assert result is not None and result.draft is not None
        self.assertEqual(result.draft.category, "Alimentacao")


if __name__ == "__main__":
    unittest.main()
