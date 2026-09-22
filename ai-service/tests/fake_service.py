"""Synthetic local HTTP fixture for end-to-end tests; never calls Gemini.

Run with: uv run python ai-service/tests/fake_service.py
Use AI_SERVICE_URL=http://127.0.0.1:8101 in an isolated Laravel test environment.
"""

from http.server import ThreadingHTTPServer

from transcriber_id import service
from transcriber_id.agents.invoice_graph import build_invoice_graph
from transcriber_id.schemas import ExtractedInvoice, ExtractedInvoiceItem


def fake_extractor(_: bytes, __: str) -> tuple[ExtractedInvoice, str]:
    invoice = ExtractedInvoice(
        invoice_number="000081",
        date_text="٩ / ؟ / ٢٠٢٦",
        seller="متجر تجريبي",
        customer=None,
        written_total_text="٠٫٣",
        unresolved_fields=["customer", "date_text"],
        items=[
            ExtractedInvoiceItem(
                description="صنف تجريبي",
                quantity_text="٣",
                unit_price_text="٠٫١",
                written_amount_text="٠٫٣",
            )
        ],
    )
    return invoice, invoice.model_dump_json()


def extract(image_bytes: bytes, media_type: str, source_filename: str):
    return build_invoice_graph(fake_extractor).invoke(
        dict(
            image_bytes=image_bytes,
            media_type=media_type,
            source_filename=source_filename,
            extraction=None,
            raw_model_output=None,
            warnings=[],
            errors=[],
        )
    )


if __name__ == "__main__":
    service.extract_invoice_image = extract
    ThreadingHTTPServer(("127.0.0.1", 8101), service.InvoiceAgentHandler).serve_forever()
