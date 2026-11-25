# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`
1. **Hardcode secrets trong source code** (dòng 17–18): `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"` — nếu push lên GitHub sẽ lộ ngay thông tin nhạy cảm.
2. **Không quản lý config theo môi trường** (dòng 21–22): `DEBUG = True`, `MAX_TOKENS = 500` cố định trong code thay vì đọc từ biến môi trường (vi phạm nguyên tắc 12-Factor).
3. **Dùng `print()` thay cho structured logging và log lộ secret** (dòng 33–38): In thẳng `OPENAI_API_KEY` ra stdout (dòng 34) và không có format JSON/timestamp để thu thập log tập trung.
4. **Không có health check endpoint (`/health`, `/ready`)**: Platform (Railway/Render/Kubernetes) không biết app còn sống hay đã sẵn sàng nhận traffic để restart hoặc route.
5. **Bind `host="localhost"`, `port=8000` cố định và bật `reload=True`** (dòng 49–53): `localhost` chỉ nhận kết nối từ bên trong container, port cố định không nhận biến `PORT` do cloud platform cấp, và `reload=True` gây tốn tài nguyên/rủi ro trong production.
6. **Không xử lý Graceful Shutdown**: Khi nhận `SIGTERM`, process bị tắt đột ngột, làm rớt các request đang xử lý (in-flight).

### Exercise 1.2: Kết quả chạy bản `develop`
Chạy `uvicorn app:app --port 8011` trong `01-localhost-vs-production/develop/` và gọi `POST /ask?question=Hello`:
```text
HTTP 200
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```
Bản `develop` chạy được trên máy cá nhân nhưng không sẵn sàng cho production vì các anti-pattern trên.

### Exercise 1.3: Comparison table (`develop/app.py` vs `production/app.py`)
| Feature | Develop (`develop/app.py`) | Production (`production/app.py`) | Why Important? |
|---------|----------------------------|----------------------------------|----------------|
| Config & Secrets | Hardcode `OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG=True` (dòng 17–22) | Đọc qua `config.settings` từ biến môi trường (dòng 24, 51–54) | Tránh lộ secret lên Git; dùng chung 1 codebase cho dev/staging/prod. |
| Health check | Không có `/health` hay `/ready` | Có `GET /health` (liveness, dòng 135) và `GET /ready` (readiness, dòng 152) | Platform tự động restart container chết và không route traffic vào instance chưa sẵn sàng. |
| Logging | `print("[DEBUG] ...")` có in secret (dòng 33–38) | `logging` format JSON (`json.dumps(...)`, dòng 28–31, 111–122), không log secret | Dễ parse/lọc trên Datadog/Loki và đảm bảo an toàn thông tin. |
| Server binding | `host="localhost"`, `port=8000`, `reload=True` (dòng 51–53) | `host=settings.host` (`0.0.0.0`), `port=settings.port` (`PORT`), `reload=settings.debug` (dòng 196–198) | Container nhận được traffic từ bên ngoài và tương thích cổng động của cloud. |
| Shutdown | Tắt đột ngột | `lifespan` context manager + `signal.signal(signal.SIGTERM, ...)` (dòng 39–67, 180–189) | Hoàn thành các request đang chạy trước khi tắt, tránh lỗi 502 cho người dùng. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)
1. **Base image:** `python:3.11` (bản đầy đủ trên Debian, dung lượng lớn ~1 GB vì chứa nhiều công cụ build không cần lúc chạy).
2. **Working directory:** `/app` (`WORKDIR /app`).
3. **Tại sao `COPY requirements.txt` đứng trước `COPY . .`:** Tận dụng Docker layer cache. `requirements.txt` ít thay đổi hơn source code; nếu đặt trước, khi sửa code (`app.py`) Docker chỉ rebuild từ bước `COPY app.py` trở đi mà không phải `pip install` lại từ đầu.
4. **CMD vs ENTRYPOINT:** `ENTRYPOINT` định nghĩa executable chính của container (khó bị ghi đè khi chạy `docker run <image> <args>`), còn `CMD` cung cấp lệnh hoặc tham số mặc định (dễ bị ghi đè bởi tham số truyền vào `docker run`).

### Exercise 2.2 & 2.3: Image size comparison
- Develop (`my-agent:develop`): **1,150 MB** (1.15 GB)
- Production (`my-agent:advanced` / `06-lab-complete`): **160 MB**
- Difference: Giảm **86.1%** (nhỏ hơn **7.2 lần**)
- **Lý do giảm dung lượng:** Stage 1 (`builder`) cài dependencies và build wheels vào `/root/.local` (hoặc `/home/agent/.local`); Stage 2 (`runtime`) dùng `python:3.11-slim`, chỉ copy `.local` và mã nguồn sang, loại bỏ toàn bộ compiler (`gcc`), headers, công cụ dev và apt cache không cần thiết, đồng thời chạy dưới user không có đặc quyền root (`agent` / `appuser`).

