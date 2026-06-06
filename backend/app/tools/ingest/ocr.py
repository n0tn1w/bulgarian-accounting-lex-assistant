"""PDF to text via Tesseract OCR (Bulgarian + English).

OCR dependencies are optional and import-guarded so the core service runs without a
system Tesseract install. Call ocr_status to check availability at runtime.
"""

from __future__ import annotations

from app.core import get_settings

try:  # optional heavy deps
    import pytesseract
    from pdf2image import convert_from_bytes, convert_from_path

    _OCR_IMPORTED = True
except Exception:  # pragma: no cover - depends on environment
    _OCR_IMPORTED = False


def ocr_status() -> dict[str, object]:
    """Report whether OCR is usable and which Tesseract version is present."""
    if not _OCR_IMPORTED:
        return {"available": False, "reason": "pytesseract/pdf2image not installed"}
    try:
        version = str(pytesseract.get_tesseract_version())
        return {"available": True, "tesseract_version": version}
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": f"tesseract binary not found: {exc}"}


def _images_to_text(images) -> str:
    settings = get_settings()
    primary = settings.ocr_languages
    parts: list[str] = []
    for image in images:
        try:
            parts.append(pytesseract.image_to_string(image, lang=primary))
        except Exception:
            # Fall back to English if the bul language pack is missing.
            parts.append(pytesseract.image_to_string(image, lang="eng"))
    return "\n\n".join(parts)


def extract_text_from_pdf(path: str) -> str:
    if not _OCR_IMPORTED:
        raise RuntimeError("OCR dependencies not available (see requirements-ocr.txt)")
    images = convert_from_path(path, dpi=get_settings().ocr_dpi)
    return _images_to_text(images)


def extract_text_from_pdf_bytes(content: bytes) -> str:
    if not _OCR_IMPORTED:
        raise RuntimeError("OCR dependencies not available (see requirements-ocr.txt)")
    images = convert_from_bytes(content, dpi=get_settings().ocr_dpi)
    return _images_to_text(images)
