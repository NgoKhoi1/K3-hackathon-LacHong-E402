import base64
import io

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _oral_like_image_base64() -> str:
    """Ảnh giả lập màu khoang miệng (hồng/đỏ nhạt + nhiễu) — đủ để vượt qua
    quality gate thật của vuong (check_image_quality: blur/brightness/oral
    cavity ratio), khác với ảnh trắng đơn sắc (sẽ bị từ chối, xem test bên dưới)."""
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


def _plain_white_image_base64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color="white").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_diagnose_happy_path():
    resp = client.post(
        "/api/v1/diagnose",
        json={"image_base64": _oral_like_image_base64(), "image_format": "jpeg"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "request_id" in body
    assert "diagnosis" in body and "findings" in body["diagnosis"]
    assert "advice" in body and "narrative" in body["advice"] and "per_condition" in body["advice"]


def test_diagnose_invalid_base64():
    resp = client.post(
        "/api/v1/diagnose",
        json={"image_base64": "not-valid-base64!!!", "image_format": "jpeg"},
    )
    assert resp.status_code == 400


def test_diagnose_unsupported_format():
    resp = client.post(
        "/api/v1/diagnose",
        json={"image_base64": _oral_like_image_base64(), "image_format": "bmp"},
    )
    assert resp.status_code == 400


def test_diagnose_rejects_low_quality_image():
    # Ảnh trắng đơn sắc: không có màu đặc trưng khoang miệng -> bị pipeline
    # thật từ chối (check_image_quality), đúng kịch bản "② mơ hồ/thiếu thông
    # tin" trong taxonomy chỗ khó của đề bài.
    resp = client.post(
        "/api/v1/diagnose",
        json={"image_base64": _plain_white_image_base64(), "image_format": "jpeg"},
    )
    assert resp.status_code == 400
