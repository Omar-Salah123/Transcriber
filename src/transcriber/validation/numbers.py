"""Conservative numeric normalization; never infer unclear handwritten values."""

import re
from decimal import Decimal

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def parse_number(value: object) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError("أدخل رقماً أو اترك الحقل فارغاً")
    text = str(value).strip().translate(DIGITS).replace("٫", ".").replace("٬", ",")
    # Commas are accepted only as unambiguous groups of three, never decimal guesses.
    if not re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?", text):
        raise ValueError("رقم غير واضح: استخدم النقطة أو ٫ للفاصل العشري")
    number = Decimal(text.replace(",", ""))
    if abs(number) >= Decimal("1000000000000") or number.as_tuple().exponent < -4:
        raise ValueError("الرقم أكبر من الحد المدعوم أو يحتوي على أكثر من ٤ منازل عشرية")
    return number
