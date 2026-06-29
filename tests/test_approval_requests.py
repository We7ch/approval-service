from __future__ import annotations

from fastapi.testclient import TestClient


def create_request(client: TestClient, headers: dict[str, str], idempotency_key: str = "create-1"):
    return client.post(
        "/api/v1/workspaces/ws_1/approval-requests",
        json={
            "sourceType": "publication",
            "sourceId": "pub_123",
            "title": "Instagram reel draft",
            "description": "Needs final approval",
            "reviewerUserIds": ["usr_1", "usr_2"],
        },
        headers={**headers, "Idempotency-Key": idempotency_key},
    )


def test_health_and_ready(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


def test_create_and_get_approval_request(client: TestClient, auth_headers: dict[str, str]):
    create_response = create_request(client, auth_headers)

    assert create_response.status_code == 201
    body = create_response.json()
    assert body["status"] == "pending"
    assert body["workspaceId"] == "ws_1"
    assert body["reviewerUserIds"] == ["usr_1", "usr_2"]
    assert len(body["events"]) == 1
    assert body["events"][0]["eventType"] == "approval_request.created"

    request_id = body["id"]
    get_response = client.get(f"/api/v1/workspaces/ws_1/approval-requests/{request_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == request_id


def test_list_requests_is_isolated_by_workspace(client: TestClient, auth_headers: dict[str, str]):
    create_request(client, auth_headers)

    other_workspace_headers = {
        "X-Auth-Workspace-Id": "ws_2",
        "X-Auth-User-Id": "usr_other",
        "X-Auth-Actions": "approval:read,approval:create",
    }
    other_create = client.post(
        "/api/v1/workspaces/ws_2/approval-requests",
        json={
            "sourceType": "scenario",
            "sourceId": "sc_456",
            "title": "Scenario draft",
            "description": "Second workspace",
            "reviewerUserIds": ["usr_5"],
        },
        headers={**other_workspace_headers, "Idempotency-Key": "create-2"},
    )
    assert other_create.status_code == 201

    ws1_list = client.get("/api/v1/workspaces/ws_1/approval-requests", headers=auth_headers)
    ws2_list = client.get("/api/v1/workspaces/ws_2/approval-requests", headers=other_workspace_headers)

    assert ws1_list.status_code == 200
    assert ws2_list.status_code == 200
    assert len(ws1_list.json()["items"]) == 1
    assert len(ws2_list.json()["items"]) == 1
    assert ws1_list.json()["items"][0]["workspaceId"] == "ws_1"
    assert ws2_list.json()["items"][0]["workspaceId"] == "ws_2"


def test_create_request_is_idempotent(client: TestClient, auth_headers: dict[str, str]):
    first_response = create_request(client, auth_headers, "same-key")
    second_response = create_request(client, auth_headers, "same-key")

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["id"] == second_response.json()["id"]

    list_response = client.get("/api/v1/workspaces/ws_1/approval-requests", headers=auth_headers)
    assert len(list_response.json()["items"]) == 1


def test_reusing_idempotency_key_with_different_payload_returns_conflict(client: TestClient, auth_headers: dict[str, str]):
    create_request(client, auth_headers, "duplicate-key")

    conflict_response = client.post(
        "/api/v1/workspaces/ws_1/approval-requests",
        json={
            "sourceType": "publication",
            "sourceId": "pub_999",
            "title": "Changed title",
            "description": "Changed payload",
            "reviewerUserIds": ["usr_9"],
        },
        headers={**auth_headers, "Idempotency-Key": "duplicate-key"},
    )

    assert conflict_response.status_code == 409
    assert "different payload" in conflict_response.json()["detail"]


def test_approve_request_and_block_other_final_transitions(client: TestClient, auth_headers: dict[str, str]):
    create_response = create_request(client, auth_headers)
    request_id = create_response.json()["id"]

    approve_response = client.post(
        f"/api/v1/workspaces/ws_1/approval-requests/{request_id}/approve",
        json={"comment": "Approved"},
        headers={**auth_headers, "Idempotency-Key": "approve-1"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"
    assert approve_response.json()["decision"]["comment"] == "Approved"
    assert approve_response.json()["decision"]["reason"] is None
    assert len(approve_response.json()["events"]) == 2

    reject_response = client.post(
        f"/api/v1/workspaces/ws_1/approval-requests/{request_id}/reject",
        json={"reason": "Too late"},
        headers={**auth_headers, "Idempotency-Key": "reject-1"},
    )
    assert reject_response.status_code == 409


def test_cancel_requires_specific_permission(client: TestClient, auth_headers: dict[str, str]):
    create_response = create_request(client, auth_headers)
    request_id = create_response.json()["id"]

    limited_headers = {
        "X-Auth-Workspace-Id": "ws_1",
        "X-Auth-User-Id": "usr_actor",
        "X-Auth-Actions": "approval:read,approval:create",
    }
    cancel_response = client.post(
        f"/api/v1/workspaces/ws_1/approval-requests/{request_id}/cancel",
        json={"reason": "Removed"},
        headers={**limited_headers, "Idempotency-Key": "cancel-1"},
    )

    assert cancel_response.status_code == 403


def test_workspace_header_must_match_path(client: TestClient, auth_headers: dict[str, str]):
    mismatched_headers = {**auth_headers, "X-Auth-Workspace-Id": "ws_other"}
    response = client.get("/api/v1/workspaces/ws_1/approval-requests", headers=mismatched_headers)

    assert response.status_code == 403


def test_missing_idempotency_key_returns_bad_request(client: TestClient, auth_headers: dict[str, str]):
    response = client.post(
        "/api/v1/workspaces/ws_1/approval-requests",
        json={
            "sourceType": "publication",
            "sourceId": "pub_123",
            "title": "Instagram reel draft",
            "description": "Needs final approval",
            "reviewerUserIds": ["usr_1", "usr_2"],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
