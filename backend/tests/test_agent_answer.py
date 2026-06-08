from app.rag.answer import assemble
from app.rag.loop import LoopResult, ToolCall


def test_sum_call_becomes_sum_card_with_citations():
    calls = [ToolCall("sum_invoices", {"vendor": "AWS"}, {
        "total_net": 300.0, "total_vat": 60.0, "total_amount": 360.0,
        "currency": "BGN", "count": 2,
        "groups": [{"key": "AWS", "total": 360.0, "count": 2, "invoice_ids": ["a", "b"]}],
    })]
    ans = assemble(LoopResult(final_text="AWS spend was 360.", calls=calls), model="test")
    assert ans.reply == "AWS spend was 360."
    assert ans.refused is False
    card = ans.cards[0]
    assert card["type"] == "sum" and card["total_amount"] == 360.0
    assert [c.invoice_id for c in ans.citations] == ["a", "b"]   # contributors cited
    assert ans.tool_trace == [{"tool": "sum_invoices", "args": {"vendor": "AWS"}}]


def test_filter_call_becomes_invoices_card():
    calls = [ToolCall("filter_invoices", {"min_amount": 5000},
                      [{"invoice_id": "x", "number": "2026-1", "vendor_name": "AWS",
                        "date": "2026-03-01", "total_amount": 6000.0, "currency": "BGN"}])]
    ans = assemble(LoopResult(final_text="One invoice over 5000.", calls=calls), model="test")
    assert ans.cards[0]["type"] == "invoices"
    assert ans.cards[0]["items"][0]["number"] == "2026-1"


def test_no_tool_calls_is_refusal():
    ans = assemble(LoopResult(final_text="I can't advise on that.", calls=[]), model="test")
    assert ans.refused is True
    assert ans.cards == []
    assert ans.reply == "I can't advise on that."


def test_ungrouped_sum_emits_sources_card_with_contributing_invoices():
    calls = [ToolCall("sum_invoices", {"vendor": "Балкан"}, {
        "total_net": 1300.0, "total_vat": 197.0, "total_amount": 1497.0,
        "currency": "BGN", "count": 1, "groups": [],
        "invoices": [{"invoice_id": "i1", "number": "2000002513",
                      "vendor_name": "Балкан АД", "date": "2025-12-04",
                      "total_amount": 942.42, "currency": "BGN"}],
    })]
    ans = assemble(LoopResult(final_text="...", calls=calls), model="m")
    assert [c["type"] for c in ans.cards] == ["sum", "sources"]
    assert ans.cards[1]["citations"][0]["source"] == "Балкан АД · 2000002513"
    assert [c.invoice_id for c in ans.citations] == ["i1"]
    assert "invoices" not in ans.cards[0]  # bulky list not duplicated into the sum card


def test_filter_answer_has_no_redundant_sources_card():
    calls = [ToolCall("filter_invoices", {}, [
        {"invoice_id": "x", "number": "2026-1", "vendor_name": "AWS",
         "date": "2026-03-01", "total_amount": 6000.0, "currency": "BGN"}])]
    ans = assemble(LoopResult(final_text="...", calls=calls), model="m")
    assert [c["type"] for c in ans.cards] == ["invoices"]  # no extra sources chips


def test_query_law_becomes_law_sources_card():
    calls = [ToolCall("query_law", {"query": "ДДС ставка"}, [
        {"id": "law:zdds-66", "source": "ЗДДС чл. 66", "kind": "law",
         "text": "Ставката на данъка е 20 на сто...", "metadata": {"url": "https://lex.bg/..."}}])]
    ans = assemble(LoopResult(final_text="Стандартната ставка е 20%.", calls=calls), model="m")
    assert ans.refused is False
    card = ans.cards[0]
    assert card["type"] == "sources"
    assert card["citations"][0] == {"id": "law:zdds-66", "source": "ЗДДС чл. 66", "kind": "law"}


def test_empty_final_text_never_blank():
    # no prose, no tools (model stalled / hit the step cap) -> graceful note, not blank
    ans = assemble(LoopResult(final_text="", calls=[]), model="m", query="какъв е въпросът")
    assert ans.reply.strip()
    # a tool ran but found nothing (e.g. query_law outside the corpus) -> 'not found', no card
    calls = [ToolCall("query_law", {"query": "x"}, [])]
    ans2 = assemble(LoopResult(final_text="   ", calls=calls), model="m", query="данъци")
    assert ans2.reply.strip() and ans2.cards == []


def test_mixed_invoice_and_law_calls_produce_both():
    calls = [
        ToolCall("sum_invoices", {"vendor": "AWS"}, {
            "total_net": 100.0, "total_vat": 20.0, "total_amount": 120.0, "currency": "BGN",
            "count": 1, "groups": [],
            "invoices": [{"invoice_id": "i1", "number": "1", "vendor_name": "AWS",
                          "date": "2025-01-01", "total_amount": 120.0, "currency": "BGN"}]}),
        ToolCall("query_law", {"query": "ДДС"}, [
            {"id": "law:zdds-66", "source": "ЗДДС чл. 66", "kind": "law", "text": "..."}]),
    ]
    ans = assemble(LoopResult(final_text="...", calls=calls), model="m")
    types = [c["type"] for c in ans.cards]
    assert types == ["sum", "sources", "sources"]  # sum + invoice-sources + law-sources
    assert ans.cards[2]["citations"][0]["kind"] == "law"
