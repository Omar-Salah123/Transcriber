"""Synthetic data only; no network or client images."""

from io import BytesIO

import pytest
from PIL import Image

from transcriber.schemas.invoice import InvoiceData, Item
from transcriber.storage.repository import Repository


@pytest.fixture
def image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (120, 180), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def repository(tmp_path) -> Repository:
    return Repository(tmp_path / "invoices")


@pytest.fixture
def complete_data() -> InvoiceData:
    return InvoiceData(
        invoice_number="000081",
        seller="متجر تجريبي",
        customer="عميل تجريبي",
        date_text="٢٠٢٦/٠٩/٢٢",
        verified_date="2026-09-22",
        written_total="٣٠٫٥",
        items=[
            Item(description="صنف تجريبي", quantity="٢", unit_price="١٥٫٢٥", written_amount="٣٠٫٥")
        ],
    )
