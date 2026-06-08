from app.rag.prompts import SYSTEM_PROMPT, build_messages


def test_system_prompt_states_the_rules():
    low = SYSTEM_PROMPT.lower()
    assert "tool" in low and "refuse" in low


def test_build_messages_threads_history_and_question():
    msgs = build_messages("how much on AWS?",
                          history=[{"role": "user", "content": "hi"},
                                   {"role": "assistant", "content": "hello"}])
    assert msgs[0]["role"] == "system"
    assert msgs[-1] == {"role": "user", "content": "how much on AWS?"}
    assert any(m["content"] == "hello" for m in msgs)
