"""Synthetic invoice fixtures for the Invoice RAG evaluation harness.

Sixty invoices with KNOWN, exact ground-truth. Every numeric value is
eyeball-verifiable: net amounts are round, vat = (net * rate) quantised to
0.01, total = net + vat. The deliberately-wrong compliance rows (53/54/55)
use a wrong rate so that vat != 20% of net, modelling a mis-applied VAT rate.

The dataset is the foundation the whole eval rests on, so the distribution is
designed to give every question category a known answer set: category words
(cloud / marketing / consulting) live in the LineItem.description; country is
keyed off the supplier VAT-number prefix; weekend dates are real Sat/Sun
(verified with date.weekday() while authoring).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.domain.models import Invoice, LineItem, Party, TaxLine
from app.tools.ingest.company import tag_company

EVAL_TENANT_ID = uuid.UUID("eeeeeeee-0000-0000-0000-000000000001")

# Columns:
# (n, vendor, vat_no, country, date, net, rate, currency, direction,
#  category_desc, weekend, reverse)
#
# country is informational; the real country signal is the vat_no prefix.
_ROWS: list[tuple] = [
    # --- CLOUD (~10): AWS / Azure / GCP / Hetzner --------------------------
    (1,  "Amazon Web Services EMEA",  "LU123456789", "LU", "2025-01-15", "1200", "0.20", "EUR", "purchase", "Cloud хостинг и сървър услуги (AWS)",            False, True),
    (2,  "Microsoft Azure Ireland",   "IE987654321", "IE", "2025-01-20", "800",  "0.20", "EUR", "purchase", "Azure cloud compute облак",                      False, True),
    (3,  "Google Cloud EMEA",         "IE112233445", "IE", "2025-02-05", "1500", "0.20", "EUR", "purchase", "GCP cloud услуги облак",                         False, True),
    (4,  "Hetzner Online GmbH",       "DE811223344", "DE", "2025-02-18", "300",  "0.20", "BGN", "purchase", "Хостинг сървър cloud (Hetzner)",                 False, True),
    (5,  "Amazon Web Services EMEA",  "LU123456789", "LU", "2025-03-10", "2000", "0.20", "EUR", "purchase", "AWS cloud облак storage",                        False, True),
    (6,  "СуперХостинг БГ ООД",       "BG201112223", "BG", "2025-03-20", "250",  "0.20", "BGN", "purchase", "Хостинг и cloud сървър",                          False, False),
    (7,  "Microsoft Azure Ireland",   "IE987654321", "IE", "2025-04-14", "900",  "0.20", "BGN", "purchase", "Azure cloud услуги облак",                       False, False),
    (8,  "Google Cloud EMEA",         "IE112233445", "IE", "2025-05-06", "1100", "0.20", "BGN", "purchase", "GCP cloud compute облак",                        False, False),
    (9,  "Hetzner Online GmbH",       "DE811223344", "DE", "2025-06-03", "400",  "0.20", "BGN", "purchase", "Сървър хостинг cloud",                            False, False),
    (10, "СуперХостинг БГ ООД",       "BG201112223", "BG", "2024-12-09", "200",  "0.20", "BGN", "purchase", "Облак хостинг cloud услуги",                      False, False),

    # --- MARKETING (~6) ----------------------------------------------------
    (11, "Реклама Плюс ЕООД",         "BG301112223", "BG", "2025-01-28", "500",  "0.20", "BGN", "purchase", "Маркетинг и реклама кампания",                    False, False),
    (12, "Ad Agency Berlin GmbH",     "DE822334455", "DE", "2025-02-12", "1800", "0.20", "EUR", "purchase", "Advertising маркетинг campaign",                  False, True),
    (13, "Дигитал Маркетинг ООД",     "BG302223334", "BG", "2025-03-18", "750",  "0.20", "BGN", "purchase", "Дигитален маркетинг реклама",                     False, False),
    (14, "Реклама Плюс ЕООД",         "BG301112223", "BG", "2025-04-09", "600",  "0.20", "BGN", "purchase", "Реклама advertising социални мрежи",              False, False),
    (15, "Creative Ads Studio",       "BG303334445", "BG", "2025-05-21", "1200", "0.20", "BGN", "purchase", "Маркетинг реклама advertising",                   False, False),
    (16, "Дигитал Маркетинг ООД",     "BG302223334", "BG", "2024-11-19", "450",  "0.20", "BGN", "purchase", "Маркетинг реклама кампания",                      False, False),

    # --- CONSULTING (~6) ---------------------------------------------------
    (17, "Експерт Консулт ЕООД",      "BG401112223", "BG", "2025-01-30", "2500", "0.20", "BGN", "purchase", "Консултантски услуги consulting",                 False, False),
    (18, "Business Consulting DE",    "DE833445566", "DE", "2025-02-25", "3000", "0.20", "EUR", "purchase", "Consulting консултантски бизнес",                 False, True),
    (19, "Експерт Консулт ЕООД",      "BG401112223", "BG", "2025-03-27", "1500", "0.20", "BGN", "purchase", "Консултантски услуги бизнес consulting",          False, False),
    (20, "ПрайсУотър Консулт ООД",    "BG402223334", "BG", "2025-04-22", "4000", "0.20", "BGN", "purchase", "Данъчен консултантски consulting",                False, False),
    (21, "Business Consulting DE",    "DE833445566", "DE", "2025-05-13", "2000", "0.20", "BGN", "purchase", "Consulting консултантски услуги",                 False, False),
    (22, "ПрайсУотър Консулт ООД",    "BG402223334", "BG", "2024-10-15", "1800", "0.20", "BGN", "purchase", "Консултантски одит consulting",                   False, False),

    # --- SOFTWARE LICENSES / GOODS / MISC ---------------------------------
    (23, "JetBrains s.r.o.",          "BG501112223", "BG", "2025-01-09", "300",  "0.20", "BGN", "purchase", "Софтуерен лиценз JetBrains IDE",                  False, False),
    (24, "Adobe Systems Ireland",     "IE544556677", "IE", "2025-02-11", "600",  "0.20", "EUR", "purchase", "Adobe Creative Cloud лиценз софтуер",             False, True),
    (25, "Канцеларски Свят ООД",      "BG502223334", "BG", "2025-03-04", "150",  "0.20", "BGN", "purchase", "Канцеларски материали хартия",                    False, False),
    (26, "Техномаркет България",      "BG503334445", "BG", "2025-04-17", "2200", "0.20", "BGN", "purchase", "Лаптоп и хардуер оборудване",                     False, False),
    (27, "Office Furniture Ltd",      "BG504445556", "BG", "2025-05-28", "900",  "0.20", "BGN", "purchase", "Офис мебели бюро столове",                        False, False),
    (28, "JetBrains s.r.o.",          "BG501112223", "BG", "2025-06-09", "350",  "0.20", "BGN", "purchase", "Софтуерен лиценз годишен абонамент",              False, False),
    (29, "Куриер Експрес ЕООД",       "BG505556667", "BG", "2025-01-22", "100",  "0.20", "BGN", "purchase", "Куриерски услуги доставка",                       False, False),
    (30, "Електроразпределение АД",   "BG506667778", "BG", "2025-02-14", "250",  "0.20", "BGN", "purchase", "Електроенергия комунални услуги",                 False, False),
    (31, "Топлофикация София",        "BG507778889", "BG", "2025-03-13", "180",  "0.20", "BGN", "purchase", "Парно отопление комунални",                       False, False),
    (32, "Мобилен Оператор АД",       "BG508889990", "BG", "2025-04-25", "120",  "0.20", "BGN", "purchase", "Мобилни телефони интернет",                       False, False),

    # --- SALES (direction=sale, ~10 total incl. edge rows) -----------------
    (33, "Моята Фирма ЕООД",          "BG999999999", "BG", "2025-01-31", "5000", "0.20", "BGN", "sale",     "Разработка софтуер услуга клиент",                False, False),
    (34, "Моята Фирма ЕООД",          "BG999999999", "BG", "2025-02-28", "6000", "0.20", "BGN", "sale",     "Софтуерна разработка проект",                     False, False),
    (35, "Моята Фирма ЕООД",          "BG999999999", "BG", "2025-03-31", "7000", "0.20", "EUR", "sale",     "Консултантски услуги клиент",                     False, False),
    (36, "Моята Фирма ЕООД",          "BG999999999", "BG", "2025-04-30", "5500", "0.20", "BGN", "sale",     "Поддръжка софтуер абонамент",                     False, False),
    (37, "Моята Фирма ЕООД",          "BG999999999", "BG", "2025-05-30", "8000", "0.20", "BGN", "sale",     "Разработка уеб приложение",                       False, False),
    (38, "Моята Фирма ЕООД",          "BG999999999", "BG", "2025-06-10", "4500", "0.20", "BGN", "sale",     "Софтуерна услуга проект",                         False, False),

    # --- More purchases to round out distribution / period spread ----------
    (39, "Хотел Бизнес Център",       "BG509990001", "BG", "2025-01-17", "400",  "0.20", "BGN", "purchase", "Командировка хотел нощувки",                      False, False),
    (40, "Ресторант Гурме ООД",       "BG510001112", "BG", "2025-02-21", "300",  "0.20", "BGN", "purchase", "Бизнес обяд представителни",                      False, False),
    (41, "Шел България ЕАД",          "BG511112223", "BG", "2025-03-07", "500",  "0.20", "BGN", "purchase", "Гориво транспорт автомобил",                      False, False),
    (42, "Счетоводна Кантора ООД",    "BG512223334", "BG", "2025-04-12", "350",  "0.20", "BGN", "purchase", "Счетоводни услуги месечни (уикенд)",              True,  False),
    (43, "Адвокатска Кантора",        "BG513334445", "BG", "2025-05-19", "1000", "0.20", "BGN", "purchase", "Правни услуги адвокат",                           False, False),
    (44, "Застраховател ЗАД",         "BG514445556", "BG", "2025-06-05", "800",  "0.20", "BGN", "purchase", "Застраховка имущество годишна",                   False, False),
    (45, "Принт Сервиз ЕООД",         "BG515556667", "BG", "2024-12-18", "220",  "0.20", "BGN", "purchase", "Печатни услуги визитки",                          False, False),
    (46, "DHL Express DE",            "DE844556677", "DE", "2025-02-04", "650",  "0.20", "EUR", "purchase", "Международна доставка карго",                     False, True),
    (47, "Транспорт Лоджистик ООД",   "BG516667778", "BG", "2025-03-26", "1300", "0.20", "BGN", "purchase", "Транспортни логистични услуги",                   False, False),
    (48, "Моята Фирма ЕООД",          "BG999999999", "BG", "2025-04-08", "5200", "0.20", "BGN", "sale",     "Софтуерна разработка клиент проект",              False, False),
    (49, "Моята Фирма ЕООД",          "BG999999999", "BG", "2025-05-15", "4800", "0.20", "BGN", "sale",     "Поддръжка и консултации клиент",                  False, False),
    (50, "Уеб Хостинг БГ ЕООД",       "BG519990001", "BG", "2025-06-02", "180",  "0.20", "BGN", "purchase", "Домейн и хостинг абонамент",                      False, False),

    # --- COMPLIANCE BLOCK (51-56): correct vs deliberately-wrong VAT -------
    (51, "ТочноЕООД",                 "BG601112223", "BG", "2025-03-03", "1000", "0.20", "BGN", "purchase", "Стоки с коректно ДДС 20%",                        False, False),
    (52, "ТочноЕООД",                 "BG601112223", "BG", "2025-03-06", "2000", "0.20", "BGN", "purchase", "Услуги коректно ДДС 20%",                         False, False),
    (53, "ГрешноЕООД",                "BG602223334", "BG", "2025-03-11", "1000", "0.15", "BGN", "purchase", "Стоки с грешно ДДС (трябва 20%)",                 False, False),
    (54, "ГрешноЕООД",                "BG602223334", "BG", "2025-03-12", "2000", "0.09", "BGN", "purchase", "Услуги с грешно ДДС (трябва 20%)",                False, False),
    (55, "ГрешноЕООД",                "BG602223334", "BG", "2025-03-21", "1500", "0.18", "BGN", "purchase", "Стоки с грешно ДДС (трябва 20%)",                 False, False),
    (56, "ТочноЕООД",                 "BG601112223", "BG", "2025-03-24", "3000", "0.20", "BGN", "purchase", "Стоки с коректно ДДС 20%",                        False, False),

    # --- EDGE ROWS (57-60) ------------------------------------------------
    # 57: EUR + weekend + reverse-charge DE
    (57, "Berlin Tech GmbH",          "DE855667788", "DE", "2025-05-10", "6000", "0.20", "EUR", "purchase", "Cloud сървър оборудване Германия",                True,  True),
    # 58: weekend sale
    (58, "Моята Фирма ЕООД",          "BG999999999", "BG", "2025-01-11", "3500", "0.20", "BGN", "sale",     "Софтуерна услуга уикенд издаване",                True,  False),
    # 59: weekend purchase, BGN
    (59, "Уикенд Доставки ЕООД",      "BG520001112", "BG", "2025-02-08", "250",  "0.20", "BGN", "purchase", "Спешна доставка събота",                          True,  False),
    # 60: weekend sale, EUR
    (60, "Моята Фирма ЕООД",          "BG999999999", "BG", "2025-06-14", "4000", "0.20", "EUR", "sale",     "Консултантски услуги уикенд",                     True,  False),
]


def _invoice(row: tuple) -> Invoice:
    n, vendor, vat_no, country, d, net_s, rate_s, cur, direction, cat, weekend, reverse = row
    net = Decimal(net_s)
    rate = Decimal(rate_s)
    vat = (net * rate).quantize(Decimal("0.01"))
    total = net + vat
    return Invoice(
        id=f"inv-{n:03d}",
        source="eval",
        doc_type="invoice",
        direction=direction,
        reverse_charge=reverse,
        number=f"EVAL-{n:04d}",
        date=d,
        currency=cur,
        supplier=Party(name=vendor, vat_number=vat_no),
        recipient=Party(name="Моята Фирма ЕООД", vat_number="BG999999999"),
        net_amount=net,
        vat_amount=vat,
        total_amount=total,
        line_items=[LineItem(description=cat, amount=net)],
        tax_lines=[TaxLine(rate=rate, base=net, amount=vat)],
    )


def build_fixture_invoices() -> list[Invoice]:
    # Route every fixture through tag_company, exactly as real ingestion does
    # (see tools/ingest/*: each path ends with tag_company before storage), so the
    # seeded rows carry company_key/company_name and match the production structure.
    return [tag_company(_invoice(r)) for r in _ROWS]
