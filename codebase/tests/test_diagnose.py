import base64
import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _sample_image_base64() -> str:
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
        json={"image_base64": _sample_image_base64(), "image_format": "jpeg"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "request_id" in body
    assert "diagnosis" in body and "findings" in body["diagnosis"]
    assert "advice" in body and "recommendations" in body["advice"]


def test_diagnose_invalid_base64():
    resp = client.post(
        "/api/v1/diagnose",
        json={"image_base64": "not-valid-base64!!!", "image_format": "jpeg"},
    )
    assert resp.status_code == 400


def test_diagnose_unsupported_format():
    resp = client.post(
        "/api/v1/diagnose",
        json={"image_base64": _sample_image_base64(), "image_format": "bmp"},
    )
    assert resp.status_code == 400