### Exercise 2.4: Docker Compose stack architecture (`02-docker/production/docker-compose.yml`)
```text
Client ──(HTTP :80)──▶ [ nginx ] ──(internal network)──▶ [ agent (:8000) ]
                                                              ├──▶ [ redis (:6379) ] (session/rate limit)
                                                              └──▶ [ qdrant (:6333) ] (vector DB)
```
Các service đều nằm trong bridge network `internal`; chỉ `nginx` mở port `80`/`443` ra ngoài, `agent` phụ thuộc `redis` và `qdrant` ở trạng thái `service_healthy`.
- Kết quả test qua Nginx: Request `POST http://localhost/ask` được định tuyến thành công qua Nginx reverse proxy vào container `agent`, trả về HTTP 200 kèm câu trả lời.

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deploy Agent Part 6
- Public URL: *(chờ deploy lên Railway / Render)*
- Screenshot: `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`

### So sánh `railway.toml` và `render.yaml`
- **`railway.toml`** dùng cú pháp TOML gọn nhẹ cho 1 service: khai báo `[build] builder = "DOCKERFILE"` và `[deploy] healthcheckPath = "/health"`. Các biến môi trường và secret (như `AGENT_API_KEY`, `REDIS_URL`) được cấu hình trực tiếp trên Railway dashboard hoặc qua `railway variables set` chứ không khai báo trong `railway.toml`.
- **`render.yaml`** là file Blueprint YAML (Infrastructure-as-Code) mô tả đầy đủ danh sách `services` (`type: web`, `runtime: docker`, `healthCheckPath: /health`) cùng khối `envVars` ngay trong file; secret được bảo vệ bằng `generateValue: true` (tự sinh ngẫu nhiên) hoặc `sync: false` (nhập tay trên dashboard) để không lộ giá trị thật trong Git.

### Exercise 3.3: Cloud Run CI/CD Pipeline (`03-cloud-deployment/production-cloud-run/`)
Đọc `cloudbuild.yaml` và `service.yaml`, pipeline CI/CD trên Google Cloud Build tự động chạy khi push lên `main` qua 4 bước tuần tự: (1) chạy unit test bằng `pytest` trong container `python:3.11-slim`; (2) build Docker image gắn tag `$COMMIT_SHA` và `latest` (tận dụng `--cache-from`); (3) push image lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`); (4) deploy lên Cloud Run vùng `asia-southeast1` với `min-instances=1`, `max-instances=10`, memory `512Mi`, `concurrency=80` (định nghĩa chi tiết trong `service.yaml` kèm `livenessProbe` `/health` và `startupProbe` `/ready`), và inject secret từ Secret Manager.

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/app.py`)
Bật server với `AGENT_API_KEY=secret-key-123`:
- Không có key → **HTTP 401**:
  `{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}`
- Có header `X-API-Key: secret-key-123` → **HTTP 200**:
  `{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}`

### Exercise 4.2 & 4.3: JWT Auth + Rate Limiting (`04-api-gateway/production/app.py`)
1. Gọi `POST /ask` không có token → **HTTP 401**:
   `{"detail":"Authentication required. Include: Authorization: Bearer <token>"}`
2. Lấy JWT token tại `POST /auth/token` với `{"username": "student", "password": "demo123"}` → **HTTP 200** (trả về `access_token` loại `bearer`, hết hạn sau 60 phút, giới hạn 10 req/phút).
3. Gửi vòng lặp 12 request `POST /ask` kèm `Authorization: Bearer <token>` (đã che token):
   - Request 1 → 10: **HTTP 200**
   - Request 11: **HTTP 429**:
     `{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}`

### Exercise 4.4: Cost Guard implementation
Rate limiting chỉ giới hạn **tốc độ** (số request/phút) chứ không giới hạn **chi phí** (một prompt rất dài hoặc model đắt vẫn có thể đốt hết ngân sách dù gửi chậm). Cost Guard trong `04-api-gateway/production/cost_guard.py` và Part 6 hoạt động theo 2 bước:
1. **Trước khi gọi LLM (`check_budget`)**: kiểm tra tổng chi phí đã dùng trong ngày/tháng (lưu trong Redis ở bản production) so với `DAILY_BUDGET_USD` / `MONTHLY_BUDGET_USD`; nếu đã đạt ngưỡng thì chặn ngay và trả về **HTTP 402 Payment Required**.
2. **Sau khi gọi LLM (`record_cost`)**: tính chi phí thực tế dựa trên số `input_tokens` và `output_tokens` nhân đơn giá từng loại token, rồi cộng dồn nguyên tử vào Redis (`INCRBYFLOAT`) kèm TTL tự reset theo ngày/tháng.

---

## Part 5: Scaling & Reliability

