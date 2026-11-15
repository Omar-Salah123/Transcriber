"""Offline behavioral checks for the standalone GPU notebook."""

import json
from pathlib import Path

import nbformat
import pytest
from openpyxl import load_workbook
from PIL import Image
from transcriber_id.extraction.gemini import EXTRACTION_INSTRUCTIONS
from transcriber_id.schemas.invoice import ExtractedInvoice, ExtractedInvoiceItem

NOTEBOOK = Path(__file__).resolve().parents[2] / "notebooks/gemma_invoice_benchmark.ipynb"


@pytest.fixture
def notebook():
    document = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(document)
    namespace = {"__name__": __name__, "metadata": {"model_id": "synthetic-test"}}
    for cell in document.cells:
        if cell.cell_type == "code":
            assert cell.outputs == []
            assert cell.execution_count is None
            if "install" not in cell.metadata.get("tags", []):
                compile(cell.source, str(NOTEBOOK), "exec")
            if set(cell.metadata.get("tags", [])) & {
                "config",
                "imports",
                "schema",
                "prompt",
                "helpers",
                "batch_helpers",
            }:
                exec(cell.source, namespace)
    return namespace


def payload():
    return ExtractedInvoice(
        invoice_number="000081",
        seller="متجر تجريبي",
        written_total_text="70,000",
        written_total_interpreted_text="70000",
        items=[
            ExtractedInvoiceItem(
                description='=HYPERLINK("https://example.invalid")',
                quantity_text="0",
                unit_price_text="٧٠٬٠٠٠",
                unit_price_interpreted_text="70000",
            ),
            ExtractedInvoiceItem(description="صنف ثان"),
        ],
    ).model_dump()


def test_matches_gemini_contract(notebook):
    assert notebook["SCHEMA"] == ExtractedInvoice.model_json_schema()
    assert notebook["EXTRACTION_INSTRUCTIONS"] == EXTRACTION_INSTRUCTIONS
    raw = json.dumps(payload(), ensure_ascii=False)
    assert notebook["parse_extraction"](f"```json\n{raw}\n```<turn|>").invoice_number == "000081"
    for invalid in ("{}", '{"items": []}', raw[:-1]):
        with pytest.raises(ValueError):
            notebook["parse_extraction"](invalid)


def test_export_preserves_source_and_safe_cell_types(notebook, tmp_path):
    record = {
        "image_sha256": "hash",
        "source_filename": "batch/invoice.png",
        "status": "ok",
        "seconds": 1.2,
        "checkpoint": "hash.json",
        "extraction": payload(),
    }
    destination = tmp_path / "benchmark.xlsx"
    notebook["export_workbook"]([record], destination, {"model_id": "fake"})
    book = load_workbook(destination)
    assert len(book.sheetnames) == 6
    headers, items = book["الفواتير"], book["الأصناف"]
    assert headers["B2"].value == "000081"
    assert headers["F2"].value == 70000
    assert items["D2"].value == 0
    assert items["F2"].value is None
    assert items["C2"].data_type == "s"
    assert items["C2"].value.startswith("=HYPERLINK")
    assert items["B3"].value == 2
    assert items["C3"].value == "صنف ثان"
    raw = list(book["item_fields"].values)
    assert raw[1][raw[0].index("unit_price_text")] == "٧٠٬٠٠٠"
    for sheet in book:
        assert sheet.freeze_panes == "A2"
        assert sheet.auto_filter.ref
        assert all(cell.data_type != "f" for row in sheet for cell in row)


def test_batch_failure_resume_and_changed_image(notebook, tmp_path):
    inputs, output = tmp_path / "images", tmp_path / "results"
    inputs.mkdir()
    output.mkdir()
    for name in ["a.png", "b.PNG"]:
        Image.new("RGB", (10, 10), "white").save(inputs / name)
    paths = notebook["discover_images"](inputs, True, None)
    calls = []

    def infer(path):
        calls.append(path.name)
        return json.dumps(payload()) if path.name == "a.png" else "not JSON"

    run = notebook["run_batch"]
    records = run(paths, inputs, output, "signature", infer)
    assert [r["status"] for r in records] == ["ok", "failed"]
    assert records[1]["raw_model_output"] == "not JSON"
    run(paths, inputs, output, "signature", infer)
    assert calls == ["a.png", "b.PNG"]
    run(paths, inputs, output, "signature", infer, retry_failed=True)
    assert calls == ["a.png", "b.PNG", "b.PNG"]
    Image.new("RGB", (10, 10), "red").save(inputs / "a.png")
    run(paths, inputs, output, "signature", infer)
    assert calls[-1] == "a.png"
    assert len(calls) == 4
    log = load_workbook(output / "gemma_results.xlsx")["run_log"]
    assert log.max_row == 3
    assert log["C3"].value == "failed"


def test_interruption_exports_completed_records(notebook, tmp_path):
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    first.write_bytes(b"synthetic-one")
    second.write_bytes(b"synthetic-two")

    def infer(path):
        if path == second:
            raise KeyboardInterrupt
        return json.dumps(payload())

    with pytest.raises(KeyboardInterrupt):
        notebook["run_batch"]([first, second], tmp_path, tmp_path, "run", infer)
    assert load_workbook(tmp_path / "gemma_results.xlsx")["run_log"].max_row == 2
