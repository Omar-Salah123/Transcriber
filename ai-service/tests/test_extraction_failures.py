from __future__ import annotations

import base64
import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from google.genai.errors import ClientError
from httpx import ReadTimeout
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
        provider_error=None,
        errors=[],
        warnings=[],
    )


def test_malformed_structured_output_preserves_tool_calls() -> None:
    raw_payload = json.dumps(
        {"tool_calls": [{"name": "invoice", "args": {"invoice_number": "000081"}, "id": "test"}]}
    )
    mock_client = MagicMock()
    mock_response = MagicMock(text=raw_payload, parsed=None)
    mock_client.models.generate_content.return_value = mock_response

    with patch("transcriber_id.extraction.gemini.create_gemini_client", return_value=mock_client):
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


@pytest.mark.parametrize("error_type", [TimeoutError, ReadTimeout])
def test_timeout_becomes_safe_error_and_next_attempt_can_run(error_type) -> None:
    def fail(*_):
        raise error_type("sensitive provider internals")

    result = build_invoice_graph(fail).invoke(state())
    assert result["errors"] == ["Extraction failed: TimeoutError"]
    assert "sensitive" not in str(result["errors"])


@pytest.mark.parametrize("status", [400, 429, 503])
def test_provider_error_keeps_public_message_safe_and_private_detail(status: int) -> None:
    def fail(*_):
        raise ClientError(
            status,
            {"error": {"code": status, "message": "private request details"}},
        )

    result = build_invoice_graph(fail).invoke(state())
    assert result["errors"] == [f"Provider HTTP {status}"]
    assert "private request details" not in str(result["errors"])
    assert result["provider_error"] == {
        "http_status": status,
        "status": None,
        "message": "private request details",
        "response": {"error": {"code": status, "message": "private request details"}},
    }


def test_private_http_response_includes_provider_diagnostic() -> None:
    private_detail = {
        "http_status": 429,
        "status": "RESOURCE_EXHAUSTED",
        "message": "Resource exhausted, please try again later.",
        "response": {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "Resource exhausted, please try again later.",
                "details": [
                    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "5s"}
                ],
            }
        },
    }
    handler = InvoiceAgentHandler.__new__(InvoiceAgentHandler)
    handler.connection = MagicMock()
    request_body = json.dumps(
        {"media_type": "image/png", "image_base64": "AA==", "source_filename": "synthetic.png"}
    ).encode()
    handler.headers = {
        "X-Invoice-Service": "laravel",
        "Content-Length": str(len(request_body)),
    }
    handler.path = "/v1/extractions"
    handler.rfile = BytesIO(request_body)
    handler.wfile = BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    with (
        patch.object(InvoiceAgentHandler, "_decode_image", return_value=b"synthetic"),
        patch(
            "transcriber_id.service.extract_invoice_image",
            return_value={
                "errors": ["Provider HTTP 429"],
                "raw_model_output": None,
                "provider_error": private_detail,
            },
        ),
    ):
        handler.do_POST()

    body = json.loads(handler.wfile.getvalue())
    assert body["errors"] == ["Provider HTTP 429"]
    assert body["provider_error"] == private_detail


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


def test_provider_request_has_timeout_below_laravel_and_no_hidden_retries() -> None:
    client = MagicMock()
    client.models.generate_content.side_effect = ReadTimeout("private details")
    with pytest.raises(ReadTimeout):
        extract_from_gemini(b"synthetic", "image/png", client=client, model_name="mock-model")
    client.models.generate_content.assert_called_once()
    options = client.models.generate_content.call_args.kwargs["config"].http_options
    assert options.timeout == 100_000
    assert options.retry_options.attempts == 1
