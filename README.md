# Approval Service

FastAPI backend service for submitting and resolving content approval requests before publication.

## Overview

The service manages an approval workflow for external content entities such as publications, scenarios, edits, or third-party materials. Related domain objects already exist in other systems and are referenced here only by identifier.

Supported operations:

- create an approval request;
- list approval requests inside a workspace;
- get a single approval request;
- approve, reject, or cancel a request.

Core guarantees:

- strict workspace isolation;
- idempotent mutation requests via `Idempotency-Key`;
- immutable final states;
- full audit trail for successful changes;
- outbox table for future event-driven integrations;
- sanitized responses, logs, and event payloads without secrets or raw provider payloads.

## Tech Stack

- Python 3
- FastAPI
- SQLAlchemy 2
- Alembic
- SQLite for local run
- PostgreSQL-ready database setup
- Pytest
- Docker / Docker Compose

## API

Implemented endpoints:

- `GET /health`
- `GET /ready`
- `POST /api/v1/workspaces/{workspace_id}/approval-requests`
- `GET /api/v1/workspaces/{workspace_id}/approval-requests`
- `GET /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}`
- `POST /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/approve`
- `POST /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/reject`
- `POST /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/cancel`

Note: this is an API service, so the root route `/` is intentionally not part of the public contract. Use `/docs`, `/health`, and `/ready` for local verification.

## Data Model

Main tables:

- `approval_requests` — current state of a request;
- `approval_request_events` — append-only audit history;
- `idempotency_records` — deduplication and replay protection;
- `outbox_events` — domain events prepared for future delivery.

Statuses:

- `pending`
- `approved`
- `rejected`
- `cancelled`

Final states are immutable.

## Auth Stub

For local development the service uses header-based stub authentication.

Required headers:

- `X-Auth-Workspace-Id`
- `X-Auth-User-Id`
- `X-Auth-Actions`

Available actions:

- `approval:read`
- `approval:create`
- `approval:decide`
- `approval:cancel`

Example:

```bash
curl -X POST "http://localhost:8000/api/v1/workspaces/ws_1/approval-requests" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: create-001" \
  -H "X-Auth-Workspace-Id: ws_1" \
  -H "X-Auth-User-Id: usr_1" \
  -H "X-Auth-Actions: approval:create,approval:read,approval:decide,approval:cancel" \
  -d '{
    "sourceType": "publication",
    "sourceId": "pub_123",
    "title": "Instagram reel draft",
    "description": "Needs final approval",
    "reviewerUserIds": ["usr_1", "usr_2"]
  }'
```

## Local Run

### Python

```bash
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Service URLs:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/ready`

### Docker Compose

```bash
docker compose up --build
```

## Tests

```bash
python -m pytest
```

## Example Decisions

Approve:

```json
{
  "comment": "Approved"
}
```

Reject:

```json
{
  "reason": "Brand tone is wrong"
}
```

Cancel:

```json
{
  "reason": "Draft was removed"
}
```

## Security Notes

- No secrets, tokens, emails, storage keys, signed URLs, provider URLs, or raw provider payloads are stored in public API responses, logs, or outbox payloads.
- Request logging is limited to method, path, status code, and duration.
- The outbox pattern is implemented as a safe extension point for future integrations.

## Future Improvements

- pagination and filtering for request lists;
- optimistic locking for high-concurrency scenarios;
- background outbox publisher;
- production PostgreSQL profile;
- richer correlation and request tracing metadata.
