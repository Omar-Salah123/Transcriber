from transcriber.evaluation import PilotCase, evaluate, score
from transcriber.schemas.invoice import InvoiceData


def test_missing_rows_count_as_numeric_and_description_errors(complete_data):
    result = score(complete_data, InvoiceData())
    assert result["missing_rows"] == 1
    assert result["numeric_fields"] == 4
    assert result["numeric_correct"] == 0
    assert result["description_character_errors"] == len(complete_data.items[0].description)


def test_pilot_does_not_score_corrected_drafts(repository, image_bytes, complete_data):
    record, _ = repository.add_image("test.png", image_bytes)
    repository.save_draft(record.id, complete_data, record.revision)
    report = evaluate(repository, [PilotCase(invoice_id=record.id, expected=complete_data)])
    assert report["metrics"]["numeric_accuracy"] == 0
    assert report["details"][0]["failed_extraction"]
    assert report["reported_api_cost_usd"] is None
