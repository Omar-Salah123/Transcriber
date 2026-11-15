# Contributing

Read `AGENTS.md`, `README.md`, and `docs/implementation-plan.md` first.
The application is local and single-operator. Agree on module ownership before
editing shared contracts. Keep Python extraction, Laravel application rules,
React UI, and workbook generation separate.

## Dependencies and checks

Docker runtime setup and update/backup instructions are in [docs/docker.md](docs/docker.md).
For changes affecting images, startup, storage, or networking, run
`docker compose config --quiet` and `python docker/smoke.py` with port 3000 free.
The smoke test uses disposable synthetic data and never calls Gemini.

Use Python 3.12 and `uv`. The root is a non-package workspace; `ai-service` owns
the installable `transcriber_id` module. Add runtime dependencies with
`uv add --package ai-service PACKAGE`; regenerate `uv.lock`, never hand-edit it.
Use Composer for backend dependencies and npm for frontend dependencies; include
their generated lockfiles.

From the repository root:

```powershell
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
cd backend
composer install
php vendor/bin/pint --test
php artisan test
cd ../frontend
npm ci
npm run lint
npm run typecheck
npm run format:check
npm run build
npx playwright install chromium
npm test
cd ..
git diff --check
git status --short
git diff
```

PHP feature tests use in-memory SQLite, fake storage, and fake HTTP calls. Tests
generate their own ephemeral encryption key and never read a developer's secrets.
Browser tests mock the API by default. Set `PLAYWRIGHT_CHANNEL=chrome` to use an
installed Chrome instead of Playwright's Chromium.

For the optional full integration test, use an isolated SQLite database and image
directory, the fixture `uv run python ai-service/tests/fake_service.py` on port
8101, Laravel with `AI_SERVICE_URL=http://127.0.0.1:8101`, and one database queue
worker using the same environment. Set `LIVE_API=1` and run
`npm test -- tests/integration.spec.ts`. Never run this fixture test against a
client database or a real AI service. CI performs this isolated run automatically.

Use `uv run ruff format .`, `php vendor/bin/pint` in backend, and
`npx prettier --write app/page.tsx lib/invoice.ts next.config.ts playwright.config.ts tests`
in frontend for intentional changes. Normal tests must not make provider calls.

Inspect the Arabic interface at desktop and narrow widths. Verify both exported
worksheets visually and by their cell types. Add behavioral tests for changes to
confirmation, row order, ambiguity, decimal arithmetic, and extraction failures.

Use focused branches prefixed `codex/` for agent work. Review the diff for private
data even if ignore rules are present. Summarize changes, checks, and remaining
limitations in the pull request. This project is licensed under the [MIT License](LICENSE).
