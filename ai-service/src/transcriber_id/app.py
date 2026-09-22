"""Runnable landing page; invoice processing will be implemented in later milestones."""

import streamlit as st


def main() -> None:
    """Render the Arabic scaffold without network calls or client-data handling."""
    st.set_page_config(page_title="استخراج بيانات الفواتير", layout="wide")
    st.markdown(
        """
        <style>
        [data-testid="stMainBlockContainer"] {
            direction: rtl;
            text-align: right;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("استخراج بيانات الفواتير العربية")
    st.info("المشروع قيد التطوير. هذه صفحة أولية فقط، ومعالجة الفواتير غير متاحة بعد.")
    st.markdown(
        """
        ### خطوات العمل المخططة
        1. رفع صور الفواتير دفعة واحدة.
        2. استخراج البيانات وعرضها بجانب صورة الفاتورة.
        3. مراجعة البيانات وتعديلها ثم تأكيدها.
        4. تنزيل ملف Excel يحتوي على الفواتير المؤكدة وأصنافها.
        """
    )
    st.caption("لا تتصل هذه الصفحة بأي خدمة ذكاء اصطناعي ولا تحتاج إلى مفتاح API.")


if __name__ == "__main__":
    main()
