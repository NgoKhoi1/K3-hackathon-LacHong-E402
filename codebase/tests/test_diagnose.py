from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import oral_like_image_base64, plain_white_image_base64

client = TestClient(app)


def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_diagnose_happy_path():
    resp = client.post(
        "/api/v1/diagnose",
        json={"image_base64": oral_like_image_base64(), "image_format": "jpeg"},
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
        json={"image_base64": oral_like_image_base64(), "image_format": "bmp"},
    )
    assert resp.status_code == 400


def test_diagnose_rejects_low_quality_image():
    # Ảnh trắng đơn sắc: không có màu đặc trưng khoang miệng -> bị pipeline
    # thật từ chối (check_image_quality), đúng kịch bản "② mơ hồ/thiếu thông
    # tin" trong taxonomy chỗ khó của đề bài.
    resp = client.post(
        "/api/v1/diagnose",
        json={"image_base64": plain_white_image_base64(), "image_format": "jpeg"},
    )
    assert resp.status_code == 400
