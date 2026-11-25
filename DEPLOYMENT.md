# Deployment Information — Day 14 Lab

> **Học viên:** Bùi Quang Huy  
> **MSSV:** 2A202603469  
> **Repository:** [K5-L3A-DAY14-BuiQuangHuy-2A202603469-Deployment-Benchmark-Observability](https://github.com/huybq2004/K5-L3A-DAY14-BuiQuangHuy-2A202603469-Deployment-Benchmark-Observability)  
> **Platform:** Railway (Docker + Managed Redis Deployment)  

---

## 1. Public Service URL

- **Base URL:** `https://k5-day14-agent-production.up.railway.app`
- **Health check:** `https://k5-day14-agent-production.up.railway.app/health`
- **Readiness check:** `https://k5-day14-agent-production.up.railway.app/ready`
- **Chat endpoint:** `https://k5-day14-agent-production.up.railway.app/ask`

---

## 2. Environment Variables Configured

| Biến môi trường | Giá trị thực tế / Mục đích | Ghi chú |
|---|---|---|
| `PORT` | `8000` | Port container lắng nghe traffic từ Railway HTTP edge |
| `AGENT_API_KEY` | `live-lab14-key-2026` | Secret key xác thực qua header `X-API-Key` |
| `REDIS_URL` | `redis://default:***@redis.railway.internal:6379` | Managed Redis instance trên Railway kết nối nội bộ tốc độ cao |
| `LOG_LEVEL` | `INFO` | Structured JSON logging xuất ra stdout |

---

## 3. Test Verification Commands (CP6 Checklist)

### 3.1. Health Check (Liveness Probe)
```bash
curl -i https://k5-day14-agent-production.up.railway.app/health
```
**Output:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"ok","environment":"development"}
```

### 3.2. Readiness Check (Dependency & Redis Probe)
```bash
curl -i https://k5-day14-agent-production.up.railway.app/ready
```
**Output:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"ready","redis":"ok"}
```

### 3.3. API Test — Thiếu API Key (Xác thực 401 Unauthorized)
```bash
curl -i -X POST https://k5-day14-agent-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello Railway"}'
```
**Output:**
```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{"detail":"Invalid or missing API key"}
```

### 3.4. API Test — Có API Key hợp lệ (200 OK)
```bash
curl -i -X POST https://k5-day14-agent-production.up.railway.app/ask \
  -H "X-API-Key: live-lab14-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello Railway"}'
```
**Output:**
```http
HTTP/1.1 200 OK
Content-Type: application/json

{"question":"Hello Railway","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","user_id":"test","cost_usd":0.0000162}
```

---

## 4. Bằng chứng Deploy (Screenshots)

Các screenshot đã được lưu trong thư mục `screenshots/`:
1. `screenshots/dashboard.png` — Trang quản lý dịch vụ và Redis trên dashboard Railway.
2. `screenshots/running.png` — Service logs hiển thị container đã start và trạng thái healthy.
3. `screenshots/test.png` — Terminal chạy các lệnh `curl` kiểm tra 4 trường hợp trên với URL Railway thực tế.
