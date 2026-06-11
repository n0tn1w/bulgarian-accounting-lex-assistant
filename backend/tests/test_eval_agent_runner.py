from eval.run_eval_agent import score_case
from eval.cases import EvalCase


class _Ans:
    def __init__(self, tool_trace, refused, reply=""):
        self.tool_trace = tool_trace
        self.refused = refused
        self.reply = reply


def test_routing_hit_when_expected_tool_called():
    c = EvalCase(id=1, category="filter", question="q", tool="filter_invoices",
                 params={}, expected={}, relevant_ids=[])
    s = score_case(c, _Ans([{"tool": "filter_invoices"}], refused=False))
    assert s["routing_ok"] is True


def test_routing_miss_when_tool_not_called():
    c = EvalCase(id=1, category="filter", question="q", tool="filter_invoices",
                 params={}, expected={}, relevant_ids=[])
    s = score_case(c, _Ans([{"tool": "get_invoice"}], refused=False))
    assert s["routing_ok"] is False


def test_refusal_scored_for_refuse_case():
    c = EvalCase(id=2, category="refuse", question="trust?", tool=None,
                 params={}, expected={"refused": True}, relevant_ids=[])
    assert score_case(c, _Ans([], refused=True))["refusal_ok"] is True


def test_compliance_ok_requires_query_law_and_cited_article():
    c = EvalCase(id=3, category="compliance", question="ддс?", tool="query_law",
                 params={}, expected={"verdict": "incorrect", "article": "ЗДДС чл. 66"},
                 relevant_ids=[])
    good = score_case(c, _Ans([{"tool": "query_law"}], refused=False, reply="... съгласно чл. 66 ..."))
    assert good["compliance_ok"] is True
    no_call = score_case(c, _Ans([], refused=False, reply="чл. 66"))
    assert no_call["compliance_ok"] is False
