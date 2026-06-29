from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import AuthContext
from app.models import ApprovalRequest, ApprovalRequestEvent, IdempotencyRecord, OutboxEvent
from app.schemas.approval_requests import (
    ApprovalDecisionResponse,
    ApprovalRequestEventResponse,
    ApprovalRequestResponse,
    ApprovalStatus,
    CreateApprovalRequestInput,
)

FINAL_STATUSES = {
    ApprovalStatus.APPROVED.value,
    ApprovalStatus.REJECTED.value,
    ApprovalStatus.CANCELLED.value,
}


@dataclass(frozen=True)
class MutationContext:
    workspace_id: str
    actor_user_id: str
    action_key: str
    idempotency_key: str


class ApprovalRequestService:
    def __init__(self, session: Session):
        self.session = session

    def get_healthcheck(self) -> bool:
        self.session.execute(text("SELECT 1"))
        return True

    def list_requests(self, workspace_id: str) -> list[ApprovalRequestResponse]:
        statement = (
            select(ApprovalRequest)
            .where(ApprovalRequest.workspace_id == workspace_id)
            .options(selectinload(ApprovalRequest.events))
            .order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc())
        )
        items = self.session.scalars(statement).all()
        return [self._to_response(item) for item in items]

    def get_request(self, workspace_id: str, request_id: str) -> ApprovalRequestResponse:
        approval_request = self._get_request_model(workspace_id=workspace_id, request_id=request_id)
        return self._to_response(approval_request)

    def create_request(
        self,
        auth_context: AuthContext,
        payload: CreateApprovalRequestInput,
        idempotency_key: str,
    ) -> tuple[ApprovalRequestResponse, int]:
        mutation_context = MutationContext(
            workspace_id=auth_context.workspace_id,
            actor_user_id=auth_context.user_id,
            action_key=f"POST:/workspaces/{auth_context.workspace_id}/approval-requests",
            idempotency_key=idempotency_key,
        )
        payload_dict = payload.model_dump(mode="json", by_alias=False)

        def operation() -> ApprovalRequestResponse:
            now = datetime.now(timezone.utc)
            approval_request = ApprovalRequest(
                id=self._generate_id("apr"),
                workspace_id=auth_context.workspace_id,
                source_type=payload.source_type.value,
                source_id=payload.source_id,
                title=payload.title,
                description=payload.description,
                status=ApprovalStatus.PENDING.value,
                reviewer_user_ids=payload.reviewer_user_ids,
                created_by_user_id=auth_context.user_id,
                last_updated_by_user_id=auth_context.user_id,
                version=1,
                created_at=now,
                updated_at=now,
            )
            self.session.add(approval_request)
            self._append_event(
                approval_request=approval_request,
                actor_user_id=auth_context.user_id,
                event_type="approval_request.created",
                previous_status=None,
                new_status=ApprovalStatus.PENDING.value,
                payload={
                    "sourceType": approval_request.source_type,
                    "sourceId": approval_request.source_id,
                    "title": approval_request.title,
                    "reviewerUserIds": approval_request.reviewer_user_ids,
                },
            )
            self._append_outbox_event(
                workspace_id=auth_context.workspace_id,
                aggregate_id=approval_request.id,
                event_type="approval_request.created",
                payload=self._outbox_payload(approval_request),
            )
            self.session.flush()
            self.session.refresh(approval_request)
            return self._to_response(approval_request)

        return self._run_idempotent_mutation(mutation_context, payload_dict, operation, status.HTTP_201_CREATED)

    def approve_request(
        self,
        workspace_id: str,
        request_id: str,
        auth_context: AuthContext,
        payload: ApproveApprovalRequestInput,
        idempotency_key: str,
    ) -> tuple[ApprovalRequestResponse, int]:
        return self._decide_request(
            workspace_id=workspace_id,
            request_id=request_id,
            auth_context=auth_context,
            payload=payload.model_dump(mode="json", by_alias=False),
            idempotency_key=idempotency_key,
            new_status=ApprovalStatus.APPROVED.value,
            event_type="approval_request.approved",
            comment=payload.comment,
            reason=None,
        )

    def reject_request(
        self,
        workspace_id: str,
        request_id: str,
        auth_context: AuthContext,
        payload: RejectApprovalRequestInput,
        idempotency_key: str,
    ) -> tuple[ApprovalRequestResponse, int]:
        return self._decide_request(
            workspace_id=workspace_id,
            request_id=request_id,
            auth_context=auth_context,
            payload=payload.model_dump(mode="json", by_alias=False),
            idempotency_key=idempotency_key,
            new_status=ApprovalStatus.REJECTED.value,
            event_type="approval_request.rejected",
            comment=None,
            reason=payload.reason,
        )

    def cancel_request(
        self,
        workspace_id: str,
        request_id: str,
        auth_context: AuthContext,
        payload: CancelApprovalRequestInput,
        idempotency_key: str,
    ) -> tuple[ApprovalRequestResponse, int]:
        return self._decide_request(
            workspace_id=workspace_id,
            request_id=request_id,
            auth_context=auth_context,
            payload=payload.model_dump(mode="json", by_alias=False),
            idempotency_key=idempotency_key,
            new_status=ApprovalStatus.CANCELLED.value,
            event_type="approval_request.cancelled",
            comment=None,
            reason=payload.reason,
        )

    def _decide_request(
        self,
        workspace_id: str,
        request_id: str,
        auth_context: AuthContext,
        payload: dict[str, Any],
        idempotency_key: str,
        new_status: str,
        event_type: str,
        comment: str | None,
        reason: str | None,
    ) -> tuple[ApprovalRequestResponse, int]:
        mutation_context = MutationContext(
            workspace_id=workspace_id,
            actor_user_id=auth_context.user_id,
            action_key=f"POST:/workspaces/{workspace_id}/approval-requests/{request_id}/{event_type.rsplit('.', maxsplit=1)[-1]}",
            idempotency_key=idempotency_key,
        )

        def operation() -> ApprovalRequestResponse:
            approval_request = self._get_request_model(workspace_id=workspace_id, request_id=request_id)
            if approval_request.status in FINAL_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Approval request is already in a final state.",
                )

            previous_status = approval_request.status
            now = datetime.now(timezone.utc)
            approval_request.status = new_status
            approval_request.decision_comment = comment
            approval_request.decision_reason = reason
            approval_request.decided_by_user_id = auth_context.user_id
            approval_request.decided_at = now
            approval_request.last_updated_by_user_id = auth_context.user_id
            approval_request.updated_at = now
            approval_request.version += 1

            audit_payload: dict[str, Any] = {}
            if comment is not None:
                audit_payload["comment"] = comment
            if reason is not None:
                audit_payload["reason"] = reason

            self._append_event(
                approval_request=approval_request,
                actor_user_id=auth_context.user_id,
                event_type=event_type,
                previous_status=previous_status,
                new_status=new_status,
                payload=audit_payload,
            )
            self._append_outbox_event(
                workspace_id=workspace_id,
                aggregate_id=approval_request.id,
                event_type=event_type,
                payload=self._outbox_payload(approval_request),
            )
            self.session.flush()
            self.session.refresh(approval_request)
            return self._to_response(approval_request)

        return self._run_idempotent_mutation(mutation_context, payload, operation, status.HTTP_200_OK)

    def _run_idempotent_mutation(
        self,
        mutation_context: MutationContext,
        payload: dict[str, Any],
        operation,
        success_status_code: int,
    ) -> tuple[ApprovalRequestResponse, int]:
        request_hash = self._hash_request(payload)
        existing_record = self.session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.workspace_id == mutation_context.workspace_id,
                IdempotencyRecord.user_id == mutation_context.actor_user_id,
                IdempotencyRecord.action_key == mutation_context.action_key,
                IdempotencyRecord.idempotency_key == mutation_context.idempotency_key,
            )
        )

        if existing_record:
            if existing_record.request_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key was already used with a different payload.",
                )
            if existing_record.response_body is None or existing_record.status_code is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Request with this Idempotency-Key is still being processed.",
                )
            cached_response = ApprovalRequestResponse.model_validate(existing_record.response_body)
            return cached_response, existing_record.status_code

        record = IdempotencyRecord(
            id=self._generate_id("idem"),
            workspace_id=mutation_context.workspace_id,
            user_id=mutation_context.actor_user_id,
            action_key=mutation_context.action_key,
            idempotency_key=mutation_context.idempotency_key,
            request_hash=request_hash,
        )
        self.session.add(record)
        try:
            response_model = operation()
            record.status_code = success_status_code
            record.response_body = response_model.model_dump(mode="json", by_alias=True)
            self.session.commit()
            return response_model, success_status_code
        except HTTPException:
            self.session.rollback()
            raise
        except IntegrityError:
            self.session.rollback()
            reloaded_record = self.session.scalar(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.workspace_id == mutation_context.workspace_id,
                    IdempotencyRecord.user_id == mutation_context.actor_user_id,
                    IdempotencyRecord.action_key == mutation_context.action_key,
                    IdempotencyRecord.idempotency_key == mutation_context.idempotency_key,
                )
            )
            if reloaded_record and reloaded_record.request_hash == request_hash and reloaded_record.response_body:
                cached_response = ApprovalRequestResponse.model_validate(reloaded_record.response_body)
                return cached_response, reloaded_record.status_code or success_status_code
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not safely process the idempotent request.",
            )
        except Exception:
            self.session.rollback()
            raise

    def _get_request_model(self, workspace_id: str, request_id: str) -> ApprovalRequest:
        statement = (
            select(ApprovalRequest)
            .where(ApprovalRequest.id == request_id, ApprovalRequest.workspace_id == workspace_id)
            .options(selectinload(ApprovalRequest.events))
        )
        approval_request = self.session.scalar(statement)
        if approval_request is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found.")
        return approval_request

    def _append_event(
        self,
        approval_request: ApprovalRequest,
        actor_user_id: str,
        event_type: str,
        previous_status: str | None,
        new_status: str,
        payload: dict[str, Any],
    ) -> None:
        event = ApprovalRequestEvent(
            id=self._generate_id("evt"),
            approval_request_id=approval_request.id,
            workspace_id=approval_request.workspace_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            previous_status=previous_status,
            new_status=new_status,
            payload=payload,
        )
        approval_request.events.append(event)

    def _append_outbox_event(
        self,
        workspace_id: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self.session.add(
            OutboxEvent(
                id=self._generate_id("out"),
                workspace_id=workspace_id,
                aggregate_type="approval_request",
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload,
            )
        )

    def _outbox_payload(self, approval_request: ApprovalRequest) -> dict[str, Any]:
        return {
            "id": approval_request.id,
            "workspaceId": approval_request.workspace_id,
            "sourceType": approval_request.source_type,
            "sourceId": approval_request.source_id,
            "title": approval_request.title,
            "status": approval_request.status,
            "reviewerUserIds": approval_request.reviewer_user_ids,
            "createdByUserId": approval_request.created_by_user_id,
            "lastUpdatedByUserId": approval_request.last_updated_by_user_id,
            "decidedByUserId": approval_request.decided_by_user_id,
            "decidedAt": approval_request.decided_at.isoformat() if approval_request.decided_at else None,
            "decisionComment": approval_request.decision_comment,
            "decisionReason": approval_request.decision_reason,
            "version": approval_request.version,
            "createdAt": approval_request.created_at.isoformat() if approval_request.created_at else None,
            "updatedAt": approval_request.updated_at.isoformat() if approval_request.updated_at else None,
        }

    def _to_response(self, approval_request: ApprovalRequest) -> ApprovalRequestResponse:
        decision = ApprovalDecisionResponse(
            decided_by_user_id=approval_request.decided_by_user_id,
            decided_at=approval_request.decided_at,
            comment=approval_request.decision_comment,
            reason=approval_request.decision_reason,
        )
        events = [
            ApprovalRequestEventResponse(
                id=event.id,
                event_type=event.event_type,
                actor_user_id=event.actor_user_id,
                previous_status=event.previous_status,
                new_status=event.new_status,
                payload=event.payload,
                created_at=event.created_at,
            )
            for event in approval_request.events
        ]
        return ApprovalRequestResponse(
            id=approval_request.id,
            workspace_id=approval_request.workspace_id,
            source_type=approval_request.source_type,
            source_id=approval_request.source_id,
            title=approval_request.title,
            description=approval_request.description,
            status=approval_request.status,
            reviewer_user_ids=approval_request.reviewer_user_ids,
            created_by_user_id=approval_request.created_by_user_id,
            last_updated_by_user_id=approval_request.last_updated_by_user_id,
            version=approval_request.version,
            created_at=approval_request.created_at,
            updated_at=approval_request.updated_at,
            decision=decision,
            events=events,
        )

    @staticmethod
    def _hash_request(payload: dict[str, Any]) -> str:
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _generate_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:20]}"
