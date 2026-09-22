from __future__ import annotations

from io import BytesIO

from PIL import Image
from transcriber_id.agents.invoice_graph import build_invoice_graph
from transcriber_id.schemas import ExtractedInvoice, ExtractedInvoiceItem


def image_bytes() -> bytes:
    image = Image.new("RGB", (1, 1), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_graph_validates_and_preserves_model_result() -> None:
    def fake_extractor(_: bytes, __: str) -> tuple[ExtractedInvoice, str]:
        return (
            ExtractedInvoice(
                invoice_number="0007",
                items=[ExtractedInvoiceItem(description="قلم", quantity_text="٢")],
            ),
            '{"invoice_number":"0007"}',
        )

    graph = build_invoice_graph(fake_extractor)
    result = graph.invoke(
        {
            "image_bytes": image_bytes(),
            "media_type": "image/png",
            "source_filename": "synthetic.png",
            "extraction": None,
            "raw_model_output": None,
            "warnings": [],
            "errors": [],
        }
    )

    assert result["errors"] == []
    assert result["extraction"].invoice_number == "0007"
    assert result["raw_model_output"] == '{"invoice_number":"0007"}'


def test_graph_rejects_invalid_image_without_calling_model() -> None:
    called = False

    def fake_extractor(_: bytes, __: str) -> tuple[ExtractedInvoice, str]:
        nonlocal called
        called = True
        return ExtractedInvoice(), "{}"

    graph = build_invoice_graph(fake_extractor)
    result = graph.invoke(
        {
            "image_bytes": b"not an image",
            "media_type": "image/png",
            "source_filename": "synthetic.png",
            "extraction": None,
            "raw_model_output": None,
            "warnings": [],
            "errors": [],
        }
    )

    assert called is False
    assert result["errors"] == ["The uploaded file is not a readable invoice image."]


def test_schema_keeps_source_marks_and_interpretations_separate() -> None:
    extracted = ExtractedInvoice.model_validate(
        {
            "written_total_text": "١٤٠،~~~",
            "written_total_interpreted_text": "140000",
            "items": [
                {
                    "quantity_text": "٢",
                    "unit_price_text": "٧٠،~~~",
                    "unit_price_interpreted_text": "70000",
                    "written_amount_text": "١٤٠،~~~",
                    "written_amount_interpreted_text": "140000",
                }
            ],
        }
    )

    assert extracted.items[0].unit_price_text == "٧٠،~~~"
    assert extracted.items[0].unit_price_interpreted_text == "70000"
    assert extracted.model_dump()["written_total_interpreted_text"] == "140000"
