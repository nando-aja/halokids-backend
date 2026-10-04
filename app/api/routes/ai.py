from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.api.deps import get_db
from app.schemas.ai_chat import AIChatRequest, AIChatResponse
from app.services.agentic_chat import AGENT


router = APIRouter()

_RATE_LIMIT = 30
_RATE_WINDOW = timedelta(minutes=1)
_rate_lock = Lock()
_request_history: dict[str, deque[datetime]] = defaultdict(deque)


def _check_rate_limit(client_key: str) -> None:
    now = datetime.now(timezone.utc)
    with _rate_lock:
        bucket = _request_history[client_key]
        while bucket and now - bucket[0] > _RATE_WINDOW:
            bucket.popleft()
        if len(bucket) >= _RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Terlalu banyak permintaan ke HaloKids AI. Silakan coba lagi sebentar.",
            )
        bucket.append(now)



@router.get("/health")
def ai_health() -> dict:
    return {
        "agent": AGENT.name,
        "status": "ready",
        "mode": "custom_deterministic_agentic",
        "external_ai_required": False,
    }


@router.post("/chat", response_model=AIChatResponse)
def chat(
    data: AIChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client_key = request.client.host if request.client else "unknown"
    _check_rate_limit(client_key)
    try:
        session_id, result = AGENT.handle(
            message=data.message,
            db=db,
            session_id=data.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return AIChatResponse(
        session_id=session_id,
        message=result.message,
        intent=result.intent.value,
        actions=result.actions,
        data=result.data,
    )
