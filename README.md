# Transcriber

A local Arabic invoice review app, intended to turn roughly 80 photographed,
handwritten invoices into a combined Excel workbook.

**Status: front-end review prototype plus backend scaffolding.** The Next.js
frontend now provides an Arabic right-to-left review workspace: local image
selection, an editable invoice and item table, an acknowledgement gate,
confirmation state, and a confirmed-only `.xlsx` download. It deliberately
does not call an AI provider or persist client data yet. The Laravel and Python
services are still scaffolds for the planned secure extraction and persistence
work.

## Intended workflow

1. Upload a batch of JPEG or PNG invoice images.
2. Extract invoice metadata and all item rows using a Gemini vision model.
3. Review the image beside editable Arabic fields and an item table.
4. Correct values or acknowledge flagged blanks, then confirm each invoice.
5. Download one workbook with invoice and item worksheets for confirmed records.

Arabic handwriting accuracy must be evaluated on representative invoices before
processing the full batch. Human review is a required part of the workflow.

## Quick start

### Next.js review interface

```powershell
cd frontend
npm run dev
```

Open `http://localhost:3000`. See [frontend/README.md](frontend/README.md)
for what is usable now and the required server-side work before processing real
client invoices.

### Original Python scaffold

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git, then
run these commands from the repository root:

```powershell
uv python install 3.12
uv sync --locked
uv run streamlit run src/transcriber/app.py --server.address 127.0.0.1
```

Open the local URL printed by Streamlit, normally `http://127.0.0.1:8501`.
Stop the server with Ctrl+C. No manual virtual-environment activation is needed.

`.env.example` documents configuration reserved for the implementation phase.
When configuration is implemented, copy it to `.env` (`Copy-Item .env.example
.env` in PowerShell, or `cp .env.example .env` on macOS/Linux) and set your own key.
The placeholder does not load or use these settings.

## Development

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Python 3.12 and dependencies are managed with `uv` and `uv.lock`. The stack is
Streamlit, Google GenAI SDK, Pydantic, Pillow, python-dotenv, and Python's built-in
SQLite. Excel generation will be added with the export feature.

```text
.github/                 CI and pull-request template
docs/                    Agreed implementation plan
src/transcriber/
  app.py                 Runnable Arabic placeholder
  extraction/            Future Gemini integration
  schemas/               Future validated invoice and item models
  storage/               Future SQLite and image persistence
  validation/            Future numeral normalization and arithmetic checks
  export/                Future Excel generation
  ui/                    Future review interface
tests/fixtures/          Synthetic test data only
data/                    Ignored local runtime data
```

Start with the [implementation plan](docs/implementation-plan.md), follow
[contributor instructions](AGENTS.md), and use the
[collaboration guide](CONTRIBUTING.md) for branches, checks, and GitHub setup.

## Data handling

The planned app stores images and review records locally and sends invoice images
to the configured Gemini API for extraction. It is not a fully offline app.
Do not commit client invoices, API keys, model outputs, databases, or exports.
Use synthetic examples for issues, pull requests, and automated tests.
