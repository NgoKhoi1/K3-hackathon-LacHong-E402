from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import oral_like_image_base64

client = TestClient(app)


def test_session_conversation_reaches_advice():
    resp = client.post(
        "/api/v1/sessions",
        json={"image_base64": oral_like_image_base64(), "image_format": "jpeg", "initial_text": ""},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("asking", "done")
    assert "session_id" in body
    assert "diagnosis" in body and "findings" in body["diagnosis"]

    session_id = body["session_id"]
    # Trả lời hết các câu hỏi agent hỏi (nếu có) tới khi status == "done" —
    # giới hạn số vòng lặp để test không treo vô hạn nếu có bug.
    guard = 0
    while body["status"] == "asking" and guard < 20:
        assert body["question"]
        resp = client.post(f"/api/v1/sessions/{session_id}/messages", json={"text": "không rõ, bình thường thôi"})
        assert resp.status_code == 200
        body = resp.json()
        guard += 1

    assert body["status"] == "done"
    assert body["advice"] is not None
    assert body["advice"]["narrative"]
    assert body["advice"]["urgency"] in ("low", "medium", "high")


def test_session_message_unknown_session_returns_404():
    resp = client.post("/api/v1/sessions/does-not-exist/messages", json={"text": "xin chào"})
    assert resp.status_code == 404
