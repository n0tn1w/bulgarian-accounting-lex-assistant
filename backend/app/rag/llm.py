"""LLM plumbing for the chat orchestrator.

`litellm_complete` is the tool-calling adapter the agent loop drives (passes
`tools`, returns tool calls). `EchoLLMClient` is the no-model fallback: when
LLM_MODEL is unset (or the agent errors), /chat summarizes the retrieved context
without a model so the app always responds.
"""
from __future__ import annotations

from typing import Protocol

from app.core import get_settings
from app.rag.base import RetrievedChunk


def litellm_complete(messages: list[dict], tools: list[dict]) -> dict:
    """Default `complete` callable for the tool loop. Normalizes a LiteLLM
    completion into {"content", "tool_calls"} (OpenAI/LiteLLM shape)."""
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


class LLMClient(Protocol):
    name: str

    def answer(self, question: str, context: list[RetrievedChunk], history: list[dict]) -> str: ...


class EchoLLMClient:
    """No-model fallback: summarises the retrieved context instead of calling a model."""

    name = "echo-stub"

    def answer(self, question: str, context: list[RetrievedChunk], history: list[dict]) -> str:
        if not context:
            return (
                "No grounded context was retrieved for this question. Add some invoices, "
                "or connect a model (set LLM_MODEL) for the full assistant."
            )
        lines = [f"Based on {len(context)} retrieved source(s):"]
        for c in context[:6]:
            lines.append(f"• [{c.source}] {c.text}")
        lines.append("\n(No model connected — set LLM_MODEL for the full tool-using assistant.)")
        return "\n".join(lines)
