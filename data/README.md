# Local runtime data

This directory is reserved for uploaded images, SQLite records, extraction output,
and optional generated workbooks. The app creates `invoices.sqlite3` and `images/`
here by default. The database stores reviewed values and raw extraction attempts.

Everything under this directory except this README is ignored by Git. Keep client
files here, not in source or test folders.
Use your organization's approved backup process for local client data; Git does
not back it up. Stop the app before copying the entire directory for a consistent
backup. Avoid deleting this directory when cleaning development artifacts.
