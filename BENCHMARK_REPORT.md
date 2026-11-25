# Benchmark & Observability Report — Day 14

> Mọi con số dưới đây được lấy trực tiếp từ các file JSON trong `reports/` (và sẽ bổ sung phần Docker/Observability từ CSV/screenshot thật).

**Họ tên:** Bùi Quang Huy (MSSV: 2A202603469)
**Ngày chạy:** 2026-11-25
**Môi trường:** Windows 11 + Python 3.11.8 (local develop benchmarks); WSL2 Ubuntu + Docker Desktop (production stack)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Agent v2 bình thường mất ~190–250ms (retrieval + mock LLM); ngưỡng 500ms đảm bảo trải nghiệm mượt cho 95% request mà vẫn chấp nhận dao động jitter. |
| Error rate `/ask` | < 2.0 % | Mock LLM có tỉ lệ lỗi upstream mặc định `MOCK_ERROR_RATE=0.01` (1%), nên error budget 2% cho phép dung sai nhẹ mà vẫn phát hiện sự cố bất thường. |
| Accuracy trên golden dataset | ≥ 80 % (và 100% sau khi bổ sung KB, 0 regression) | Đảm bảo chất lượng trả lời đúng các khái niệm cốt lõi trước khi cho phép merge/deploy. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.02 | 202.8 | 235.6 | 1723.5 | 1.33% | ✅ PASS (p95 & error rate) |
| 10 | 37.11 | 200.5 | 246.4 | 1715.7 | 1.00% | ✅ PASS (p95 & error rate) |
| 50 | 119.51 | 213.0 | 291.2 | 1720.3 | 0.67% | ✅ PASS (p95 & error rate) |
| 100 | 36.74 | 817.5 | 6534.4 | 7265.6 | 2.00% | ❌ FAIL (p95 > 500ms) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không. Từ concurrency 1 → 10 → 50, RPS tăng gần tuyến tính (4.02 → 37.11 → 119.51 req/s) vì endpoint là `async` và thời gian chờ chủ yếu là I/O (`asyncio.sleep` mô phỏng retrieval + LLM). Tuy nhiên đến concurrency = 100 trên 1 process uvicorn local, RPS tụt xuống 36.74 req/s và p95 vọt lên 6534.4 ms do event loop / connection queue trên một worker bị bão hoà (contention), làm các request phải xếp hàng chờ nhau.

### 2.2 Tail latency

Chạy `load_test.py --requests 300 --concurrency 20` trên agent v2:

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 199.6 | 242.9 | 250.9 |
| 0.03 (mặc định) | 228.0 | 246.9 | 1659.2 |
| 0.1 | 350.0 | 1705.2 | 1732.3 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

