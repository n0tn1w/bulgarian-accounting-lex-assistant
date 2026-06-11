from decimal import Decimal
from eval.fixtures.invoices import build_fixture_invoices, EVAL_TENANT_ID


def test_sixty_invoices_with_stable_ids():
    invs = build_fixture_invoices()
    assert len(invs) == 60
    assert invs[0].id == "inv-001"
    assert {i.id for i in invs} == {f"inv-{n:03d}" for n in range(1, 61)}


def test_amounts_total_is_net_plus_vat():
    for i in build_fixture_invoices():
        if i.net_amount is not None and i.vat_amount is not None and i.total_amount is not None:
            assert i.total_amount == i.net_amount + i.vat_amount


def test_eval_tenant_id_is_fixed_uuid():
    assert str(EVAL_TENANT_ID) == "eeeeeeee-0000-0000-0000-000000000001"


def test_compliance_has_wrong_vat_rows():
    invs = {i.id: i for i in build_fixture_invoices()}
    # rows 53,54,55 must have vat != 20% of net (deliberately wrong)
    for bad in ("inv-053", "inv-054", "inv-055"):
        i = invs[bad]
        assert i.vat_amount != (i.net_amount * Decimal("0.20")).quantize(Decimal("0.01"))
    # rows 51,52,56 must be correct 20%
    for good in ("inv-051", "inv-052", "inv-056"):
        i = invs[good]
        assert i.vat_amount == (i.net_amount * Decimal("0.20")).quantize(Decimal("0.01"))
