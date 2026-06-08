import json

from app.rag.loop import run_tool_loop


def _assistant_tool_call(name, args):
    return {"content": None, "tool_calls": [
        {"id": "call_1", "type": "function",
         "function": {"name": name, "arguments": json.dumps(args)}}
    ]}


def test_loop_runs_tool_then_returns_text():
    # scripted model: first asks to call a tool, then returns prose
    scripted = [
        _assistant_tool_call("sum_invoices", {"vendor": "AWS"}),
        {"content": "You spent 360 on AWS.", "tool_calls": None},
    ]
    calls_seen = []

    def complete(messages, tools):
        return scripted.pop(0)

    def dispatch(name, args):
        calls_seen.append((name, args))
        return {"total_amount": 360.0}

    result = run_tool_loop([{"role": "user", "content": "AWS total?"}], [], dispatch, complete, max_steps=5)

    assert result.final_text == "You spent 360 on AWS."
    assert [c.name for c in result.calls] == ["sum_invoices"]
    assert result.calls[0].args == {"vendor": "AWS"}
    assert result.calls[0].result == {"total_amount": 360.0}
    assert calls_seen == [("sum_invoices", {"vendor": "AWS"})]


def test_loop_stops_at_max_steps():
    # model loops forever asking for tools; max_steps must cap it
    def complete(messages, tools):
        return _assistant_tool_call("filter_invoices", {})

    def dispatch(name, args):
        return {"rows": []}

    result = run_tool_loop([{"role": "user", "content": "x"}], [], dispatch, complete, max_steps=3)
    assert len(result.calls) == 3          # capped
    assert result.final_text == ""         # never produced prose


def test_loop_no_tools_returns_text_immediately():
    def complete(messages, tools):
        return {"content": "I can only answer questions about your invoices.", "tool_calls": None}

    result = run_tool_loop([{"role": "user", "content": "hi"}], [], lambda n, a: None, complete, max_steps=5)
    assert result.calls == []
    assert "invoices" in result.final_text


def test_loop_does_not_mutate_caller_messages():
    msgs = [{"role": "user", "content": "q"}]
    original_len = len(msgs)
    scripted = [
        _assistant_tool_call("get_invoice", {}),
        {"content": "Done.", "tool_calls": None},
    ]
    run_tool_loop(msgs, [], lambda n, a: {}, lambda m, t: scripted.pop(0))
    assert len(msgs) == original_len
