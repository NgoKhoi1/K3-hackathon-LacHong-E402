# Dental Diagnosis Agent — API

Luồng chính: học viên gửi ảnh răng miệng → model YOLO chẩn đoán tình trạng →
LLM sinh lời khuyên dựa trên chẩn đoán → trả kết quả.

Model YOLO và LLM được phát triển ở ngoài repo này. Trong `app/services/`,
mỗi model có một interface (`YoloDiagnosisService`, `LLMAdvisorService`) và
một implementation mock để phát triển/test luồng chính trước. Route không
cần sửa gì khi đổi mock → thật.

### Cắm model YOLO (.pt) thật

1. `pip install -r requirements-yolo.txt` (thêm ultralytics/torch, khá nặng nên tách riêng).
2. Trong `.env`: set `DENTAL_USE_MOCK_MODELS=false` và `DENTAL_YOLO_MODEL_PATH=<đường dẫn file .pt>`.
3. Mở `app/services/yolo_service.py`, sửa `YOLO_CLASS_NAME_MAP` cho khớp đúng
   tên class model đã được train (xem `model.names` hoặc `data.yaml` lúc train)
   — sai mapping ở đây là app hiển thị nhầm bệnh dù model đoán đúng.
4. `RealYoloDiagnosisService` sẽ được wire tự động qua `app/api/deps.py`.

Tích hợp LLM thật làm tương tự: implement `LLMAdvisorService` trong
`app/services/llm_service.py`, wire vào `get_llm_service()` trong `deps.py`.

## Chạy local

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs

## Endpoint chính

`POST /api/v1/diagnose`

```json
{
  "image_base64": "<base64 string, không kèm data URI prefix>",
  "image_format": "jpeg"
}
```

Trả về `diagnosis` (danh sách finding: condition, confidence, bbox) và
`advice` (summary, recommendations, urgency, disclaimer).

## Test

```bash
pytest
```

## Frontend (thử luồng chính qua UI)

`frontend/` là Next.js app tối giản: upload ảnh → gọi `/api/v1/diagnose` →
hiển thị kết quả chẩn đoán + lời khuyên. Chạy song song với backend:

```bash
cd frontend
npm install
npm run dev
```

Mở http://localhost:3000. `frontend/.env.local` trỏ `NEXT_PUBLIC_API_BASE_URL`
về `http://127.0.0.1:8000` — đổi nếu backend chạy port khác. Backend đã bật
CORS cho `http://localhost:3000` qua `DENTAL_CORS_ALLOW_ORIGINS` (`app/core/config.py`).
