"""
Production AI Agent — Part 6 Final Project
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    """Định dạng mỗi dòng log thành một JSON object hợp lệ."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for field in ("event", "method", "path", "status", "ms"):
            val = getattr(record, field, None)
            if val is not None:
                payload[field] = val
        return json.dumps(payload, ensure_ascii=False)


def _setup_logging() -> logging.Logger:
    log = logging.getLogger("agent")
    log.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    log.propagate = False
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        log.addHandler(handler)
    return log


logger = _setup_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Agent starting up", extra={"event": "startup"})
    yield
    logger.info("Agent shutting down gracefully", extra={"event": "shutdown"})
    if r is not None:
        try:
            r.close()
        except Exception:
            pass


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "HTTP request completed",
        extra={
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": elapsed_ms,
        },
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    logger.error("Unhandled server error", extra={"event": "error", "status": 500})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, max_length=128)


@app.get("/health")
def health():
    """Liveness check — luôn trả 200 khi process còn sống."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    """Readiness check — 200 khi Redis sẵn sàng, 503 khi mất kết nối."""
    if redis_healthy():
        return {"status": "ready", "redis": "ok"}
    return JSONResponse(status_code=503, content={"status": "not_ready", "redis": "down"})


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)
    input_tokens = max(1, len(body.question.split()) * 2)
    output_tokens = max(1, len(answer.split()) * 2)
    cost = record_cost(input_tokens, output_tokens)

    return {
        "question": body.question,
        "answer": answer,
        "user_id": body.user_id,
        "cost_usd": round(cost, 8),
    }
