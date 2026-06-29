from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, get_idempotency_key, require_action
from app.db.session import get_db_session
from app.schemas.approval_requests import (
    ApprovalRequestListResponse,
    ApprovalRequestResponse,
    ApproveApprovalRequestInput,
    CancelApprovalRequestInput,
    CreateApprovalRequestInput,
    RejectApprovalRequestInput,
)
from app.services.approval_requests import ApprovalRequestService

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/approval-requests", tags=["approval-requests"])


@router.post("", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED)
def create_approval_request(
    payload: CreateApprovalRequestInput,
    response: Response,
    auth_context: AuthContext = Depends(require_action("approval:create")),
    session: Session = Depends(get_db_session),
    idempotency_key: str = Depends(get_idempotency_key),
) -> ApprovalRequestResponse:
    service = ApprovalRequestService(session)
    result, status_code = service.create_request(auth_context=auth_context, payload=payload, idempotency_key=idempotency_key)
    response.status_code = status_code
    return result


@router.get("", response_model=ApprovalRequestListResponse)
def list_approval_requests(
    workspace_id: str,
    auth_context: AuthContext = Depends(require_action("approval:read")),
    session: Session = Depends(get_db_session),
) -> ApprovalRequestListResponse:
    service = ApprovalRequestService(session)
    return ApprovalRequestListResponse(items=service.list_requests(workspace_id=auth_context.workspace_id))


@router.get("/{request_id}", response_model=ApprovalRequestResponse)
def get_approval_request(
    request_id: str,
    auth_context: AuthContext = Depends(require_action("approval:read")),
    session: Session = Depends(get_db_session),
) -> ApprovalRequestResponse:
    service = ApprovalRequestService(session)
    return service.get_request(workspace_id=auth_context.workspace_id, request_id=request_id)


@router.post("/{request_id}/approve", response_model=ApprovalRequestResponse)
def approve_approval_request(
    request_id: str,
    payload: ApproveApprovalRequestInput,
    response: Response,
    auth_context: AuthContext = Depends(require_action("approval:decide")),
    session: Session = Depends(get_db_session),
    idempotency_key: str = Depends(get_idempotency_key),
) -> ApprovalRequestResponse:
    service = ApprovalRequestService(session)
    result, status_code = service.approve_request(
        workspace_id=auth_context.workspace_id,
        request_id=request_id,
        auth_context=auth_context,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    response.status_code = status_code
    return result


@router.post("/{request_id}/reject", response_model=ApprovalRequestResponse)
def reject_approval_request(
    request_id: str,
    payload: RejectApprovalRequestInput,
    response: Response,
    auth_context: AuthContext = Depends(require_action("approval:decide")),
    session: Session = Depends(get_db_session),
    idempotency_key: str = Depends(get_idempotency_key),
) -> ApprovalRequestResponse:
    service = ApprovalRequestService(session)
    result, status_code = service.reject_request(
        workspace_id=auth_context.workspace_id,
        request_id=request_id,
        auth_context=auth_context,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    response.status_code = status_code
    return result


@router.post("/{request_id}/cancel", response_model=ApprovalRequestResponse)
def cancel_approval_request(
    request_id: str,
    payload: CancelApprovalRequestInput,
    response: Response,
    auth_context: AuthContext = Depends(require_action("approval:cancel")),
    session: Session = Depends(get_db_session),
    idempotency_key: str = Depends(get_idempotency_key),
) -> ApprovalRequestResponse:
    service = ApprovalRequestService(session)
    result, status_code = service.cancel_request(
        workspace_id=auth_context.workspace_id,
        request_id=request_id,
        auth_context=auth_context,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    response.status_code = status_code
    return result
