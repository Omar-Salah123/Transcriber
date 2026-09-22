# فاتورتي — Next.js review interface

This is the Arabic, right-to-left reviewer interface for the invoice workflow.
It is usable as a local interaction prototype; it is not yet a complete
production invoice-processing service.

## Run it

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

If this Windows environment reports a missing `npm-cli.js`, the installed Next.js
binary can be started directly instead:

```powershell
node .\node_modules\next\dist\bin\next dev
```

## What the interface does now

- Adds JPEG and PNG files to a browser-local review queue. They are not sent to
  a model or server by the current UI.
- Displays the source image beside editable header fields and item rows.
- Calculates line and invoice totals separately from the written values, while
  preserving values entered as invoice text.
- Requires acknowledgement when a field is blank or a reviewer note is present.
- Confirms a record once, returns it to review if it is edited, and exports only
  confirmed records.
- Creates a real `.xlsx` workbook in the browser with RTL **الفواتير** and
  **الأصناف** sheets. Model and invoice text are written as literal spreadsheet
  strings rather than formulas.

The example invoice is synthetic. Uploaded files and changes live only for the
current browser session; “حفظ مسودة” is a visible placeholder until the backend
persists drafts.

## Before using real invoices

Keep the Gemini key and the extraction request on a server-side API. That API
should hash and persist images locally, call the model with a strict structured
schema, preserve the raw result independently from reviewed fields, and return
validated data to this UI. It must also enforce duplicate detection,
acknowledgement, confirmation idempotency, and confirmed-only exports; browser
state is not an authoritative record. The agreed architecture and acceptance
tests are in [../docs/implementation-plan.md](../docs/implementation-plan.md).
