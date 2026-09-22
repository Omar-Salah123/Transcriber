from io import BytesIO

from openpyxl import load_workbook
from PIL import Image

from transcriber.export.workbook import build_workbook


def test_eighty_invoices_do_not_duplicate_or_export_unconfirmed(repository, complete_data):
    for index in range(80):
        buffer = BytesIO()
        Image.new("RGB", (8, 8), (index, 0, 0)).save(buffer, format="PNG")
        record, added = repository.add_image(f"{index}.png", buffer.getvalue())
        assert added
        _, duplicate = repository.add_image(f"copy-{index}.png", buffer.getvalue())
        assert not duplicate
        if index < 79:
            record = repository.save_draft(record.id, complete_data, record.revision)
            repository.confirm(record.id, record.revision)
    assert len(repository.list()) == 80
    for _ in range(2):
        book = load_workbook(BytesIO(build_workbook(repository.list())))
        assert book["الفواتير"].max_row == 80
        assert book["الأصناف"].max_row == 80
        ids = [row[0].value for row in book["الفواتير"].iter_rows(min_row=2)]
        assert len(set(ids)) == 79
