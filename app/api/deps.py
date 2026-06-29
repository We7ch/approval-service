from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Path, Request, status
@dataclass(frozen=True)
class AuthContext:
    workspace_id: str
    user_id: str
    actions: set[str]


def get_auth_context(
    workspace_id: str = Path(...),
    auth_workspace_id: str | None = Header(default=None, alias="X-Auth-Workspace-Id"),
    auth_user_id: str | None = Header(default=None, alias="X-Auth-User-Id"),
    auth_actions: str | None = Header(default=None, alias="X-Auth-Actions"),
) -> AuthContext:
    if not auth_workspace_id or not auth_user_id or auth_actions is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing auth stub headers.",
        )
    if auth_workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace header does not match request path.",
        )
    actions = {action.strip() for action in auth_actions.split(",") if action.strip()}
    return AuthContext(workspace_id=auth_workspace_id, user_id=auth_user_id, actions=actions)


def require_action(required_action: str):
    def dependency(auth_context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if required_action not in auth_context.actions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required action: {required_action}",
            )
        return auth_context

    return dependency


def get_idempotency_key(request: Request) -> str:
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required for mutation requests.",
        )
    return idempotency_key
