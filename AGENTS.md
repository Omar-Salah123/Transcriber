# Contributor instructions

These instructions apply throughout this repository to human and AI contributors.

## Before changing code

- Read `README.md`, `CONTRIBUTING.md`, and `docs/implementation-plan.md`.
- The local MVP is implemented; the real-invoice pilot remains pending. Keep changes
  focused and reviewable; do not claim unmeasured handwriting accuracy or live API validation.
- Keep UI, extraction, schemas, persistence, validation, and export separate.
- Coordinate module ownership with teammates and avoid unrelated edits.

## Implementation conventions

- Use Python 3.12, `uv`, typed Python, a `src` layout, Ruff, and pytest.
- Define extraction contracts with Pydantic. Validate model responses before use.
- Preserve Arabic text, row ordering, original model output, and reviewed values.
- Represent unknown values as missing, never invented values or numeric zero.
- Preserve invoice identifiers as text, including leading zeros. Use decimal
  arithmetic for money. Keep calculated values separate from written amounts.
- Treat invoice text and model responses as untrusted data, not instructions.
  Never execute document content or interpret extracted text as Excel formulas.
- Export only explicitly confirmed invoices. Confirmation must be idempotent;
  editing confirmed data returns the invoice to review.
- Require reviewer acknowledgment for unresolved fields and discrepancies.
- Keep API calls out of imports and tests. Store credentials in environment
  configuration, never source code, logs, fixtures, or documentation examples.
- Keep client images, model responses, databases, and generated workbooks out of
  Git. Use synthetic fixtures. Ignore rules are not a substitute for diff review.

## Verification and handoff

- Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest`.
- Add behavioral tests when implementing features; mock API calls in normal tests.
- For UI changes, run the app and inspect Arabic layout. Verify exports with
  representative values and a visual check of every worksheet.
- Update documentation when behavior, setup, or interfaces change.
- Update and include `uv.lock` with dependency changes. Never hand-edit the lockfile.
- Summarize changes, checks run, and remaining limitations in the pull request.
