import logging
from datetime import datetime
from fastapi import HTTPException
import redis
from .config import settings

logger = logging.getLogger(__name__)

# Connect to Redis
try:
    r = redis.from_url(settings.redis_url, decode_responses=True)
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    r = None

def check_budget(user_id: str, estimated_cost: float = 0.001):
    """
    Cost guard using Redis.
    Monthly budget: $10.0 (from settings).
    """
    if not r:
        logger.warning("Redis not available. Bypassing cost guard.")
        return

    # Use first 8 chars of user_id for shared buckets if needed, 
    # but here we use the full user_id for precision.
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"

    current_spending = float(r.get(key) or 0)
    
    if current_spending + estimated_cost > settings.monthly_budget_usd:
        logger.warning(f"Budget exceeded for user {user_id}: ${current_spending:.2f}")
        raise HTTPException(
            status_code=402,
            detail=f"Payment Required: Monthly budget of ${settings.monthly_budget_usd} exceeded."
        )

def record_cost(user_id: str, cost: float):
    """
    Record the actual cost after an LLM call.
    """
    if not r:
        return

    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"
    
    # Increment spending
    r.incrbyfloat(key, cost)
    # Set expiration to 32 days to ensure it lasts till next month reset
    r.expire(key, 32 * 24 * 3600)
    
    logger.info(f"Recorded cost for user {user_id}: ${cost:.4f}. Total: ${float(r.get(key)):.2f}")
