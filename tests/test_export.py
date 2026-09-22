from io import BytesIO

from openpyxl import load_workbook

from transcriber.export.workbook import build_workbook


def test_export_only_confirmed_and_preserve_types(repository, image_bytes, complete_data):
    record, _ = repository.add_image("test.png", image_bytes)
    record = repository.save_draft(record.id, complete_data, record.revision)
    empty = load_workbook(BytesIO(build_workbook([record])))
    assert empty["الفواتير"].max_row == 1
    record = repository.confirm(record.id, record.revision)
    book = load_workbook(BytesIO(build_workbook([record, record])))
    invoices, items = book["الفواتير"], book["الأصناف"]
    assert invoices.max_row == 2
    assert items.max_row == 2
    assert invoices["C2"].value == "000081"
    assert invoices["C2"].data_type == "s"
    assert invoices["E2"].is_date
    assert items["E2"].value == 2
    assert items["E2"].data_type == "n"
    assert items["H2"].value == 30.5
    assert items["A2"].value == invoices["A2"].value
    for sheet in book:
        assert sheet.sheet_view.rightToLeft
        assert sheet.freeze_panes == "A2"
        assert sheet.auto_filter.ref


def test_untrusted_text_and_blanks(repository, image_bytes, complete_data):
    complete_data.items[0].description = '=HYPERLINK("https://example.com","click")'
    complete_data.items[0].quantity = None
    complete_data.invoice_number = "#N/A"
    record, _ = repository.add_image("test.png", image_bytes)
    record = repository.save_draft(record.id, complete_data, record.revision)
    record = repository.confirm(record.id, record.revision, acknowledge=True)
    book = load_workbook(BytesIO(build_workbook([record])))
    assert book["الأصناف"]["D2"].data_type == "s"
    assert book["الأصناف"]["D2"].value.startswith("=HYPERLINK")
    assert book["الفواتير"]["C2"].data_type == "s"
    assert book["الأصناف"]["E2"].value is None
    assert book["الفواتير"]["I2"].value is None
    assert book["الفواتير"]["K2"].value == "غير مكتمل"
