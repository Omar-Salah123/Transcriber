from decimal import Decimal

import pandas as pd

from transcriber.schemas.invoice import InvoiceData, Item
from transcriber.ui.review import ITEM_COLUMNS, editor_rows, read_items


def test_editor_add_delete_and_arabic_numbers(complete_data):
    frame = editor_rows(complete_data)
    frame.loc[1] = ["صنف جديد", "٣", "١٠", "٣٠", ""]
    items = read_items(frame.drop(index=0))
    assert len(items) == 1
    assert items[0].description == "صنف جديد"
    assert items[0].quantity == Decimal(3)


def test_unreadable_row_is_not_silently_removed():
    rows = editor_rows(InvoiceData(items=[Item()]))
    assert len(read_items(rows)) == 1
    empty = pd.DataFrame(columns=list(ITEM_COLUMNS), dtype=str)
    assert read_items(empty) == []
