"""LLM vision fallback for poorly scanned documents.

When OCR confidence is low, the page images are sent to a vision-capable model which
reads the fields directly and returns strict JSON. The result fills only the fields the
regex pass was unsure about, so a clean text reading is never overwritten. Self-disables
when no vision model is configured; any failure returns None so OCR remains the result.
"""

from __future__ import annotations

import base64
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Callable

from app.core import get_settings
from app.domain import ExtractedField, Invoice

_HIGH = 0.9
_VISION_CONF = 0.85  # below _HIGH so the register can still canonicalise a legal name
_MAX_PAGES = 4

_PROMPT = (
    "You read Bulgarian accounting documents. Return ONLY a JSON object with these "
    "string keys (use null when not present): number, date (ISO YYYY-MM-DD), "
    "supplier_name, supplier_vat, supplier_eik, recipient_name, recipient_vat, "
    "recipient_eik, net_amount, vat_amount, total_amount, currency. Keep names exactly "
    "as printed. Do not add commentary or code fences."
)

_STRING_FIELDS = (
    "number", "date",
    "supplier_name", "supplier_vat", "supplier_eik",
    "recipient_name", "recipient_vat", "recipient_eik",
    "currency",
)
_AMOUNT_FIELDS = ("net_amount", "vat_amount", "total_amount")


def vision_model() -> str:
    s = get_settings()
    return s.ocr_vision_model or s.llm_model


def should_use_vision(invoice: Invoice, mean_conf: float) -> bool:
    """Decide whether the vision model is worth consulting for this page."""
    s = get_settings()
    if not s.ocr_vision_fallback or not vision_model():
        return False
    return mean_conf < s.ocr_vision_conf_min or _key_fields_weak(invoice)


def _key_fields_weak(invoice: Invoice) -> bool:
    fc = invoice.field_confidence
    weak = sum(
        fc.get(k, 0.0) < _HIGH
        for k in ("number", "total_amount", "supplier_name", "recipient_name")
    )
    return weak >= 2


def extract_invoice_via_vision(
    page_images: list[bytes],
    doc_id: str = "",
    *,
    complete: Callable[[str, list[bytes]], str] | None = None,
) -> dict[str, ExtractedField] | None:
    """Ask the vision model to read the page images; return field -> ExtractedField."""
    model = vision_model()
    if not model or not page_images:
        return None
    complete = complete or _vision_complete
    try:
        raw = complete(model, page_images[:_MAX_PAGES])
        data = _parse_json(raw)
    except Exception:  # pragma: no cover - model/transport failure
        return None
    return _to_fields(data) if data else None


def merge_into_invoice(invoice: Invoice, fields: dict[str, ExtractedField]) -> Invoice:
    """Apply vision fields, overriding only what was missing or low-confidence."""
    fc = invoice.field_confidence

    def take(key: str) -> bool:
        return key in fields and bool(fields[key].value) and fc.get(key, 0.0) < _HIGH

    if take("number"):
        invoice.number = fields["number"].value
        fc["number"] = _VISION_CONF
    if take("date"):
        invoice.date = fields["date"].value
        fc["date"] = _VISION_CONF

    for who, party in (("supplier", invoice.supplier), ("recipient", invoice.recipient)):
        touched = False
        for attr, key in (
            ("name", f"{who}_name"),
            ("vat_number", f"{who}_vat"),
            ("eik", f"{who}_eik"),
        ):
            if take(key):
                setattr(party, attr, fields[key].value)
                fc[key] = _VISION_CONF
                touched = True
        if touched and party.source == "extracted":
            party.source = "vision"

    for key in _AMOUNT_FIELDS:
        if take(key):
            try:
                setattr(invoice, key, Decimal(fields[key].value))
                fc[key] = _VISION_CONF
            except (InvalidOperation, TypeError):
                pass

    if "currency" in fields and fields["currency"].value:
        invoice.currency = fields["currency"].value
    return invoice


def _vision_complete(model: str, images: list[bytes]) -> str:
    import litellm

    s = get_settings()
    blocks: list[dict] = [{"type": "text", "text": _PROMPT}]
    for img in images:
        b64 = base64.b64encode(img).decode("ascii")
        blocks.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        )
    kwargs: dict = {
        "model": model,
        "messages": [{"role": "user", "content": blocks}],
        "temperature": 0,
        "timeout": s.llm_timeout,
    }
    if s.llm_api_base:
        kwargs["api_base"] = s.llm_api_base
    if s.llm_api_key:
        kwargs["api_key"] = s.llm_api_key
    resp = litellm.completion(**kwargs)
    msg = resp["choices"][0]["message"]
    return msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")


def _parse_json(raw: str | None) -> dict:
    if not raw:
        return {}
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.IGNORECASE).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _to_fields(data: dict) -> dict[str, ExtractedField]:
    out: dict[str, ExtractedField] = {}
    for key in (*_STRING_FIELDS, *_AMOUNT_FIELDS):
        value = data.get(key)
        if value in (None, "", "null"):
            continue
        out[key] = ExtractedField(value=str(value).strip(), confidence=_VISION_CONF)
    return out
