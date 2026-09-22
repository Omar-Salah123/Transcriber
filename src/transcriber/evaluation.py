"""Offline pilot scoring against original extraction attempts, never corrected drafts.

Run: uv run python -m transcriber.evaluation data/pilot.json --data-dir data
"""

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from transcriber.extraction.gemini import parse_extraction
from transcriber.schemas.invoice import InvoiceData
from transcriber.storage.repository import Repository


class PilotCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_id: str
    expected: InvoiceData
    review_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    manual_seconds: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    api_cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)


def edit_distance(expected: str, actual: str) -> int:
    previous = list(range(len(actual) + 1))
    for index, left in enumerate(expected, 1):
        current = [index]
        for column, right in enumerate(actual, 1):
            current.append(
                min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (left != right))
            )
        previous = current
    return previous[-1]


def score(expected: InvoiceData, actual: InvoiceData) -> dict:
    numeric_total = numeric_correct = descriptions = description_correct = errors = characters = 0
    if expected.written_total is not None:
        numeric_total += 1
        numeric_correct += int(expected.written_total == actual.written_total)
    for index, item in enumerate(expected.items):
        predicted = actual.items[index] if index < len(actual.items) else None
        for key in ("quantity", "unit_price", "written_amount"):
            value = getattr(item, key)
            if value is not None:
                numeric_total += 1
                numeric_correct += int(predicted is not None and getattr(predicted, key) == value)
        text = " ".join(item.description.split())
        if text:
            guess = " ".join(predicted.description.split()) if predicted else ""
            descriptions += 1
            description_correct += int(text == guess)
            errors += edit_distance(text, guess)
            characters += len(text)
    return {
        "numeric_fields": numeric_total,
        "numeric_correct": numeric_correct,
        "descriptions": descriptions,
        "descriptions_correct": description_correct,
        "description_character_errors": errors,
        "description_characters": characters,
        "missing_rows": max(0, len(expected.items) - len(actual.items)),
        "extra_rows": max(0, len(actual.items) - len(expected.items)),
    }


def evaluate(repository: Repository, cases: list[PilotCase]) -> dict:
    if not cases or len({case.invoice_id for case in cases}) != len(cases):
        raise ValueError("Provide at least one case and no duplicate invoice IDs")
    details = []
    for case in cases:
        repository.get(case.invoice_id)
        attempts = repository.attempts(case.invoice_id)
        successful = [attempt for attempt in attempts if not attempt["error"]]
        if successful:
            actual = parse_extraction(successful[-1]["raw_text"])
        else:
            actual = InvoiceData()
        metrics = score(case.expected, actual)
        metrics.update(
            invoice_id=case.invoice_id,
            failed_extraction=not bool(successful),
            attempts=len(attempts),
            models=sorted({a["model"] for a in attempts}),
            api_elapsed_seconds=sum(
                json.loads(a["metadata"]).get("elapsed_seconds", 0) for a in attempts
            ),
            usage=[json.loads(a["metadata"]).get("usage", {}) for a in attempts],
        )
        details.append(metrics)
    summed = {
        key: sum(detail[key] for detail in details)
        for key in (
            "numeric_fields",
            "numeric_correct",
            "descriptions",
            "descriptions_correct",
            "description_character_errors",
            "description_characters",
            "missing_rows",
            "extra_rows",
        )
    }
    for name, numerator, denominator in (
        ("numeric_accuracy", "numeric_correct", "numeric_fields"),
        ("description_exact_accuracy", "descriptions_correct", "descriptions"),
        (
            "description_character_error_rate",
            "description_character_errors",
            "description_characters",
        ),
    ):
        summed[name] = summed[numerator] / summed[denominator] if summed[denominator] else None
    paired = [
        case
        for case in cases
        if case.review_seconds is not None and case.manual_seconds is not None
    ]
    costs = [case.api_cost_usd for case in cases if case.api_cost_usd is not None]
    return {
        "invoices": len(cases),
        "metrics": summed,
        "timed_invoices": len(paired),
        "review_seconds": sum(case.review_seconds for case in paired) if paired else None,
        "manual_seconds": sum(case.manual_seconds for case in paired) if paired else None,
        "costed_invoices": len(costs),
        "reported_api_cost_usd": sum(costs) if costs else None,
        "alignment": "source row position; extra/missing row counts are net counts",
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not (args.data_dir / "invoices.sqlite3").is_file():
        parser.error("No existing invoice database found in --data-dir")
    cases = TypeAdapter(list[PilotCase]).validate_json(args.cases.read_text(encoding="utf-8"))
    report = evaluate(Repository(args.data_dir), cases)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
