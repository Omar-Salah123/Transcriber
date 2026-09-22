"""Validate image content and prepare an oriented, metadata-free API image."""

import warnings
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 25_000_000


def validate_image(content: bytes) -> str:
    if not content or len(content) > MAX_BYTES:
        raise ValueError("حجم الصورة يجب أن يكون بين ١ بايت و١٥ ميغابايت")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format not in {"JPEG", "PNG"}:
                    raise ValueError("الصور المدعومة JPEG وPNG فقط")
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError("الصورة تتجاوز ٢٥ مليون بكسل")
                mime = "image/jpeg" if image.format == "JPEG" else "image/png"
                image.verify()
            with Image.open(BytesIO(content)) as image:
                image.load()
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError("الصورة تالفة أو غير مدعومة") from exc
    return mime


def display_image(content: bytes) -> Image.Image:
    with Image.open(BytesIO(content)) as original:
        oriented = ImageOps.exif_transpose(original)
        rgba = oriented.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        return Image.alpha_composite(background, rgba).convert("RGB")


def api_image(content: bytes) -> bytes:
    image = display_image(content)
    image.thumbnail((3000, 3000))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()
