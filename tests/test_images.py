from io import BytesIO

import pytest
from PIL import Image

from transcriber.storage.images import api_image, display_image, validate_image


def test_exif_orientation_is_applied_without_changing_original():
    source = Image.new("RGB", (20, 40), "white")
    exif = Image.Exif()
    exif[274] = 6
    buffer = BytesIO()
    source.save(buffer, format="JPEG", exif=exif)
    content = buffer.getvalue()
    assert validate_image(content) == "image/jpeg"
    assert display_image(content).size == (40, 20)
    prepared = Image.open(BytesIO(api_image(content)))
    assert prepared.size == (40, 20)
    assert not prepared.getexif()
    assert Image.open(BytesIO(content)).size == (20, 40)


def test_non_image_or_unsupported_format_rejected():
    buffer = BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format="GIF")
    with pytest.raises(ValueError):
        validate_image(buffer.getvalue())
