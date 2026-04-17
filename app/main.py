import time
import signal
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Security, Depends, Request, Response
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import redis

from .config import settings
from .agent_logic import graph
from .rate_limiter import check_rate_limit
from .cost_guard import check_budget, record_cost
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage, message_to_dict, messages_from_dict

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=settings.log_level,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False

# Connect to Redis for History
try:
    r_history = redis.from_url(settings.redis_url, decode_responses=True)
except Exception as e:
    logger.error(f"Failed to connect to Redis for history: {e}")
    r_history = None

# ─────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    return api_key

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    
    # Check Redis Connectivity
    try:
        if r_history:
            r_history.ping()
            logger.info(json.dumps({"event": "redis_connected"}))
    except Exception as e:
        logger.error(json.dumps({"event": "redis_connection_failed", "error": str(e)}))

    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))

    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    start = time.time()
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        logger.error(json.dumps({
            "event": "request_error",
            "method": request.method,
            "path": request.url.path,
            "error": str(e)
        }))
        raise

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    user_id: str = Field(..., description="Unique ID for the user conversation session")
    question: str = Field(..., min_length=1, max_length=2000)

class AskResponse(BaseModel):
    question: str
    answer: str
    timestamp: str

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/health", tags=["Ops"])
def health():
    return {"status": "ok", "uptime": round(time.time() - START_TIME, 1)}

@app.get("/ready", tags=["Ops"])
def ready():
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    return {"status": "ready"}

@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    _key: str = Depends(verify_api_key)
):
    # 1. Rate Limiting
    check_rate_limit(body.user_id)

    # 2. Daily/Monthly Budget Check
    check_budget(body.user_id)

    # 3. Get History from Redis (Stateless)
    history_key = f"history:{body.user_id}"
    history_messages = []
    if r_history:
        raw_history = r_history.get(history_key)
        if raw_history:
            try:
                history_messages = messages_from_dict(json.loads(raw_history))
            except Exception as e:
                logger.error(f"Failed to parse history for {body.user_id}: {e}")

    # 4. Invoke Agent
    try:
        # Add current question
        messages = history_messages + [HumanMessage(content=body.question)]
        
        # Call Graph
        result = graph.invoke({"messages": messages})
        
        # Get final response
        last_message = result["messages"][-1]
        answer = last_message.content

        # 5. Save History Back to Redis
        if r_history:
            # Keep only last 10 messages to avoid huge state
            new_history = result["messages"][-10:]
            serialized_history = json.dumps([message_to_dict(m) for m in new_history])
            r_history.set(history_key, serialized_history, ex=3600)  # Expire in 1 hour

        # 6. Record Cost (Mock cost for now)
        tokens = (len(body.question) + len(answer)) / 4
        cost = (tokens / 1000) * 0.01
        record_cost(body.user_id, cost)

        return AskResponse(
            question=body.question,
            answer=answer,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        logger.error(f"Agent error for {body.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Agent internal error")

# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))
    # Perform cleanups here if needed

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
