# Gemma invoice benchmark

Upload `gemma_invoice_benchmark.ipynb` to Google Colab or Kaggle and enable an
NVIDIA GPU. Run setup, set `INPUT_DIR`, `OUTPUT_DIR`, and `MODEL_ID`, then run the
remaining cells. No application checkout is needed in the GPU runtime.
The default E2B model is a small baseline; larger models need more memory.

The notebook snapshots Gemini's extraction schema and instructions, preserving
Arabic, leading-zero identifiers, missing values, ordered items, and separate
thousands-shorthand interpretations. It writes `gemma_results.xlsx` containing:

- `الفواتير` / `الأصناف`: compact Arabic views, marked unreviewed.
- `invoice_fields` / `item_fields`: exact extraction fields as text.
- `run_log`: attempted images, status, elapsed seconds, and checkpoint filename.
- `settings`: model revision, prompt hash, schema, runtime versions, and settings.

Private JSON checkpoints retain raw responses and full errors. Reruns resume
matching images/settings; `RETRY_FAILED` retries failures. Use persistent output
storage across GPU sessions. A manual interruption exports completed records;
an abrupt runtime loss leaves checkpoints that can be resumed. No application
records are created, edited, or confirmed.

Compare by source filename and row order, not database ID. The notebook uses image
hashes as IDs and EXIF orientation/RGB conversion. Use the same image versions for
both models. Reviewed Gemini exports are not raw Gemini predictions; agreement
between models is not accuracy. The compact views omit application calculation
and reviewer fields. Exact-field sheets preserve written/interpreted distinctions.
Excel text is literal and numbers beyond Excel precision stay text.

GPU dependencies are installed by the notebook, separately from the application.
Development dependencies `nbformat` and `openpyxl` validate the notebook offline.
Tests use synthetic responses and do not establish live model accuracy.

Clear notebook outputs before sharing. Keep private images, checkpoints, tokens,
and generated workbooks out of Git; use the ignored `outputs/` folder locally.
