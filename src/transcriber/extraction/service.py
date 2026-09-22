"""Persist each attempted extraction, including failed model output."""

from time import perf_counter
from typing import Protocol

import httpx

from transcriber.extraction.gemini import ExtractionError, ExtractionResult, validate_result
from transcriber.schemas.invoice import Invoice, Status
from transcriber.storage.repository import Repository


class Extractor(Protocol):
    model: str

    def extract(self, content: bytes) -> ExtractionResult: ...


def extract_invoice(repository: Repository, invoice_id: str, extractor: Extractor) -> Invoice:
    record = repository.get(invoice_id)
    if record.status not in {Status.PENDING, Status.FAILED}:
        raise ValueError("الاستخراج متاح للفواتير الجديدة أو الفاشلة فقط؛ تُحفظ تعديلات المراجعة")
    result = ExtractionResult("")
    data = None
    error = ""
    started = perf_counter()
    try:
        result = extractor.extract(repository.image_bytes(record))
        data = validate_result(result)
    except ExtractionError as exc:
        error = str(exc)
    except (httpx.HTTPError, OSError, TimeoutError):
        error = "تعذر قراءة الصورة أو الاتصال بالخدمة؛ تحقق من الاتصال والملف ثم أعد المحاولة"
    result.metadata["elapsed_seconds"] = round(perf_counter() - started, 3)
    return repository.record_attempt(
        record,
        model=extractor.model,
        raw_text=result.raw_text,
        metadata=result.metadata,
        data=data,
        error=error,
    )
