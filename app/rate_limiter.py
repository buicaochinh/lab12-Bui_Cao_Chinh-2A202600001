import time
import logging
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

def check_rate_limit(user_id: str):
    """
    Sliding window rate limiter using Redis.
    Default: 10 requests per minute per user.
    """
    if not r:
        logger.warning("Redis not available. Bypassing rate limit.")
        return

    now = time.time()
    key = f"rate_limit:{user_id}"
    
    # Use a Redis pipeline for atomicity
    pipe = r.pipeline()
    # Remove old timestamps (outside the 60s window)
    pipe.zremrangebyscore(key, 0, now - 60)
    # Count requests in window
    pipe.zcard(key)
    # Add current timestamp
    pipe.zadd(key, {str(now): now})
    # Set expiration on the key
    pipe.expire(key, 60)
    
    # Execute
    results = pipe.execute()
    request_count = results[1]

    if request_count >= settings.rate_limit_per_minute:
        logger.warning(f"Rate limit exceeded for user {user_id}: {request_count} req/min")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {settings.rate_limit_per_minute} requests per minute.",
            headers={"Retry-After": "60"}
        )
