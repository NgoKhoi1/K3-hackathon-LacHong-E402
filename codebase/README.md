# Dental Diagnosis Agent — API

Luồng chính: học viên gửi ảnh răng miệng → detector+classifier chẩn đoán tình
trạng → LLM đánh giá nguy cơ + sinh lời khuyên → trả kết quả.

Model nhận diện (detector YOLOv8 + classifier EfficientNet-B1) và agent LLM
được phát triển riêng trong `../vuong/` (không phải trong `codebase/`), tích
hợp qua `RealVisionService`/`RealAdvisorService` trong `app/services/`. Các
service này import động các file `vuong/1_*.py`, `2_*.py`, `5_*.py` qua
`app/core/vuong_bridge.py` — không copy/sửa code gốc của vuong/.

**Khác biệt quan trọng so với agent gốc**: `5_chatbot_dental_agent.py` gốc là
hội thoại nhiều lượt (hỏi thêm triệu chứng trước khi chốt mức nguy cơ).
`RealAdvisorService` ở đây chỉ dùng **1 lượt** — gọi thẳng `TriageEngine.assess`
+ `finalize()` với `symptoms={}` (bỏ qua bước hỏi thêm), khớp với API
`/diagnose` 1-lượt hiện có. Vì vậy đánh giá nguy cơ sẽ bảo thủ/kém chi tiết
hơn so với chạy CLI gốc (`python 5_chatbot_dental_agent.py <ảnh>`) — nếu cần
hỏi thêm triệu chứng thật, phải thêm endpoint session riêng (chưa làm ở đây).

## Yêu cầu

- `../vuong/artifacts/classifier_best.pt` và
  `../vuong/artifacts/detector_runs/weights/best.pt` phải tồn tại (đã có sẵn
  trong repo). Nếu `vuong/` không nằm cạnh `codebase/`, set `DENTAL_VUONG_DIR=<đường dẫn>`.
- `DENTAL_OPENAI_API_KEY` phải được set trong `.env` (agent dùng OpenAI API thật).

## Chạy local

```bash
pip install -r requirements.txt
pip install -r requirements-model.txt   # torch/torchvision/ultralytics/opencv/openai — nặng, cần cho model thật
cp .env.example .env                    # rồi điền DENTAL_OPENAI_API_KEY
uvicorn app.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs

Lưu ý: request `/diagnose` đầu tiên sẽ chậm (~10-15s) vì phải load detector +
classifier vào bộ nhớ; các request sau nhanh hơn nhiều vì model được cache
(singleton qua `app/api/deps.py`).

## Endpoint chính

`POST /api/v1/diagnose`

```json
{
  "image_base64": "<base64 string, không kèm data URI prefix>",
  "image_format": "jpeg"
}
```

Trả về `diagnosis` (danh sách finding: condition, confidence, bbox — bbox có
thể `null` với Calculus/Hypodontia vì chỉ classifier toàn ảnh phát hiện, không
có vị trí cụ thể) và `advice` (narrative — văn bản LLM tổng hợp, urgency,
per_condition — mức nguy cơ + ghi chú rule-based cho từng finding, disclaimer).

## Test

```bash
pytest
```

Test gọi qua `TestClient` xuống thẳng service thật (model + OpenAI) — không
mock. Mỗi lần chạy sẽ tốn vài giây load model (lần đầu) + gọi OpenAI thật.

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
