from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator

from app.schemas.common import CamelModel


class SourceType(StrEnum):
    PUBLICATION = "publication"
    SCENARIO = "scenario"
    EDIT = "edit"
    EXTERNAL = "external"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class CreateApprovalRequestInput(CamelModel):
    source_type: SourceType
    source_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    reviewer_user_ids: list[str] = Field(min_length=1, max_length=50)

    @field_validator("reviewer_user_ids")
    @classmethod
    def ensure_unique_reviewers(cls, reviewer_user_ids: list[str]) -> list[str]:
        normalized = [reviewer_id.strip() for reviewer_id in reviewer_user_ids if reviewer_id.strip()]
        if not normalized:
            raise ValueError("At least one reviewer user id is required.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Reviewer user ids must be unique.")
        return normalized


class ApproveApprovalRequestInput(CamelModel):
    comment: str | None = Field(default=None, max_length=4000)


class RejectApprovalRequestInput(CamelModel):
    reason: str = Field(min_length=1, max_length=4000)


class CancelApprovalRequestInput(CamelModel):
    reason: str = Field(min_length=1, max_length=4000)


class ApprovalRequestEventResponse(CamelModel):
    id: str
    event_type: str
    actor_user_id: str
    previous_status: str | None
    new_status: str
    payload: dict
    created_at: datetime


class ApprovalDecisionResponse(CamelModel):
    decided_by_user_id: str | None
    decided_at: datetime | None
    comment: str | None = None
    reason: str | None = None


class ApprovalRequestResponse(CamelModel):
    id: str
    workspace_id: str
    source_type: str
    source_id: str
    title: str
    description: str | None
    status: str
    reviewer_user_ids: list[str]
    created_by_user_id: str
    last_updated_by_user_id: str
    version: int
    created_at: datetime
    updated_at: datetime
    decision: ApprovalDecisionResponse
    events: list[ApprovalRequestEventResponse]


class ApprovalRequestListResponse(CamelModel):
    items: list[ApprovalRequestResponse]
