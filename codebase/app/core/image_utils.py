import base64
import binascii
import io

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

from app.core.config import settings


def decode_and_validate_image(image_base64: str, image_format: str) -> bytes:
    fmt = image_format.lower().lstrip(".")
    if fmt not in settings.allowed_image_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng ảnh '{image_format}' không được hỗ trợ. Cho phép: {settings.allowed_image_formats}",
        )

    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="image_base64 không hợp lệ") from exc

    size_mb = len(image_bytes) / (1024 * 1024)
    if size_mb > settings.max_image_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"Ảnh {size_mb:.1f}MB vượt giới hạn {settings.max_image_size_mb}MB",
        )

    try:
        Image.open(io.BytesIO(image_bytes)).verify()
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Dữ liệu không phải ảnh hợp lệ") from exc

    return image_bytes
