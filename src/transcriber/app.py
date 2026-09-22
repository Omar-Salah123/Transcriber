"""Run with: uv run streamlit run src/transcriber/app.py"""

import sqlite3

import streamlit as st

from transcriber.config import load_settings
from transcriber.export.workbook import build_workbook
from transcriber.extraction.gemini import ExtractionError, GeminiExtractor
from transcriber.extraction.service import extract_invoice
from transcriber.schemas.invoice import Status
from transcriber.storage.repository import ConflictError, Repository
from transcriber.ui.review import render_review

STATUS_LABELS = {
    Status.PENDING: "بانتظار الاستخراج",
    Status.EXTRACTED: "تحتاج إلى مراجعة",
    Status.FAILED: "فشل الاستخراج",
    Status.CONFIRMED: "مؤكدة",
}


def main() -> None:
    st.set_page_config(page_title="مراجعة الفواتير العربية", layout="wide")
    st.markdown(
        """
        <style>
        [data-testid="stMainBlockContainer"], [data-testid="stSidebar"] {
            direction: rtl;
            text-align: right;
        }
        [data-testid="stApp"], [data-testid="stApp"] h1,
        [data-testid="stApp"] h2, [data-testid="stApp"] h3,
        [data-testid="stApp"] input, [data-testid="stApp"] textarea,
        [data-testid="stApp"] button {
            font-family: Tahoma, Arial, sans-serif;
        }
        [data-testid="stMarkdownContainer"] { text-align: right; }
        [data-testid="stTextInput"] input, textarea { direction: rtl; text-align: right; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("مراجعة الفواتير العربية")
    st.caption("ارفع الصور، راجع البيانات بجانب الفاتورة، ثم أكدها لإضافتها إلى Excel.")
    settings = load_settings()
    try:
        repository = Repository(settings.data_dir)
    except (OSError, sqlite3.Error, ValueError):
        st.error("تعذر فتح مجلد البيانات؛ تحقق من المسار وصلاحيات الكتابة")
        return
    if message := st.session_state.pop("notice", None):
        st.success(message)
    with st.expander("رفع صور الفواتير", expanded=not repository.list()):
        st.write("تُحفظ الصور محلياً. زر الاستخراج يرسل الصور إلى Gemini ويستهلك رصيد API.")
        uploads = st.file_uploader(
            "اختر صور JPEG أو PNG (بحد أقصى ١٥ ميغابايت للصورة)",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
        )
        if st.button("إضافة الصور إلى القائمة", disabled=not uploads):
            added, duplicates = 0, 0
            for upload in uploads:
                try:
                    record, created = repository.add_image(upload.name, upload.getvalue())
                    added += int(created)
                    duplicates += int(not created)
                    st.session_state["selected_invoice"] = record.id
                except ValueError as exc:
                    st.error(f"{upload.name}: {exc}")
            st.success(f"صور جديدة: {added} — صور موجودة مسبقاً: {duplicates}")
    records = repository.list()
    with st.sidebar:
        st.header("الفواتير")
        st.write(f"الإجمالي: {len(records)}")
        confirmed = [record for record in records if record.status == Status.CONFIRMED]
        st.write(f"المؤكدة: {len(confirmed)}")
        if confirmed:
            st.download_button(
                "تنزيل Excel للفواتير المؤكدة",
                data=build_workbook(confirmed),
                file_name="invoices.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        st.caption("يشمل التنزيل البيانات المحفوظة والمؤكدة فقط.")
    if not settings.api_key:
        st.info("للاستخراج اضبط GEMINI_API_KEY في ملف .env. المراجعة اليدوية والتصدير متاحان.")
    pending = [record for record in records if record.status == Status.PENDING]
    if st.button("استخراج جميع الفواتير الجديدة", disabled=not pending or not settings.api_key):
        try:
            extractor = GeminiExtractor(settings.api_key, settings.model)
            progress = st.progress(0, text="بدء الاستخراج")
            for index, record in enumerate(pending, 1):
                try:
                    extract_invoice(repository, record.id, extractor)
                except ValueError:
                    st.warning("تم تخطي فاتورة عُدلت أثناء الاستخراج")
                progress.progress(
                    index / len(pending), text=f"تمت معالجة {index} من {len(pending)}"
                )
            st.session_state["notice"] = "اكتملت المحاولات؛ راجع حالة كل فاتورة في القائمة"
            st.rerun()
        except ExtractionError as exc:
            st.error(str(exc))
    if not records:
        st.info("ابدأ بإضافة صور الفواتير من قسم الرفع.")
        return
    by_id = {record.id: record for record in records}
    if st.session_state.get("selected_invoice") not in by_id:
        st.session_state["selected_invoice"] = records[0].id
    selected = st.selectbox(
        "اختر فاتورة للمراجعة",
        list(by_id),
        key="selected_invoice",
        format_func=lambda key: f"{by_id[key].filename} — {STATUS_LABELS[by_id[key].status]}",
    )
    record = repository.get(selected)
    if record.error:
        st.error(record.error)
    if record.status in {Status.PENDING, Status.FAILED}:
        label = (
            "إعادة محاولة الاستخراج" if record.status == Status.FAILED else "استخراج هذه الفاتورة"
        )
        if st.button(label, disabled=not settings.api_key):
            try:
                with st.spinner("جاري استخراج البيانات…"):
                    extract_invoice(
                        repository, record.id, GeminiExtractor(settings.api_key, settings.model)
                    )
                st.rerun()
            except (ExtractionError, ConflictError) as exc:
                st.error(str(exc))
    render_review(repository, record)


if __name__ == "__main__":
    main()
