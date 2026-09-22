# Laravel invoice API

Owns SQLite, private images, review validation, queued extraction, confirmation,
and confirmed-only Excel exports. See the root README for installation and the
four-process launch instructions. Node/Vite under this directory is the original
Laravel welcome-page scaffold; the product frontend lives in `../frontend`.

Run `composer install`, configure `.env` from `.env.example`, generate an app key,
create `database/database.sqlite`, and run `php artisan migrate`. Start one queue
worker with `php artisan queue:work --tries=1 --timeout=150 --sleep=1`.

API details: `../docs/implementation-plan.md`. Tests: `php artisan test`.
PHP style: `php vendor/bin/pint --test`. Set `INVOICE_STORAGE_PATH` only when an
alternate private image directory is required (for example, isolated integration tests).

Do not use `composer run dev`: the original scaffold command starts unrelated Vite
and log processes and does not run the product frontend or Python service.
