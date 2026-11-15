# Transcriber

**Transcriber** is a local-first web application for extracting, reviewing, and exporting handwritten Arabic invoices into structured Excel workbooks. It pairs vision-LLM extraction (Google Gemini via LangGraph) with a purpose-built Arabic right-to-left (RTL) human-in-the-loop review workspace, strict decimal validation, and safe `.xlsx` generation.

Nothing is sent to an external AI provider until an operator explicitly requests extraction for an invoice, and invoices can also be transcribed and reviewed entirely by hand.

> **Evaluation Status:** The end-to-end application workflow is verified with automated tests using synthetic fixtures. Live handwriting accuracy depends on your documents and configured model and has **not** yet been formally benchmarked. See the [10-invoice evaluation guide](docs/pilot.md) and the standalone [Gemma invoice benchmark notebook](notebooks/README.md) for Colab/Kaggle comparisons.

---

## Key Features

- **Batch Image Upload & Deduplication:** Upload JPEG and PNG invoice scans (up to 10 MiB and 12,000 pixels per dimension). Identical file contents are automatically deduplicated via SHA-256 even if uploaded under different filenames.
- **On-Demand AI Extraction:** A private Python service validates images, runs a LangGraph extraction workflow against Google Gemini using strict Pydantic contracts, and stores both the structured candidate and the raw model response for auditability.
- **Arabic RTL Review Workspace:** Inspect the original invoice scan (with zoom and rotation controls) side by side with editable header fields and ordered line items. Save intermediate drafts at any time without losing your place in the queue.
- **Strict Numerical & Text Integrity:**
  - **No Invented Values:** Missing or illegible fields remain blank—never guessed or coerced to `0`.
  - **Literal Identifiers:** Invoice numbers (such as `000081`) and raw date strings are preserved as literal text with leading zeros intact.
  - **Source vs. Shorthand vs. Calculated Amounts:** Written source strings, optional thousands-shorthand interpretations (ungrouped ASCII digits such as `70000`), and Brick Math decimal calculations (up to 4 fractional digits) are stored and validated separately.
  - **Numeral Normalization:** Arabic/Persian digits and well-formed thousands separators are normalized to ASCII digits (`0-9`) across reviewed fields, API responses, and exports, while ambiguous numeric strings are flagged for human review.
- **Mandatory Acknowledgment & Idempotent Confirmation:** Arithmetic discrepancies, unresolved fields, and shorthand interpretations generate explicit warnings that must be acknowledged before confirmation. Confirming an invoice is idempotent, and saving edits to a confirmed invoice automatically returns it to review.
- **Confirmed-Only Excel Export:** Generates a two-sheet RTL Excel workbook (`الفواتير` for invoice headers and `الأصناف` for line items) containing only saved, confirmed invoices—complete with frozen headers, auto-filters, typed numeric cells, and formula-injection protection.

---

## Architecture Overview

Transcriber is designed as a single-operator local application where all services bind exclusively to loopback (`127.0.0.1`):

| Component | Stack | Responsibilities |
| --- | --- | --- |
| **Frontend (`frontend/`)** | Next.js 16, React 19, TypeScript, Tailwind CSS | Arabic RTL review queue, side-by-side image viewer, draft editing, warning acknowledgment, and workbook download. |
| **Backend & Worker (`backend/`)** | Laravel 12, PHP 8.4, SQLite, Brick Math, PhpSpreadsheet | Private image storage, SHA-256 deduplication, SQLite persistence, decimal arithmetic, sequential extraction queue worker, and `.xlsx` export. |
| **AI Service (`ai-service/`)** | Python 3.12, LangGraph, Pydantic, `google-genai` | Private loopback extraction service (`127.0.0.1:8100`) that validates images and queries Gemini API or Vertex AI. Holds all AI credentials. |
| **Benchmarks (`notebooks/`)** | Jupyter, PyTorch, Hugging Face, OpenPyXL | Standalone GPU notebook for benchmarking open-weights Gemma models against the same extraction contract on Colab or Kaggle. |

For detailed API routes, state transitions, and data contracts, see [`docs/implementation-plan.md`](docs/implementation-plan.md).

> **Security Note:** This application is built for a single operator running locally on `127.0.0.1` and does not include multi-user authentication. Do not expose the frontend, backend API, or Python extraction service to a shared network or the public internet.

---

## Getting Started

