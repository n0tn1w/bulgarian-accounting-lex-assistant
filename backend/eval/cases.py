"""Shared eval-case schema + JSONL loader (used by tool and agent runners)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

CATEGORIES = {"lookup", "filter", "aggregation", "semantic", "trend", "compliance", "refuse"}


class EvalCase(BaseModel):
    id: int
    category: str
    question: str
    tool: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] = Field(default_factory=dict)
    relevant_ids: list[str] = Field(default_factory=list)


def load_cases(path: str | Path) -> list[EvalCase]:
    text = Path(path).read_text(encoding="utf-8")
    return [EvalCase(**json.loads(line)) for line in text.splitlines() if line.strip()]
