"""LiteLLM adapter: the default `complete` callable for the loop.

Normalizes a LiteLLM completion into {"content", "tool_calls"} so the loop stays
provider-agnostic. tool_calls are returned in OpenAI/LiteLLM shape.
"""
from __future__ import annotations

from app.core import get_settings


def litellm_complete(messages: list[dict], tools: list[dict]) -> dict:
    import litellm

    s = get_settings()
    kwargs: dict = {
        "model": s.llm_model,
        "messages": messages,
        "tools": tools,
        "temperature": s.llm_temperature,
        "timeout": s.llm_timeout,
    }
    if s.llm_api_base:
        kwargs["api_base"] = s.llm_api_base
    if s.llm_api_key:
        kwargs["api_key"] = s.llm_api_key
    resp = litellm.completion(**kwargs)
    msg = resp["choices"][0]["message"]
    # litellm message may be an object or dict; normalize both
    content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
    raw_tcs = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
    tool_calls = None
    if raw_tcs:
        tool_calls = []
        for tc in raw_tcs:
            d = tc if isinstance(tc, dict) else tc.model_dump()
            tool_calls.append({
                "id": d["id"], "type": "function",
                "function": {"name": d["function"]["name"], "arguments": d["function"]["arguments"]},
            })
    return {"content": content, "tool_calls": tool_calls}