### Option 1: Docker Compose (Recommended)

The easiest way to run the full stack with isolated dependencies and automatic pre-migration backups is via [Docker Compose](docs/docker.md).

1. Configure your AI credentials by copying `docker/ai.env.example` to `docker/ai.env` and setting `GEMINI_API_KEY` and `GEMINI_MODEL` (or leave them blank to use manual transcription only).
2. Start the stack from the repository root:

   **Windows (PowerShell):**
   ```powershell
   Copy-Item docker/ai.env.example docker/ai.env
   ./docker/start.ps1
   ```

   **Linux / macOS:**
   ```sh
   cp docker/ai.env.example docker/ai.env
   sh docker/start.sh
   ```

3. Open **http://127.0.0.1:3000** in your browser.

Re-run the same startup script after pulling updates; it safely stops the worker, backs up existing SQLite and image data before running migrations, and restarts the containers. See [`docs/docker.md`](docs/docker.md) for backup exports, restores, and Vertex AI credential mounting.

---

### Option 2: Native Local Setup

#### Prerequisites

- **Python:** 3.12 with [`uv`](https://docs.astral.sh/uv/) `0.12.17` or newer
- **PHP:** 8.4 with `pdo_sqlite`, `sqlite3`, `fileinfo`, `gd`, `mbstring`, `xml`, and `zip` extensions, plus [Composer](https://getcomposer.org/)
- **Node.js:** 22+ and `npm`

#### Installation

From the repository root (PowerShell):

```powershell
# 1. Python workspace & AI extraction service
uv python install 3.12
uv sync --locked
Copy-Item ai-service/.env.example ai-service/.env

# 2. Laravel backend & SQLite database
cd backend
composer install
Copy-Item .env.example .env
php artisan key:generate
New-Item -ItemType File -Path database/database.sqlite -ErrorAction SilentlyContinue
php artisan migrate

# 3. Next.js frontend
cd ../frontend
npm ci
```

Configure `ai-service/.env` with your `GEMINI_API_KEY` and set `GEMINI_MODEL` to a model verified as available for your Google AI or Vertex AI project (there is intentionally no fallback model). Keep all provider credentials inside `ai-service/.env`. When updating an existing installation, do not overwrite your `.env` files or `database.sqlite`.

#### Running Locally

Start the four services in separate terminals from the repository root:

```powershell
# Terminal 1: Private Python extraction service (127.0.0.1:8100)
uv run python -m transcriber_id.service
```

```powershell
# Terminal 2: Laravel API (127.0.0.1:8000, with 10 MiB image upload limits)
cd backend/public
php -d upload_max_filesize=11M -d post_max_size=12M -S 127.0.0.1:8000 ../vendor/laravel/framework/src/Illuminate/Foundation/resources/server.php
```

```powershell
# Terminal 3: Single sequential extraction queue worker
cd backend
php artisan queue:work --tries=0 --timeout=150 --sleep=1
```

```powershell
# Terminal 4: Next.js review interface (127.0.0.1:3000)
cd frontend
npm run dev
```

Open **http://127.0.0.1:3000**. Stop each process with `Ctrl+C`. For a local production frontend build, run `npm run build` followed by `npm start` instead of `npm run dev`.

---

## Operator Workflow

1. **Upload Invoices:** Add one or more JPEG/PNG files (max 10 MiB and 12,000 px per side). Duplicate uploads automatically return the existing invoice record.
2. **Run Extraction (or Transcribe Manually):** Trigger extraction for a single invoice or all waiting/failed invoices in the queue. Requests are processed sequentially by the worker while the UI polls progress. You can also transcribe any pending or failed invoice manually without calling Gemini.
3. **Review & Edit:** Compare the invoice scan against every header field and line item:
   - Preserve uncertain dates, Arabic descriptions, and leading-zero identifiers (`000081`).
   - For unit prices and line-item amounts using thousands shorthand, the table displays the interpreted value when available; compare it carefully against the image.
   - Invoice totals maintain separate **written** and **interpreted** fields. Interpreted values use ungrouped ASCII digits (e.g., `70000`) and always require reviewer acknowledgment.
   - Add, reorder, or remove line items and record per-row or invoice-level review notes.
4. **Save Draft:** Click **Save draft** before confirming. Saving persists your changes to SQLite, increments the record version, and recalculates line products, invoice totals, and validation warnings. Unsaved browser edits do not survive a page refresh.
5. **Acknowledge & Confirm:** Review every remaining warning (discrepancies, unresolved fields, shorthand interpretations, or uncalculated high-precision values), check the acknowledgment box, and confirm the invoice. Repeated confirmation is a safe no-op; editing and saving a confirmed invoice reopens review.
6. **Export to Excel:** Download the two-sheet `.xlsx` workbook containing all saved, confirmed invoices:
   - **`الفواتير` (Invoices):** Includes one total column (`تفسير الإجمالي المكتوب`) using the reviewed interpreted total when present, or the written total otherwise.
   - **`الأصناف` (Items):** Includes one unit price column and one amount column, using interpreted values when available and written values otherwise.
   - Calculated amounts and review warnings remain inside the application for verification and are omitted from the exported spreadsheet. Valid numbers are written as numeric Excel cells; non-numeric or literal strings remain safe text cells.

---

## Storage, Upgrades & Troubleshooting

- **Local Data & Backups:**
  - Native SQLite database: `backend/database/database.sqlite`
  - Private uploaded images: `backend/storage/app/private`
  - Stop all application processes before backing up both paths together. Raw model outputs and extraction attempts are stored privately in SQLite and are never sent to the browser or written to logs.
- **Upgrading:** Stop all servers, back up your database and private images, install locked dependencies (`uv sync --locked`, `composer install`, `npm ci`), run `php artisan migrate`, rebuild the frontend if needed, and restart all processes. Never run `migrate:fresh` on real invoice data. On upgrade, migrations normalize legacy interpreted digits and recalculate totals; any affected confirmed invoices return to review for re-confirmation.
- **Transient Provider Errors & Retries:** If extraction fails, select the invoice to see whether the image, provider request, model output, service connection, or timeout caused the failure. Transient failures (HTTP `429`, `408`, `500`/`502`/`503`/`504`, provider timeouts, and service connection errors) are retried automatically up to three times with backoff delays of roughly 1, 2, and 4 minutes, pausing other queued Gemini requests during the cooldown. Provider error details are recorded privately in `extraction_attempts.provider_error`. Permanent failures (invalid model output, image errors, or credential/configuration issues) are not retried automatically.
- **Database Busy When Scheduling:** If SQLite is busy during batch scheduling, the affected invoice is not sent to Python. Wait for the active write to complete and click the queue button again. Always run exactly one queue worker and avoid running migrations during extraction.
- **Stuck Jobs & Tab Conflicts:** Ensure the queue worker process is running. Jobs interrupted after starting automatically become retryable after 5 minutes when the queue refreshes. If another browser tab updates the same invoice (`409 Conflict`), re-select the invoice in the queue to reload the latest saved version.

---

## Documentation

- [**Docker Guide (`docs/docker.md`)**](docs/docker.md) — Containerized setup, safe upgrades, volume backups, restores, and Vertex AI credentials.
- [**Architecture & Implementation Plan (`docs/implementation-plan.md`)**](docs/implementation-plan.md) — System boundaries, API endpoints, state machine, and validation rules.
- [**Handwriting Pilot Guide (`docs/pilot.md`)**](docs/pilot.md) — Protocol for evaluating live handwriting extraction accuracy, review time, and API cost on a 10-invoice sample.
- [**Gemma Benchmark Notebook (`notebooks/README.md`)**](notebooks/README.md) — Standalone Google Colab / Kaggle GPU notebook for benchmarking Gemma models against the invoice schema.
- [**Contributing Guide (`CONTRIBUTING.md`)**](CONTRIBUTING.md) — Development setup, code style, linter commands, and test suites.

---

## Contributing & Verification

Contributions are welcome! Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`AGENTS.md`](AGENTS.md) before submitting changes. Keep client invoice images, raw model responses, SQLite databases, API keys, and generated Excel workbooks out of Git—all automated tests use synthetic fixtures and mocked provider calls.

Quick check commands from the repository root:

```powershell
# Python lint, format, and unit tests
uv run ruff check .
uv run ruff format --check .
uv run pytest

# Laravel code style and feature tests
cd backend
php vendor/bin/pint --test
php artisan test

# Frontend lint, typecheck, format, build, and Playwright tests
cd ../frontend
npm run lint
npm run typecheck
npm run format:check
npm run build
npm test
```

---

## License

This project is open-source software licensed under the [MIT License](LICENSE).
