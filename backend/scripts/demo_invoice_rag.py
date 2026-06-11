"""Quick end-to-end demo of the invoice_rag tools.

Seeds a fixed demo tenant with a handful of realistic invoices, builds the index,
then runs each tool the way a Phase-2 agent will — question -> tool -> cited answer.

Usage:  python scripts/demo_invoice_rag.py
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import text

from app.db import init_db
from app.db.base import SessionLocal, admin_engine
from app.domain import Invoice, LineItem, Party
from app.services.workspace import store_invoices
from invoice_rag.citations import citation_from_sum_group, citations_from_views
from invoice_rag.models import DateRange, FilterParams
from invoice_rag.tools.compare import compare_periods
from invoice_rag.tools.filter import filter_invoices
from invoice_rag.tools.lookup import get_invoice
from invoice_rag.tools.search import semantic_search
from invoice_rag.tools.aggregate import sum_invoices

DEMO_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000de")


def _inv(num, vendor, desc, net, vat, total, *, date, currency="BGN",
         direction="purchase", reverse=False):
    return Invoice(
        id=num, number=num, date=date, currency=currency, direction=direction,
        reverse_charge=reverse,
        supplier=Party(name=vendor),
        recipient=Party(name="Моята Фирма ЕООД", vat_number="BG200000001"),
        line_items=[LineItem(description=desc, amount=Decimal(net))],
        net_amount=Decimal(net), vat_amount=Decimal(vat), total_amount=Decimal(total),
    )


SEED = [
    _inv("INV-2026-001", "AWS EMEA SARL", "Amazon Web Services cloud compute", 1000, 200, 1200, date="2026-01-15"),
    _inv("INV-2026-002", "AWS EMEA SARL", "Amazon Web Services cloud compute", 1500, 300, 1800, date="2026-04-10"),
    _inv("INV-2026-003", "Microsoft Ireland", "Azure cloud subscription", 800, 160, 960, date="2026-05-02"),
    _inv("INV-2026-004", "Office Depot", "офис консумативи и хартия", 200, 40, 240, date="2026-03-07"),  # Saturday
    _inv("INV-2026-005", "Hetzner Online GmbH", "dedicated server hosting", 500, 0, 500,
         date="2026-04-20", currency="EUR", reverse=True),
    _inv("INV-2026-006", "Майкрософт България ЕООД", "консултантски услуги", 3000, 600, 3600, date="2026-05-15"),
    _inv("INV-2026-007", "Бранд Студио ООД", "маркетинг и реклама кампания", 6000, 1200, 7200, date="2026-04-25"),
]


def _line(c=""):
    print(c)


def _show(views):
    for v in views:
        amt = f"{v.total_amount:.2f} {v.currency}" if v.total_amount is not None else "—"
        sc = f"  (score {v.score:.3f})" if v.score is not None else ""
        print(f"     • {v.number:<14} {v.vendor_name:<24} {amt}{sc}")


def main() -> None:
    init_db()
    # fresh demo tenant
    with admin_engine.begin() as c:
        c.execute(text("DELETE FROM stored_invoices WHERE tenant_id=:t"), {"t": str(DEMO_TENANT)})
        c.execute(text("DELETE FROM tenants WHERE id=:t"), {"t": str(DEMO_TENANT)})
        c.execute(text("INSERT INTO tenants (id, name) VALUES (:t, 'demo')"), {"t": str(DEMO_TENANT)})

    db = SessionLocal()
    db.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(DEMO_TENANT)})
    n = store_invoices(db, DEMO_TENANT, SEED)   # embeds (BGE-M3) + builds BM25
    db.commit()
    db.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(DEMO_TENANT)})
    _line(f"\nSeeded {n} invoices into demo tenant.\n" + "=" * 70)

    # 1) LOOKUP
    _line('\n[LOOKUP]  "Show me invoice INV-2026-003"')
    v = get_invoice(db, number="INV-2026-003")
    print(f"     → {v.number} | {v.vendor_name} | {v.total_amount:.2f} {v.currency}")

    # 2) FILTER — over 5000 BGN
    _line('\n[FILTER]  "Which invoices are over 5,000 BGN?"')
    _show(filter_invoices(db, FilterParams(min_amount=5000)))

    # 3) FILTER — EUR
    _line('\n[FILTER]  "List all invoices in EUR"')
    _show(filter_invoices(db, FilterParams(currency="EUR")))

    # 4) FILTER — reverse charge
    _line('\n[FILTER]  "Show me invoices with reverse-charge VAT"')
    _show(filter_invoices(db, FilterParams(reverse_charge=True)))

    # 5) FILTER — weekend (fraud signal)
    _line('\n[FILTER]  "Which invoices were issued on weekends?"')
    _show(filter_invoices(db, FilterParams(weekend_only=True)))

    # 6) AGGREGATION — total per vendor
    _line('\n[AGGREGATE]  "Total spending broken down by vendor"')
    res = sum_invoices(db, FilterParams(), group_by="vendor")
    for g in res.groups:
        print(f"     • {g.key:<26} {g.total:>9.2f}   ({g.count} inv)")
    print(f"     GRAND TOTAL: {res.total_amount:.2f} across {res.count} invoices")

    # 7) AGGREGATION — how much on AWS this year
    _line('\n[AGGREGATE]  "How much have we spent on AWS this year?"')
    res = sum_invoices(db, FilterParams(vendor="AWS", period="this year"))
    print(f"     → {res.total_amount:.2f} BGN across {res.count} invoices")
    for c in citations_from_views(filter_invoices(db, FilterParams(vendor="AWS", period="this year"))):
        print(f"        cite: {c.invoice_number} ({c.amount:.2f})")

    # 8) TREND — compare AWS Q1 vs Q2
    _line('\n[COMPARE]  "Did AWS spend grow in Q2 vs Q1?"')
    cmp = compare_periods(
        db, metric="total_spent",
        period_a=DateRange(date_from="2026-01-01", date_to="2026-03-31"),
        period_b=DateRange(date_from="2026-04-01", date_to="2026-06-30"),
        vendor="AWS",
    )
    print(f"     Q1 = {cmp.value_a:.2f} | Q2 = {cmp.value_b:.2f} | "
          f"Δ = {cmp.delta:+.2f} ({cmp.pct_change:+.1f}%)")

    # 9) SEMANTIC — implicit category "cloud services"
    _line('\n[SEMANTIC]  "Find invoices related to cloud services"')
    _show(semantic_search(db, DEMO_TENANT, "cloud services", top_k=4))

    # 10) SEMANTIC — implicit category "marketing"
    _line('\n[SEMANTIC]  "Show me marketing expenses"')
    _show(semantic_search(db, DEMO_TENANT, "marketing advertising", top_k=3))

    _line("\n" + "=" * 70)
    _line("Demo tenant left in place (id …0000de) — explore it via the API too.")
    db.close()


if __name__ == "__main__":
    main()
