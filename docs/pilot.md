# Ten-invoice pilot

The application workflow is tested with synthetic inputs. No real-invoice accuracy,
Gemini availability for the configured account, or actual API cost is established yet.

1. Choose 10 invoices spanning clear/poor photos, handwriting styles, blanks, and
   dense tables. Keep the images and annotations under the ignored data directory.
2. Have an Arabic reader transcribe the source independently **before** reviewing
   model predictions. Preserve row order and mark unreadable values as null.
3. Run extraction in the app. Review and correct it while measuring review time.
   Separately measure manual transcription time. Record actual API charges for all
   attempts, including retries, from the provider's usage records.
4. Create `data/pilot.json`, a list of cases with the shape below. Get each internal
   `invoice_id` from the confirmed workbook's first column. Do not use the seller's
   invoice number as the internal ID.
5. Run the offline scorer and inspect per-invoice results:

```powershell
uv run python -m transcriber.evaluation data/pilot.json --data-dir data --output data/pilot-report.json
```

Synthetic annotation shape (replace with independently transcribed values):

```json
[
  {
    "invoice_id": "internal-id-from-the-app",
    "expected": {
      "invoice_number": "000081",
      "date_text": "2026-09-22",
      "verified_date": "2026-09-22",
      "seller": "متجر تجريبي",
      "customer": "عميل تجريبي",
      "written_total": "30.50",
      "items": [
        {
          "description": "أنبوب مياه",
          "quantity": "2",
          "unit_price": "15.25",
          "written_amount": "30.50",
          "notes": ""
        }
      ],
      "notes": ""
    },
    "review_seconds": 45,
    "manual_seconds": 120,
    "api_cost_usd": null
  }
]
```

The scorer compares the latest successful **original extraction** with ground truth,
never the corrected draft. Failed extraction counts as missing predictions. It reports
exact numeric accuracy for known quantities/prices/amounts/totals, description exact
matches, character error rate, and net missing/extra row counts. Whitespace is collapsed
for description comparison; Arabic letters are not otherwise normalized.

Rows are compared by source position. A missing row can misalign subsequent rows;
manually inspect those cases. Net row counts cannot detect an equal number of inserted
and omitted rows. Header/date correctness and false claims in ground-truth-unknown fields
must also be checked manually. These limitations prevent treating one aggregate score
as a complete assessment of extraction quality.

The report includes stored model names, token usage and elapsed API time. Costs are
operator-supplied, not guessed from tokens or potentially stale pricing. Missing timing
and cost observations stay unavailable and coverage counts are reported.

Discuss observed errors, review time versus manual entry, and usage cost with the owner
before processing the full batch. There is no agreed numerical accuracy acceptance
threshold yet. Record that decision and any model/prompt adjustments with the results.
