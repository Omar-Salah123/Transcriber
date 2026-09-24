"""A small, auditable LangGraph workflow for one invoice image."""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO
from typing import TypedDict

from google.genai.errors import APIError
from langgraph.graph import END, START, StateGraph
from PIL import Image, UnidentifiedImageError

from transcriber_id.extraction import extract_from_gemini
from transcriber_id.extraction.gemini import ExtractionFailure
from transcriber_id.schemas import ExtractedInvoice

ModelExtractor = Callable[[bytes, str], tuple[ExtractedInvoice, str]]


class InvoiceGraphState(TypedDict):
    image_bytes: bytes
    media_type: str
    source_filename: str
    extraction: ExtractedInvoice | None
    raw_model_output: str | None
    warnings: list[str]
    errors: list[str]


def _validate_image(state: InvoiceGraphState) -> dict[str, list[str]]:
    """Reject unreadable images before any chargeable model request."""

    try:
        with Image.open(BytesIO(state["image_bytes"])) as image:
            expected = {"image/png": "PNG", "image/jpeg": "JPEG"}.get(state["media_type"])
            if image.format != expected or max(image.size) > 12000:
                return {"errors": ["Image type or dimensions are not supported."]}
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        return {"errors": ["The uploaded file is not a readable invoice image."]}
    return {"errors": []}


def _after_validation(state: InvoiceGraphState) -> str:
    return "stop" if state["errors"] else "extract"


def _extract_with_gemini(
    extractor: ModelExtractor,
) -> Callable[[InvoiceGraphState], dict[str, object]]:
    def extract(state: InvoiceGraphState) -> dict[str, object]:
        try:
            extraction, raw_model_output = extractor(state["image_bytes"], state["media_type"])
        except ExtractionFailure as error:
            return {
                "errors": ["Invalid structured output."],
                "raw_model_output": error.raw_model_output,
            }
        except APIError as error:
            # The SDK exception text may include request details. Only pass a
            # numeric HTTP status across the service boundary.
            code = error.code
            reason = (
                f"Provider HTTP {code}"
                if isinstance(code, int) and 400 <= code <= 599
                else "Provider request failed"
            )
            return {"errors": [reason], "warnings": []}
        except Exception as error:  # Do not expose model internals to the browser.
            return {"errors": [f"Extraction failed: {type(error).__name__}"], "warnings": []}
        return {
            "extraction": extraction,
            "raw_model_output": raw_model_output,
            "warnings": list(extraction.unresolved_fields),
            "errors": [],
        }

    return extract


def _validate_extraction(state: InvoiceGraphState) -> dict[str, object]:
    """Apply Pydantic validation again at the graph boundary."""

    if state["errors"]:
        return {"errors": state["errors"]}
    if state.get("extraction") is None:
        return {"errors": ["Extraction returned no invoice data."]}
    try:
        extraction = ExtractedInvoice.model_validate(state["extraction"])
    except Exception:
        return {"errors": ["Extraction did not match the invoice schema."]}
    return {"extraction": extraction, "errors": state["errors"]}


def build_invoice_graph(extractor: ModelExtractor | None = None):
    """Build the graph lazily; default extraction creates Gemini clients on invoke."""

    graph = StateGraph(InvoiceGraphState)
    graph.add_node("validate_image", _validate_image)
    graph.add_node("extract_with_gemini", _extract_with_gemini(extractor or extract_from_gemini))
    graph.add_node("validate_extraction", _validate_extraction)
    graph.add_edge(START, "validate_image")
    graph.add_conditional_edges(
        "validate_image",
        _after_validation,
        {"extract": "extract_with_gemini", "stop": END},
    )
    graph.add_edge("extract_with_gemini", "validate_extraction")
    graph.add_edge("validate_extraction", END)
    return graph.compile()


def extract_invoice_image(
    image_bytes: bytes, media_type: str, source_filename: str
) -> InvoiceGraphState:
    """Run one request through the local workflow."""

    graph = build_invoice_graph()
    return graph.invoke(
        {
            "image_bytes": image_bytes,
            "media_type": media_type,
            "source_filename": source_filename,
            "extraction": None,
            "raw_model_output": None,
            "warnings": [],
            "errors": [],
        }
    )
