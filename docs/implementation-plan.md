# Arabic invoice application architecture

The Streamlit plan has been replaced by Next.js/React → Laravel/SQLite → private
Python LangGraph/Gemini. The local workflow is implemented; live provider
availability and the 10-invoice accuracy pilot remain operator acceptance work.

## Ownership and data

- React renders the Arabic RTL review queue and sends explicit saves. Browser state
  is an unsaved draft, never the authority for confirmation or export.
- Laravel owns private JPEG/PNG files, SHA-256 deduplication, SQLite invoice/item
  records, ordered rows, review validation, queue status, and PhpSpreadsheet export.
- Python validates images, invokes Gemini with a Pydantic contract, and returns
  candidates plus raw messages. Document/model text is data, never instructions.
- Numeric-looking source values remain nullable text. Calculations use Brick Math
  decimals, stored as text to avoid SQLite floating-point coercion. No source amount
  is overwritten. Separate optional interpreted values represent a reviewed
  thousands-shorthand reading for unit prices, line amounts, and invoice totals.
  Their presence creates an acknowledgment warning. Invalid/missing values or
  unsupported precision produce warnings.
- `original_extraction` and `raw_model_output` are independent of edits;
  `extraction_attempts` retains successful/failed responses. Private outputs are
  omitted from browser resources. New provider failures retain the SDK status,
  message, and response details in `extraction_attempts.provider_error`. No provider
  response is written to application logs.

## Interfaces

Frontend requests use `/api` proxied to loopback Laravel on port 8000. Mutations
include `X-Invoice-Client: local-review`; only loopback requests and configured
local frontend origins are accepted. This is not an authenticated multi-user API.

| Method/path | Behavior |
| --- | --- |
| `POST /api/invoices` | Multipart `image`; returns `{invoice, duplicate}` (201 new, 200 duplicate) |
| `GET /api/invoices` | Saved queue including ordered items, warnings, image URLs, and versions |
| `GET /api/invoices/{id}` | Current reviewed record |
| `GET /api/invoices/{id}/image` | Original private image, no-store response |
| `PUT /api/invoices/{id}` | Complete reviewed header/items, unresolved fields, notes, and version |
| `POST /api/invoices/{id}/extract` | Queue pending/failed invoice; 202 accepted, 409 incompatible state |
| `POST /api/invoices/{id}/confirm` | `{version, acknowledged}`; server validates current saved record |
| `GET /api/exports/invoices` | Download confirmed database records as `.xlsx`; 422 if none |

Invoice header fields: `invoice_number`, `date_text`, `seller`, `customer`,
`written_total_text`, optional `written_total_interpreted_text`, `review_notes`,
`unresolved_fields`. Items contain `description`, `quantity_text`,
`unit_price_text`, optional `unit_price_interpreted_text`, `written_amount_text`,
optional `written_amount_interpreted_text`, `unresolved_fields`, `review_note`;
array order becomes `row_order` starting at 1. Interpretation fields use
ungrouped ASCII digits for the shop's clear thousands shorthand only. Changing
the written total in a save without supplying a new interpretation clears its
previous interpretation.
The server supplies IDs, status, calculations, version, and warnings `{field,message}`.
Only whitelisted validated fields are accepted for edits. A stale version returns 409.

Laravel calls `POST http://127.0.0.1:8100/v1/extractions` with
`X-Invoice-Service: laravel` and JSON `{image_base64, media_type, source_filename}`.
Python returns `{extraction, raw_model_output, warnings}` or a safe error including
available raw output. It rejects browser Origin headers. Credentials stay in Python.

## State transitions and failure handling

- Upload → `pending`; extraction request → `processing`; successful validated result
  → `review`; failed request → `failed`; explicit retry → `processing`.
- A single database worker processes jobs sequentially. Jobs dispatch after commit.
  HTTP timeout is 120 seconds, worker timeout 150 seconds, queue retry-after 180 seconds.
  Python provider timeout is 100 seconds with automatic retries disabled.
- SQLite waits up to 10 seconds for a competing writer and starts application
  transactions in immediate mode, so a batch scheduling request does not upgrade
  a stale read transaction into a write. Transient scheduling locks are retried;
  a persistent lock returns a safe error without queueing that invoice.
- Each extraction has a token and atomic start claim. Duplicate delivery is a no-op;
  stale results cannot replace reviews. After five minutes, started but interrupted
  work becomes failed when listing invoices. Queued work has no start time yet.
- Manual save from pending/failed/review/confirmed → `review`; save increments the
  version and clears acknowledgment. Saving while processing is rejected.
- Confirmation requires saved review plus acknowledgment of all warnings. Repeated
  confirmation is a no-op. Editing and saving a confirmed record excludes it from export.
- No destructive retry exists for human-reviewed invoices. Re-transcribe manually
  if necessary, preserving the initial machine result separately.

## Export and acceptance

Two Arabic worksheets: **الفواتير** and **الأصناف**, linked by internal invoice ID.
Both use RTL, filters, frozen headers, typed amounts, literal identifiers/text,
blank missing values, review notes, separately labeled shorthand interpretations,
and separately labeled derived totals.
Export reads a database snapshot of confirmed invoices and items.

Automated checks cover image validation, deduplication, decimal parsing, blanks,
row ordering, discrepancies, drafts, stale edits, acknowledgment, confirmation,
extraction failure/retry, literal spreadsheet text, and frontend review behavior.
Synthetic fixtures only. See `docs/pilot.md` for the outstanding real-image pilot.

Not in v1: authentication, hosting, PDF ingestion, fine-tuning, multiple operators,
or a claim of measured handwriting accuracy. Keep SQLite and original images together
in backups. Existing migrations are extended, not replaced or reset.
