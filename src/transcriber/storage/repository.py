"""Transactional local records with optimistic revisions and immutable API attempts."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from transcriber.schemas.invoice import Invoice, InvoiceData, Status
from transcriber.storage.images import validate_image
from transcriber.validation.checks import analyze


class ConflictError(ValueError):
    """A newer review exists; reload rather than overwriting it."""


def now() -> str:
    return datetime.now(UTC).isoformat()


class Repository:
    def __init__(self, directory: Path):
        self.directory = directory
        self.images = directory / "images"
        self.images.mkdir(parents=True, exist_ok=True)
        self.database = directory / "invoices.sqlite3"
        with self.connection() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise ValueError("قاعدة البيانات تخص إصداراً أحدث من التطبيق")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id TEXT PRIMARY KEY, digest TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL, mime_type TEXT NOT NULL,
                    status TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
                    data TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, confirmed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY, invoice_id TEXT NOT NULL REFERENCES invoices(id),
                    model TEXT NOT NULL, raw_text TEXT NOT NULL, metadata TEXT NOT NULL,
                    error TEXT NOT NULL, created_at TEXT NOT NULL
                );
                PRAGMA user_version = 1;
            """)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _record(row: sqlite3.Row) -> Invoice:
        values = dict(row)
        values["data"] = InvoiceData.model_validate_json(values["data"])
        return Invoice.model_validate(values)

    def get(self, invoice_id: str) -> Invoice:
        with self.connection() as db:
            row = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if row is None:
            raise ValueError("الفاتورة غير موجودة")
        return self._record(row)

    def list(self, *, confirmed_only: bool = False) -> list[Invoice]:
        sql = "SELECT * FROM invoices"
        if confirmed_only:
            sql += " WHERE status = 'confirmed'"
        with self.connection() as db:
            return [self._record(row) for row in db.execute(sql + " ORDER BY created_at, id")]

    def add_image(self, filename: str, content: bytes) -> tuple[Invoice, bool]:
        mime = validate_image(content)
        digest = hashlib.sha256(content).hexdigest()
        # Original image bytes are stored under an internal digest, never a user path.
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM invoices WHERE digest = ?", (digest,)).fetchone()
            if existing:
                return self._record(existing), False
            target = self.images / digest
            temporary = self.images / f"{digest}.{uuid4().hex}.tmp"
            try:
                temporary.write_bytes(content)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            invoice_id = uuid4().hex
            safe_name = filename.replace("\\", "/").split("/")[-1][:240] or "invoice"
            db.execute(
                "INSERT INTO invoices (id,digest,filename,mime_type,status,data,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    invoice_id,
                    digest,
                    safe_name,
                    mime,
                    Status.PENDING,
                    InvoiceData().model_dump_json(),
                    now(),
                ),
            )
        return self.get(invoice_id), True

    def image_bytes(self, invoice: Invoice) -> bytes:
        return (self.images / invoice.digest).read_bytes()

    def save_draft(self, invoice_id: str, data: InvoiceData, revision: int) -> Invoice:
        data = InvoiceData.model_validate(data.model_dump())
        with self.connection() as db:
            result = db.execute(
                "UPDATE invoices SET data=?,status='extracted',revision=revision+1,"
                "acknowledged=0,confirmed_at=NULL,error='' WHERE id=? AND revision=?",
                (data.model_dump_json(), invoice_id, revision),
            )
            if result.rowcount != 1:
                raise ConflictError("تم تعديل الفاتورة في نافذة أخرى؛ أعد تحميلها")
        return self.get(invoice_id)

    def confirm(self, invoice_id: str, revision: int, *, acknowledge: bool = False) -> Invoice:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            if row is None:
                raise ValueError("الفاتورة غير موجودة")
            record = self._record(row)
            if record.status == Status.CONFIRMED and revision in (
                record.revision,
                record.revision - 1,
            ):
                return record
            if record.revision != revision:
                raise ConflictError("تغيرت البيانات؛ راجع النسخة المحفوظة أولاً")
            if record.status != Status.EXTRACTED:
                raise ValueError("احفظ بيانات المراجعة قبل التأكيد")
            if analyze(record.data).warnings and not acknowledge:
                raise ValueError("يجب الإقرار بالقيم الناقصة والتنبيهات قبل التأكيد")
            db.execute(
                "UPDATE invoices SET status='confirmed',acknowledged=?,confirmed_at=?,"
                "revision=revision+1 WHERE id=?",
                (int(acknowledge), now(), invoice_id),
            )
        return self.get(invoice_id)

    def record_attempt(
        self,
        record: Invoice,
        *,
        model: str,
        raw_text: str,
        metadata: dict,
        data: InvoiceData | None,
        error: str = "",
    ) -> Invoice:
        with self.connection() as db:
            result = db.execute(
                "UPDATE invoices SET data=?,status=?,error=?,revision=revision+1 "
                "WHERE id=? AND revision=? AND status IN ('pending','failed')",
                (
                    (data or record.data).model_dump_json(),
                    Status.EXTRACTED if data is not None else Status.FAILED,
                    error,
                    record.id,
                    record.revision,
                ),
            )
            conflict = result.rowcount != 1
            if conflict:
                error = "تغيرت الفاتورة أثناء الاستخراج؛ لم تُستبدل التعديلات"
            db.execute(
                "INSERT INTO attempts (invoice_id,model,raw_text,metadata,error,created_at) "
                "VALUES (?,?,?,?,?,?)",
                (record.id, model, raw_text, json.dumps(metadata), error, now()),
            )
        if conflict:
            raise ConflictError(error)
        return self.get(record.id)

    def attempts(self, invoice_id: str) -> list[dict]:
        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM attempts WHERE invoice_id=? ORDER BY id", (invoice_id,)
                )
            ]