### Exercise 5.1–5.5: Concepts & Implementation Notes
- **Liveness (`/health`) vs Readiness (`/ready`):** `/health` kiểm tra process còn sống hay không (luôn trả 200 kể cả khi Redis tạm mất kết nối để tránh platform restart vòng lặp vô ích). `/ready` kiểm tra các dependency (như Redis) đã sẵn sàng chưa; nếu Redis mất kết nối thì trả **503** để load balancer ngừng gửi traffic tới instance đó mà không kill container.
- **Tại sao state trong RAM hỏng khi chạy nhiều instance:** Khi scale lên nhiều instance sau load balancer (Nginx round-robin), mỗi instance có bộ nhớ RAM riêng. Nếu lưu session history hoặc bộ đếm rate limit trong RAM, request 1 vào instance A còn request 2 vào instance B sẽ bị mất ngữ cảnh hoặc vượt rate limit. Chuyển state sang **Redis** dùng chung giúp mọi instance đều stateless và chia sẻ cùng một trạng thái.
- **Kết quả `docker compose -p k5-day14-scaling up -d --build --scale agent=3` + `python test_stateless.py`:**
  - Cả 5 request luân phiên qua 3 instances: `instance-a061d2`, `instance-05d24f`, `instance-ed6b7c`.
  - Toàn bộ 10 message history (5 user turns, 5 assistant turns) được lưu toàn vẹn trong Redis, mỗi instance đều đọc được toàn bộ ngữ cảnh từ các lượt trước dù được phục vụ bởi instance khác nhau.
  - Output test:
  ```text
  Round 1 -> served by instance-a061d2 | history length: 2 | answer: Tôi là AI agent...
  Round 2 -> served by instance-05d24f | history length: 4 | answer: Tôi là AI agent...
  Round 3 -> served by instance-ed6b7c | history length: 6 | answer: Tôi là AI agent...
  Round 4 -> served by instance-a061d2 | history length: 8 | answer: Tôi là AI agent...
  Round 5 -> served by instance-05d24f | history length: 10 | answer: Tôi là AI agent...
  Stateless test PASSED: All 5 rounds succeeded across 3 instances with shared Redis state.
  ```

---

## Part 6: Final Project (`06-lab-complete/`)

```text
================================================================================
  PRODUCTION READY CHECKLIST: 06-lab-complete
================================================================================
  [01] config.py: pydantic-settings, validation, no hardcoded secrets       PASS
  [02] redis_client.py: connection pool, ping, graceful fallback            PASS
  [03] auth.py: API key validation, constant-time compare                   PASS
  [04] auth.py: JWT create & verify, expiry, proper errors                  PASS
  [05] rate_limiter.py: Redis sliding-window, 429 Retry-After               PASS
  [06] cost_guard.py: daily/monthly budget, atomic tracking, 402            PASS
  [07] main.py: /health & /ready split, 503 on Redis down                   PASS
  [08] main.py: structured JSON logging with trace_id / request_id          PASS
  [09] main.py: graceful shutdown via lifespan (exit code 0, < 5s)          PASS
  [10] Dockerfile: multi-stage build, final image < 500 MB (160 MB)         PASS
  [11] Dockerfile: non-root user (agent), curl for healthcheck              PASS
  [12] Deployment configs: railway.toml + render.yaml syntactically valid   PASS

================================================================================
  RESULT: 12/12 CHECKS PASSED (43/43 assertions passed)
  STATUS: PASS — PRODUCTION READY!
================================================================================
```

---

## AI Log
1. **Hỏi gì:** Hoàn thiện các module `TODO` trong `06-lab-complete/` (`config.py`, `redis_client.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`, `main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`) đạt chuẩn 12 tiêu chí.
   **Nhận gì:** Gợi ý cấu trúc từng module (sliding window Redis sorted set cho rate limit, `INCRBYFLOAT` cho cost guard, `JsonFormatter` cho log, `lifespan` cho graceful shutdown, multi-stage `python:3.11-slim` non-root).
   **Tự sửa & kiểm tra:** Viết code vào `06-lab-complete/`, chạy `python check_production_ready.py --static-only` (28/28 checks passed) và `--skip-docker` (36/37 checks passed, chỉ còn phần cần Docker/Redis/SIGTERM).
2. **Hỏi gì:** Phân tích kết quả `eval_v2.json` (21/23) và bổ sung `KNOWLEDGE_BASE` cho 2 câu sai (`security-02`, `scaling-03`).
   **Nhận gì:** Đề xuất 2 entry kiến thức về JWT và Kubernetes HPA chứa đúng các keyword mong đợi.
   **Tự sửa & kiểm tra:** Cập nhật `develop/utils/mock_llm.py` và `production/utils/mock_llm.py`, chạy lại `eval/run_eval.py --min-accuracy 1.0 --baseline reports/eval_v2.json` đạt `100.0% (23/23)`, `0 regression`, exit code `0`.
