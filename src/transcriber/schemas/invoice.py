"""Validated review records. JSON serialization preserves decimal precision."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from transcriber.validation.numbers import parse_number

Number = Annotated[Decimal | None, BeforeValidator(parse_number)]


class Status(StrEnum):
    PENDING = "pending"
    EXTRACTED = "extracted"
    FAILED = "failed"
    CONFIRMED = "confirmed"


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str = Field(default="", max_length=4000)
    quantity: Number = None
    unit_price: Number = None
    written_amount: Number = None
    notes: str = Field(default="", max_length=4000)


class InvoiceData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    invoice_number: str = Field(default="", max_length=500)
    date_text: str = Field(default="", max_length=500)
    verified_date: date | None = None
    seller: str = Field(default="", max_length=4000)
    customer: str = Field(default="", max_length=4000)
    written_total: Number = None
    items: list[Item] = Field(default_factory=list, max_length=500)
    notes: str = Field(default="", max_length=8000)

    @field_validator("verified_date", mode="before")
    @classmethod
    def blank_date(cls, value: object) -> object:
        return None if value == "" else value


class Invoice(BaseModel):
    id: str
    digest: str
    filename: str
    mime_type: str
    status: Status
    revision: int
    data: InvoiceData
    error: str = ""
    acknowledged: bool = False
    created_at: str
    confirmed_at: str | None = None
