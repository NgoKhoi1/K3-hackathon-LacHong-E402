# Dental Diagnosis Agent — API

Luồng chính: học viên gửi ảnh răng miệng (+ mô tả triệu chứng, tuỳ chọn) →
detector+classifier chẩn đoán tình trạng → agent hỏi thêm triệu chứng nếu cần
→ đánh giá nguy cơ + sinh lời khuyên → trả kết quả.

Model nhận diện (detector YOLOv8 + classifier EfficientNet-B1) và agent LLM
được phát triển riêng trong `../vuong/` (không phải trong `codebase/`), tích
hợp qua `RealVisionService`/`RealAdvisorService` trong `app/services/`. Các
service này import động các file `vuong/1_*.py`, `2_*.py`, `5_*.py` qua
`app/core/vuong_bridge.py` — không copy/sửa code gốc của vuong/.

`RealAdvisorService` dùng chung **một** `DentalScreeningAgent` cho cả vòng đời
process (không tạo mới mỗi request), vì `agent.sessions` là dict lưu trạng
thái hội thoại phải sống xuyên suốt nhiều lượt HTTP — mất khi backend restart
(chấp nhận được ở quy mô demo). Không gọi thẳng `agent.start_session()` vì hàm
đó tự load detector/classifier qua `vuong/artifacts/inference_config.json`
(chứa path tuyệt đối của máy dev gốc, không khớp máy này) — vision luôn chạy
qua `RealVisionService` (path đúng) trước, kết quả được tái tạo lại thành
`VisionFindings` để đưa vào các bước hội thoại.

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

Lưu ý: request đầu tiên chạm tới model sẽ chậm (~10-15s) vì phải load detector
+ classifier vào bộ nhớ; các request sau nhanh hơn nhiều vì model được cache
(singleton qua `app/api/deps.py`).

## Endpoint

### Luồng hội thoại nhiều lượt (frontend dùng đường này)

`POST /api/v1/sessions` — bắt đầu phiên: gửi ảnh + mô tả triệu chứng ban đầu
(tuỳ chọn), nhận về `diagnosis` (kết quả nhận diện) và hoặc câu hỏi tiếp theo
(`status: "asking"`) hoặc kết quả cuối luôn nếu không cần hỏi thêm
(`status: "done"`).

```json
{ "image_base64": "<base64, không kèm data URI prefix>", "image_format": "jpeg", "initial_text": "" }
```

`POST /api/v1/sessions/{session_id}/messages` — trả lời câu hỏi hiện tại,
nhận về câu hỏi tiếp theo hoặc kết quả cuối (cùng shape `status`/`question`/`advice`
như trên). 404 nếu `session_id` không tồn tại (vd sau khi backend restart).

```json
{ "text": "câu trả lời của người dùng" }
```

### Luồng 1-lượt (vẫn còn, không bị frontend dùng nữa)

`POST /api/v1/diagnose` — bỏ qua hoàn toàn bước hỏi thêm triệu chứng
(`symptoms={}`), trả `diagnosis` + `advice` ngay trong 1 lần gọi. Đánh giá
nguy cơ vì vậy bảo thủ/kém chi tiết hơn luồng session ở trên.

```json
{ "image_base64": "<base64, không kèm data URI prefix>", "image_format": "jpeg" }
```

### Shape chung

`diagnosis.findings[]`: `condition`, `confidence`, `bboxes[]` (chuẩn hoá 0-1,
rỗng với Calculus/Hypodontia vì chỉ classifier toàn ảnh phát hiện, không có
vị trí cụ thể — có thể nhiều box nếu 1 điều kiện xuất hiện nhiều vùng).

`advice`: `narrative` (văn bản LLM tổng hợp), `urgency`, `per_condition[]`
(mức nguy cơ + ghi chú rule-based cho từng finding, từ `TriageEngine` — không
phải LLM tự suy diễn), `disclaimer`.

## Test

```bash
pytest
```

Test gọi qua `TestClient` xuống thẳng service thật (model + OpenAI) — không
mock. Mỗi lần chạy sẽ tốn vài giây load model (lần đầu) + gọi OpenAI thật.

## Frontend (thử luồng chính qua UI)

`frontend/` là Next.js app: upload ảnh (+ mô tả triệu chứng tuỳ chọn) → gọi
`/api/v1/sessions` → nếu agent hỏi thêm thì hiện khung hỏi-đáp ngay trong màn
kết quả (agent hỏi, người dùng trả lời, lặp lại) → khi xong hiện "Nhận định
từ AI". Ảnh phân tích có vẽ khung (bbox) đè lên vùng nghi ngờ, màu theo mức độ
nguy cơ. Chạy song song với backend:

```bash
cd frontend
npm install
npm run dev
```

Mở http://localhost:3000. `frontend/.env.local` trỏ `NEXT_PUBLIC_API_BASE_URL`
về `http://127.0.0.1:8000` — đổi nếu backend chạy port khác. Backend đã bật
CORS cho `http://localhost:3000` qua `DENTAL_CORS_ALLOW_ORIGINS` (`app/core/config.py`).
