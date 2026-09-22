"""Deterministic checks that preserve source amounts and missing values."""

from dataclasses import dataclass
from decimal import Decimal

from transcriber.schemas.invoice import InvoiceData


@dataclass(frozen=True)
class Analysis:
    calculated_amounts: list[Decimal | None]
    calculated_total: Decimal | None
    written_sum: Decimal | None
    warnings: list[str]


def analyze(data: InvoiceData) -> Analysis:
    warnings: list[str] = []
    for key, label in [
        ("invoice_number", "رقم الفاتورة"),
        ("seller", "البائع"),
        ("customer", "العميل"),
    ]:
        if not getattr(data, key):
            warnings.append(f"{label}: غير متوفر")
    if data.verified_date is None:
        warnings.append("التاريخ لم يتم التحقق منه؛ يُحفظ النص الأصلي كما هو")
    if data.written_total is None:
        warnings.append("الإجمالي المكتوب غير متوفر")
    if data.notes:
        warnings.append(f"ملاحظات الفاتورة: {data.notes}")
    if not data.items:
        warnings.append("لا توجد أصناف؛ تحقق من عدم فقدان صفوف")
    amounts: list[Decimal | None] = []
    for index, item in enumerate(data.items, 1):
        prefix = f"الصنف {index}"
        if not item.description:
            warnings.append(f"{prefix}: الوصف غير متوفر")
        for key, label in [
            ("quantity", "العدد"),
            ("unit_price", "سعر الوحدة"),
            ("written_amount", "المبلغ المكتوب"),
        ]:
            value = getattr(item, key)
            if value is None:
                warnings.append(f"{prefix}: {label} غير متوفر")
            elif value < 0:
                warnings.append(f"{prefix}: {label} سالب؛ تحقق من المصدر")
        calculated = (
            item.quantity * item.unit_price
            if item.quantity is not None and item.unit_price is not None
            else None
        )
        amounts.append(calculated)
        if (
            calculated is not None
            and item.written_amount is not None
            and abs(calculated - item.written_amount) > Decimal("0.01")
        ):
            warnings.append(f"{prefix}: العدد × سعر الوحدة لا يساوي المبلغ المكتوب")
        if item.notes:
            warnings.append(f"{prefix}: {item.notes}")
    total = sum(amounts, Decimal(0)) if amounts and all(x is not None for x in amounts) else None
    written = [item.written_amount for item in data.items]
    written_sum = (
        sum(written, Decimal(0)) if written and all(x is not None for x in written) else None
    )
    if data.written_total is not None:
        if data.written_total < 0:
            warnings.append("الإجمالي المكتوب سالب؛ تحقق من المصدر")
        for value, label in [(total, "الإجمالي المحسوب"), (written_sum, "مجموع مبالغ الأصناف")]:
            if value is not None and abs(value - data.written_total) > Decimal("0.01"):
                warnings.append(f"{label} لا يساوي الإجمالي المكتوب")
    return Analysis(amounts, total, written_sum, warnings)
