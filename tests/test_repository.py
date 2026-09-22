import pytest

from transcriber.schemas.invoice import InvoiceData, Status
from transcriber.storage.repository import ConflictError, Repository


def test_deduplicate_and_restore(repository, image_bytes, complete_data):
    invoice, created = repository.add_image("../../client.png", image_bytes)
    duplicate, created_again = repository.add_image("different.png", image_bytes)
    assert created and not created_again
    assert duplicate.id == invoice.id
    assert invoice.filename == "client.png"
    saved = repository.save_draft(invoice.id, complete_data, invoice.revision)
    reopened = Repository(repository.directory)
    assert reopened.get(invoice.id).data == complete_data
    assert reopened.image_bytes(saved) == image_bytes


def test_confirmation_reopen_and_idempotency(repository, image_bytes, complete_data):
    record, _ = repository.add_image("invoice.png", image_bytes)
    with pytest.raises(ValueError):
        repository.confirm(record.id, record.revision, acknowledge=True)
    record = repository.save_draft(record.id, complete_data, record.revision)
    confirmed = repository.confirm(record.id, record.revision)
    assert repository.confirm(record.id, record.revision) == confirmed
    again = repository.confirm(confirmed.id, confirmed.revision)
    assert again == confirmed
    assert len(repository.list(confirmed_only=True)) == 1
    reopened = repository.save_draft(record.id, complete_data, confirmed.revision)
    assert reopened.status == Status.EXTRACTED
    assert not reopened.acknowledged
    assert reopened.confirmed_at is None
    assert repository.list(confirmed_only=True) == []


def test_missing_values_require_acknowledgment(repository, image_bytes):
    record, _ = repository.add_image("invoice.png", image_bytes)
    record = repository.save_draft(record.id, InvoiceData(), record.revision)
    with pytest.raises(ValueError):
        repository.confirm(record.id, record.revision)
    confirmed = repository.confirm(record.id, record.revision, acknowledge=True)
    assert confirmed.acknowledged
    assert confirmed.data.written_total is None


def test_stale_draft_cannot_overwrite_or_confirm(repository, image_bytes, complete_data):
    record, _ = repository.add_image("invoice.png", image_bytes)
    current = repository.save_draft(record.id, complete_data, record.revision)
    with pytest.raises(ConflictError):
        repository.save_draft(record.id, InvoiceData(), record.revision)
    with pytest.raises(ConflictError):
        repository.confirm(record.id, record.revision, acknowledge=True)
    assert repository.get(record.id).data == current.data


def test_invalid_image_is_not_persisted(repository):
    with pytest.raises(ValueError):
        repository.add_image("fake.jpg", b"not an image")
    assert not repository.list()