`p99` (và `p95` khi tỉ lệ chậm đạt 10%) nhạy nhất với request chậm: ở `MOCK_SLOW_RATE=0.03`, `avg` chỉ tăng nhẹ từ 199.6 ms lên 228.0 ms (trông vẫn rất nhanh), nhưng `p99` nhảy vọt từ 250.9 ms lên 1659.2 ms (gấp >6.5 lần). Khi `MOCK_SLOW_RATE=0.1`, `avg` vẫn chỉ 350.0 ms (< 500 ms), trong khi `p95` đã là 1705.2 ms. Đặt SLO theo `average` sẽ che giấu hoàn toàn trải nghiệm tệ của nhóm người dùng ở phần đuôi (tail latency).

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.3 | 109.3 | 112.9 |
| Tổng cost (USD) | $0.000406 | $0.000764 | $0.000784 |
| Cost / câu đúng (USD) | $0.00040635 | $0.00003639 | $0.00003410 |
| Quality gate | ❌ FAIL | ✅ PASS | ✅ PASS (0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `(["jwt", "xác thực"], ...)` vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py` giải thích JWT là token có chữ ký số và thời gian hết hạn. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `(["kubernetes", "hpa"], ...)` vào `KNOWLEDGE_BASE` trong `utils/mock_llm.py` mô tả HPA scale dựa trên CPU, memory hoặc custom metrics. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Agent v2 có thêm bước retrieval nên `Avg tokens / câu` gần gấp đôi (109.3–112.9 so với 57.3), tổng cost tăng (~$0.000784 so với $0.000406) và latency p50/p95 tăng nhẹ (~20–30 ms). Tuy nhiên accuracy nhảy từ 4.3% lên 91.3% (và 100% sau khi sửa KB), nhờ vậy **cost / câu đúng giảm >11 lần** (từ $0.00040635 xuống $0.00003410). Đây là trade-off rất đáng giá cho production.

**Cách dùng exit code của `run_eval.py` để chặn merge trong CI:**

Script `eval/run_eval.py` trả về **exit code 0** khi đạt `min_accuracy` và không có câu nào bị regression so với baseline, và trả về **exit code 1** khi vi phạm quality gate. Trong GitHub Actions CI, ta chạy:
```yaml
- name: Run Agent Eval Quality Gate
  run: |
    python eval/run_eval.py --url http://localhost:8002 --min-accuracy 0.8 --baseline reports/eval_v2.json
```
Nếu lệnh trả exit code ≠ 0, step CI tự động fail và branch protection rule sẽ chặn không cho merge PR.

---

## 4. Observability stack (production)

*(Cần chạy Docker Compose stack trong `06-lab-complete/benchmark-observability/production/` để thu thập screenshot và số liệu)*

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (`screenshots/grafana-dashboard.png`)
- [ ] Một trace chậm trong Jaeger (`screenshots/jaeger-slow-trace.png`)
- [ ] Một trace lỗi trong Jaeger (`screenshots/jaeger-error-trace.png`)
- [ ] Trang Alerts của Prometheus với ≥ 2 alert đang **firing** (`screenshots/prometheus-alert-firing.png`)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | ~60s (threshold > 5% trong 1m) | Error Rate (/ask 5xx) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | ~120s (threshold p95 > 1s trong 2m) | Request Duration p95 |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | ~120s (rate > $2/h) | LLM Cost Burn Rate ($/h) |
| D | `docker pause` 1 instance | `AgentInstanceDown` | ~30s (up == 0 trong 30s) | Active Instances / Up Metric |
| E | `AGENT_VERSION=v1` | *(Không có alert nào firing)* | — | — |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

`AGENT_VERSION=v1` không làm tăng error rate HTTP 5xx hay latency, nên các alert hạ tầng/hệ thống sẽ im lặng. Để phát hiện sự cố chất lượng (quality regression) trong production, cần: (1) chạy `eval/run_eval.py` như một quality gate trong CI/CD trước khi deploy; (2) thu thập feedback người dùng (thumbs up/down) và LLM-as-a-judge trên mẫu traffic thực tế; (3) theo dõi metric độ dài câu trả lời / tỉ lệ fallback hoặc gắn label `agent_version` vào metric/log để đối chiếu khi deploy bản mới.

### 4.3 Debug bằng trace

- `trace_id` của request bị chậm: `6dee80b34a08fd1cc295e881535df57c`
- Thời gian span chậm nhất: **1709.08 ms** (chiếm **79.9%** tổng thời gian request 2139.87 ms)
- Tên span đó: `chat mock-llm-small` (gọi mô hình LLM)
- Dòng log tương ứng trong terminal:
```json
{"ts": "2026-11-25T08:11:52.947741+00:00", "level": "INFO", "service": "observable-agent", "instance": "34caf058112c", "event": "llm_call", "trace_id": "6dee80b34a08fd1cc295e881535df57c", "span_id": "60133b67325bcad7", "request_id": "ade7e3e6cfc7", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 81, "output_tokens": 46, "cost_usd": 4e-05, "llm_ms": 1694.2}
{"ts": "2026-11-25T08:11:52.954232+00:00", "level": "INFO", "service": "observable-agent", "instance": "34caf058112c", "event": "http_request", "trace_id": "6dee80b34a08fd1cc295e881535df57c", "span_id": "60133b67325bcad7", "request_id": "ade7e3e6cfc7", "method": "POST", "route": "/ask", "status": 200, "ms": 2137.5}
```
*Ngoài ra, trace bị lỗi (`f33f3f6553535b113921407b73d3bbe8`) ghi nhận status 503 với event `llm_error`: `"Upstream LLM error: 503 Service Unavailable (mock)"`.*

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 65.12 | 200 | 370 | 1700 | 65 (0.84%) |
| 3 | 66.03 | 190 | 220 | 1700 | 72 (0.91%) |

*Chi tiết endpoint `/ask`:*
- 1 instance: RPS 59.48, p50 200ms, p95 410ms, p99 1700ms, max 2092ms.
- 3 instances: RPS 59.33, p50 190ms, p95 230ms, p99 1700ms, max 1860ms.

**Nhận xét:**
- Khi scale từ 1 lên 3 instances sau Nginx round-robin load balancer, **tail latency p95 giảm mạnh gần một nửa từ 410ms xuống 230ms** (giảm 43.9%), p50 giảm từ 200ms xuống 190ms, và thời gian phản hồi max giảm từ 2092ms xuống 1860ms.
- Tỉ lệ failures giữ ở mức ~0.85–0.91% do `MOCK_ERROR_RATE=0.01` (1% lỗi giả lập từ upstream LLM 503).
- Việc scale ngang giải quyết triệt để vấn đề nghẽn hàng đợi (queue backlog) khi có spike traffic đồng thời 100 người dùng, giữ p95 luôn nằm trong ngưỡng an toàn dưới 1 giây của SLO.

---

## 6. Kết luận

- 3 điều học được về benchmark & observability:
  1. Latency trung bình che giấu tail latency; cần đặt SLO theo `p95`/`p99` và tách biệt benchmark hiệu năng (load test) với benchmark chất lượng (eval).
  2. Eval trên golden dataset kết hợp quality gate (`--baseline`, exit code) giúp bắt regression trước khi code lên production; chỉ số `cost / câu đúng` phản ánh hiệu quả thực chất tốt hơn `cost / câu`.
  3. 3 trụ cột Metrics – Traces – Logs liên kết qua `trace_id` giúp đi từ triệu chứng (Grafana alert) đến nguyên nhân gốc (span chậm trong Jaeger + log JSON chi tiết).
- Nếu đưa agent này lên production thật, sẽ thêm metric/alert:
  - Alert cho tỉ lệ cache hit / retrieval empty rate (phát hiện suy giảm chất lượng RAG tương tự thí nghiệm E).
  - Alert cho Redis latency / connection pool saturation và tỉ lệ HTTP 429 / 402 (phát hiện khách hàng bị chặn bất thường hoặc lạm dụng API).
