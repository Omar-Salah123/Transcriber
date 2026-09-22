"""Validated, literal-text contracts for Gemini invoice extraction."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExtractedInvoiceItem(BaseModel):
    """One item exactly as it appears on a source invoice.

    Numeric-looking values deliberately remain text. The review layer decides
    whether a value is trustworthy and calculates derived amounts separately.
    """

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, description="Arabic item description as written")
    quantity_text: str | None = Field(default=None, description="Quantity exactly as written")
    unit_price_text: str | None = Field(default=None, description="Unit price exactly as written")
    unit_price_interpreted_text: str | None = Field(
        default=None,
        description=(
            "Ungrouped ASCII digits for a clear thousands-shorthand unit price; otherwise null"
        ),
    )
    written_amount_text: str | None = Field(
        default=None, description="Line amount exactly as written"
    )
    written_amount_interpreted_text: str | None = Field(
        default=None,
        description=(
            "Ungrouped ASCII digits for a clear thousands-shorthand line amount; otherwise null"
        ),
    )
    unresolved_fields: list[str] = Field(default_factory=list)


class ExtractedInvoice(BaseModel):
    """The only model-shaped payload accepted from the extraction agent."""

    model_config = ConfigDict(extra="forbid")

    invoice_number: str | None = Field(
        default=None, description="Invoice number, preserving leading zeros"
    )
    date_text: str | None = Field(default=None, description="Date exactly as written; do not guess")
    seller: str | None = Field(default=None, description="Seller name")
    customer: str | None = Field(default=None, description="Customer name")
    written_total_text: str | None = Field(
        default=None, description="Invoice total exactly as written"
    )
    written_total_interpreted_text: str | None = Field(
        default=None,
        description=(
            "Ungrouped ASCII digits for a clear thousands-shorthand invoice total; otherwise null"
        ),
    )
    items: list[ExtractedInvoiceItem] = Field(default_factory=list)
    unresolved_fields: list[str] = Field(default_factory=list)


class ExtractionResponse(BaseModel):
    """Response returned only from the local AI service to Laravel."""

    model_config = ConfigDict(extra="forbid")

    extraction: ExtractedInvoice
    raw_model_output: str
    warnings: list[str] = Field(default_factory=list)
