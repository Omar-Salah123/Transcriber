from __future__ import annotations

import base64
import json
from io import BytesIO
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from PIL import Image
from transcriber_id.agents.invoice_graph import build_invoice_graph
from transcriber_id.extraction.gemini import ExtractionFailure, extract_from_gemini
from transcriber_id.service import InvoiceAgentHandler


def state(media_type: str = "image/png") -> dict:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
    return dict(
        image_bytes=buffer.getvalue(),
        media_type=media_type,
        source_filename="synthetic.png",
        extraction=None,
        raw_model_output=None,
        errors=[],
        warnings=[],
    )


def test_malformed_structured_output_preserves_tool_calls() -> None:
    message = AIMessage(
        content="",
        tool_calls=[{"name": "invoice", "args": {"invoice_number": "000081"}, "id": "test"}],
    )
    with patch("transcriber_id.extraction.gemini.ChatGoogleGenerativeAI") as model:
        model.return_value.with_structured_output.return_value.invoke.return_value = {
            "parsed": None,
            "raw": message,
        }
        with pytest.raises(ExtractionFailure) as caught:
            extract_from_gemini(
                b"synthetic", "image/png", api_key="test-only", model_name="mock-model"
            )
    raw = json.loads(caught.value.raw_model_output)
    assert raw["tool_calls"][0]["args"]["invoice_number"] == "000081"


def test_graph_keeps_failure_output_and_error() -> None:
    def fail(*_):
        raise ExtractionFailure("original malformed output")

    result = build_invoice_graph(fail).invoke(state())
    assert result["raw_model_output"] == "original malformed output"
    assert result["errors"] == ["Invalid structured output."]


def test_timeout_becomes_safe_error_and_next_attempt_can_run() -> None:
    def fail(*_):
        raise TimeoutError("sensitive provider internals")

    result = build_invoice_graph(fail).invoke(state())
    assert result["errors"] == ["Extraction failed: TimeoutError"]
    assert "sensitive" not in str(result["errors"])


def test_media_type_must_match_image_bytes() -> None:
    def never(*_):
        pytest.fail("Model must not be called")

    assert build_invoice_graph(never).invoke(state("image/jpeg"))["errors"]


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"media_type": "image/png", "image_base64": "!"},
        {"media_type": "image/gif", "image_base64": "AA=="},
    ],
)
def test_http_boundary_rejects_bad_payloads(payload) -> None:
    with pytest.raises(ValueError):
        InvoiceAgentHandler._decode_image(payload)


def test_http_boundary_decodes_valid_image() -> None:
    original = state()["image_bytes"]
    assert (
        InvoiceAgentHandler._decode_image(
            {"media_type": "image/png", "image_base64": base64.b64encode(original).decode()}
        )
        == original
    )
