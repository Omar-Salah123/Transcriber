# Ten-invoice handwriting pilot

Not yet run. Synthetic tests verify application behavior, not transcription accuracy.
One supplied example image is insufficient for a representative ten-invoice evaluation.

1. Choose 10 authorized images covering clear/faint handwriting, slanted photographs,
   blank metadata, uncertain dates, many rows, and arithmetic discrepancies.
2. Transcribe each independently, preserving identifiers, row order, source text,
   blanks, written values, and unresolved fields. Keep images and truth outside Git.
3. Verify model availability for the actual Gemini project and set `GEMINI_MODEL`.
   Record exact model, prompt revision (Git commit), request date, and settings.
4. Extract each invoice once and retain raw outputs. Record wall time, provider usage
   and actual price/cost, manual-entry time, and review/correction time. Do not infer
   cost from unverified pricing or use synthetic timings as measured results.
5. Compare source-number fields after documented numeral normalization, identifiers
   exactly (including leading zeros), descriptions against the human transcription,
   shorthand interpretations separately from visible source marks, and row
   sequences for missing/extra/misaligned rows. Record false shorthand expansions
   as well as missed expansions. Report numerators and
   denominators, including missing/incorrect fields, rather than one overall score.
6. Summarize total API cost and review time versus manual entry, with examples of
   failure classes. The owner decides whether the observed results justify processing
   the remaining invoices. No numerical accuracy threshold has been agreed.

Suggested report columns: invoice ID, truth row count, extracted row count, matched
numeric fields/total numeric fields, description errors, missed rows, extra rows,
extraction seconds, review seconds, manual seconds, cost, and unresolved issues.
Do not put real invoice content into issues, fixtures, screenshots, or Git commits.
