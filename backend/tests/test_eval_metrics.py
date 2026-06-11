from decimal import Decimal
from eval.metrics import precision_recall_at_k, mrr, numeric_match


def test_precision_recall_at_k():
    p, r = precision_recall_at_k(["a", "b", "x"], ["a", "b", "c"], k=3)
    assert p == round(2 / 3, 3)
    assert r == round(2 / 3, 3)


def test_precision_recall_empty_relevant():
    assert precision_recall_at_k(["a"], [], k=3) == (0.0, 0.0)


def test_mrr_first_relevant_rank():
    assert mrr(["x", "a", "b"], ["a"]) == 0.5
    assert mrr(["a"], ["a"]) == 1.0
    assert mrr(["x"], ["a"]) == 0.0


def test_numeric_match_within_tolerance():
    assert numeric_match(Decimal("100.00"), Decimal("100.004")) is True
    assert numeric_match(Decimal("100.00"), Decimal("100.02")) is False
    assert numeric_match(None, Decimal("1")) is False
