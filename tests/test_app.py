from pathlib import Path

from streamlit.testing.v1 import AppTest

from transcriber.schemas.invoice import Status
from transcriber.storage.repository import Repository

APP = Path(__file__).parents[1] / "src/transcriber/app.py"


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception


def test_no_key_empty_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCRIBER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "")
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    assert app.title[0].value == "مراجعة الفواتير العربية"
    assert next(
        button for button in app.button if button.label == "استخراج جميع الفواتير الجديدة"
    ).disabled


def test_review_confirm_and_reopen(tmp_path, monkeypatch, image_bytes, complete_data):
    monkeypatch.setenv("TRANSCRIBER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "")
    repository = Repository(tmp_path)
    record, _ = repository.add_image("test.png", image_bytes)
    repository.save_draft(record.id, complete_data, record.revision)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    next(field for field in app.text_input if field.label == "رقم الفاتورة").set_value("000099")
    click(app, "حفظ ومراجعة للتأكيد")
    assert repository.get(record.id).data.invoice_number == "000099"
    click(app, "تأكيد البيانات المحفوظة")
    assert repository.get(record.id).status == Status.CONFIRMED
    click(app, "إعادة فتح للتعديل")
    assert repository.get(record.id).status == Status.EXTRACTED
    assert not repository.list(confirmed_only=True)


def test_blank_invoice_confirmation_needs_explicit_ack(tmp_path, monkeypatch, image_bytes):
    monkeypatch.setenv("TRANSCRIBER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "")
    repository = Repository(tmp_path)
    record, _ = repository.add_image("test.png", image_bytes)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    click(app, "حفظ ومراجعة للتأكيد")
    assert next(
        button for button in app.button if button.label == "تأكيد البيانات المحفوظة"
    ).disabled
    app.checkbox[0].check().run()
    click(app, "تأكيد البيانات المحفوظة")
    assert repository.get(record.id).acknowledged
