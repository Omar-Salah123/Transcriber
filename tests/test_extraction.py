import json
from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors, types

from transcriber.extraction.gemini import (
    ExtractionError,
    ExtractionResult,
    GeminiExtractor,
    parse_extraction,
    validate_result,
)
from transcriber.extraction.service import extract_invoice
from transcriber.schemas.invoice import Status
from transcriber.storage.repository import ConflictError


def payload() -> str:
    return json.dumps(
        {
            "invoice_number": "000081",
            "date_text": "١/٢/٢٦",
            "seller": "تجريبي",
            "customer": None,
            "written_total": None,
            "notes": "",
            "items": [
                {
                    "description": "صنف",
                    "quantity": "٢",
                    "unit_price": "١٢؟",
                    "written_amount": "24",
                    "notes": "",
                },
            ],
        }
    )


class FakeExtractor:
    model = "fake"

    def __init__(self, output):
        self.output = output

    def extract(self, content):
        if isinstance(self.output, Exception):
            raise self.output
        return ExtractionResult(self.output)


def test_unreadable_numbers_and_dates_preserved():
    data = parse_extraction(payload())
    assert data.items[0].quantity == 2
    assert data.items[0].unit_price is None
    assert "١٢؟" in data.items[0].notes
    assert data.verified_date is None
    assert data.date_text == "١/٢/٢٦"


def test_failure_retry_raw_attempts_and_review_protection(repository, image_bytes):
    record, _ = repository.add_image("invoice.png", image_bytes)
    failed = extract_invoice(repository, record.id, FakeExtractor("invalid json"))
    assert failed.status == Status.FAILED
    assert repository.attempts(record.id)[0]["raw_text"] == "invalid json"
    extracted = extract_invoice(repository, record.id, FakeExtractor(payload()))
    assert extracted.status == Status.EXTRACTED
    assert len(repository.attempts(record.id)) == 2
    with pytest.raises(ValueError):
        extract_invoice(repository, record.id, FakeExtractor(payload()))
    assert repository.attempts(record.id)[1]["raw_text"] == payload()


def test_api_failure_is_recorded(repository, image_bytes):
    record, _ = repository.add_image("invoice.png", image_bytes)
    failed = extract_invoice(repository, record.id, FakeExtractor(ExtractionError("try later")))
    assert failed.error == "try later"
    assert repository.attempts(record.id)[0]["error"] == "try later"


def test_api_result_cannot_overwrite_concurrent_edit(repository, image_bytes, complete_data):
    record, _ = repository.add_image("invoice.png", image_bytes)
    repository.save_draft(record.id, complete_data, record.revision)
    with pytest.raises(ConflictError):
        repository.record_attempt(
            record, model="fake", raw_text=payload(), metadata={}, data=complete_data
        )


def test_real_sdk_call_contract_without_network(image_bytes):
    client = MagicMock()
    client.models.generate_content.return_value = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                finish_reason="STOP", content=types.Content(parts=[types.Part(text=payload())])
            )
        ],
    )
    with patch("transcriber.extraction.gemini.genai.Client") as factory:
        factory.return_value.__enter__.return_value = client
        result = GeminiExtractor("fake-key", "fake-model").extract(image_bytes)
    assert result.raw_text == payload()
    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema["properties"]["items"]
    assert factory.call_args.kwargs["http_options"].retry_options.attempts == 1


def test_truncated_output_is_not_accepted():
    with pytest.raises(ExtractionError):
        validate_result(ExtractionResult(payload(), {"finish_reasons": ["MAX_TOKENS"]}))


def test_rate_limit_error_does_not_expose_provider_body(image_bytes):
    client = MagicMock()
    client.models.generate_content.side_effect = errors.ClientError(
        429, {"error": {"code": 429, "message": "sensitive-provider-detail"}}
    )
    with patch("transcriber.extraction.gemini.genai.Client") as factory:
        factory.return_value.__enter__.return_value = client
        with pytest.raises(ExtractionError) as caught:
            GeminiExtractor("fake-key", "fake-model").extract(image_bytes)
    assert "sensitive-provider-detail" not in str(caught.value)
    assert "حد الاستخدام" in str(caught.value)
