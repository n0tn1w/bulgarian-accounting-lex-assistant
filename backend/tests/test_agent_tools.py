from invoice_rag.agent.tools import INVOICE_TOOL_SCHEMAS as TOOL_SCHEMAS


def test_five_tools_with_function_shape():
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    assert names == {"get_invoice", "filter_invoices", "sum_invoices",
                     "compare_periods", "semantic_search"}
    for t in TOOL_SCHEMAS:
        assert t["type"] == "function"
        fn = t["function"]
        assert fn["description"]                         # non-empty description
        assert fn["parameters"]["type"] == "object"      # JSON-schema object


def test_filter_schema_exposes_filterparams_fields():
    fn = next(t["function"] for t in TOOL_SCHEMAS if t["function"]["name"] == "filter_invoices")
    props = fn["parameters"]["properties"]
    for field in ("vendor", "min_amount", "currency", "period", "reverse_charge", "weekend_only"):
        assert field in props
