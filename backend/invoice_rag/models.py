"""Pydantic contracts for the invoice RAG tools (agent-ready in Phase 2)."""
from __future__ import annotations

from datetime import date as date_
from typing import Literal, Optional

from pydantic import BaseModel, Field

GroupBy = Literal["vendor", "month", "quarter", "vat_rate", "country", "currency", "direction"]
Metric = Literal["total_spent", "invoice_count", "avg_amount"]


class DateRange(BaseModel):
    date_from: str  # ISO YYYY-MM-DD (inclusive)
    date_to: str    # ISO YYYY-MM-DD (inclusive)


class FilterParams(BaseModel):
    vendor: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    period: Optional[str] = None  # natural language; resolved by dates.py
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    currency: Optional[str] = None
    country: Optional[str] = None
    vat_rate: Optional[float] = None
    direction: Optional[Literal["sale", "purchase", "unknown"]] = None
    reverse_charge: Optional[bool] = None
    doc_type: Optional[str] = None
    weekend_only: bool = False
    limit: int = 50


class InvoiceView(BaseModel):
    invoice_id: str
    external_id: Optional[str] = None
    number: Optional[str] = None
    date: Optional[str] = None
    vendor_name: Optional[str] = None
    direction: Optional[str] = None
    net_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    score: Optional[float] = None


class SumGroup(BaseModel):
    key: str
    total: float
    count: int
    invoice_ids: list[str] = Field(default_factory=list)


class SumResult(BaseModel):
    total_net: float
    total_vat: float
    total_amount: float
    currency: Optional[str] = None
    count: int
    groups: list[SumGroup] = Field(default_factory=list)
    # Every contributing invoice, so the total is always citable (even ungrouped).
    invoices: list[InvoiceView] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    metric: Metric
    value_a: float
    value_b: float
    delta: float
    pct_change: Optional[float] = None
    invoice_ids_a: list[str] = Field(default_factory=list)
    invoice_ids_b: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    invoice_id: str
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    date: Optional[date_] = None
    amount: Optional[float] = None
    relevance: str = ""
