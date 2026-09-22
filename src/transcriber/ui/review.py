"""Review saved revisions beside the source, with an explicit confirmation screen."""

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from transcriber.schemas.invoice import Invoice, InvoiceData, Item, Status
from transcriber.storage.images import display_image
from transcriber.storage.repository import Repository
from transcriber.validation.checks import analyze

ITEM_COLUMNS = {
    "description": "البيان",
    "quantity": "العدد",
    "unit_price": "سعر الوحدة",
    "written_amount": "المبلغ المكتوب",
    "notes": "ملاحظات الصنف",
}


def editor_rows(data: InvoiceData) -> pd.DataFrame:
    rows = [
        {key: "" if value is None else str(value) for key, value in item.model_dump().items()}
        for item in data.items
    ]
    return pd.DataFrame(rows, columns=list(ITEM_COLUMNS), dtype=str)


def read_items(rows: pd.DataFrame) -> list[Item]:
    items = []
    for row in rows.fillna("").to_dict(orient="records"):
        items.append(Item.model_validate(row))
    return items


def saved_summary(record: Invoice) -> None:
    data = record.data
    st.write(f"رقم الفاتورة: {data.invoice_number or '—'}")
    st.write(f"البائع: {data.seller or '—'} — العميل: {data.customer or '—'}")
    st.write(f"التاريخ الأصلي: {data.date_text or '—'}")
    st.write(f"التاريخ المتحقق: {data.verified_date or '—'}")
    st.dataframe(editor_rows(data).rename(columns=ITEM_COLUMNS), hide_index=True)
    result = analyze(data)
    st.write(f"الإجمالي المكتوب: {data.written_total if data.written_total is not None else '—'}")
    calculated = result.calculated_total if result.calculated_total is not None else "غير مكتمل"
    st.write(f"الإجمالي المحسوب: {calculated}")
    st.caption("الحساب منفصل عن المبالغ المكتوبة ولا يستبدلها. هامش مقارنة المبالغ: ٠٫٠١.")
    if result.warnings:
        st.warning("توجد قيم ناقصة أو ملاحظات تحتاج إلى مراجعة")
        for warning in result.warnings:
            st.write(f"• {warning}")


def render_review(repository: Repository, record: Invoice) -> None:
    image_column, fields_column = st.columns([1, 1], gap="large")
    with image_column:
        st.subheader("الصورة الأصلية")
        rotation = st.select_slider(
            "تدوير العرض", options=[0, 90, 180, 270], key=f"rotate-{record.id}"
        )
        zoom = st.slider("تكبير الصورة", 1.0, 4.0, 1.0, 0.25, key=f"zoom-{record.id}")
        try:
            content = repository.image_bytes(record)
            image = display_image(content).rotate(-rotation, expand=True)
            if zoom > 1:
                horizontal = st.slider("الموضع الأفقي", 0, 100, 50, key=f"pan-x-{record.id}")
                vertical = st.slider("الموضع الرأسي", 0, 100, 50, key=f"pan-y-{record.id}")
                width, height = int(image.width / zoom), int(image.height / zoom)
                left = int((image.width - width) * horizontal / 100)
                top = int((image.height - height) * vertical / 100)
                image = image.crop((left, top, left + width, top + height))
            st.image(image, width="stretch")
            st.download_button(
                "تنزيل الصورة الأصلية",
                content,
                file_name=record.filename,
                mime=record.mime_type,
                key=f"image-{record.id}",
            )
        except (OSError, ValueError):
            st.error("تعذر عرض الصورة الأصلية؛ استعد ملفها قبل تأكيد البيانات")
            return
    with fields_column:
        st.subheader("بيانات الفاتورة")
        confirming = st.session_state.get("confirm_revision") == (record.id, record.revision)
        if record.status == Status.CONFIRMED:
            st.success("هذه الفاتورة مؤكدة ومدرجة في Excel")
            saved_summary(record)
            if st.button("إعادة فتح للتعديل", key=f"reopen-{record.id}"):
                try:
                    repository.save_draft(record.id, record.data, record.revision)
                    st.session_state.pop("confirm_revision", None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            return
        if confirming:
            saved_summary(record)
            warnings = analyze(record.data).warnings
            acknowledged = (
                st.checkbox(
                    "راجعت القيم الناقصة والتنبيهات وأوافق على حفظها كما هي",
                    key=f"ack-{record.id}-{record.revision}",
                )
                if warnings
                else False
            )
            if st.button(
                "تأكيد البيانات المحفوظة",
                type="primary",
                disabled=bool(warnings) and not acknowledged,
            ):
                try:
                    repository.confirm(record.id, record.revision, acknowledge=acknowledged)
                    st.session_state.pop("confirm_revision", None)
                    st.session_state["notice"] = "تم التأكيد وإضافة الفاتورة إلى تنزيل Excel"
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            if st.button("العودة للتعديل"):
                st.session_state.pop("confirm_revision", None)
                st.rerun()
            return
        st.caption(
            "احفظ التعديلات قبل تغيير الفاتورة أو إغلاق الصفحة. "
            "الحقول الفارغة تعني بيانات غير متوفرة."
        )
        data = record.data
        with st.form(f"review-{record.id}-{record.revision}"):
            number = st.text_input("رقم الفاتورة", value=data.invoice_number)
            seller = st.text_input("البائع", value=data.seller)
            customer = st.text_input("العميل", value=data.customer)
            date_text = st.text_input("التاريخ كما كُتب", value=data.date_text)
            verified = st.text_input(
                "التاريخ المتحقق (YYYY-MM-DD، اختياري)", value=str(data.verified_date or "")
            )
            total = st.text_input(
                "الإجمالي المكتوب",
                value=str(data.written_total) if data.written_total is not None else "",
            )
            st.caption(
                "يمكن إدخال الأرقام العربية. الفاصل العشري نقطة أو ٫. "
                "أضف أو احذف صفوف الأصناف أدناه."
            )
            rows = st.data_editor(
                editor_rows(data),
                hide_index=True,
                num_rows="dynamic",
                column_config={
                    key: st.column_config.TextColumn(label) for key, label in ITEM_COLUMNS.items()
                },
                key=f"items-{record.id}-{record.revision}",
            )
            notes = st.text_area("ملاحظات المراجعة", value=data.notes)
            save = st.form_submit_button("حفظ مسودة")
            review = st.form_submit_button("حفظ ومراجعة للتأكيد", type="primary")
        if save or review:
            try:
                edited = InvoiceData(
                    invoice_number=number,
                    seller=seller,
                    customer=customer,
                    date_text=date_text,
                    verified_date=verified,
                    written_total=total,
                    items=read_items(rows),
                    notes=notes,
                )
                updated = repository.save_draft(record.id, edited, record.revision)
                if review:
                    st.session_state["confirm_revision"] = (record.id, updated.revision)
                st.session_state["notice"] = "تم حفظ البيانات"
                st.rerun()
            except ValidationError as exc:
                for error in exc.errors(include_input=False, include_url=False):
                    st.error(f"قيمة غير صالحة ({'.'.join(map(str, error['loc']))}): {error['msg']}")
            except ValueError as exc:
                st.error(str(exc))
