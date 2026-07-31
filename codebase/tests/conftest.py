import base64
import io

import numpy as np
from PIL import Image


def oral_like_image_base64() -> str:
    """Ảnh giả lập màu khoang miệng (hồng/đỏ nhạt + nhiễu) — đủ để vượt qua
    quality gate thật của vuong (check_image_quality: blur/brightness/oral
    cavity ratio), khác với ảnh trắng đơn sắc (sẽ bị từ chối)."""
    rng = np.random.default_rng(42)
    h, w = 480, 640
    base = np.zeros((h, w, 3), dtype=np.uint8)
    base[:, :, 0] = 220
    base[:, :, 1] = 140
    base[:, :, 2] = 150
    noise = rng.integers(-30, 30, size=(h, w, 3))
    arr = np.clip(base.astype(int) + noise, 0, 255).astype(np.uint8)
    arr[100:200, 150:500] = [235, 230, 225]
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()


def plain_white_image_base64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color="white").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()
