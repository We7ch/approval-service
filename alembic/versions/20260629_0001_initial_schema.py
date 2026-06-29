"""Initial approval workflow schema.

Revision ID: 20260629_0001
Revises:
Create Date: 2026-06-29 00:00:01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260629_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewer_user_ids", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=False),
        sa.Column("last_updated_by_user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decided_by_user_id", sa.String(length=64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"], unique=False)
    op.create_index("ix_approval_requests_workspace_id", "approval_requests", ["workspace_id"], unique=False)
    op.create_index(
        "ix_approval_requests_workspace_created_at",
        "approval_requests",
        ["workspace_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_workspace_status",
        "approval_requests",
        ["workspace_id", "status"],
        unique=False,
    )

    op.create_table(
        "approval_request_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("approval_request_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_request_events_approval_request_id", "approval_request_events", ["approval_request_id"], unique=False)
    op.create_index("ix_approval_request_events_workspace_id", "approval_request_events", ["workspace_id"], unique=False)
    op.create_index(
        "ix_approval_request_events_workspace_created_at",
        "approval_request_events",
        ["workspace_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("action_key", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=128), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", "action_key", "idempotency_key", name="uq_idempotency_scope"),
    )
    op.create_index("ix_idempotency_records_user_id", "idempotency_records", ["user_id"], unique=False)
    op.create_index("ix_idempotency_records_workspace_id", "idempotency_records", ["workspace_id"], unique=False)

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"], unique=False)
    op.create_index("ix_outbox_events_workspace_id", "outbox_events", ["workspace_id"], unique=False)
    op.create_index(
        "ix_outbox_events_workspace_created_at",
        "outbox_events",
        ["workspace_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_workspace_created_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_workspace_id", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate_id", table_name="outbox_events")
    op.drop_table("outbox_events")

    op.drop_index("ix_idempotency_records_workspace_id", table_name="idempotency_records")
    op.drop_index("ix_idempotency_records_user_id", table_name="idempotency_records")
    op.drop_table("idempotency_records")

    op.drop_index("ix_approval_request_events_workspace_created_at", table_name="approval_request_events")
    op.drop_index("ix_approval_request_events_workspace_id", table_name="approval_request_events")
    op.drop_index("ix_approval_request_events_approval_request_id", table_name="approval_request_events")
    op.drop_table("approval_request_events")

    op.drop_index("ix_approval_requests_workspace_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_workspace_created_at", table_name="approval_requests")
    op.drop_index("ix_approval_requests_workspace_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_table("approval_requests")
