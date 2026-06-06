"""Ingestion endpoints: XML extraction, text extraction, and PDF/OCR upload."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.schemas import (
    ExtractCsvRequest,
    ExtractCsvResponse,
    ExtractTextRequest,
    ExtractXmlRequest,
    ExtractXmlResponse,
    InvoiceResponse,
)
from app.tools.ingest import (
    extract_invoice_from_text,
    extract_text_from_pdf_bytes,
    group_by_company,
    invoices_from_xml_content,
    ocr_status,
    parse_csv,
    parse_xml,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/extract-xml", response_model=ExtractXmlResponse)
def extract_xml(req: ExtractXmlRequest) -> ExtractXmlResponse:
    """Parse any XML (XXE-safe) into typed invoices grouped by company. Handles the
    Controlisy/ExportedData schema and generic record-based schemas (SAP, UBL, ...)."""
    docs = parse_xml(req.xml, req.label)
    invoices = invoices_from_xml_content(req.xml, req.label)
    groups = group_by_company(invoices)
    return ExtractXmlResponse(documents=docs, invoices=invoices, groups=groups)


@router.post("/extract-csv", response_model=ExtractCsvResponse)
def extract_csv(req: ExtractCsvRequest) -> ExtractCsvResponse:
    """Parse a CSV export / VAT ledger into typed invoices grouped by company."""
    invoices = parse_csv(req.csv, req.label)
    return ExtractCsvResponse(invoices=invoices, groups=group_by_company(invoices))


@router.post("/extract-text", response_model=InvoiceResponse)
def extract_text(req: ExtractTextRequest) -> InvoiceResponse:
    """Extract structured invoice fields from raw text (e.g. pasted OCR output)."""
    invoice = extract_invoice_from_text(req.text, req.doc_id, req.source)
    return InvoiceResponse(invoice=invoice)


@router.post("/extract-pdf", response_model=InvoiceResponse)
async def extract_pdf(file: UploadFile = File(...)) -> InvoiceResponse:
    """OCR a PDF (Bulgarian+English) and extract structured invoice fields."""
    if not ocr_status().get("available"):
        raise HTTPException(status_code=503, detail="OCR not available on this server")
    content = await file.read()
    try:
        text = extract_text_from_pdf_bytes(content)
    except Exception as exc:  # pragma: no cover - depends on OCR env
        raise HTTPException(status_code=422, detail=f"OCR failed: {exc}") from exc
    doc_id = (file.filename or "invoice").rsplit(".", 1)[0]
    invoice = extract_invoice_from_text(text, doc_id, source="ocr")
    return InvoiceResponse(invoice=invoice)
