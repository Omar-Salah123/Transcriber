# فاتورتي — Arabic review interface

Next.js/React frontend for the local Laravel invoice API. Run `npm ci` and
`npm run dev`, then open `http://127.0.0.1:3000`. `/api/*` proxies to Laravel at
`127.0.0.1:8000`. Python and Gemini are never called directly from the browser.

Uploads are persisted by Laravel. Extraction is explicit. Saved drafts survive
restarts. Confirmation and Excel generation are enforced on the server.
Unsaved edits are marked, protected from polling, and prevent confirmation/export
until saved. Dates remain written text. Zoom/rotation affect the preview only.

Checks: `npm run lint`, `npm run typecheck`, `npm run format:check`,
`npm run build`, `npm test`. Browser tests use mocked APIs unless `LIVE_API=1`.
See `../CONTRIBUTING.md` for isolated integration tests.
