from decimal import Decimal

import pytest

from transcriber.schemas.invoice import InvoiceData, Item
from transcriber.validation.checks import analyze
from transcriber.validation.numbers import parse_number


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("١٬٢٣٤٫٥٠", "1234.50"),
        ("۱۲.۵", "12.5"),
        ("1,234.50", "1234.50"),
        ("0", "0"),
        ("-٢", "-2"),
        ("", None),
        (None, None),
    ],
)
def test_number_normalization(source, expected):
    assert parse_number(source) == (None if expected is None else Decimal(expected))


@pytest.mark.parametrize("value", ["١٢؟", "1,2", "NaN", "Infinity", "1e8", True, "1.00001"])
def test_ambiguous_values_are_rejected(value):
    with pytest.raises(ValueError):
        parse_number(value)


def test_complete_data_has_no_warnings(complete_data):
    result = analyze(complete_data)
    assert result.calculated_total == Decimal("30.50")
    assert not result.warnings


def test_missing_factors_are_not_zero():
    result = analyze(InvoiceData(items=[Item(quantity="0", unit_price=None)]))
    assert result.calculated_total is None
    assert result.written_sum is None
    assert result.calculated_amounts == [None]
    assert result.warnings


def test_zero_and_discrepancy_do_not_overwrite_source(complete_data):
    complete_data.items[0].quantity = Decimal(0)
    result = analyze(complete_data)
    assert result.calculated_total == 0
    assert complete_data.items[0].written_amount == Decimal("30.5")
    assert any("لا يساوي" in warning for warning in result.warnings)


def test_decimal_round_trip(complete_data):
    restored = InvoiceData.model_validate_json(complete_data.model_dump_json())
    assert restored == complete_data
    assert restored.invoice_number == "000081"
