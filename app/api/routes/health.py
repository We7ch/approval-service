from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.services.approval_requests import ApprovalRequestService

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(session: Session = Depends(get_db_session)) -> dict[str, str]:
    service = ApprovalRequestService(session)
    service.get_healthcheck()
    return {"status": "ready"}
