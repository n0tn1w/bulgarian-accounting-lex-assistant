from eval.cases import EvalCase, load_cases


def test_evalcase_parses_minimal():
    c = EvalCase(id=1, category="refuse", question="trust?", tool=None,
                 params={}, expected={"refused": True}, relevant_ids=[])
    assert c.category == "refuse"
    assert c.tool is None


def test_load_cases_reads_jsonl(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(
        '{"id":1,"category":"lookup","question":"q","tool":"get_invoice","params":{},'
        '"expected":{"id":"inv-001"},"relevant_ids":["inv-001"]}\n\n',
        encoding="utf-8",
    )
    cases = load_cases(p)
    assert len(cases) == 1
    assert cases[0].tool == "get_invoice"
