"""Portable Excel export for the application runtime."""

from datetime import date
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from transcriber.schemas.invoice import Invoice, Status
from transcriber.validation.checks import analyze

INVOICE_HEADERS = [
    "معرف الفاتورة",
    "ملف المصدر",
    "رقم الفاتورة",
    "التاريخ كما كُتب",
    "التاريخ المتحقق",
    "البائع",
    "العميل",
    "الإجمالي المكتوب",
    "الإجمالي المحسوب",
    "مجموع المبالغ المكتوبة",
    "اكتمال الحساب",
    "ملاحظات المراجعة",
    "التنبيهات المقبولة",
    "وقت التأكيد",
]
ITEM_HEADERS = [
    "معرف الفاتورة",
    "رقم الفاتورة",
    "ترتيب الصنف",
    "البيان",
    "العدد",
    "سعر الوحدة",
    "المبلغ المكتوب",
    "المبلغ المحسوب",
    "ملاحظات الصنف",
    "تنبيهات الصنف",
]


def append_row(sheet: Worksheet, values: list) -> None:
    row = sheet.max_row + 1
    for column, value in enumerate(values, 1):
        cell = sheet.cell(row, column)
        if isinstance(value, str):
            # Force text even for '=...', '#N/A', and external-link-like values.
            # XML 1.0 disallows certain control characters.
            value = "".join(c for c in value if c in "\t\n\r" or ord(c) >= 32)
            cell.value = value
            cell.data_type = "s"
        else:
            cell.value = value
        cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
        if isinstance(value, Decimal):
            cell.number_format = "#,##0.####"
        elif isinstance(value, date):
            cell.number_format = "yyyy-mm-dd"


def style_sheet(sheet: Worksheet, headers: list[str], widths: list[int]) -> None:
    sheet.sheet_view.rightToLeft = True
    sheet.freeze_panes = "A2"
    sheet.append(headers)
    for cell in sheet[1]:
        cell.fill = PatternFill("solid", fgColor="164E63")
        cell.font = Font(name="Arial", bold=True, color="FFFFFF", size=11)
        cell.alignment = Alignment(horizontal="right", vertical="center", wrap_text=True)
    sheet.row_dimensions[1].height = 34
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = width


def build_workbook(records: list[Invoice]) -> bytes:
    book = Workbook()
    invoices = book.active
    invoices.title = "الفواتير"
    items = book.create_sheet("الأصناف")
    style_sheet(invoices, INVOICE_HEADERS, [36, 28, 18, 24, 20, 28, 24, 20, 20, 24, 18, 50, 65, 30])
    style_sheet(items, ITEM_HEADERS, [36, 18, 16, 45, 16, 20, 22, 22, 50, 60])
    seen: set[str] = set()
    for record in records:
        if record.status != Status.CONFIRMED or record.id in seen:
            continue
        seen.add(record.id)
        data = record.data
        result = analyze(data)
        summary_warnings = [w for w in result.warnings if not w.startswith("الصنف ")]
        if len(summary_warnings) != len(result.warnings):
            summary_warnings.append("توجد تنبيهات للأصناف؛ راجع عمود تنبيهات الصنف في ورقة الأصناف")
        append_row(
            invoices,
            [
                record.id,
                record.filename,
                data.invoice_number,
                data.date_text,
                data.verified_date,
                data.seller,
                data.customer,
                data.written_total,
                result.calculated_total,
                result.written_sum,
                "مكتمل" if result.calculated_total is not None else "غير مكتمل",
                data.notes,
                "\n".join(summary_warnings),
                record.confirmed_at,
            ],
        )
        for index, (item, amount) in enumerate(
            zip(data.items, result.calculated_amounts, strict=True), 1
        ):
            append_row(
                items,
                [
                    record.id,
                    data.invoice_number,
                    index,
                    item.description,
                    item.quantity,
                    item.unit_price,
                    item.written_amount,
                    amount,
                    item.notes,
                    "\n".join(w for w in result.warnings if w.startswith(f"الصنف {index}:")),
                ],
            )
    for sheet in book:
        sheet.auto_filter.ref = sheet.dimensions
        for row in sheet.iter_rows(min_row=2):
            lines = max(
                (
                    len(str(cell.value or "")) // 45 + str(cell.value or "").count("\n")
                    for cell in row
                ),
                default=0,
            )
            sheet.row_dimensions[row[0].row].height = min(300, max(32, (lines + 1) * 16))
            for cell in row:
                cell.font = Font(name="Arial", size=11)
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.paperSize = sheet.PAPERSIZE_A3
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.print_title_rows = "1:1"
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()
