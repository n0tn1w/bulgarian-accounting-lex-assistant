"""LLM clients for the chat orchestrator.

A LiteLLM-backed client makes the model provider interchangeable (local Ollama or cloud
Claude/OpenAI), selected via LLM_MODEL. EchoLLMClient is the no-model fallback so the
pipeline always returns something.
"""

from __future__ import annotations

from typing import Protocol

from app.core import get_settings
from app.rag.base import RetrievedChunk

SYSTEM_PROMPT = (
    "You are Ledgerly, an assistant for Bulgarian accountants. Answer in the user's "
    "language (Bulgarian or English). Use ONLY the information in CONTEXT — it contains "
    "the user's own invoices and excerpts of Bulgarian accounting/tax law. Cite the "
    "sources you use inline in square brackets exactly as given (e.g. [ЗДДС чл. 117] or "
    "[БАЛКАН АД · 2000002487]). Never invent figures, dates or article numbers; if the "
    "context does not contain the answer, say so plainly. This is guidance, not legal advice."
)


def _format_context(context: list[RetrievedChunk]) -> str:
    if not context:
        return "(no context retrieved)"
    return "\n".join(f"[{c.source}] ({c.kind}) {c.text}" for c in context)


class LLMClient(Protocol):
    name: str

    def answer(self, question: str, context: list[RetrievedChunk], history: list[dict]) -> str: ...


class EchoLLMClient:
    """Summarises the retrieved context instead of calling a model."""

    name = "echo-stub"

    def answer(self, question: str, context: list[RetrievedChunk], history: list[dict]) -> str:
        if not context:
            return (
                "No grounded context was retrieved for this question. Add some invoices, "
                "or rephrase — and connect a model (LLM_MODEL) for a written answer."
            )
        lines = [f"Based on {len(context)} retrieved source(s):"]
        for c in context[:6]:
            lines.append(f"• [{c.source}] {c.text}")
        lines.append("\n(No model connected — set LLM_MODEL to get a written answer.)")
        return "\n".join(lines)


class LiteLLMClient:
    """Calls any provider supported by LiteLLM (Ollama / Claude / OpenAI / etc.)."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.name = self.settings.llm_model

    def answer(self, question: str, context: list[RetrievedChunk], history: list[dict]) -> str:
        import litellm

        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in history[-6:]:
            role, content = turn.get("role"), turn.get("content")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append(
            {"role": "user", "content": f"CONTEXT:\n{_format_context(context)}\n\nQUESTION: {question}"}
        )

        kwargs: dict = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
            "timeout": self.settings.llm_timeout,
        }
        if self.settings.llm_api_base:
            kwargs["api_base"] = self.settings.llm_api_base

        resp = litellm.completion(**kwargs)
        return resp["choices"][0]["message"]["content"]


def get_llm_client() -> LLMClient:
    """LiteLLM client when a model is configured, otherwise the echo fallback."""
    return LiteLLMClient() if get_settings().llm_model else EchoLLMClient()
