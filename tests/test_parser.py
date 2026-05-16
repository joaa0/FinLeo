from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chamaleon.services.parser import detect_intent, parse_multiple_transaction_texts, parse_transaction_candidate, parse_transaction_text


class ParserTests(unittest.TestCase):
    def test_parses_expense_sentence(self) -> None:
        draft = parse_transaction_text("gastei 39 no ifood")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.transaction_type, "expense")
        self.assertEqual(draft.category, "Alimentacao")
        self.assertEqual(draft.amount, Decimal("39.00"))

    def test_ignores_currency_words_in_description(self) -> None:
        draft = parse_transaction_text("Gastei 60 reais no mercado comprando bebida")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.description, "mercado comprando bebida")
        self.assertEqual(draft.amount, Decimal("60.00"))

    def test_maps_remedio_to_saude(self) -> None:
        draft = parse_transaction_text("90 reais remédio")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.category, "Saude")
        self.assertEqual(draft.description, "remedio")

    def test_parses_income_sentence(self) -> None:
        draft = parse_transaction_text("recebi 1200 de freelance")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.transaction_type, "income")
        self.assertEqual(draft.category, "Trabalho")
        self.assertEqual(draft.amount, Decimal("1200.00"))

    def test_parses_yesterday_reference(self) -> None:
        draft = parse_transaction_text("ontem paguei 82 no mercado")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.transaction_date, date.today() - timedelta(days=1))

    def test_detects_summary_intent(self) -> None:
        intent = detect_intent("quanto sobrou esse mes?")
        self.assertEqual(intent.intent, "show_summary")

    def test_rejects_multiple_amounts_in_one_sentence(self) -> None:
        draft = parse_transaction_text("Ontem paguei 2 remédios e gastei 90 reais na farmácia")
        self.assertIsNone(draft)

    def test_rejects_mixed_income_and_expense_sentence(self) -> None:
        draft = parse_transaction_text("Recebi 3500 de salário e gastei 42 no uber")
        self.assertIsNone(draft)

    def test_rejects_installment_phrase_with_competing_numbers(self) -> None:
        draft = parse_transaction_text("Comprei um fone por 120 em 3x no cartão")
        self.assertIsNone(draft)

    def test_rejects_item_quantity_before_real_amount(self) -> None:
        draft = parse_transaction_text("Comprei 4 garrafas de água por 18 reais")
        self.assertIsNone(draft)

    def test_rejects_time_competing_with_amount(self) -> None:
        draft = parse_transaction_text("Hoje às 19:30 gastei 42 no uber")
        self.assertIsNone(draft)

    def test_rejects_numeric_date_competing_with_amount(self) -> None:
        draft = parse_transaction_text("No dia 12/05 gastei 90 na farmácia")
        self.assertIsNone(draft)

    def test_parses_currency_symbol_stuck_to_amount(self) -> None:
        draft = parse_transaction_text("Paguei R$90 no mercado")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.amount, Decimal("90.00"))
        self.assertEqual(draft.category, "Compras")

    def test_parses_brazilian_decimal_amount(self) -> None:
        draft = parse_transaction_text("Gastei 12,50 no café")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.amount, Decimal("12.50"))
        self.assertEqual(draft.transaction_type, "expense")

    def test_parses_brazilian_thousands_amount(self) -> None:
        draft = parse_transaction_text("Recebi 1.250,00 de freelance")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.amount, Decimal("1250.00"))
        self.assertEqual(draft.transaction_type, "income")

    def test_parses_short_phrase_without_explicit_verb(self) -> None:
        draft = parse_transaction_text("90 farmácia")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.amount, Decimal("90.00"))
        self.assertEqual(draft.category, "Saude")

    def test_maps_brand_to_entertainment(self) -> None:
        draft = parse_transaction_text("Assinei netflix por 39,90")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.category, "Entretenimento")
        self.assertEqual(draft.amount, Decimal("39.90"))

    def test_parses_pix_income_with_origin(self) -> None:
        draft = parse_transaction_text("Entrou pix de 350 da Maria")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.transaction_type, "income")
        self.assertEqual(draft.amount, Decimal("350.00"))

    def test_rejects_negated_sentence_with_late_correction(self) -> None:
        draft = parse_transaction_text("Não gastei 50 no mercado, foi 15")
        self.assertIsNone(draft)

    def test_rejects_self_correction_with_two_values(self) -> None:
        draft = parse_transaction_text("Gastei 80, digo, 60 no uber")
        self.assertIsNone(draft)

    def test_preserves_context_in_health_description(self) -> None:
        draft = parse_transaction_text("Paguei remédio pra gripe na farmácia por 27")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.category, "Saude")
        self.assertIn("gripe", draft.description)

    def test_preserves_client_context_in_income_description(self) -> None:
        draft = parse_transaction_text("Caiu 500 do cliente João")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.transaction_type, "income")
        self.assertIn("joao", draft.description)

    def test_preserves_location_context_in_expense_description(self) -> None:
        draft = parse_transaction_text("Gastei 48 no posto da avenida")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.amount, Decimal("48.00"))
        self.assertIn("avenida", draft.description)

    def test_maps_food_delivery_terms(self) -> None:
        draft = parse_transaction_text("Paguei 32 no uber eats")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.category, "Alimentacao")

    def test_maps_transcribed_ifood_with_trailing_period(self) -> None:
        draft = parse_transaction_text("Gastei 39 no iFood.")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.category, "Alimentacao")
        self.assertEqual(draft.description, "ifood")

    def test_maps_housing_bill_terms(self) -> None:
        draft = parse_transaction_text("Paguei 140 de condomínio")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.category, "Moradia")

    def test_maps_education_terms(self) -> None:
        draft = parse_transaction_text("Gastei 85 com apostila")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.category, "Educacao")

    def test_maps_entertainment_terms(self) -> None:
        draft = parse_transaction_text("Assinei hbo por 29,90")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.category, "Entretenimento")

    def test_maps_work_income_terms(self) -> None:
        draft = parse_transaction_text("Recebi 500 de comissão")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.category, "Trabalho")
        self.assertEqual(draft.transaction_type, "income")

    def test_maps_subscription_verb_and_keeps_clean_description(self) -> None:
        draft = parse_transaction_text("Assinei spotify por 21,90")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.category, "Entretenimento")
        self.assertEqual(draft.description, "spotify")

    def test_maps_fuel_verb_and_preserves_context(self) -> None:
        draft = parse_transaction_text("Abasteci 200 de gasolina no posto shell")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.category, "Transporte")
        self.assertIn("gasolina", draft.description)
        self.assertIn("shell", draft.description)

    def test_maps_pingou_as_income(self) -> None:
        draft = parse_transaction_text("Pingou 900 do freela")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.transaction_type, "income")
        self.assertEqual(draft.category, "Trabalho")

    def test_detects_more_natural_history_intent(self) -> None:
        intent = detect_intent("me mostra minhas transações")
        self.assertEqual(intent.intent, "show_history")

    def test_detects_more_natural_summary_intent(self) -> None:
        intent = detect_intent("quanto ainda posso gastar esse mês?")
        self.assertEqual(intent.intent, "show_summary")

    def test_detects_more_natural_report_intent(self) -> None:
        intent = detect_intent("gera um relatório pra mim")
        self.assertEqual(intent.intent, "request_report")

    def test_detects_salary_update_intent_without_amount(self) -> None:
        intent = detect_intent("quero atualizar meu salário")
        self.assertEqual(intent.intent, "update_salary")

    def test_detects_undo_last_transaction_intent(self) -> None:
        intent = detect_intent("desfaz o último lançamento")
        self.assertEqual(intent.intent, "undo_last_transaction")

    def test_detects_edit_last_transaction_amount_intent(self) -> None:
        intent = detect_intent("corrige o valor para 52")
        self.assertEqual(intent.intent, "edit_last_transaction_amount")
        self.assertEqual(intent.entities["amount"], "52.00")

    def test_detects_recurring_management_intent(self) -> None:
        intent = detect_intent("quero ver minhas recorrências")
        self.assertEqual(intent.intent, "manage_recurring")

    def test_detects_budget_management_intent(self) -> None:
        intent = detect_intent("quero ver meus orçamentos")
        self.assertEqual(intent.intent, "manage_budgets")

    def test_high_confidence_single_transaction_stays_local(self) -> None:
        result = parse_transaction_candidate("gastei 39 no ifood")
        self.assertIsNotNone(result.draft)
        self.assertFalse(result.should_use_ai_fallback)
        self.assertGreaterEqual(result.confidence, 0.80)

    def test_ambiguous_transaction_requests_ai_fallback(self) -> None:
        result = parse_transaction_candidate("acho que gastei uns 50 e pouco no mercado ontem")
        self.assertTrue(result.should_use_ai_fallback)
        self.assertGreater(result.confidence, 0.0)

    def test_complex_multiple_transactions_request_ai_fallback(self) -> None:
        result = parse_transaction_candidate("ontem fui no mercado deu 87 e depois peguei uber de 22")
        self.assertTrue(result.should_use_ai_fallback)

    def test_parses_two_transactions_split_by_e(self) -> None:
        drafts = parse_multiple_transaction_texts("recebi 3500 de salário e gastei 42 no uber")
        self.assertEqual(len(drafts), 2)
        self.assertEqual(drafts[0].transaction_type, "income")
        self.assertEqual(drafts[1].transaction_type, "expense")
        self.assertEqual(drafts[1].category, "Transporte")

    def test_parses_two_transactions_split_by_comma(self) -> None:
        drafts = parse_multiple_transaction_texts("paguei 90 na farmácia, paguei 20 no café")
        self.assertEqual(len(drafts), 2)
        self.assertEqual(drafts[0].category, "Saude")
        self.assertEqual(drafts[1].category, "Alimentacao")

    def test_rejects_ambiguous_multiple_transaction_text(self) -> None:
        drafts = parse_multiple_transaction_texts("gastei 30 no uber e 20 no ifood")
        self.assertEqual(drafts, [])


if __name__ == "__main__":
    unittest.main()
