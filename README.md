# Transcriber

Arabic handwritten invoice extraction, human review, and cumulative Excel export
for one operator running locally. React (Next.js) talks to Laravel, which owns
SQLite records and private images. Laravel queues extraction requests to a private
Python LangGraph/Gemini service. Nothing is sent to Gemini until extraction is requested.

Implemented: batch image upload, duplicate detection, sequential extraction,
editable RTL review, saved drafts, image zoom/rotation, decimal checks,
acknowledgment, idempotent confirmation, and confirmed-only Excel exports.
Live handwriting accuracy has **not** been evaluated. See [the pilot](docs/pilot.md).

## Install

Requirements: Python 3.12, uv 0.12.17 or newer, Node.js 22+, PHP 8.4 with
PDO SQLite, fileinfo, GD, mbstring, XML, and zip, and Composer. The current Composer
lock contains dependencies requiring PHP 8.4. Keep all servers bound to loopback.

From the repository root (PowerShell):

```powershell
uv python install 3.12
uv sync --locked
Copy-Item ai-service/.env.example ai-service/.env
cd backend
composer install
Copy-Item .env.example .env
php artisan key:generate
New-Item -ItemType File -Path database/database.sqlite -ErrorAction SilentlyContinue
php artisan migrate
cd ../frontend
npm ci
```

Do not overwrite an existing `.env` or database when updating. In
`ai-service/.env`, set `GEMINI_API_KEY` and `GEMINI_MODEL` to a model verified as
available for your project. The previously proposed `gemini-3.8-flash` was never
verified; there is intentionally no fallback model. Credentials stay in Python.

## Run

Open four terminals, starting from the repository root:

```powershell
# 1. Private extraction service
uv run python -m transcriber_id.service
```

```powershell
# 2. Laravel API (upload limits also apply to the child PHP server)
cd backend/public
php -d upload_max_filesize=11M -d post_max_size=12M -S 127.0.0.1:8000 ../vendor/laravel/framework/src/Illuminate/Foundation/resources/server.php
```

```powershell
# 3. Exactly one extraction worker
cd backend
php artisan queue:work --tries=1 --timeout=150 --sleep=1
```

```powershell
# 4. Review interface
cd frontend
npm run dev
```

Open **http://127.0.0.1:3000**. Stop each process with Ctrl+C. For a production
frontend build use `npm run build` then `npm start` instead of `npm run dev`.
Do not expose this single-operator application to a network or the internet.

## Operator workflow

1. Add JPEG/PNG files, at most 10 MiB and 12,000 pixels per dimension. Identical
   file contents return the existing invoice, even if its filename changes.
2. Extract one invoice or all waiting/failed invoices. This sends images to Gemini
   and may incur API charges. Processing is sequential; the interface polls progress.
3. Compare the image with every field and row. Preserve uncertain date text, Arabic
   text, and identifiers such as `000081`. For this shop's thousands shorthand,
   compare the visible marks with separate interpreted price/amount/total fields.
   Interpreted values use ungrouped ASCII digits (for example `70000`); they are
   suggestions and require acknowledgment before confirmation. Add/remove rows
   and record review notes.
4. **Save draft** before confirming. Saved values survive refresh/restart; unsaved
   changes do not. Calculations and warnings refresh after saving.
5. Review and acknowledge every remaining warning, then confirm. Repeated
   confirmation cannot duplicate rows. Editing and saving confirmed data reopens review.
6. Download the two-sheet Excel workbook. Only saved, confirmed invoices appear.

Unknowns remain blank. Written amounts stay separate from calculated amounts.
The source transcription stays separate from any shorthand interpretation;
calculations use a present interpretation only after validating its numeric form.
Arabic/Persian numerals and well-formed thousands separators are supported;
ambiguous numeric strings are flagged rather than guessed. Decimal inputs support
up to four fractional digits. Products requiring more precision or exceeding the
supported range remain uncalculated and require acknowledgment.
Reviewed fields, API responses, and exports display digits as `0-9`, including
digits embedded in Arabic text. Source separators and punctuation remain as written;
the original model output and extraction candidate remain available privately.
On upgrade, `php artisan migrate` normalizes older interpreted values and
recalculates their totals. Affected confirmed invoices return to review and
must be confirmed again before export.

## Storage, backup, and troubleshooting

- SQLite: `backend/database/database.sqlite`; images: `backend/storage/app/private`.
  Back up both while all application processes are stopped. Original model messages
  and extraction attempts are private database records, independent of reviewed values.
- Failed extraction: check Python is running, its key/model configuration, and the
  queue worker. Retry from the interface. No automatic paid retry is performed.
- Waiting indefinitely: start the worker. Requests interrupted after they start
  become retryable after five minutes when the queue is refreshed.
- Conflict while saving: another tab changed the invoice. Select its queue entry
  again to reload; the application will ask before discarding unsaved changes.
- A pending/failed invoice may be transcribed manually and saved without Gemini.
- New versions: stop servers, back up data, install locked dependencies, run
  `php artisan migrate`, rebuild the frontend, and restart all processes. Never use
  `migrate:fresh` on real invoice data.

Keep invoices, model responses, databases, keys, and generated workbooks out of Git.
The source image supplied during development is not a fixture and is not committed.
See [CONTRIBUTING.md](CONTRIBUTING.md) for checks and [the architecture](docs/implementation-plan.md)
for API contracts and remaining acceptance work.
