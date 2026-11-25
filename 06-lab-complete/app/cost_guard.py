"""
Cost guard (tiêu chí 8) — theo dõi chi phí LLM theo ngày/tháng trong Redis.
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_memory_spend: dict[str, float] = {}


def _budget_keys() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return f"cost:daily:{now.strftime('%Y-%m-%d')}", f"cost:monthly:{now.strftime('%Y-%m')}"


def _get_spend(key: str) -> float:
    if r is not None:
        try:
            val = r.get(key)
            return float(val) if val is not None else 0.0
        except Exception:
            pass
    return _memory_spend.get(key, 0.0)


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    daily_key, monthly_key = _budget_keys()
    if _get_spend(daily_key) >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")
    if _get_spend(monthly_key) >= settings.monthly_budget_usd:
        raise HTTPException(status_code=402, detail="Monthly budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    daily_key, monthly_key = _budget_keys()

    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.incrbyfloat(daily_key, cost)
            pipe.expire(daily_key, 172800)
            pipe.incrbyfloat(monthly_key, cost)
            pipe.expire(monthly_key, 3024000)
            pipe.execute()
            return cost
        except Exception:
            pass

    _memory_spend[daily_key] = _memory_spend.get(daily_key, 0.0) + cost
    _memory_spend[monthly_key] = _memory_spend.get(monthly_key, 0.0) + cost
    return cost
