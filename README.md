# Transcriber

A local Arabic invoice review app, intended to turn roughly 80 photographed,
handwritten invoices into a combined Excel workbook.

**Status: working local MVP; live handwriting pilot pending.** Batch upload,
Gemini extraction, editable Arabic review, persistent drafts, explicit confirmation,
and Excel export are implemented. Automated tests use synthetic invoices and mocked
API responses. Real-client accuracy and cost have not yet been measured.

## Workflow

1. Upload a batch of JPEG or PNG invoice images.
2. Extract invoice metadata and all item rows using a Gemini vision model.
3. Review the image beside editable Arabic fields and an item table.
4. Save corrections, inspect the saved revision, acknowledge flagged blanks, and confirm.
5. Download one workbook with invoice and item worksheets for confirmed records.

Arabic handwriting accuracy must be evaluated on representative invoices before
processing the full batch. Human review is a required part of the workflow.

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git, then
run these commands from the repository root:

```powershell
uv python install 3.12
uv sync --locked
uv run streamlit run src/transcriber/app.py --server.address 127.0.0.1
```

Open the local URL printed by Streamlit, normally `http://127.0.0.1:8501`.
Stop the server with Ctrl+C. No manual virtual-environment activation is needed.

For AI extraction, copy `.env.example` to `.env` and set your own Gemini API key:

```powershell
Copy-Item .env.example .env
```

On macOS/Linux use `cp .env.example .env`. Existing environment variables take
precedence over `.env`. Run from the repository root; relative data paths resolve
from the working directory. Never commit your key. Review, manual entry, and export
work without a key. Images are sent to Gemini only when you click an extraction
button; upload alone stores them locally. Each retry makes a new paid API request.

See the [Arabic operator guide](docs/operator-guide.md) for the review process,
retries, backups, and numeric entry rules. See the [pilot guide](docs/pilot.md) to
evaluate representative handwriting before processing all invoices.

## Development

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Python 3.12 and dependencies are managed with `uv` and `uv.lock`. The stack is
Streamlit, Google GenAI SDK, Pydantic, Pillow, python-dotenv, and Python's built-in
SQLite. The portable Excel exporter uses openpyxl; pandas backs the editable table.

```text
.github/                 CI and pull-request template
docs/                    Agreed implementation plan
src/transcriber/
  app.py                 Arabic upload queue and app entrypoint
  config.py              Environment configuration
  evaluation.py          Offline pilot scoring command
  extraction/            Gemini adapter and extraction service
  schemas/               Validated invoice and item models
  storage/               SQLite, original images, and extraction attempts
  validation/            Numeral normalization and arithmetic checks
  export/                Confirmed-invoice Excel generation
  ui/                    Side-by-side review and confirmation
tests/fixtures/          Synthetic test data only
data/                    Ignored local runtime data
```

Start with the [implementation plan](docs/implementation-plan.md), follow
[contributor instructions](AGENTS.md), and use the
[collaboration guide](CONTRIBUTING.md) for branches, checks, and GitHub setup.

## Data handling

The app stores images and review records locally and sends invoice images
to the configured Gemini API for extraction. It is not a fully offline app.
Do not commit client invoices, API keys, model outputs, databases, or exports.
Use synthetic examples for issues, pull requests, and automated tests.

Saved data lives in `TRANSCRIBER_DATA_DIR` (default `data/`): `invoices.sqlite3`
stores review records and immutable API attempts; `images/` stores original bytes
under content hashes. Stop the app before backing up the entire directory.
Downloads are snapshots of confirmed records, not the authoritative data store.

Limits: one local operator, one image per invoice, JPEG/PNG up to 15 MiB and
25 million pixels each, no PDF ingestion or hosted authentication. Monetary inputs
support up to four decimal places and magnitudes below one trillion; arithmetic
warnings use an absolute tolerance of 0.01. Unreadable dates remain source text
until the reviewer supplies an unambiguous ISO date. The app never fabricates a year.
