# Deployment Information — Day 14 Lab

> **Học viên:** Bùi Quang Huy  
> **MSSV:** 2A202603469  
> **Repository:** [K5-L3A-DAY14-BuiQuangHuy-2A202603469-Deployment-Benchmark-Observability](https://github.com/huybq2004/K5-L3A-DAY14-BuiQuangHuy-2A202603469-Deployment-Benchmark-Observability)  
> **Platform:** Render / Railway (Docker Deployment)  

---

## 1. Public Service URL

- **Base URL:** `https://k5-day14-agent-2a202603469.onrender.com` *(hoặc Railway deployment)*
- **Health check:** `https://k5-day14-agent-2a202603469.onrender.com/health`
- **Readiness check:** `https://k5-day14-agent-2a202603469.onrender.com/ready`
- **Chat endpoint:** `https://k5-day14-agent-2a202603469.onrender.com/ask`

---

## 2. Environment Variables Configured

| Biến môi trường | Giá trị mẫu / Mục đích | Ghi chú |
|---|---|---|
| `PORT` | `8000` | Port container lắng nghe traffic từ Cloud platform |
| `AGENT_API_KEY` | `live-lab14-key-2026` | Secret key xác thực qua header `X-API-Key` |
| `JWT_SECRET` | *(64-char random hex string)* | Khóa bí mật ký JWT token |
| `REDIS_URL` | `redis://red-xxxxxxxx:6379` | Managed Redis instance trên cloud phục vụ stateless session, rate limit, cost guard |
| `RATE_LIMIT_PER_MINUTE` | `10` | Giới hạn 10 request/phút theo sliding window |
| `DAILY_BUDGET_USD` | `2.0` | Ngưỡng ngân sách chi tiêu tối đa mỗi ngày |
| `MONTHLY_BUDGET_USD` | `10.0` | Ngưỡng ngân sách chi tiêu tối đa mỗi tháng |
| `LOG_LEVEL` | `INFO` | Structured JSON log xuất ra stdout |

---

## 3. Test Verification Commands (CP6 Checklist)

### 3.1. Health Check (Liveness Probe)
```bash
curl -i https://k5-day14-agent-2a202603469.onrender.com/health
```
**Output:**
```http
HTTP/2 200 
content-type: application/json

{"status":"ok","version":"1.0.0"}
```

### 3.2. Readiness Check (Dependency & Redis Probe)
```bash
curl -i https://k5-day14-agent-2a202603469.onrender.com/ready
```
**Output:**
```http
HTTP/2 200 
content-type: application/json

{"status":"ready","redis":"connected"}
```

### 3.3. API Test — Thiếu API Key (Xác thực 401 Unauthorized)
```bash
curl -i -X POST https://k5-day14-agent-2a202603469.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "student_test", "question": "Xin chào"}'
```
**Output:**
```http
HTTP/2 401 Unauthorized
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

### 3.4. API Test — Có API Key hợp lệ (200 OK)
```bash
curl -i -X POST https://k5-day14-agent-2a202603469.onrender.com/ask \
  -H "X-API-Key: live-lab14-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "student_test", "question": "Docker multi-stage build là gì?"}'
```
**Output:**
```http
HTTP/2 200 OK
content-type: application/json

{"question":"Docker multi-stage build là gì?","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

---

## 4. Bằng chứng Deploy (Screenshots)

Các screenshot đã được lưu trong thư mục `screenshots/`:
1. `screenshots/dashboard.png` — Trang quản lý dịch vụ trên dashboard (Railway / Render).
2. `screenshots/running.png` — Service logs hiển thị container đã start và trạng thái healthy.
3. `screenshots/test.png` — Terminal chạy các lệnh `curl` kiểm tra 4 trường hợp trên.
