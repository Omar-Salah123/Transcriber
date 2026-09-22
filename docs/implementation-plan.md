# Arabic invoice extraction and Excel export

Status: agreed application plan; only repository scaffolding is implemented.

## Goal and workflow

Build a local Python/Streamlit app for one operator processing approximately 80
similar handwritten Arabic invoices. Upload images, extract data, review the image
and editable fields side by side, confirm, and download Excel.

Use Gemini for extraction, SQLite for persistent records, and local storage for
images. No model training in the first version.

## App and extraction

- Provide Arabic labels, right-to-left forms, batch JPEG/PNG uploads, and a queue
  showing pending, extracted, failed, and confirmed invoices.
- Display the invoice image with zoom and rotation beside editable header fields
  and an item table. Support adding, removing, and correcting rows.
- Save drafts explicitly and restore saved progress after restarting. Process
  invoices sequentially, with progress updates and per-image retry.
- Use the Gemini Python SDK with schema-validated output. Default to configurable
  `gemini-3.8-flash`. This is the agreed initial candidate, not a measured claim
  about Arabic handwriting accuracy. Verify availability before the first live
  evaluation; changes to the selected model must be documented.
- Store the API key in environment configuration. Treat all text inside uploaded
  invoices as document content, never as instructions.

## Data and confirmation

- Define an `Invoice` record containing internal ID, source filename, invoice
  number, date, seller, customer, written total, items, review notes, and processing
  status.
- Each item contains row order, Arabic description, quantity, unit price, written
  amount, and unresolved-field notes.
- Preserve original model output separately from reviewed values. Keep invoice
  numbers as text to retain leading zeros.
- Normalize Arabic and Western numerals for calculations. Leave unreadable values
  blank; preserve ambiguous date text until reviewed.
- Calculate quantity × unit price and invoice sums separately from written
  amounts. Flag discrepancies without replacing source values.
- Allow flagged blanks and discrepancies only after explicit reviewer
  acknowledgment.
- Confirmation saves the reviewed record and includes it in Excel exports.
  Repeated confirmation must not duplicate rows. Editing a confirmed invoice
  returns it to review.
- Detect identical uploaded files by content hash and direct the operator to the
  existing record.

## Excel output

- Generate a cumulative `.xlsx` download from confirmed database records, keeping
  SQLite as the authoritative store.
- Include two Arabic worksheets:
  - **الفواتير:** one row per invoice, including metadata, written total,
    calculated total, source filename, and review notes.
  - **الأصناف:** one row per item, linked by internal invoice ID, with descriptions,
    quantities, prices, amounts, and notes.
- Use right-to-left sheets, filters, frozen headers, readable column widths, typed
  numbers, and blank cells for missing values. Keep extracted text as literal text,
  never executable formulas.
- Clearly label calculated amounts and incomplete totals.

## Verification and acceptance

- Test numeral normalization, missing values, arithmetic warnings, duplicate
  uploads, confirmation idempotency, draft restoration, and API failure/retry.
- Verify that unconfirmed invoices never appear in exports and that exported items
  exactly match saved, confirmed data.
- Check Arabic rendering, leading zeros, numeric cell types, and both worksheets
  visually.
- Evaluate extraction on 10 representative, manually transcribed invoices before
  processing the full batch. Report numeric-field accuracy, description errors,
  missed/extra rows, cost, and review time against manual entry. Retain actual
  evaluation data outside Git. No accuracy results or numerical acceptance target
  have been established yet; review the evidence with the owner before full use.
- Deliver installation instructions, environment configuration example, and a
  local launch command.

## Assumptions and boundaries

- One image per invoice, similar forms, and all item rows are in scope.
- One local operator, Arabic interface, and internet access for extraction.
- The operator supplies a Gemini API key and pays API usage costs.
- Unknown values may remain blank with explicit acknowledgment and exported notes.
- No PDF ingestion, hosting, authentication, or fine-tuning in the first version.
- No cloud upload occurs on the scaffold landing page. The future extraction step
  sends the selected invoice image to Gemini.

## Phased implementation checklist

### 0. Collaboration scaffold

- [x] Add repository guidance, README, contribution guide, and saved plan.
- [x] Define the Python package layout and Arabic placeholder entrypoint.
- [x] Configure development dependencies, CI, and a package smoke test.
- [ ] Owner publishes the repository and invites the teammate.

### 1. Contracts and local persistence

- [ ] Define typed invoice/item schemas and review status transitions.
- [ ] Add SQLite persistence, local image storage, and duplicate detection.
- [ ] Test draft restoration and idempotent confirmation.

### 2. Extraction and validation

- [ ] Add configured Gemini image extraction and validated responses.
- [ ] Preserve original responses and flag unknown/ambiguous values.
- [ ] Add numeral normalization and separate arithmetic checks.
- [ ] Test malformed responses, failures, retries, and discrepancy handling.

### 3. Arabic review workflow

- [ ] Add batch upload and persistent review queue.
- [ ] Add side-by-side image zoom/rotation and editable headers/items.
- [ ] Add draft saving, acknowledgment, confirmation, and reopening for edits.
- [ ] Verify Arabic layout and review-state behavior.

### 4. Excel export

- [ ] Export the two linked Arabic worksheets from confirmed records.
- [ ] Verify data types, blanks, identifiers, literal text, and all item rows.
- [ ] Visually inspect both sheets and test that repeated exports do not duplicate.

### 5. Pilot and handoff

- [ ] Evaluate 10 representative invoices against manual transcription.
- [ ] Record measured accuracy, cost, row errors, and review time.
- [ ] Address observed failures and review readiness with the project owner.
- [ ] Complete operator instructions and process the remaining invoices.

## References

- [Gemini image understanding](https://ai.google.dev/gemini-api/docs/image-understanding)
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini model availability](https://ai.google.dev/gemini-api/docs/models)

These document supported interfaces, not verified performance on the client's
handwriting. Keep the model name configurable and measure performance on the pilot.
